"""Bounded Jira REST v2 reads and explicitly authorized issue writes."""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class AdapterError(RuntimeError):
    """A safe-to-display integration error; it never includes request headers."""


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise AdapterError("Redirect rejected")


def canonical_json(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Payload must be canonical JSON") from exc


def _origin(base_url):
    value = urlsplit(base_url)
    if value.scheme != "https" or not value.hostname or value.username or value.password or value.query or value.fragment or value.path not in ("", "/"):
        raise ValueError("HTTPS origin URL required")
    return base_url.rstrip("/")


def _safe_identifier(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 255 or "/" in value or ".." in value:
        raise ValueError("Invalid " + name)
    return quote(value, safe="")


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: object


class SafeJsonTransport:
    """HTTPS JSON transport with a strict response cap and no redirect forwarding."""
    def __init__(self, *, max_bytes=2_000_000, timeout=20):
        if not isinstance(max_bytes, int) or not 1 <= max_bytes <= 20_000_000:
            raise ValueError("Invalid response limit")
        self.max_bytes, self.timeout = max_bytes, timeout

    def __call__(self, method, url, headers, body=None):
        if urlsplit(url).scheme != "https":
            raise AdapterError("HTTPS required")
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with build_opener(_RejectRedirects()).open(request, timeout=self.timeout) as response:
                raw = response.read(self.max_bytes + 1)
                if len(raw) > self.max_bytes:
                    raise AdapterError("Response size limit exceeded")
                return HttpResponse(response.status, json.loads(raw.decode("utf-8")) if raw else None)
        except AdapterError:
            raise
        except HTTPError as exc:
            raise AdapterError("HTTP " + str(exc.code)) from None
        except (URLError, OSError, UnicodeError, ValueError) as exc:
            raise AdapterError("Transport failed: " + type(exc).__name__) from None


class JiraAdapter:
    """Jira Cloud REST v2 subset. The verifier must be a trusted external service."""
    def __init__(self, base_url, token, *, transport=None, create_reconciliation_resolver=None):
        self.origin = _origin(base_url)
        if not isinstance(token, str) or not token:
            raise ValueError("Jira token required")
        self._token = token
        self._transport = transport or SafeJsonTransport()
        if create_reconciliation_resolver is not None and not callable(create_reconciliation_resolver):
            raise ValueError("Create reconciliation resolver must be callable")
        self._create_reconciliation_resolver=create_reconciliation_resolver

    def _request(self, method, path, payload=None):
        if not path.startswith("/") or ".." in path or "://" in path:
            raise ValueError("Unsafe API path")
        headers = {"Accept": "application/json", "Authorization": "Bearer " + self._token, "User-Agent": "QA-Master/1.0"}
        body = None if payload is None else canonical_json(payload)
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            result = self._transport(method, self.origin + path, headers, body)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError("Transport failed: " + type(exc).__name__) from None
        if not isinstance(result, HttpResponse) or not isinstance(result.status, int):
            raise AdapterError("Invalid transport response")
        if not 200 <= result.status < 300:
            raise AdapterError("HTTP " + str(result.status))
        return result.body

    def project(self, project_key):
        return self._request("GET", "/rest/api/2/project/" + _safe_identifier(project_key, "project key"))

    def issue(self, issue_key):
        return self._request("GET", "/rest/api/2/issue/" + _safe_identifier(issue_key, "issue key"))

    @staticmethod
    def _approved(approval, action, target, payload):
        digest=hashlib.sha256(canonical_json(payload)).hexdigest()
        if (getattr(approval,"action",None),getattr(approval,"target",None),getattr(approval,"payload_sha256",None)) != (action,target,digest):
            raise PermissionError("Bound journal approval required")

    def create_issue(self, project_key, fields, *, coordinator, idempotency_key, verifier):
        _safe_identifier(project_key, "project key")
        if self._create_reconciliation_resolver is None:
            raise AdapterError("Jira create requires an explicit trusted reconciliation resolver")
        if not isinstance(fields, dict) or fields.get("project", {}).get("key") != project_key:
            raise ValueError("Issue fields must bind the requested project")
        payload = {"fields": fields}
        target = "jira-project:" + project_key + ":issue"
        return coordinator.submit(idempotency_key,action="jira.issue.create",target=target,payload=payload,verifier=verifier)

    def update_issue(self, issue_key, fields, *, coordinator, idempotency_key, verifier):
        _safe_identifier(issue_key, "issue key")
        if not isinstance(fields, dict):
            raise ValueError("Issue fields required")
        payload = {"fields": fields}
        target = "jira-issue:" + issue_key
        return coordinator.submit(idempotency_key,action="jira.issue.update",target=target,payload=payload,verifier=verifier)

    def write(self, *, action, target, payload, approval):
        self._approved(approval,action,target,payload)
        if action=="jira.issue.create":
            project=(payload.get("fields",{}).get("project",{}) if isinstance(payload,dict) else {})
            key=project.get("key")
            if not isinstance(key,str) or target!="jira-project:"+key+":issue":raise PermissionError("Jira target/payload mismatch")
            return self._request("POST","/rest/api/2/issue",payload)
        if action=="jira.issue.update":
            prefix="jira-issue:"
            if not target.startswith(prefix):raise PermissionError("Jira update target mismatch")
            key=target[len(prefix):];encoded=_safe_identifier(key,"issue key")
            return self._request("PUT","/rest/api/2/issue/"+encoded,payload)
        raise AdapterError("Unsupported Jira write action")

    def _issue_matches(self, payload, issue):
        fields=payload.get("fields") if isinstance(payload,dict) else None
        actual=issue.get("fields") if isinstance(issue,dict) else None
        return isinstance(fields,dict) and isinstance(actual,dict) and all(key in actual and self._submitted_subset(value,actual[key]) for key,value in fields.items())

    @staticmethod
    def _submitted_subset(expected, actual):
        """Jira may enrich objects; every submitted value must still be present."""
        if type(expected) is not type(actual):return False
        if isinstance(expected,dict):
            return all(key in actual and JiraAdapter._submitted_subset(value,actual[key]) for key,value in expected.items())
        if isinstance(expected,list):
            return len(expected)==len(actual) and all(JiraAdapter._submitted_subset(left,right) for left,right in zip(expected,actual))
        return expected==actual

    def readback(self, *, action, target, payload, remote_result=None):
        if action=="jira.issue.create":
            key=remote_result.get("key") if isinstance(remote_result,dict) else None
            if not isinstance(key,str):
                candidates=self._create_reconciliation_resolver(action=action,target=target,payload=payload)
                if not isinstance(candidates,(list,tuple)) or len(candidates)!=1 or not isinstance(candidates[0],str):
                    raise AdapterError("Jira create reconciliation needs exactly one trusted candidate key")
                key=candidates[0]
            issue=self.issue(key)
        elif action=="jira.issue.update":
            prefix="jira-issue:"
            if not target.startswith(prefix):raise AdapterError("Jira update target invalid")
            issue=self.issue(target[len(prefix):])
        else:raise AdapterError("Unsupported Jira readback action")
        return {"issue":issue,"matches_payload":self._issue_matches(payload,issue)}

    def manual_readback(self, *, action, target, payload, candidate_key, approval):
        recovery_action=action+".manual_reconcile";recovery_target=target+":candidate:"+candidate_key
        digest=hashlib.sha256(canonical_json(payload)).hexdigest()
        if (getattr(approval,"action",None),getattr(approval,"target",None),getattr(approval,"payload_sha256",None)) != (recovery_action,recovery_target,digest):
            raise PermissionError("Bound manual reconciliation approval required")
        if action!="jira.issue.create":raise AdapterError("Manual reconciliation supports Jira creates only")
        issue=self.issue(candidate_key)
        return {"issue":issue,"matches_payload":self._issue_matches(payload,issue)}

    @staticmethod
    def matches_readback(expected, observed):
        return isinstance(observed,dict) and observed.get("matches_payload") is True
