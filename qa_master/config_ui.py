"""Loopback-only configuration UI; it never contacts enterprise services."""
from __future__ import annotations

import argparse
import html
import ipaddress
import json
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .configuration import ConfigurationError, load_configuration, save_configuration


MAX_BODY_BYTES = 64 * 1024
OVERSIZED_DRAIN_TIMEOUT_SECONDS = 0.25


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _parse_authority(value: str | None) -> tuple[str, int] | None:
    if not value or any(char.isspace() for char in value):
        return None
    try:
        parsed = urlsplit("//" + value)
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return None
        port = parsed.port
        if not parsed.hostname or port is None:
            return None
        return parsed.hostname.lower(), port
    except ValueError:
        return None


def _valid_local_host(host_header: str | None, port: int) -> bool:
    host = _parse_authority(host_header)
    return bool(host and host[1] == port and _is_loopback(host[0]))


def _valid_origin(origin: str | None, host_header: str | None, port: int) -> bool:
    host = _parse_authority(host_header)
    if not _valid_local_host(host_header, port):
        return False
    if not origin:
        return False
    try:
        parsed = urlsplit(origin)
        if parsed.scheme != "http" or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return False
        origin_authority = _parse_authority(parsed.netloc)
    except ValueError:
        return False
    return origin_authority == host


def make_handler(config_path, csrf_token: str):
    """Construct a handler fixed to one local config file and one CSRF token."""
    class ConfigurationHandler(BaseHTTPRequestHandler):
        server_version = "QA-Master-Config/1"

        def log_message(self, _format, *_args):
            return

        def _reply(self, status: HTTPStatus, body: str, content_type: str = "text/html; charset=utf-8"):
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            )
            self.send_header("X-Frame-Options", "DENY")
            if self.close_connection:
                self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(encoded)

        def _discard_oversized_body(self, length: int):
            """Consume a bounded amount before closing, without waiting indefinitely."""
            original_timeout = self.connection.gettimeout()
            self.connection.settimeout(OVERSIZED_DRAIN_TIMEOUT_SECONDS)
            try:
                self.rfile.read(min(length, MAX_BODY_BYTES + 1))
            except OSError:
                pass
            finally:
                self.connection.settimeout(original_timeout)

        def _page(self, message: str = "", status: HTTPStatus = HTTPStatus.OK):
            try:
                config_text = json.dumps(load_configuration(config_path), ensure_ascii=False, indent=2, sort_keys=True)
            except ConfigurationError as error:
                config_text = json.dumps({}, ensure_ascii=False, indent=2)
                message = f"无法读取现有配置：{error}"
                status = HTTPStatus.BAD_REQUEST
            notice = f"<p class=notice>{html.escape(message)}</p>" if message else ""
            body = f"""<!doctype html><html lang=zh-CN><head><meta charset=utf-8><title>QA Master 配置</title>
<style>body{{font-family:system-ui,sans-serif;max-width:880px;margin:2rem auto;padding:0 1rem}}textarea{{box-sizing:border-box;width:100%;height:32rem;font-family:ui-monospace,monospace}}button{{padding:.6rem 1rem}}.notice{{color:#a13b00}}</style>
</head><body><h1>QA Master 本地配置</h1><p>这里只保存端点、项目映射、机器元数据和环境变量引用。不会保存或显示密码、Token、Cookie、私钥，也不会连接企业系统或执行测试。</p>{notice}
<form method=post action=/save><input type=hidden name=csrf value=\"{html.escape(csrf_token, quote=True)}\"><label for=config>配置 JSON</label><textarea id=config name=config required>{html.escape(config_text)}</textarea><p><button type=submit>校验并保存</button></p></form></body></html>"""
            self._reply(status, body)

        def do_GET(self):
            if not _valid_local_host(self.headers.get("Host"), self.server.server_port):
                self._reply(HTTPStatus.FORBIDDEN, "Invalid local host", "text/plain; charset=utf-8")
                return
            if self.path != "/":
                self._reply(HTTPStatus.NOT_FOUND, "Not found", "text/plain; charset=utf-8")
                return
            self._page()

        def do_POST(self):
            if self.path != "/save":
                self._reply(HTTPStatus.NOT_FOUND, "Not found", "text/plain; charset=utf-8")
                return
            if not _valid_origin(self.headers.get("Origin"), self.headers.get("Host"), self.server.server_port):
                self._reply(HTTPStatus.FORBIDDEN, "Invalid local origin", "text/plain; charset=utf-8")
                return
            try:
                length = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY_BYTES:
                if length > MAX_BODY_BYTES:
                    self._discard_oversized_body(length)
                self.close_connection = True
                self._reply(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request too large", "text/plain; charset=utf-8")
                return
            try:
                form = parse_qs(self.rfile.read(length).decode("utf-8", "strict"), keep_blank_values=True)
            except UnicodeDecodeError:
                self._reply(HTTPStatus.BAD_REQUEST, "Invalid request encoding", "text/plain; charset=utf-8")
                return
            if not secrets.compare_digest(form.get("csrf", [""])[0], csrf_token):
                self._reply(HTTPStatus.FORBIDDEN, "Invalid CSRF token", "text/plain; charset=utf-8")
                return
            raw_config = form.get("config", [""])[0]
            try:
                candidate = json.loads(raw_config)
                save_configuration(config_path, candidate)
            except (ConfigurationError, json.JSONDecodeError, UnicodeDecodeError) as error:
                self._page(f"配置未保存：{error}", HTTPStatus.BAD_REQUEST)
                return
            self._page("配置已保存。本页面未连接任何企业系统。")
    return ConfigurationHandler


def create_server(config_path, host: str = "127.0.0.1", port: int = 8765):
    """Create a server only for loopback binding."""
    if not _is_loopback(host):
        raise ValueError("Configuration UI may bind only to a loopback address")
    if not isinstance(port, int) or not 0 <= port <= 65535:
        raise ValueError("Invalid port")
    bind_host = "127.0.0.1" if host.lower() == "localhost" else host
    return ThreadingHTTPServer((bind_host, port), make_handler(config_path, secrets.token_urlsafe(32)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Loopback-only QA Master non-secret configuration UI")
    parser.add_argument("--config", required=True, help="Local JSON configuration path")
    parser.add_argument("--host", default="127.0.0.1", help="Loopback host only")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args(argv)
    server = create_server(arguments.config, arguments.host, arguments.port)
    print(f"QA Master configuration UI: http://{arguments.host}:{server.server_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
