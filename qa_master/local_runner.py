"""Local, bounded test execution with explicit host trust and no remote access."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
import uuid

MAX_STREAM_BYTES = 200_000
_ALLOWED_NAMES = {"pytest", "python", "python3"}
_SENSITIVE_NAME = re.compile(r"(?:secret|token|password|credential|api[_-]?key|private[_-]?key)", re.I)
_SENSITIVE_ARGUMENT = re.compile(r"(?:^--?(?:secret|token|password|credential|api[_-]?key|private[_-]?key)(?:=|$)|authorization\s*:)", re.I)
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MANIFEST_FILE_LIMIT = 2_000
_MANIFEST_BYTE_LIMIT = 50_000_000

@dataclass(frozen=True)
class RunPermit:
    """Caller assertion of execution scope; deliberately not an identity proof."""
    project: str
    command: tuple[str, ...]
    workdir: str
    approver: str
    artifact_version: str

    def verify(self, project, command, workdir, artifact_version):
        if not all((self.project, self.command, self.workdir, self.approver, self.artifact_version)):
            raise PermissionError("Missing approval")
        if (self.project, self.command, self.workdir, self.artifact_version) != (project, tuple(command), workdir, artifact_version):
            raise PermissionError("Execution scope mismatch")

@dataclass(frozen=True)
class TrustedExecutionReceipt:
    """Receipt issued by a configured trust provider, not by a caller boolean."""
    provider: str
    receipt_id: str
    binding_sha256: str
    signature: str

def _binding_digest(binding: dict) -> str:
    raw = json.dumps(binding, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _is_python(executable: str) -> bool:
    try:
        return Path(executable).resolve() == Path(sys.executable).resolve()
    except OSError:
        return False

def _validate_argv(argv) -> None:
    if not isinstance(argv, (list, tuple)) or not argv or any(not isinstance(arg, str) or "\x00" in arg for arg in argv):
        raise ValueError("Invalid argv")
    if argv[0] not in _ALLOWED_NAMES and not _is_python(argv[0]):
        raise PermissionError("Unsupported executable")
    if any(_SENSITIVE_ARGUMENT.search(arg) for arg in argv[1:]):
        raise PermissionError("Secrets in argv are not supported")
    if (_is_python(argv[0]) or argv[0] in {"python", "python3"}) and (len(argv) < 3 or argv[1] != "-m" or argv[2] not in {"pytest", "unittest"}):
        raise PermissionError("Only test modules allowed")

def _resolve_executable(executable: str) -> Path:
    candidate = Path(executable)
    if candidate.is_absolute() or candidate.parent != Path("."):
        resolved = candidate.resolve(strict=True)
    elif _is_python(executable):
        resolved = Path(sys.executable).resolve(strict=True)
    else:
        found = shutil.which(executable, path=os.defpath)
        if not found:
            raise PermissionError("Executable cannot be resolved from safe PATH")
        resolved = Path(found).resolve(strict=True)
    if not resolved.is_file():
        raise PermissionError("Executable must be a file")
    return resolved

def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def _source_manifest(base: Path) -> tuple[list[dict], str]:
    """Bounded, deterministic digest manifest of the actual test workspace."""
    entries, total = [], 0
    for path in sorted(base.rglob("*")):
        relative = path.relative_to(base)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.is_symlink():
            raise PermissionError("Symlinks are not permitted in execution manifest")
        if not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        if len(entries) >= _MANIFEST_FILE_LIMIT or total > _MANIFEST_BYTE_LIMIT:
            raise PermissionError("Workspace manifest exceeds execution safety limit")
        entries.append({"path": relative.as_posix(), "size": size, "sha256": _file_sha256(path)})
    return entries, _binding_digest({"files": entries})

def _verify_provider(provider, binding: dict) -> TrustedExecutionReceipt:
    verify = getattr(provider, "verify_execution", None)
    if not callable(verify):
        raise PermissionError("Trusted execution provider required for local execution")
    try:
        receipt = verify(binding)
    except Exception as error:
        raise PermissionError("Trusted execution provider rejected execution") from error
    if not isinstance(receipt, TrustedExecutionReceipt) or not all((receipt.provider, receipt.receipt_id, receipt.signature)):
        raise PermissionError("Trusted execution provider did not issue a valid receipt")
    if receipt.binding_sha256 != _binding_digest(binding):
        raise PermissionError("Trusted execution receipt does not bind this execution")
    return receipt

def _minimal_environment(workdir: Path, injected_env: dict[str, str] | None) -> tuple[dict[str, str], set[str]]:
    """Build a child environment without inheriting parent secrets or settings."""
    safe_path = []
    for entry in os.defpath.split(os.pathsep):
        if not entry or entry == ".":
            continue
        try:
            if Path(entry).resolve() == workdir:
                continue
        except OSError:
            continue
        safe_path.append(entry)
    env = {"PATH": os.pathsep.join(safe_path), "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    if os.name == "nt":
        for name in ("SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP"):
            if value := os.environ.get(name):
                env[name] = value
    else:
        env["LANG"] = "C.UTF-8"
    secret_values = {value for name, value in os.environ.items() if _SENSITIVE_NAME.search(name) and len(value) >= 4}
    if injected_env is None:
        return env, secret_values
    if not isinstance(injected_env, dict):
        raise ValueError("Injected environment must be a string mapping")
    for name, value in injected_env.items():
        if not isinstance(name, str) or not _ENV_NAME.fullmatch(name) or not isinstance(value, str) or "\x00" in value:
            raise ValueError("Invalid injected environment")
        if _SENSITIVE_NAME.search(name):
            raise PermissionError("Sensitive environment injection requires an external opaque-secret provider")
        env[name] = value
    return env, secret_values

def _redact(text: str, values: set[str]) -> str:
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, "[REDACTED]")
    return text

def _read_stream(stream, parts: list[bytes], state: dict[str, int], limit: int) -> None:
    """Drain a pipe while retaining a strict bounded prefix for evidence."""
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            remaining = max(0, limit - state["retained"])
            if remaining:
                kept = chunk[:remaining]
                parts.append(kept)
                state["retained"] += len(kept)
            state["truncated"] += max(0, len(chunk) - remaining)
    finally:
        stream.close()

def _wait_reap(proc: subprocess.Popen, timeout: float) -> bool:
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    return proc.poll() is not None

def _terminate_process_tree(proc: subprocess.Popen) -> bool:
    """Terminate and reap the child tree; report false when it remains live."""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], shell=False, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if _wait_reap(proc, 5):
            return True
        try:
            proc.kill()
        except OSError:
            return proc.poll() is not None
        return _wait_reap(proc, 5)
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        try:
            proc.terminate()
        except OSError:
            pass
    if _wait_reap(proc, 2):
        return True
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        try:
            proc.kill()
        except OSError:
            return proc.poll() is not None
    return _wait_reap(proc, 5)

def _validate_output_path(output_dir, base: Path) -> Path:
    if not isinstance(output_dir, (str, os.PathLike)):
        raise ValueError("Evidence directory required")
    output = Path(output_dir).expanduser().resolve()
    if output.exists() and not output.is_dir():
        raise ValueError("Evidence path must be a directory")
    if output == base or base in output.parents:
        raise ValueError("Evidence directory must be separate")
    return output

def run_local(project, argv, workdir, artifact_version, permit, output_dir, timeout=60, *, trusted_execution_provider=None,
              injected_env: dict[str, str] | None = None):
    """Run a narrowly allowed local test after an external trust check."""
    _validate_argv(argv)
    if not 1 <= timeout <= 3600:
        raise ValueError("Invalid timeout")
    base = Path(workdir).resolve(strict=True)
    if not base.is_dir():
        raise ValueError("Working directory missing")
    permit.verify(project, argv, str(base), artifact_version)
    output = _validate_output_path(output_dir, base)
    env, secret_values = _minimal_environment(base, injected_env)
    executable = _resolve_executable(argv[0])
    launch_argv = [str(executable), *argv[1:]]
    manifest, manifest_sha256 = _source_manifest(base)
    binding = {"project": project, "argv": launch_argv, "requested_argv": list(argv), "workdir": str(base), "artifact_version": artifact_version,
               "output_dir": str(output), "timeout_seconds": timeout,
               "resolved_executable": str(executable), "executable_sha256": _file_sha256(executable),
               "source_manifest": manifest, "source_manifest_sha256": manifest_sha256,
               "environment_names": sorted(env),
               "environment_bindings": {name: hashlib.sha256(value.encode("utf-8")).hexdigest() for name, value in sorted(injected_env.items())} if injected_env else {}}
    receipt = _verify_provider(trusted_execution_provider, binding)
    output.mkdir(parents=True, exist_ok=True)
    event, started = str(uuid.uuid4()), time.time()
    popen_kwargs = {"cwd": base, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": False, "shell": False, "env": env}
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True
    stdout_parts: list[bytes] = []
    stderr_parts: list[bytes] = []
    stdout_state, stderr_state = {"retained": 0, "truncated": 0}, {"retained": 0, "truncated": 0}
    process_reaped = None
    try:
        proc = subprocess.Popen(launch_argv, **popen_kwargs)
        stdout_thread = threading.Thread(target=_read_stream, args=(proc.stdout, stdout_parts, stdout_state, MAX_STREAM_BYTES))
        stderr_thread = threading.Thread(target=_read_stream, args=(proc.stderr, stderr_parts, stderr_state, MAX_STREAM_BYTES))
        stdout_thread.start()
        stderr_thread.start()
        try:
            code = proc.wait(timeout=timeout)
            status = "PROCESS_SUCCEEDED" if code == 0 else "PROCESS_FAILED"
        except subprocess.TimeoutExpired:
            code = None
            process_reaped = _terminate_process_tree(proc)
            status = "TIMEOUT" if process_reaped else "ENVIRONMENT_ERROR"
        stdout_thread.join(timeout=10)
        stderr_thread.join(timeout=10)
        if stdout_thread.is_alive() or stderr_thread.is_alive():
            status, code = "ENVIRONMENT_ERROR", None
    except OSError as error:
        status, code = "ENVIRONMENT_ERROR", None
        stdout_parts, stderr_parts = [], [type(error).__name__.encode("utf-8")]
    stdout = _redact(b"".join(stdout_parts).decode("utf-8", errors="replace"), secret_values)
    stderr = _redact(b"".join(stderr_parts).decode("utf-8", errors="replace"), secret_values)
    out, err, meta = output / f"{event}.stdout.txt", output / f"{event}.stderr.txt", output / f"{event}.json"
    out.write_text(stdout, encoding="utf-8")
    err.write_text(stderr, encoding="utf-8")
    record = {"run_id": event, "project": project, "argv": list(argv), "executed_argv": launch_argv, "workdir": str(base), "artifact_version": artifact_version,
              "output_dir": str(output), "timeout_seconds": timeout,
              "approver": permit.approver, "process_status": status, "business_result": "NOT_ASSESSED", "returncode": code,
              "duration_sec": round(time.time() - started, 4), "stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest(),
              "stderr_sha256": hashlib.sha256(stderr.encode()).hexdigest(), "stdout_path": str(out), "stderr_path": str(err),
              "stdout_truncated_bytes": stdout_state["truncated"], "stderr_truncated_bytes": stderr_state["truncated"],
              "process_reaped": process_reaped,
              "environment": "SANITIZED_MINIMAL", "workspace_isolation": "NOT_PROVIDED", "source_manifest_sha256": manifest_sha256,
              "executable_sha256": binding["executable_sha256"], "trusted_provider": receipt.provider,
              "trusted_receipt_id": receipt.receipt_id, "execution_binding_sha256": receipt.binding_sha256}
    meta.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record
