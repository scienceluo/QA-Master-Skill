"""Native process capture. No execution takes place on import."""
from __future__ import annotations

import os
import hashlib
import json
import re
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from ._paired_contract import LIMIT, SECRET_KEYS, canonical, digest, exact, fail, integer, read_bytes, strict_json, text, PairedEvaluationError

ENV_POLICY = {
    'id': 'CODEX_ENV_V1',
    'Windows': sorted('SYSTEMROOT WINDIR COMSPEC PATH PATHEXT TEMP TMP USERPROFILE LOCALAPPDATA APPDATA CODEX_HOME SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE'.split()),
    'POSIX': sorted('HOME PATH TMPDIR LANG LC_ALL CODEX_HOME SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE'.split()),
}


def environment():
    names = ENV_POLICY['Windows' if os.name == 'nt' else 'POSIX']
    result = {key: value for key, value in os.environ.items() if (key.upper() if os.name == 'nt' else key) in names}
    return result, {'policy_id': ENV_POLICY['id'], 'policy_sha256': digest(canonical(ENV_POLICY)), 'inherited_names': sorted(result)}


def redact(raw):
    """Withhold the entire artifact on a known sensitive pattern; never guess prose safety."""
    patterns = [
        rb'(?i)["\x27]?(?:password|passwd|access_token|refresh_token|api_key|authorization|cookie|private_key|client_secret|credential|presigned_url|token)["\x27]?\s*[:=]\s*[^\s,}]+',
        rb'(?i)\b(?:bearer|basic)\s+[A-Za-z0-9+/_.=-]{8,}',
        rb'(?i)https?://[^\s/:]+:[^\s/@]+@',
        rb'(?i)[?&](?:token|key|signature|sig|x-amz-signature|access_token)=',
        rb'\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9]{12,})',
        rb'-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----',
    ]
    def suspicious(data, depth=0):
        if depth > 32:
            return True  # excessive encoded nesting cannot be safely retained
        # Normalize bounded JSON escapes even in malformed/mixed output, which
        # cannot safely wait for a successful JSON parser before withholding.
        normalized = data
        try:
            for _ in range(8):
                changed = re.sub(rb'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)).encode('utf-8'), normalized)
                changed = changed.replace(b'\\/', b'/').replace(b'\\"', b'"')
                if changed == normalized:
                    break
                normalized = changed
            else:
                return True
        except UnicodeError:
            return True
        if any(re.search(pattern, normalized) for pattern in patterns):
            return True
        if any(re.search(pattern, data) for pattern in patterns):
            return True
        def walk(value):
            if isinstance(value, dict):
                return any(key.casefold() in SECRET_KEYS or walk(child) for key, child in value.items())
            if isinstance(value, list):
                return any(walk(child) for child in value)
            if isinstance(value, str):
                return suspicious(value.encode('utf-8'), depth+1)
            return False
        # Final JSON and each JSONL event are decoded before scanning. This also
        # inspects JSON strings containing the agent's escaped final response.
        for line in [data, *data.splitlines()]:
            secret_key = False
            def pairs(rows):
                nonlocal secret_key
                secret_key |= any(key.casefold() in SECRET_KEYS for key, _ in rows)
                return dict(rows)
            try:
                decoded = json.loads(line, object_pairs_hook=pairs)
                if secret_key or walk(decoded):
                    return True
            except (ValueError, UnicodeError):
                if secret_key:
                    return True
                continue
            except RecursionError:
                return True
        return False
    if suspicious(raw):
        safe = b'{"artifact_withheld":"CONTROLLED_SECRET_PATTERN"}\n'
        return safe, {'state': 'REDACTED', 'transform_id': 'WHOLE_ARTIFACT_V1', 'original_byte_count': len(raw), 'original_sha256': digest(raw)}
    return raw, {'state': 'UNCHANGED', 'transform_id': 'NONE', 'original_byte_count': None, 'original_sha256': None}


def parse_trace(raw):
    warnings = []
    violation = False
    records = []
    try:
        lines = raw.splitlines()
        if not lines:
            fail('TRACE_EMPTY')
        for line in lines:
            row = strict_json(line)
            if isinstance(row, dict) and row.get('type') in ('item.started', 'item.completed'):
                item = row.get('item')
                if isinstance(item, dict) and isinstance(item.get('type'), str) and item['type'] not in ('error', 'agent_message'):
                    violation = True
            records.append(row)
        phase = 'thread'
        usage = None
        agent_text = None
        for row in records:
            kind = row.get('type') if isinstance(row, dict) else None
            if phase == 'thread' and kind == 'thread.started':
                exact(row, 'type thread_id'); text(row['thread_id']); phase = 'warnings'
            elif phase == 'warnings' and kind == 'item.completed' and row.get('item', {}).get('type') == 'error':
                exact(row, 'type item'); exact(row['item'], 'id type message')
                text(row['item']['id']); text(row['item']['message'])
                warnings.append(row['item']['message'])
            elif phase == 'warnings' and kind == 'turn.started':
                exact(row, 'type'); phase = 'message'
            elif phase == 'message' and kind == 'item.completed' and row.get('item', {}).get('type') == 'agent_message':
                exact(row, 'type item'); exact(row['item'], 'id type text')
                text(row['item']['id']); text(row['item']['text'], LIMIT)
                agent_text = row['item']['text']; phase = 'end'
            elif phase == 'end' and kind == 'turn.completed':
                exact(row, 'type usage')
                exact(row['usage'], 'input_tokens cached_input_tokens cache_write_input_tokens output_tokens reasoning_output_tokens')
                for count in row['usage'].values():
                    integer(count, 0, 2**63-1)
                usage = row['usage']; phase = 'done'
            else:
                fail('TRACE_SCHEMA_UNSUPPORTED')
        if phase != 'done':
            fail('TRACE_SCHEMA_UNSUPPORTED')
        return {'valid': True, 'policy_outcome': 'NO_VIOLATION_OBSERVED', 'warnings': warnings, 'usage': usage, 'agent_text': agent_text, 'error': None}
    except (PairedEvaluationError, AttributeError, TypeError):
        return {'valid': False, 'policy_outcome': 'POLICY_VIOLATION_OBSERVED' if violation else 'NOT_EVALUATED',
                'warnings': warnings, 'usage': None, 'agent_text': None, 'error': 'TRACE_SCHEMA_UNSUPPORTED'}


def _terminate(process):
    observation = {'method': 'taskkill_tree' if os.name == 'nt' else 'killpg', 'return_code': None, 'parent_exit_observed': False}
    try:
        if os.name == 'nt':
            if process.poll() is None:
                system = Path(os.environ.get('SYSTEMROOT', r'C:\Windows')) / 'System32' / 'taskkill.exe'
                result = subprocess.run([str(system), '/PID', str(process.pid), '/T', '/F'],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, shell=False,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                observation['return_code'] = result.returncode
        else:
            os.killpg(process.pid, signal.SIGKILL)
            observation['return_code'] = 0
        process.wait(timeout=5)
        observation['parent_exit_observed'] = True
    except (OSError, subprocess.SubprocessError):
        observation['parent_exit_observed'] = process.poll() is not None
    verified = observation['parent_exit_observed'] and observation['return_code'] == 0
    return ('TERMINATION_OBSERVED' if verified else 'TERMINATION_UNCONFIRMED'), observation


def native_capture(*, executable, model, features, prompt, timeout_seconds):
    """One native invocation; bounded streams, no retry, allowlisted environment.

    Final-message staging is child-written and has a monitored (not OS-enforced)
    size limit. It is removed before this function returns; deletion is not erasure.
    """
    env, env_record = environment()
    result = {'process_outcome': 'SPAWN_FAILED', 'termination_outcome': 'NOT_REQUESTED',
              'termination': None, 'exit_code': None, 'pid': None, 'stdout': None,
              'stderr': None, 'final': None, 'integrity_failure': False,
              'cleanup_outcome': 'NOT_REQUIRED', 'environment': env_record,
              'duration_ms': 0, 'command': [], 'stdin_outcome': 'NOT_SENT', 'stdin_bytes_sent': 0,
              'stream_observations': {}}
    stage = Path(tempfile.mkdtemp(prefix='qa-master-paired-'))
    cwd = stage / 'cwd'
    cwd.mkdir(mode=0o700)
    final_path = stage / 'last-message.json'
    command = [executable, 'exec', '--ephemeral', '--sandbox', 'read-only', '--skip-git-repo-check',
               '--ignore-user-config', '--model', model['alias'], '-c',
               'model_reasoning_effort=' + model['reasoning_effort'], '--json',
               '--output-last-message', str(final_path)]
    for feature in features:
        command.extend(['--disable', feature])
    command.extend(['--enable', 'skip_host_skill_discovery', '-'])
    result['command'] = ['<NATIVE_CODEX>' if n == 0 else '<STAGING_FINAL>' if item == str(final_path) else item for n, item in enumerate(command)]
    started = time.monotonic()
    process = None
    workers = []
    exceeded = threading.Event()
    reader_error = threading.Event()
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    stream_observations = {name: {'observed_byte_count': 0, 'observed_sha256': None, 'eof_observed': False, 'overflow': False} for name in buffers}
    try:
        kwargs = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
        try:
            process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False, **kwargs)
        except OSError:
            return result
        result['pid'] = process.pid
        def drain(pipe, name):
            observed_hash = hashlib.sha256()
            try:
                while True:
                    chunk = pipe.read(8192)
                    if not chunk:
                        stream_observations[name]['eof_observed'] = True
                        break
                    observed_hash.update(chunk)
                    stream_observations[name]['observed_byte_count'] += len(chunk)
                    available = max(0, LIMIT - len(buffers[name]))
                    buffers[name].extend(chunk[:available])
                    if len(chunk) > available:
                        stream_observations[name]['overflow'] = True
                        exceeded.set()
            except (OSError, ValueError):
                reader_error.set()
            finally:
                stream_observations[name]['observed_sha256'] = observed_hash.hexdigest()
                pipe.close()
        def send():
            try:
                sent = process.stdin.write(prompt)
                result['stdin_bytes_sent'] = sent
                process.stdin.flush()
                result['stdin_outcome'] = 'SENT_COMPLETE' if sent == len(prompt) else 'PARTIAL'
                if sent != len(prompt):
                    reader_error.set()
            except (BrokenPipeError, OSError):
                result['stdin_outcome'] = 'WRITE_FAILED'
                reader_error.set()
            finally:
                try:
                    process.stdin.close()
                except OSError:
                    result['stdin_outcome'] = 'WRITE_FAILED'
                    reader_error.set()
        for target, args in ((drain, (process.stdout, 'stdout')), (drain, (process.stderr, 'stderr')), (send, ())):
            worker = threading.Thread(target=target, args=args, daemon=True)
            worker.start(); workers.append(worker)
        timed_out = False
        while process.poll() is None:
            try:
                if final_path.exists() and final_path.stat().st_size > LIMIT:
                    exceeded.set()
            except OSError:
                reader_error.set()
            timed_out = time.monotonic() - started >= timeout_seconds
            if timed_out or exceeded.is_set() or reader_error.is_set():
                result['termination_outcome'], result['termination'] = _terminate(process)
                break
            time.sleep(0.02)
        for worker in workers:
            worker.join(timeout=1)
        if any(worker.is_alive() for worker in workers):
            result['integrity_failure'] = True
            result['termination_outcome'], result['termination'] = _terminate(process)
            for worker in workers:
                worker.join(timeout=1)
        result['exit_code'] = process.poll()
        result['process_outcome'] = 'TIMED_OUT' if timed_out else ('EXITED_ZERO' if process.returncode == 0 else 'EXITED_NONZERO')
        result['integrity_failure'] |= exceeded.is_set() or reader_error.is_set()
        for name in buffers:
            result[name] = None if stream_observations[name]['overflow'] else bytes(buffers[name])
        result['stream_observations'] = stream_observations
        if final_path.exists():
            try:
                result['final'] = read_bytes(final_path)
            except PairedEvaluationError:
                result['integrity_failure'] = True
        return result
    finally:
        if process is not None and process.poll() is None:
            result['termination_outcome'], result['termination'] = _terminate(process)
            result['integrity_failure'] = True
            for worker in workers:
                worker.join(timeout=1)
        # Remove only our exact staging artifact and empty directories, never recurse.
        try:
            if final_path.exists():
                final_path.unlink()
            cwd.rmdir(); stage.rmdir()
            result['cleanup_outcome'] = 'DELETED'
        except OSError:
            result['cleanup_outcome'] = 'DELETE_FAILED'
            result['integrity_failure'] = True
        result['duration_ms'] = int((time.monotonic() - started) * 1000)
