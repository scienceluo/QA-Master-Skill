"""Confluence REST v2 page reader; it intentionally has no write API."""
from __future__ import annotations

from urllib.parse import urlencode
from .jira_adapter import AdapterError, HttpResponse, SafeJsonTransport, _origin, _safe_identifier


class ConfluenceReader:
    def __init__(self, base_url, token, *, transport=None):
        self.origin = _origin(base_url)
        if not isinstance(token, str) or not token:
            raise ValueError("Confluence token required")
        self._token, self._transport = token, transport or SafeJsonTransport()

    def page(self, page_id, *, include_body=False, include_version=True):
        identifier = _safe_identifier(str(page_id), "page id")
        params = []
        if include_body:
            params.append(("body-format", "storage"))
        if include_version:
            params.append(("include-version", "true"))
        url = self.origin + "/wiki/api/v2/pages/" + identifier
        if params:
            url += "?" + urlencode(params)
        try:
            response = self._transport("GET", url, {"Accept": "application/json", "Authorization": "Bearer " + self._token, "User-Agent": "QA-Master/1.0"})
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError("Transport failed: " + type(exc).__name__) from None
        if not isinstance(response, HttpResponse) or not 200 <= response.status < 300:
            raise AdapterError("Invalid Confluence response")
        return response.body
