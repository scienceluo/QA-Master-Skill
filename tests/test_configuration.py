import http.client
import json
import re
import subprocess
import sys
import tempfile
import threading
import unittest
import socket
from pathlib import Path
from urllib.parse import urlencode

from qa_master.config_ui import MAX_BODY_BYTES, create_server
from qa_master.configuration import (
    ConfigurationError,
    default_configuration,
    load_configuration,
    save_configuration,
    validate_configuration,
)


def configured():
    value = default_configuration()
    value["services"]["gitlab"] = {
        "base_url": "https://gitlab.example.test/root",
        "credential_env": "GITLAB_READ_TOKEN",
    }
    value["project_mappings"]["gitlab_project"] = "quality/master"
    value["machines"] = [
        {
            "id": "windows-lab-01",
            "platform": "windows",
            "host": "192.0.2.10",
            "transport": "winrm",
            "credential_env": "QA_WINRM_SECRET",
            "exclusive": True,
        },
        {
            "id": "linux-lab-01",
            "platform": "linux",
            "host": "lab.example.test",
            "transport": "ssh",
            "credential_env": "QA_SSH_SECRET",
            "exclusive": False,
        },
    ]
    return value


class ConfigurationPersistenceTests(unittest.TestCase):
    def test_missing_file_uses_safe_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_configuration(Path(directory) / "absent.json"), default_configuration())

    def test_atomic_save_and_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "configuration.json"
            expected = configured()
            self.assertEqual(save_configuration(path, expected), expected)
            self.assertEqual(load_configuration(path), expected)
            self.assertFalse(list(path.parent.glob(".qa-master-config-*.json")))

    def test_malformed_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "configuration.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ConfigurationError):
                load_configuration(path)

    def test_raw_secret_field_is_rejected(self):
        value = configured()
        value["services"]["jira"]["token"] = "do-not-store-me"
        with self.assertRaises(ConfigurationError):
            validate_configuration(value)

    def test_unsafe_endpoint_and_machine_are_rejected(self):
        value = configured()
        value["services"]["jira"] = {
            "base_url": "https://user:secret@jira.example.test/api?token=bad",
            "credential_env": "JIRA_TOKEN",
        }
        with self.assertRaises(ConfigurationError):
            validate_configuration(value)
        value = configured()
        value["services"]["gitlab"]["base_url"] = "https://bad host.example.test"
        with self.assertRaises(ConfigurationError):
            validate_configuration(value)
        value = configured()
        value["machines"][0]["transport"] = "telnet"
        with self.assertRaises(ConfigurationError):
            validate_configuration(value)

    def test_secret_reference_must_be_environment_variable_name(self):
        value = configured()
        value["services"]["gitlab"]["credential_env"] = "secret://qa/gitlab"
        with self.assertRaises(ConfigurationError):
            validate_configuration(value)


class ConfigurationUiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "configuration.json"
        self.server = create_server(self.path, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.directory.cleanup()

    def request(self, method, path, body=None, headers=None):
        status, content, _ = self.request_with_headers(method, path, body, headers)
        return status, content

    def request_with_headers(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        content = response.read().decode("utf-8")
        status = response.status
        response_headers = dict(response.getheaders())
        connection.close()
        return status, content, response_headers

    def page_token(self):
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        match = re.search(r'name=csrf value="([^"]+)"', page)
        self.assertIsNotNone(match)
        return match.group(1)

    def save_headers(self):
        return {
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": f"127.0.0.1:{self.port}",
            "Origin": f"http://127.0.0.1:{self.port}",
        }

    def test_local_ui_persists_valid_configuration(self):
        payload = urlencode({"csrf": self.page_token(), "config": json.dumps(configured())})
        status, page = self.request("POST", "/save", payload, self.save_headers())
        self.assertEqual(status, 200)
        self.assertIn("配置已保存", page)
        self.assertEqual(load_configuration(self.path), configured())

    def test_ui_rejects_missing_csrf_and_cross_origin(self):
        headers = self.save_headers()
        payload = urlencode({"csrf": "wrong", "config": json.dumps(configured())})
        self.assertEqual(self.request("POST", "/save", payload, headers)[0], 403)
        headers["Origin"] = "http://evil.example.test"
        payload = urlencode({"csrf": self.page_token(), "config": json.dumps(configured())})
        self.assertEqual(self.request("POST", "/save", payload, headers)[0], 403)
        self.assertFalse(self.path.exists())

    def test_get_rejects_non_loopback_host_and_sets_anti_embedding_policy(self):
        status, _, _ = self.request_with_headers("GET", "/", headers={"Host": f"evil.example.test:{self.port}"})
        self.assertEqual(status, 403)
        status, _, headers = self.request_with_headers("GET", "/", headers={"Host": f"127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)
        self.assertIn("form-action 'self'", headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_ui_rejects_oversized_request_and_non_loopback_bind(self):
        headers = self.save_headers()
        body = b"x" * (MAX_BODY_BYTES + 1)
        headers["Content-Length"] = str(len(body))
        self.assertEqual(self.request("POST", "/save", body, headers)[0], 413)
        with self.assertRaises(ValueError):
            create_server(self.path, "0.0.0.0", 0)

    def test_oversized_incomplete_request_has_bounded_413_response(self):
        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as connection:
            connection.sendall(
                (
                    "POST /save HTTP/1.1\r\n"
                    f"Host: 127.0.0.1:{self.port}\r\n"
                    f"Origin: http://127.0.0.1:{self.port}\r\n"
                    "Content-Length: 1048576\r\n"
                    "\r\n"
                ).encode("ascii")
            )
            connection.settimeout(1)
            response = connection.recv(4096)
        self.assertIn(b" 413 ", response)

    def test_module_cli_exposes_config_and_port_options(self):
        result = subprocess.run(
            [sys.executable, "-m", "qa_master.config_ui", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--config", result.stdout)
        self.assertIn("--port", result.stdout)
