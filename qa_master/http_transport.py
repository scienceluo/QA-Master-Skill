"""Bounded HTTP reads; authenticated requests never follow redirects."""
from urllib.request import HTTPRedirectHandler, Request, build_opener


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Even same-origin redirects may alter a pinned API resource.
        return None


def read_bytes(url, headers, *, limit, timeout=20):
    if type(limit) is not int or limit < 1:
        raise ValueError("Positive response size limit required")
    with build_opener(RejectRedirects()).open(
        Request(url, headers=headers, method="GET"), timeout=timeout
    ) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Response exceeds size limit")
        return data
