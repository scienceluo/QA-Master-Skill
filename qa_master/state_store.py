"""Revisioned, atomic local JSON state persistence."""
from __future__ import annotations

import json
import hashlib
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


class StateConflictError(RuntimeError):
    """A state file changed after its caller loaded the recorded revision."""


def _revision(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("State revision must be a non-negative integer")
    return value


@contextmanager
def _file_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        if os.fstat(lock.fileno()).st_size == 0:
            lock.seek(0)
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def load_document(path: str | os.PathLike[str]) -> dict:
    """Read one JSON state document, treating legacy documents as revision zero."""
    source = Path(path)
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("State file cannot be read") from error
    if not isinstance(value, dict):
        raise ValueError("State file must contain a JSON object")
    value = dict(value)
    value["revision"] = _revision(value.get("revision", 0))
    return value


def save_document(path: str | os.PathLike[str], document: dict, *, expected_revision: int,
                  create_if_absent: bool = False, expected_sha256: str | None = None,
                  backup_legacy: bool = False) -> dict:
    """CAS-save a JSON object and return the persisted document with new revision."""
    if not isinstance(document, dict):
        raise ValueError("State document must be a JSON object")
    expected_revision = _revision(expected_revision)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock(destination):
        if destination.exists():
            if create_if_absent:
                raise StateConflictError("State already exists")
            original = destination.read_bytes()
            source_digest = hashlib.sha256(original).hexdigest()
            if expected_sha256 is not None and source_digest != expected_sha256:
                raise StateConflictError("State changed; reload and retry")
            current = load_document(destination)
            current_revision = current["revision"]
            if current_revision != expected_revision:
                raise StateConflictError("State changed; reload and retry")
        elif expected_revision != 0 or expected_sha256 is not None:
            raise StateConflictError("State file is missing; reload before saving")
        persisted = dict(document)
        persisted["revision"] = expected_revision + 1
        payload = json.dumps(persisted, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if backup_legacy:
            if not destination.exists():
                raise StateConflictError("Migration source is missing")
            backup = destination.with_name(destination.name + ".legacy-" + source_digest + ".json")
            try:
                with backup.open("xb") as saved:
                    if os.name != "nt":
                        os.chmod(backup, 0o600)
                    saved.write(original)
                    saved.flush()
                    os.fsync(saved.fileno())
            except FileExistsError:
                if backup.read_bytes() != original:
                    raise StateConflictError("Legacy backup does not match source")
        descriptor, temporary_name = tempfile.mkstemp(prefix=".qa-master-state-", suffix=".json", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_name, destination)
            if os.name == 'posix':
                directory_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
    return persisted
