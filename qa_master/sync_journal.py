"""Durable, reconciliation-first write coordination for explicit adapter contracts."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .jira_adapter import AdapterError, SafeJsonTransport, canonical_json, _origin


def _digest(payload):
    return hashlib.sha256(canonical_json(payload)).hexdigest()


def _reject_secret_fields(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str) and any(marker in key.lower() for marker in ("token", "password", "authorization", "cookie", "secret", "private_key")):
                raise ValueError("Journal payload must not contain credential fields")
            _reject_secret_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_secret_fields(nested)


class OperationJournal:
    """Small atomic JSON journal. It stores payloads, so callers must exclude secrets."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    @contextmanager
    def _exclusive(self):
        """Cross-process lock. A stale lock fails closed and needs operator recovery."""
        deadline=time.monotonic()+5
        while True:
            try:
                handle=os.open(self.lock_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
                break
            except FileExistsError:
                if time.monotonic()>=deadline:raise RuntimeError("Operation journal is busy; manual stale-lock review required")
                time.sleep(.02)
        try:
            os.write(handle,str(os.getpid()).encode("ascii"))
            yield
        finally:
            os.close(handle)
            try:os.unlink(self.lock_path)
            except FileNotFoundError:pass

    def _load(self):
        if not self.path.exists():
            return {"operations": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, dict) or not isinstance(value.get("operations"), dict):
                raise ValueError
            return value
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Invalid operation journal") from exc

    def _save(self, document):
        handle, name = tempfile.mkstemp(prefix=self.path.name + ".", dir=str(self.path.parent))
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(document, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def prepare(self, key, *, action, target, payload):
        if not isinstance(key, str) or not key.strip() or len(key) > 200:
            raise ValueError("Valid idempotency key required")
        if not all(isinstance(v, str) and v for v in (action, target)):
            raise ValueError("Action and target required")
        _reject_secret_fields(payload)
        digest = _digest(payload)
        with self._exclusive():
            document = self._load()
            existing = document["operations"].get(key)
            if existing:
                if (existing["action"], existing["target"], existing["payload_sha256"]) != (action, target, digest):
                    raise ValueError("Idempotency key payload drift")
                return existing
            entry = {"idempotency_key": key, "action": action, "target": target, "payload": payload,
                     "payload_sha256": digest, "state": "PENDING", "attempts": 0, "remote_result": None}
            document["operations"][key] = entry
            self._save(document)
            return entry

    def get(self, key):
        return self._load()["operations"].get(key)

    def transition(self, key, state, *, remote_result=None, reconciliation_error=None):
        if state not in {"PENDING", "SUBMITTED", "UNKNOWN", "VERIFIED", "READBACK_MISMATCH"}:
            raise ValueError("Invalid operation state")
        with self._exclusive():
            document = self._load()
            entry = document["operations"].get(key)
            if not entry:raise KeyError(key)
            entry["state"] = state
            if remote_result is not None:entry["remote_result"] = remote_result
            if reconciliation_error is not None:entry["reconciliation_error"] = reconciliation_error
            document["operations"][key] = entry;self._save(document)
            return entry

    def claim(self, key, lease_id):
        """Atomically mark the one allowed attempt as UNKNOWN before remote I/O."""
        with self._exclusive():
            document=self._load();entry=document["operations"].get(key)
            if not entry:raise KeyError(key)
            if entry["state"]!="PENDING":return entry
            entry["attempts"]+=1;entry["state"]="UNKNOWN";entry["lease_id"]=lease_id
            document["operations"][key]=entry;self._save(document)
            return entry


class WriteCoordinator:
    """Writes once. Remote success is only SUBMITTED until caller-provided readback matches."""
    def __init__(self, journal, adapter):
        self.journal, self.adapter = journal, adapter

    def submit(self, key, *, action, target, payload, verifier):
        entry = self.journal.prepare(key, action=action, target=target, payload=payload)
        if entry["state"] != "PENDING":
            return entry
        if not callable(verifier) or verifier(action=action, target=target, canonical_payload=canonical_json(payload)) is not True:
            raise PermissionError("Write approval rejected")
        approval=_ApprovedWrite(action,target,_digest(payload))
        lease_id=uuid.uuid4().hex
        claimed=self.journal.claim(key,lease_id)  # persist UNKNOWN before the irreversible boundary
        if claimed.get("lease_id")!=lease_id:return claimed
        try:
            response = self.adapter.write(action=action, target=target, payload=payload, approval=approval)
        except Exception as exc:
            # A failed call may have reached the service. Do not retry automatically.
            return self.journal.transition(key, "UNKNOWN", reconciliation_error=type(exc).__name__)
        return self.journal.transition(key, "SUBMITTED", remote_result=response)

    def reconcile(self, key, *, matches):
        entry = self.journal.get(key)
        if not entry:
            raise KeyError(key)
        if entry["state"] not in {"SUBMITTED", "UNKNOWN"}:
            return entry
        try:
            observed = self.adapter.readback(action=entry["action"], target=entry["target"], payload=entry["payload"], remote_result=entry["remote_result"])
        except Exception as exc:
            return self.journal.transition(key, "UNKNOWN", reconciliation_error=type(exc).__name__)
        if not callable(matches):
            raise ValueError("Readback matcher required")
        return self.journal.transition(key, "VERIFIED" if matches(entry["payload"], observed) is True else "READBACK_MISMATCH", remote_result=observed)

    def reconcile_manual(self, key, *, candidate_key, verifier, matches):
        """Human-approved candidate recovery; it never creates or retries a remote object."""
        entry=self.journal.get(key)
        if not entry:raise KeyError(key)
        if entry["state"] not in {"SUBMITTED","UNKNOWN"}:return entry
        action=entry["action"]+".manual_reconcile";target=entry["target"]+":candidate:"+candidate_key
        if not callable(verifier) or verifier(action=action,target=target,canonical_payload=canonical_json(entry["payload"])) is not True:
            raise PermissionError("Manual reconciliation approval rejected")
        approval=_ManualReconciliation(action,target,_digest(entry["payload"]))
        try:
            observed=self.adapter.manual_readback(action=entry["action"],target=entry["target"],payload=entry["payload"],candidate_key=candidate_key,approval=approval)
        except Exception as exc:
            return self.journal.transition(key,"UNKNOWN",reconciliation_error=type(exc).__name__)
        if not callable(matches):raise ValueError("Readback matcher required")
        return self.journal.transition(key,"VERIFIED" if matches(entry["payload"],observed) is True else "READBACK_MISMATCH",remote_result=observed)


@dataclass(frozen=True)
class SynapseRTProfile:
    deployment_id: str
    base_url: str
    operations: dict
    def __post_init__(self):
        _origin(self.base_url)
        if not isinstance(self.deployment_id, str) or not self.deployment_id.strip() or not isinstance(self.operations, dict):
            raise ValueError("Validated deployment profile required")
        for action, contract in self.operations.items():
            if not isinstance(action, str) or not isinstance(contract, dict) or contract.get("method") not in {"POST", "PUT", "PATCH"} or not isinstance(contract.get("path"), str) or not contract["path"].startswith("/") or ".." in contract["path"]:
                raise ValueError("Invalid explicit SynapseRT operation contract")

@dataclass(frozen=True)
class _ApprovedWrite:
    action:str
    target:str
    payload_sha256:str

@dataclass(frozen=True)
class _ManualReconciliation:
    action:str
    target:str
    payload_sha256:str


class SynapseRTAdapter:
    """Generic profile-backed adapter; no vendor endpoint is assumed by this product."""
    def __init__(self, profile, token, *, transport=None):
        if not isinstance(profile, SynapseRTProfile):
            raise AdapterError("SynapseRT requires a validated deployment API profile")
        self.profile, self.origin = profile, _origin(profile.base_url)
        if not isinstance(token, str) or not token:
            raise ValueError("SynapseRT token required")
        self.token, self.transport = token, transport or SafeJsonTransport()

    def write(self, *, action, target, payload, approval):
        contract = self.profile.operations.get(action)
        if not contract:
            raise AdapterError("SynapseRT action unsupported by deployment profile")
        expected_target="synapsert:"+self.profile.deployment_id+":"+contract["method"]+":"+contract["path"]
        if target!=expected_target:
            raise PermissionError("SynapseRT approval target does not match deployment contract")
        if not isinstance(approval,_ApprovedWrite) or (approval.action,approval.target,approval.payload_sha256)!=(action,target,_digest(payload)):
            raise PermissionError("Bound write approval required")
        response = self.transport(contract["method"], self.origin + contract["path"],
                                  {"Accept": "application/json", "Content-Type": "application/json", "Authorization": "Bearer " + self.token, "User-Agent": "QA-Master/1.0"}, canonical_json(payload))
        if not hasattr(response, "status") or not 200 <= response.status < 300:
            raise AdapterError("SynapseRT write failed")
        return response.body

    def readback(self, *, action, target, payload):
        raise AdapterError("SynapseRT readback contract must be supplied by deployment adapter")
