"""Explicit local exploratory paired evaluation (TASK-041, DES-040).

Only ``run_pair`` invokes a model. Validation, preview, inspection and grading
are process-free. Existing benchmark submissions remain a separate contract.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import re
from pathlib import Path

from ._paired_contract import (
    LIMIT, PROMPT_LIMIT, PROFILE, ISOLATION, DISABLED_FEATURES, VALUE_TYPES,
    PROMPT_TEMPLATE_V1, NEUTRAL_RESPONSE_SCHEMA_V1, PairedEvaluationError,
    array, canonical, check_keys, contained, digest, exact, fail, file_digest,
    hash_value, identifier, integer, no_links, parse_envelope, read_bytes,
    relative, strict_json, text, typed, unique,
)
from ._paired_process import native_capture, parse_trace, redact

MAX_SCENARIOS = 32
MAX_MATERIALIZED_BYTES = 64 * 1024 * 1024


def _utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _utf8(raw):
    try:
        return raw.decode('utf-8')
    except UnicodeError:
        fail('INVALID_UTF8')


def _source(descriptor, base, *, asset=False):
    exact(descriptor, 'path source_path media_type byte_count sha256' if asset else 'source_path byte_count sha256')
    integer(descriptor['byte_count'], 0, LIMIT)
    hash_value(descriptor['sha256'])
    raw = read_bytes(contained(base, descriptor['source_path']))
    if len(raw) != descriptor['byte_count'] or digest(raw) != descriptor['sha256']:
        fail('SOURCE_INTEGRITY_FAILURE')
    _utf8(raw)
    if asset:
        relative(descriptor['path'])
        if descriptor['media_type'] not in ('text/plain', 'text/markdown', 'application/json'):
            fail('UNSUPPORTED_MEDIA_TYPE')
        if descriptor['media_type'] == 'application/json':
            strict_json(raw)
    # Known secret patterns are rejected in inputs as well as withheld in output.
    if redact(raw)[1]['state'] != 'UNCHANGED':
        fail('PROHIBITED_INPUT_PATTERN')
    return raw


def _visible(raw, scenario):
    value = strict_json(raw)
    exact(value, 'schema_version scenario_id method title request known_facts scope checks')
    integer(value['schema_version'], 1, 1)
    check_keys(value, {'oracle', 'expected', 'answer', 'rating', 'score', 'winner'})
    if value['scenario_id'] != scenario['id'] or value['method'] != scenario['method']:
        fail('SCENARIO_MISMATCH')
    for key in ('title', 'request', 'scope'):
        text(value[key])
    for fact in array(value['known_facts'], 256, 1):
        exact(fact, 'id text'); identifier(fact['id']); text(fact['text'])
    unique([fact['id'] for fact in value['known_facts']])
    for check in array(value['checks'], 256):
        exact(check, 'id question value_type'); identifier(check['id']); text(check['question'])
        if check['value_type'] not in VALUE_TYPES:
            fail('UNKNOWN_VALUE_TYPE')
    unique([check['id'] for check in value['checks']])
    return value


def _runtime(value):
    exact(value, 'codex model policy host timeout_seconds retry_count')
    codex = exact(value['codex'], 'executable_path executable_sha256 version')
    name = text(codex['executable_path'], 4096)
    exe = Path(name)
    if not exe.is_absolute() or '..' in exe.parts or '\x00' in name:
        fail('INVALID_EXECUTABLE_PATH')
    exe = no_links(exe)
    try:
        with exe.open('rb') as stream:
            magic = stream.read(4)
    except OSError:
        fail('MISSING_EXECUTABLE')
    valid = exe.suffix.lower() == '.exe' and magic[:2] == b'MZ' if os.name == 'nt' else (
        os.access(exe, os.X_OK) and magic in (b'\x7fELF', b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe'))
    if not valid:
        fail('NATIVE_EXECUTABLE_REQUIRED')
    if file_digest(exe) != hash_value(codex['executable_sha256']):
        fail('EXECUTABLE_DRIFT')
    text(codex['version'], 128)
    model = exact(value['model'], 'alias reasoning_effort provider_revision system_baseline temperature_state seed_state')
    identifier(model['alias'])
    if model['reasoning_effort'] not in ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra'):
        fail('INVALID_REASONING_EFFORT')
    for name in ('provider_revision', 'system_baseline'):
        record = exact(model[name], 'state value evidence_sha256')
        if record['state'] == 'VERIFIED':
            fail('ATTESTATION_NOT_SUPPORTED')
        if record['state'] not in ('NOT_AVAILABLE', 'UNVERIFIED'):
            fail('INVALID_ATTESTATION_STATE')
        if record['state'] == 'NOT_AVAILABLE' and (record['value'] is not None or record['evidence_sha256'] is not None):
            fail('INVALID_ATTESTATION_STATE')
        if record['value'] is not None:
            text(record['value'])
        if record['evidence_sha256'] is not None:
            hash_value(record['evidence_sha256'])
    if model['temperature_state'] != 'NOT_AVAILABLE' or model['seed_state'] != 'NOT_AVAILABLE':
        fail('UNSUPPORTED_MODEL_SETTING')
    expected_policy = {'sandbox': 'read-only', 'add_dirs': [], 'ignore_user_config': True,
                       'ephemeral': True, 'skip_host_skill_discovery': True, 'requested_tool_policy': 'NO_TOOL_USE',
                       'disabled_features': DISABLED_FEATURES, 'isolation_level': ISOLATION}
    if canonical(value['policy']) != canonical(expected_policy):
        fail('POLICY_MISMATCH')
    if value['host'] != {'os': platform.system(), 'architecture': platform.machine()}:
        fail('HOST_MISMATCH')
    integer(value['timeout_seconds'], 1, 1800)
    integer(value['retry_count'], 0, 0)


def _prepare_unchecked(payload, manifest_dir):
    manifest = strict_json(payload)
    if redact(payload)[1]['state'] != 'UNCHANGED':
        fail('PROHIBITED_INPUT_PATTERN')
    exact(manifest, 'schema_version run_id profile created_at_utc participants scenarios prompt_template response_schema evaluator_commitment_sha256 runtime schedule')
    integer(manifest['schema_version'], 1, 1)
    identifier(manifest['run_id'])
    # Run/attempt IDs become path components and must also satisfy the path grammar.
    relative(manifest['run_id'])
    if manifest['profile'] == 'STRICT_COMPARISON_CANDIDATE':
        fail('STRICT_PROFILE_NOT_SUPPORTED')
    if manifest['profile'] != PROFILE:
        fail('INVALID_PROFILE')
    try:
        dt.datetime.strptime(manifest['created_at_utc'], '%Y-%m-%dT%H:%M:%SZ')
    except (TypeError, ValueError):
        fail('INVALID_TIMESTAMP')
    hash_value(manifest['evaluator_commitment_sha256'])
    _runtime(manifest['runtime'])
    participants = array(manifest['participants'], 2, 2)
    if [p.get('arm_id') if isinstance(p, dict) else None for p in participants] != ['A', 'B']:
        fail('INVALID_ARMS')
    assets = {}
    for participant in participants:
        exact(participant, 'arm_id participant_id source entry_asset assets')
        identifier(participant['participant_id'])
        source = exact(participant['source'], 'repository_id commit tree_oid')
        identifier(source['repository_id']); hash_value(source['commit'], git=True); hash_value(source['tree_oid'], git=True)
        rows = array(participant['assets'], 64, 1)
        copied = {}
        for row in rows:
            raw = _source(row, manifest_dir, asset=True)
            key = row['path']
            if key.casefold() in {p.casefold() for p in copied}:
                fail('DUPLICATE_ASSET')
            copied[key] = raw
        if list(copied) != sorted(copied) or participant['entry_asset'] not in copied:
            fail('INVALID_ASSET_INVENTORY')
        if sum(map(len, copied.values())) > LIMIT:
            fail('ASSET_TOTAL_LIMIT')
        assets[participant['arm_id']] = copied
    unique([p['participant_id'] for p in participants])
    scenarios = array(manifest['scenarios'], MAX_SCENARIOS, 3)
    visible = {}; input_bytes = {}
    for scenario in scenarios:
        exact(scenario, 'id method visible_input oracle_commitment_sha256')
        identifier(scenario['id']); hash_value(scenario['oracle_commitment_sha256'])
        if scenario['method'] not in ('boundary', 'decision_table', 'state_transition'):
            fail('INVALID_METHOD')
        raw = _source(scenario['visible_input'], manifest_dir)
        input_bytes[scenario['id']] = raw
        visible[scenario['id']] = _visible(raw, scenario)
    unique([row['id'] for row in scenarios])
    if {row['method'] for row in scenarios} != {'boundary', 'decision_table', 'state_transition'}:
        fail('PILOT_METHODS_INCOMPLETE')
    template = _source(manifest['prompt_template'], manifest_dir)
    schema = _source(manifest['response_schema'], manifest_dir)
    if template != PROMPT_TEMPLATE_V1 or schema != NEUTRAL_RESPONSE_SCHEMA_V1:
        fail('COMMON_CONTRACT_MISMATCH')
    schedule = array(manifest['schedule'], MAX_SCENARIOS, 3)
    for row in schedule:
        exact(row, 'attempt_id scenario_id order')
        identifier(row['attempt_id']); relative(row['attempt_id'])
        if row['scenario_id'] not in visible or row['order'] not in (['A', 'B'], ['B', 'A']):
            fail('INVALID_SCHEDULE')
    unique([row['attempt_id'].casefold() for row in schedule])
    if sorted(row['scenario_id'] for row in schedule) != sorted(visible):
        fail('INVALID_SCHEDULE')
    return {'manifest': manifest, 'assets': assets, 'inputs': input_bytes, 'visible': visible}


def _prepare(payload, manifest_dir):
    try:
        return _prepare_unchecked(payload, manifest_dir)
    except (TypeError, KeyError, AttributeError, RecursionError):
        fail('INVALID_SCHEMA')
    except OSError:
        fail('LOCAL_IO_FAILURE')


def load_run_manifest(payload, *, manifest_dir):
    return _prepare(payload, manifest_dir)['manifest']


def validate_run_manifest(payload, *, manifest_dir):
    prepared = _prepare(payload, manifest_dir)
    return {'status': 'VALIDATED_NOT_EXECUTED', 'run_manifest_sha256': digest(canonical(prepared['manifest'])),
            'claim_status': 'NOT_ASSERTED', 'human_rating_status': 'NOT_EXECUTED'}


def _projection(assets):
    chunks = [b'PARTICIPANT_CONTEXT_V1\n']
    for path, raw in assets.items():
        path_bytes = path.encode('utf-8')
        chunks.extend([f'ASSET {len(path_bytes)} {len(raw)} {digest(raw)}\n'.encode('ascii'),
                       path_bytes, b'\n', raw, b'\nEND_ASSET\n'])
    return b''.join(chunks) + b'END_PARTICIPANT_CONTEXT\n'


def _prompt(context, visible):
    blocks = {b'{{PARTICIPANT_CONTEXT}}': context, b'{{VISIBLE_INPUT}}': visible,
              b'{{RESPONSE_CONTRACT}}': NEUTRAL_RESPONSE_SCHEMA_V1}
    # Callback visits only tokens in the original template, never inserted data.
    result = re.sub(rb'\{\{[A-Z_]+\}\}', lambda match: blocks[match[0]], PROMPT_TEMPLATE_V1)
    if len(result) > PROMPT_LIMIT:
        fail('PROMPT_SIZE_LIMIT')
    return result


def _exclusions(path, prepared, manifest_dir, output_root):
    path = no_links(path)
    if path.is_relative_to(no_links(manifest_dir)) or path.is_relative_to(no_links(output_root)):
        fail('EVALUATOR_PATH_NOT_SEPARATE')
    value = strict_json(read_bytes(path))
    exact(value, 'schema_version forbidden_locators forbidden_sha256 fixture_markers')
    integer(value['schema_version'], 1, 1)
    for name in ('forbidden_locators', 'forbidden_sha256', 'fixture_markers'):
        array(value[name], 256); unique(value[name])
    for locator in value['forbidden_locators']:
        relative(locator)
    for hashed in value['forbidden_sha256']:
        hash_value(hashed)
    for marker in value['fixture_markers']:
        if not isinstance(marker, str) or not re.fullmatch(r'[\x20-\x7e]{16,128}', marker):
            fail('INVALID_FIXTURE_MARKER')
    if digest(canonical(value)) != prepared['manifest']['evaluator_commitment_sha256']:
        fail('EVALUATOR_COMMITMENT_MISMATCH')
    return value


def _leak(raw, locator, exclusions):
    needles = exclusions['forbidden_locators'] + exclusions['fixture_markers']
    if digest(raw) in exclusions['forbidden_sha256'] or any(n.encode('utf-8') in raw or n in locator for n in needles):
        fail('EVALUATOR_LEAKAGE')


def _write(root, locator, raw):
    path = contained(root, locator)
    path.parent.mkdir(parents=True, exist_ok=True)
    no_links(path.parent)
    try:
        with path.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        if read_bytes(path, max(LIMIT, PROMPT_LIMIT)) != raw:
            fail('ARTIFACT_WRITE_FAILURE')
    except FileExistsError:
        fail('ARTIFACT_EXISTS')
    except OSError:
        fail('ARTIFACT_WRITE_FAILURE')


def _ledger_write(root, locator, raw, role):
    if raw is None:
        return {'role': role, 'relative_path': locator, 'capture_state': 'ABSENT', 'byte_count': None, 'sha256': None,
                'redaction': {'state': 'UNCHANGED', 'transform_id': 'NONE', 'original_byte_count': None, 'original_sha256': None}}
    safe, transformation = redact(raw)
    _write(root, locator, safe)
    return {'role': role, 'relative_path': locator, 'capture_state': 'REDACTED' if transformation['state'] == 'REDACTED' else 'RETAINED',
            'byte_count': len(safe), 'sha256': digest(safe), 'redaction': transformation}


def _materialize(manifest_path, exclusions_path, output_root, preview=False):
    manifest_path = no_links(manifest_path)
    prepared = _prepare(read_bytes(manifest_path), manifest_path.parent)
    manifest = prepared['manifest']
    outer = no_links(output_root)
    exclusions = _exclusions(exclusions_path, prepared, manifest_path.parent, outer)
    root = outer if preview else contained(outer, manifest['run_id'])
    if root.is_relative_to(manifest_path.parent):
        fail('OUTPUT_NOT_SEPARATE')
    plans = []
    materialized_bytes = len(canonical(manifest)) + 1
    for row in manifest['schedule']:
        for arm in row['order']:
            context = _projection(prepared['assets'][arm])
            visible = prepared['inputs'][row['scenario_id']]
            prompt = _prompt(context, visible)
            call_id = row['attempt_id'] + '-' + arm
            files = {'common/visible-input.json': visible, 'common/response.schema.json': NEUTRAL_RESPONSE_SCHEMA_V1}
            files.update({'assets/' + path: raw for path, raw in prepared['assets'][arm].items()})
            for locator, raw in files.items():
                _leak(raw, locator, exclusions)
            _leak(prompt, 'stdin.txt', exclusions)
            materialized_bytes += sum(map(len, files.values())) + len(prompt)
            if materialized_bytes > MAX_MATERIALIZED_BYTES:
                fail('MATERIALIZATION_CAPACITY_LIMIT')
            plans.append({'call_id': call_id, 'attempt_id': row['attempt_id'], 'scenario_id': row['scenario_id'],
                          'arm_id': arm, 'files': files, 'prompt': prompt, 'participant_context_sha256': digest(context),
                          'common_request_sha256': digest(canonical({'template_sha256': digest(PROMPT_TEMPLATE_V1),
                              'visible_input_sha256': digest(visible), 'response_schema_sha256': digest(NEUTRAL_RESPONSE_SCHEMA_V1)}))})
    writes = [('manifest.json', canonical(manifest)+b'\n', 'manifest')]
    for plan in plans:
        for locator, raw in plan['files'].items():
            writes.append(('calls/'+plan['call_id']+'/'+locator, raw, 'materialized_input'))
        writes.append(('calls/'+plan['call_id']+'/stdin.txt', plan['prompt'], 'stdin'))
    for locator, raw, role in writes:
        if redact(raw)[1]['state'] != 'UNCHANGED':
            fail('PROHIBITED_INPUT_PATTERN')
    ledger = [{'role': role, 'relative_path': locator, 'capture_state': 'RETAINED', 'byte_count': len(raw), 'sha256': digest(raw),
               'redaction': {'state': 'UNCHANGED', 'transform_id': 'NONE', 'original_byte_count': None, 'original_sha256': None}}
              for locator, raw, role in writes]
    preflight = {'schema_version': 1, 'status': 'PREVIEW_NOT_RUN' if preview else 'SEALED', 'created_at_utc': _utc(),
                 'run_manifest_sha256': digest(canonical(manifest)), 'runtime': manifest['runtime'],
                 'settings_canonical_sha256': digest(canonical(manifest['runtime'])),
                 'evaluator_commitment_sha256': manifest['evaluator_commitment_sha256'], 'leakage_matches': 0,
                 'ledger': ledger, 'planned_calls': [{key: value for key, value in plan.items() if key not in ('files', 'prompt')} for plan in plans]}
    preflight_bytes = canonical(preflight)+b'\n'
    if len(preflight_bytes) > LIMIT//2 or len(preflight_bytes)+len(plans)*10240 > LIMIT:
        fail('CONTROL_RECORD_CAPACITY_LIMIT')
    if materialized_bytes+len(preflight_bytes) > MAX_MATERIALIZED_BYTES:
        fail('MATERIALIZATION_CAPACITY_LIMIT')
    try:
        root.parent.mkdir(parents=True, exist_ok=True)
        no_links(root.parent)
        root.mkdir(mode=0o700)
    except FileExistsError:
        fail('RUN_ID_EXISTS')
    except OSError:
        fail('RUN_RESERVATION_FAILED')
    for locator, raw, role in writes:
        _write(root, locator, raw)
    _write(root, 'preflight.json', preflight_bytes)
    return root, prepared, plans, preflight


def materialize_preview(manifest_path, evaluator_exclusions_path, preview_root):
    root, prepared, plans, preflight = _materialize(manifest_path, evaluator_exclusions_path, preview_root, True)
    return {'status': 'PREVIEW_NOT_RUN', 'run_manifest_sha256': preflight['run_manifest_sha256'], 'call_count': len(plans)}


def _terminal(record, participant_failure=False):
    if record['process_outcome'] == 'SPAWN_FAILED' or record['output_outcome'] == 'INTEGRITY_FAILURE':
        return 'INFRASTRUCTURE_FAILURE'
    if record['process_outcome'] == 'TIMED_OUT':
        return 'TIMED_OUT'
    if record['policy_outcome'] == 'POLICY_VIOLATION_OBSERVED':
        return 'POLICY_VIOLATION'
    if record['output_outcome'] in ('NOT_AVAILABLE', 'OUTPUT_INVALID'):
        return 'OUTPUT_INVALID'
    if participant_failure:
        return 'PARTICIPANT_FAILURE'
    if record['process_outcome'] != 'EXITED_ZERO':
        return 'RUN_FAILURE_UNATTRIBUTED'
    return 'COMPLETED_PROCESS'


def _run(manifest_path, exclusions_path, output_root, launcher, backend):
    root, prepared, plans, preflight = _materialize(manifest_path, exclusions_path, output_root)
    manifest = prepared['manifest']; runtime = manifest['runtime']
    attempts = []; stop = None
    ledger = list(preflight['ledger'])
    ledger.append({'role': 'preflight', 'relative_path': 'preflight.json', 'capture_state': 'RETAINED',
                   'byte_count': len(read_bytes(root/'preflight.json')), 'sha256': file_digest(root/'preflight.json'),
                   'redaction': {'state': 'UNCHANGED', 'transform_id': 'NONE', 'original_byte_count': None, 'original_sha256': None}})
    for ordinal, plan in enumerate(plans):
        record = {key: plan[key] for key in ('call_id', 'attempt_id', 'scenario_id', 'arm_id', 'participant_context_sha256', 'common_request_sha256')}
        record.update({'ordinal': ordinal, 'stdin_sha256': digest(plan['prompt']), 'response_schema_sha256': digest(NEUTRAL_RESPONSE_SCHEMA_V1),
                       'started_at_utc': None, 'ended_at_utc': None, 'process_outcome': 'NOT_STARTED',
                       'termination_outcome': 'NOT_REQUESTED', 'output_outcome': 'NOT_AVAILABLE', 'policy_outcome': 'NOT_EVALUATED',
                       'terminal_status': 'NOT_EXECUTED', 'stop_reason': stop, 'ledger': []})
        prefix = 'attempts/' + plan['call_id'] + '/'
        if stop is None:
            record['started_at_utc'] = _utc()
            try:
                # Recheck executable and every materialized byte immediately before launch.
                if file_digest(runtime['codex']['executable_path']) != runtime['codex']['executable_sha256']:
                    fail('EXECUTABLE_DRIFT')
                for entry in preflight['ledger']:
                    path = contained(root, entry['relative_path'])
                    if file_digest(path) != entry['sha256']:
                        fail('MATERIALIZED_DRIFT')
                capture = launcher(executable=runtime['codex']['executable_path'], model=runtime['model'],
                                   features=runtime['policy']['disabled_features'], prompt=plan['prompt'], timeout_seconds=runtime['timeout_seconds'])
                record.update({key: capture[key] for key in ('process_outcome', 'termination_outcome', 'termination',
                    'exit_code', 'pid', 'cleanup_outcome', 'environment', 'duration_ms', 'command')})
                record.update({key: capture[key] for key in ('stdin_outcome', 'stdin_bytes_sent', 'stream_observations')})
                for role in ('stdout', 'stderr', 'final'):
                    raw = capture[role]
                    if raw is not None and (not isinstance(raw, bytes) or len(raw) > LIMIT):
                        fail('CAPTURE_LIMIT')
                    record['ledger'].append(_ledger_write(root, prefix+role+('.jsonl' if role == 'stdout' else '.txt'), raw, role))
                trace = parse_trace(capture['stdout'] or b'')
                record.update({'policy_outcome': trace['policy_outcome'], 'trace_error': trace['error'], 'usage': trace['usage']})
                # Warning text is already in the redacted stream; never duplicate unfiltered text.
                record['trace_warning_count'] = len(trace['warnings'])
                envelope = None
                if (capture['integrity_failure'] or capture['stdin_outcome'] != 'SENT_COMPLETE'
                    or capture['stdin_bytes_sent'] != len(plan['prompt'])
                    or any(item['capture_state'] == 'REDACTED' for item in record['ledger'])):
                    record['output_outcome'] = 'INTEGRITY_FAILURE'
                elif not capture['final'] or not capture['stdout']:
                    record['output_outcome'] = 'NOT_AVAILABLE'
                else:
                    try:
                        envelope = parse_envelope(capture['final'], prepared['visible'][plan['scenario_id']], prepared['assets'][plan['arm_id']])
                        if not trace['valid'] or canonical(strict_json(trace['agent_text'].encode('utf-8'))) != canonical(envelope):
                            fail('TRACE_FINAL_MISMATCH')
                        record['output_outcome'] = 'COMPLETE'
                        record['ledger'].append(_ledger_write(root, prefix+'envelope.json', canonical(envelope)+b'\n', 'envelope'))
                    except PairedEvaluationError as exc:
                        envelope = None; record['output_outcome'] = 'OUTPUT_INVALID'; record['output_error'] = exc.code
                record['terminal_status'] = _terminal(record, bool(envelope and envelope['response_status'] == 'PARTICIPANT_FAILURE'))
            except (PairedEvaluationError, OSError) as exc:
                record['output_outcome'] = 'INTEGRITY_FAILURE'
                record['terminal_status'] = 'INFRASTRUCTURE_FAILURE'
                record['infrastructure_error'] = exc.code if isinstance(exc, PairedEvaluationError) else 'LOCAL_IO_FAILURE'
            record['ended_at_utc'] = _utc()
            if (record['process_outcome'] == 'SPAWN_FAILED' or record['output_outcome'] == 'INTEGRITY_FAILURE'
                or record['policy_outcome'] == 'POLICY_VIOLATION_OBSERVED' or record['termination_outcome'] == 'TERMINATION_UNCONFIRMED'):
                stop = 'RUN_STOP_' + record['terminal_status'] + '_' + plan['attempt_id']
        record_ledger = _ledger_write(root, prefix+'record.json', canonical(record)+b'\n', 'attempt_record')
        ledger.extend(record['ledger']); ledger.append(record_ledger)
        attempts.append(record)
    complete = all(row['terminal_status'] == 'COMPLETED_PROCESS' for row in attempts)
    started = any(row['process_outcome'] not in ('NOT_STARTED', 'SPAWN_FAILED') for row in attempts)
    result = {'schema_version': 1, 'run_id': manifest['run_id'], 'created_at_utc': _utc(),
              'run_manifest_sha256': preflight['run_manifest_sha256'], 'response_schema_sha256': digest(NEUTRAL_RESPONSE_SCHEMA_V1),
              'execution_backend': backend, 'evidence_class': PROFILE if backend == 'NATIVE_CODEX' else 'TEST_DOUBLE',
              'pilot_status': ('COMPLETE' if complete else 'PARTIAL' if started else 'FAILED') if backend == 'NATIVE_CODEX' else 'NOT_EXECUTED',
              'claim_status': 'NOT_ASSERTED', 'human_rating_status': 'NOT_EXECUTED', 'runtime': runtime,
              'attempts': attempts, 'ledger': ledger}
    result_bytes = canonical(result)+b'\n'
    if len(result_bytes) > LIMIT:
        fail('CONTROL_RECORD_CAPACITY_LIMIT')
    _write(root, 'result.json', result_bytes)
    return result


def run_pair(manifest_path, evaluator_exclusions_path, output_root):
    return _run(manifest_path, evaluator_exclusions_path, output_root, native_capture, 'NATIVE_CODEX')


def _run_pair_with_ports(manifest_path, evaluator_exclusions_path, output_root, *, launcher):
    """Private deterministic test port. Never produces native pilot evidence."""
    return _run(manifest_path, evaluator_exclusions_path, output_root, launcher, 'TEST_DOUBLE')


def _check_ledger(entries):
    locators = []
    for item in array(entries, 20000):
        exact(item, 'role relative_path capture_state byte_count sha256 redaction')
        text(item['role'], 64); relative(item['relative_path'])
        locators.append(item['relative_path'].casefold())
        if item['capture_state'] not in ('RETAINED', 'ABSENT', 'REDACTED'):
            fail('INVALID_LEDGER')
        if item['capture_state'] == 'ABSENT':
            if item['byte_count'] is not None or item['sha256'] is not None:
                fail('INVALID_LEDGER')
        else:
            integer(item['byte_count'], 0, PROMPT_LIMIT); hash_value(item['sha256'])
        transform = exact(item['redaction'], 'state transform_id original_byte_count original_sha256')
        if transform['state'] not in ('UNCHANGED', 'REDACTED'):
            fail('INVALID_LEDGER')
        if transform['state'] == 'UNCHANGED':
            if transform != {'state': 'UNCHANGED', 'transform_id': 'NONE', 'original_byte_count': None, 'original_sha256': None}:
                fail('INVALID_LEDGER')
        else:
            if item['capture_state'] != 'REDACTED' or transform['transform_id'] != 'WHOLE_ARTIFACT_V1':
                fail('INVALID_LEDGER')
            integer(transform['original_byte_count'], 0, LIMIT); hash_value(transform['original_sha256'])
    unique(locators)


def _inspect(run_root):
    root = no_links(run_root)
    result_file = root/'result.json'
    preflight = strict_json(read_bytes(root/'preflight.json'))
    exact(preflight, 'schema_version status created_at_utc run_manifest_sha256 runtime settings_canonical_sha256 evaluator_commitment_sha256 leakage_matches ledger planned_calls')
    integer(preflight['schema_version'], 1, 1)
    if preflight['status'] not in ('SEALED', 'PREVIEW_NOT_RUN'):
        fail('INVALID_PREFLIGHT')
    manifest = strict_json(read_bytes(root/'manifest.json'))
    if digest(canonical(manifest)) != preflight['run_manifest_sha256'] or canonical(manifest['runtime']) != canonical(preflight['runtime']):
        fail('INVALID_PREFLIGHT')
    if digest(canonical(preflight['runtime'])) != preflight['settings_canonical_sha256']:
        fail('INVALID_PREFLIGHT')
    _check_ledger(preflight['ledger'])
    planned = preflight['planned_calls']
    for plan in array(planned, 512):
        exact(plan, 'call_id attempt_id scenario_id arm_id participant_context_sha256 common_request_sha256')
        relative(plan['call_id']); identifier(plan['attempt_id']); identifier(plan['scenario_id'])
        hash_value(plan['participant_context_sha256']); hash_value(plan['common_request_sha256'])
        if plan['arm_id'] not in ('A', 'B'):
            fail('INVALID_PLAN')
    unique([row['call_id'].casefold() for row in planned])
    document = strict_json(read_bytes(result_file)) if result_file.exists() else preflight
    _check_ledger(document['ledger'])
    if result_file.exists():
        exact(document, 'schema_version run_id created_at_utc run_manifest_sha256 response_schema_sha256 execution_backend evidence_class pilot_status claim_status human_rating_status runtime attempts ledger')
        integer(document['schema_version'], 1, 1)
        if (preflight['status'] != 'SEALED' or document['run_id'] != manifest['run_id']
            or document['run_manifest_sha256'] != preflight['run_manifest_sha256']
            or document['response_schema_sha256'] != digest(NEUTRAL_RESPONSE_SCHEMA_V1)
            or canonical(document['runtime']) != canonical(preflight['runtime'])
            or document['claim_status'] != 'NOT_ASSERTED' or document['human_rating_status'] != 'NOT_EXECUTED'):
            fail('INVALID_RESULT')
        if document['execution_backend'] not in ('NATIVE_CODEX', 'TEST_DOUBLE'):
            fail('INVALID_RESULT')
        if document['evidence_class'] != (PROFILE if document['execution_backend'] == 'NATIVE_CODEX' else 'TEST_DOUBLE'):
            fail('INVALID_RESULT')
        attempts = array(document['attempts'], 512)
        if len(attempts) != len(planned):
            fail('ATTEMPT_INVENTORY_MISMATCH')
        global_entries = {item['relative_path']: item for item in document['ledger']}
        for item in preflight['ledger']:
            if global_entries.get(item['relative_path']) != item:
                fail('LEDGER_MISMATCH')
        expected_stop = None
        for ordinal, (record, plan) in enumerate(zip(attempts, planned)):
            required = set('call_id attempt_id scenario_id arm_id participant_context_sha256 common_request_sha256 ordinal stdin_sha256 response_schema_sha256 started_at_utc ended_at_utc process_outcome termination_outcome output_outcome policy_outcome terminal_status stop_reason ledger'.split())
            optional = set('termination exit_code pid cleanup_outcome environment duration_ms command stdin_outcome stdin_bytes_sent stream_observations trace_error usage trace_warning_count output_error infrastructure_error'.split())
            if not isinstance(record, dict) or not required.issubset(record) or set(record)-required-optional:
                fail('INVALID_ATTEMPT')
            if record['ordinal'] != ordinal or any(record[key] != value for key, value in plan.items()):
                fail('ATTEMPT_INVENTORY_MISMATCH')
            if (record['process_outcome'] not in ('NOT_STARTED', 'SPAWN_FAILED', 'EXITED_ZERO', 'EXITED_NONZERO', 'TIMED_OUT')
                or record['termination_outcome'] not in ('NOT_REQUESTED', 'TERMINATION_OBSERVED', 'TERMINATION_UNCONFIRMED')
                or record['output_outcome'] not in ('NOT_AVAILABLE', 'COMPLETE', 'OUTPUT_INVALID', 'INTEGRITY_FAILURE')
                or record['policy_outcome'] not in ('NOT_EVALUATED', 'POLICY_VIOLATION_OBSERVED', 'NO_VIOLATION_OBSERVED')
                or record['terminal_status'] not in ('NOT_EXECUTED', 'PRECHECK_REJECTED', 'INFRASTRUCTURE_FAILURE', 'TIMED_OUT', 'POLICY_VIOLATION', 'OUTPUT_INVALID', 'PARTICIPANT_FAILURE', 'RUN_FAILURE_UNATTRIBUTED', 'COMPLETED_PROCESS')):
                fail('INVALID_ATTEMPT')
            _check_ledger(record['ledger'])
            unique([entry['role'] for entry in record['ledger']])
            roles = {entry['role']: entry for entry in record['ledger']}
            if set(roles)-{'stdout', 'stderr', 'final', 'envelope'}:
                fail('INVALID_ATTEMPT_ROLE')
            for item in record['ledger']:
                if global_entries.get(item['relative_path']) != item or not item['relative_path'].startswith('attempts/'+plan['call_id']+'/'):
                    fail('LEDGER_MISMATCH')
            record_path = 'attempts/'+plan['call_id']+'/record.json'
            if record_path not in global_entries or canonical(strict_json(read_bytes(contained(root, record_path)))) != canonical(record):
                fail('ATTEMPT_RECORD_MISMATCH')
            stdin_entry = global_entries.get('calls/'+plan['call_id']+'/stdin.txt')
            if (stdin_entry is None or record['stdin_sha256'] != stdin_entry['sha256']
                or record['response_schema_sha256'] != digest(NEUTRAL_RESPONSE_SCHEMA_V1)):
                fail('ATTEMPT_INPUT_MISMATCH')
            if any(item['capture_state'] == 'REDACTED' for item in roles.values()) and record['output_outcome'] != 'INTEGRITY_FAILURE':
                fail('REDACTION_OUTCOME_MISMATCH')
            if record.get('cleanup_outcome') == 'DELETE_FAILED' and record['output_outcome'] != 'INTEGRITY_FAILURE':
                fail('CLEANUP_OUTCOME_MISMATCH')
            if record['process_outcome'] in ('EXITED_ZERO', 'EXITED_NONZERO', 'TIMED_OUT'):
                if ((record.get('stdin_outcome') != 'SENT_COMPLETE' or record.get('stdin_bytes_sent') != stdin_entry['byte_count'])
                    and record['output_outcome'] != 'INTEGRITY_FAILURE'):
                    fail('STDIN_OUTCOME_MISMATCH')
            envelope = None
            if record['output_outcome'] == 'COMPLETE':
                if set(roles) != {'stdout', 'stderr', 'final', 'envelope'} or any(item['capture_state'] != 'RETAINED' for item in roles.values()):
                    fail('ATTEMPT_OUTPUT_MISMATCH')
                visible = strict_json(read_bytes(contained(root, 'calls/'+plan['call_id']+'/common/visible-input.json')))
                participant = next(p for p in manifest['participants'] if p['arm_id'] == plan['arm_id'])
                envelope = parse_envelope(read_bytes(contained(root, roles['envelope']['relative_path'])), visible, [a['path'] for a in participant['assets']])
                final = strict_json(read_bytes(contained(root, roles['final']['relative_path'])))
                trace = parse_trace(read_bytes(contained(root, roles['stdout']['relative_path'])))
                if (canonical(final) != canonical(envelope) or not trace['valid']
                    or canonical(strict_json(trace['agent_text'].encode('utf-8'))) != canonical(envelope)
                    or record['policy_outcome'] != trace['policy_outcome']
                    or record.get('stdin_outcome') != 'SENT_COMPLETE'
                    or record.get('stdin_bytes_sent') != stdin_entry['byte_count']):
                    fail('ATTEMPT_OUTPUT_MISMATCH')
            elif 'envelope' in roles:
                fail('ATTEMPT_OUTPUT_MISMATCH')
            for role, observation in record.get('stream_observations', {}).items():
                if role not in ('stdout', 'stderr') or not isinstance(observation, dict):
                    fail('INVALID_STREAM_OBSERVATION')
                exact(observation, 'observed_byte_count observed_sha256 eof_observed overflow')
                integer(observation['observed_byte_count'], 0, 2**63-1)
                if observation['observed_sha256'] is not None:
                    hash_value(observation['observed_sha256'])
                if type(observation['eof_observed']) is not bool or type(observation['overflow']) is not bool:
                    fail('INVALID_STREAM_OBSERVATION')
                if observation['overflow'] and (roles.get(role, {}).get('capture_state') != 'ABSENT' or record['output_outcome'] != 'INTEGRITY_FAILURE'):
                    fail('INVALID_STREAM_OBSERVATION')
            if record['terminal_status'] == 'NOT_EXECUTED':
                if (record['process_outcome'] != 'NOT_STARTED' or record['output_outcome'] != 'NOT_AVAILABLE'
                    or record['ledger'] or record['started_at_utc'] is not None or record['ended_at_utc'] is not None
                    or expected_stop is None or record['stop_reason'] != expected_stop):
                    fail('INVALID_UNEXECUTED_ATTEMPT')
            else:
                if expected_stop is not None or record['stop_reason'] is not None:
                    fail('STOP_CHAIN_MISMATCH')
                if record['terminal_status'] != _terminal(record, bool(envelope and envelope['response_status'] == 'PARTICIPANT_FAILURE')):
                    fail('ATTEMPT_TERMINAL_MISMATCH')
                if (record['process_outcome'] == 'SPAWN_FAILED' or record['output_outcome'] == 'INTEGRITY_FAILURE'
                    or record['policy_outcome'] == 'POLICY_VIOLATION_OBSERVED' or record['termination_outcome'] == 'TERMINATION_UNCONFIRMED'):
                    expected_stop = 'RUN_STOP_'+record['terminal_status']+'_'+record['attempt_id']
        complete = all(row['terminal_status'] == 'COMPLETED_PROCESS' for row in attempts)
        started = any(row['process_outcome'] not in ('NOT_STARTED', 'SPAWN_FAILED') for row in attempts)
        expected_status = ('COMPLETE' if complete else 'PARTIAL' if started else 'FAILED') if document['execution_backend'] == 'NATIVE_CODEX' else 'NOT_EXECUTED'
        if document['pilot_status'] != expected_status:
            fail('INVALID_RESULT')
    rows = []; known = {'result.json', 'preflight.json'}
    for item in document['ledger']:
        locator = relative(item['relative_path']); known.add(locator)
        path = contained(root, locator)
        if item['capture_state'] == 'ABSENT':
            status = 'MISMATCH' if path.exists() else 'INTACT'
        elif not path.exists():
            status = 'MISSING'
        else:
            status = 'INTACT' if path.stat().st_size == item['byte_count'] and file_digest(path) == item['sha256'] else 'MISMATCH'
        rows.append({'relative_path': locator, 'status': status})
    for path in root.rglob('*'):
        no_links(path)
        if path.is_file() and path.relative_to(root).as_posix() not in known:
            rows.append({'relative_path': path.relative_to(root).as_posix(), 'status': 'UNDECLARED'})
    return {'status': 'INTACT' if all(row['status'] == 'INTACT' for row in rows) else 'INTEGRITY_FAILURE',
            'completion': 'RECORDED' if result_file.exists() else 'INCOMPLETE', 'artifacts': rows,
            'claim_status': 'NOT_ASSERTED', 'human_rating_status': 'NOT_EXECUTED'}


def inspect_run(run_root):
    try:
        return _inspect(run_root)
    except (PairedEvaluationError, OSError, KeyError, TypeError, AttributeError, RecursionError):
        raise PairedEvaluationError('RUN_INTEGRITY_FAILURE') from None


def _grade_run(run_root, assertions_path, output_path):
    root = no_links(run_root); output = no_links(output_path); source = no_links(assertions_path)
    if output.is_relative_to(root) or source.is_relative_to(root):
        fail('GRADING_PATH_NOT_SEPARATE')
    if output.exists():
        fail('ARTIFACT_EXISTS')
    inspection = inspect_run(root)
    if inspection['status'] != 'INTACT' or inspection['completion'] != 'RECORDED':
        fail('RUN_INTEGRITY_FAILURE')
    result = strict_json(read_bytes(root/'result.json'))
    manifest = strict_json(read_bytes(root/'manifest.json'))
    scenario_ids = {row['id'] for row in manifest['scenarios']}
    check_ids = {}
    for attempt in result['attempts']:
        visible = strict_json(read_bytes(contained(root, 'calls/'+attempt['call_id']+'/common/visible-input.json')))
        check_ids[attempt['scenario_id']] = {row['id'] for row in visible['checks']}
    bundle = strict_json(read_bytes(source))
    exact(bundle, 'schema_version run_manifest_sha256 response_schema_sha256 assertions')
    integer(bundle['schema_version'], 1, 1)
    for key in ('run_manifest_sha256', 'response_schema_sha256'):
        if bundle[key] != result[key]:
            fail('GRADER_BINDING_MISMATCH')
    assertions = array(bundle['assertions'], 1024)
    for assertion in assertions:
        exact(assertion, 'id scenario_id check_id expected required_evidence_refs oracle_ref')
        identifier(assertion['id']); identifier(assertion['scenario_id']); identifier(assertion['check_id'])
        if assertion['scenario_id'] not in scenario_ids or assertion['check_id'] not in check_ids[assertion['scenario_id']]:
            fail('UNKNOWN_ASSERTION_BINDING')
        expected = exact(assertion['expected'], 'value_type value'); typed(expected['value_type'], expected['value'])
        for ref in array(assertion['required_evidence_refs'], 64):
            text(ref)
        unique(assertion['required_evidence_refs']); relative(assertion['oracle_ref'])
    unique([row['id'] for row in assertions])
    rows = []
    for attempt in result['attempts']:
        envelope_rows = [entry for entry in attempt['ledger'] if entry['role'] == 'envelope' and entry['capture_state'] == 'RETAINED']
        envelope = strict_json(read_bytes(contained(root, envelope_rows[0]['relative_path']))) if len(envelope_rows) == 1 else None
        for assertion in assertions:
            if assertion['scenario_id'] != attempt['scenario_id']:
                continue
            observations = [item for item in envelope['observations'] if item['check_id'] == assertion['check_id']] if envelope else []
            status = 'UNSCORABLE'
            if len(observations) == 1:
                observed = observations[0]
                equivalent = canonical({'value_type': observed['value_type'], 'value': observed['value']}) == canonical(assertion['expected'])
                equivalent &= set(assertion['required_evidence_refs']).issubset(observed['evidence_refs'])
                status = 'SATISFIED' if equivalent else 'VIOLATED'
            rows.append({'assertion_id': assertion['id'], 'call_id': attempt['call_id'], 'arm_id': attempt['arm_id'],
                         'status': status, 'evidence_pointer': envelope_rows[0]['relative_path']+'#/observations' if envelope_rows else None,
                         'oracle_ref': assertion['oracle_ref']})
    report = {'schema_version': 1, 'run_manifest_sha256': result['run_manifest_sha256'], 'assertions_sha256': digest(canonical(bundle)),
              'execution_backend': result['execution_backend'], 'assertions': rows, 'claim_status': 'NOT_ASSERTED', 'human_rating_status': 'NOT_EXECUTED',
              'parser': {'version': 1, 'implementation_sha256': file_digest(__file__)}}
    _write(output.parent, output.name, canonical(report)+b'\n')
    return report


def grade_run(run_root, assertions_path, output_path):
    try:
        return _grade_run(run_root, assertions_path, output_path)
    except (KeyError, TypeError, AttributeError, RecursionError):
        raise PairedEvaluationError('INVALID_ASSERTION_SCHEMA') from None
    except OSError:
        raise PairedEvaluationError('LOCAL_IO_FAILURE') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    validate = subs.add_parser('validate'); validate.add_argument('manifest')
    for name in ('materialize', 'run'):
        command = subs.add_parser(name); command.add_argument('manifest'); command.add_argument('--exclusions', required=True); command.add_argument('--output', required=True)
    inspect = subs.add_parser('inspect'); inspect.add_argument('run_root')
    grade = subs.add_parser('grade'); grade.add_argument('run_root'); grade.add_argument('--assertions', required=True); grade.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate':
            result = validate_run_manifest(read_bytes(args.manifest), manifest_dir=Path(args.manifest).absolute().parent)
        elif args.command == 'materialize':
            result = materialize_preview(args.manifest, args.exclusions, args.output)
        elif args.command == 'run':
            result = run_pair(args.manifest, args.exclusions, args.output)
        elif args.command == 'inspect':
            result = inspect_run(args.run_root)
        else:
            result = grade_run(args.run_root, args.assertions, args.output)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except (PairedEvaluationError, OSError) as exc:
        print(json.dumps({'status': 'FAILED', 'code': exc.code if isinstance(exc, PairedEvaluationError) else 'LOCAL_IO_FAILURE', 'claim_status': 'NOT_ASSERTED'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
