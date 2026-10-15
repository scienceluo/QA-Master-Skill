"""Validated non-secret local configuration for QA Master."""
from __future__ import annotations

import copy
import ipaddress
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Raised when a configuration is unsafe or does not match schema v1."""


SCHEMA_VERSION = 1
MAX_CONFIG_BYTES = 256 * 1024
MAX_MACHINES = 64
_ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]{0,127}\Z")
_HOST_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?\Z")
_SERVICES = ("gitlab", "jira", "confluence")
_MAPPING_KEYS = ("gitlab_project", "jira_project", "confluence_space", "synapsert_project")

DEFAULT_CONFIGURATION = {
    "schema_version": SCHEMA_VERSION,
    "services": {name: {"base_url": "", "credential_env": ""} for name in _SERVICES},
    "project_mappings": {name: "" for name in _MAPPING_KEYS},
    "machines": [],
}


def default_configuration() -> dict:
    """Return a mutable safe, empty schema-v1 configuration."""
    return copy.deepcopy(DEFAULT_CONFIGURATION)


def _require_exact_keys(value: dict, keys: tuple[str, ...], label: str) -> None:
    if set(value) != set(keys):
        raise ConfigurationError(f"{label} contains unsupported or missing fields")


def _text(value: object, label: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or len(value) > maximum or any(ord(char) < 32 for char in value):
        raise ConfigurationError(f"Invalid {label}")
    return value


def _environment_reference(value: object, label: str) -> str:
    text = _text(value, label, 128)
    if text and not _ENV_NAME.fullmatch(text):
        raise ConfigurationError(f"Invalid {label}; use an environment variable name")
    return text


def _endpoint(value: object, label: str) -> str:
    text = _text(value, label, 2048)
    if not text:
        return ""
    parsed = urlsplit(text)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ConfigurationError(f"Invalid {label}; use a clean HTTPS endpoint")
    try:
        port = parsed.port
    except ValueError as error:
        raise ConfigurationError(f"Invalid {label}; invalid port") from error
    if port is not None and not 1 <= port <= 65535:
        raise ConfigurationError(f"Invalid {label}; invalid port")
    _validate_network_host(parsed.hostname, label)
    if ".." in parsed.path.split("/"):
        raise ConfigurationError(f"Invalid {label}; unsafe path")
    return text


def _validate_network_host(value: str | None, label: str) -> None:
    if not value:
        raise ConfigurationError(f"Invalid {label}")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        if not _HOST_NAME.fullmatch(value) or ".." in value or value.startswith(".") or value.endswith("."):
            raise ConfigurationError(f"Invalid {label}")


def _host(value: object) -> str:
    text = _text(value, "machine host", 253)
    if not text or "://" in text or "@" in text:
        raise ConfigurationError("Invalid machine host")
    _validate_network_host(text, "machine host")
    return text


def _mapping(value: object, label: str) -> str:
    return _text(value, label, 256)


def validate_configuration(candidate: object) -> dict:
    """Validate and normalize a schema-v1 non-secret configuration."""
    if not isinstance(candidate, dict):
        raise ConfigurationError("Configuration must be a JSON object")
    _require_exact_keys(candidate, ("schema_version", "services", "project_mappings", "machines"), "configuration")
    if type(candidate["schema_version"]) is not int or candidate["schema_version"] != SCHEMA_VERSION:
        raise ConfigurationError("Unsupported configuration schema version")
    services = candidate["services"]
    if not isinstance(services, dict):
        raise ConfigurationError("services must be an object")
    _require_exact_keys(services, _SERVICES, "services")
    normalized_services = {}
    for name in _SERVICES:
        service = services[name]
        if not isinstance(service, dict):
            raise ConfigurationError(f"{name} service must be an object")
        _require_exact_keys(service, ("base_url", "credential_env"), f"{name} service")
        normalized_services[name] = {
            "base_url": _endpoint(service["base_url"], f"{name} endpoint"),
            "credential_env": _environment_reference(service["credential_env"], f"{name} credential reference"),
        }
    mappings = candidate["project_mappings"]
    if not isinstance(mappings, dict):
        raise ConfigurationError("project_mappings must be an object")
    _require_exact_keys(mappings, _MAPPING_KEYS, "project_mappings")
    machines = candidate["machines"]
    if not isinstance(machines, list) or len(machines) > MAX_MACHINES:
        raise ConfigurationError("machines must be a bounded list")
    normalized_machines = []
    identifiers = set()
    for machine in machines:
        if not isinstance(machine, dict):
            raise ConfigurationError("machine must be an object")
        _require_exact_keys(machine, ("id", "platform", "host", "transport", "credential_env", "exclusive"), "machine")
        identifier = _text(machine["id"], "machine id", 128)
        if not identifier or identifier in identifiers:
            raise ConfigurationError("Machine IDs must be nonempty and unique")
        identifiers.add(identifier)
        platform = machine["platform"]
        transport = machine["transport"]
        if platform not in ("windows", "linux"):
            raise ConfigurationError("Machine platform must be windows or linux")
        if transport not in ("ssh", "winrm", "runner"):
            raise ConfigurationError("Unsupported machine transport")
        if not isinstance(machine["exclusive"], bool):
            raise ConfigurationError("Machine exclusive must be boolean")
        normalized_machines.append(
            {
                "id": identifier,
                "platform": platform,
                "host": _host(machine["host"]),
                "transport": transport,
                "credential_env": _environment_reference(machine["credential_env"], "machine credential reference"),
                "exclusive": machine["exclusive"],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "services": normalized_services,
        "project_mappings": {key: _mapping(mappings[key], key) for key in _MAPPING_KEYS},
        "machines": normalized_machines,
    }


def load_configuration(path: str | os.PathLike[str]) -> dict:
    """Load a bounded configuration, returning defaults when it is absent."""
    config_path = Path(path)
    if not config_path.exists():
        return default_configuration()
    if config_path.stat().st_size > MAX_CONFIG_BYTES:
        raise ConfigurationError("Configuration file exceeds size limit")
    try:
        with config_path.open("r", encoding="utf-8") as source:
            return validate_configuration(json.load(source))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError("Configuration file cannot be read") from error


def save_configuration(path: str | os.PathLike[str], candidate: object) -> dict:
    """Validate and atomically replace a local configuration file."""
    normalized = validate_configuration(candidate)
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if len(payload.encode("utf-8")) > MAX_CONFIG_BYTES:
        raise ConfigurationError("Configuration exceeds size limit")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".qa-master-config-", suffix=".json", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, destination)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    return normalized
