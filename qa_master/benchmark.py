"""Offline validation and recording for a paired QA capability benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


class BenchmarkError(ValueError):
    """Raised when comparison evidence is incomplete or inconsistent."""


RUBRIC_DIMENSIONS = ("factuality", "scope", "oracle", "traceability", "coverage")
MAX_ARTIFACT_BYTES = 2 * 1024 * 1024


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_json(path: str | os.PathLike[str]) -> tuple[object, str]:
    source = Path(path)
    try:
        raw = source.read_bytes()
    except OSError as error:
        raise BenchmarkError("Cannot read benchmark artifact") from error
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise BenchmarkError("Benchmark artifact exceeds size limit")
    try:
        return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BenchmarkError("Benchmark artifact is not valid UTF-8 JSON") from error


def _nonempty_text(value: object, label: str, maximum: int = 200_000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise BenchmarkError(f"Missing or invalid {label}")
    return value


def load_scenarios(path: str | os.PathLike[str]) -> tuple[list[dict], str]:
    """Load an original scenario set and derive its canonical SHA-256 identity."""
    value, _raw_hash = _read_json(path)
    if not isinstance(value, dict) or set(value) != {"schema_version", "title", "scenarios"}:
        raise BenchmarkError("Invalid scenario-set schema")
    if value["schema_version"] != 1 or not isinstance(value["scenarios"], list) or len(value["scenarios"]) < 12:
        raise BenchmarkError("Scenario set requires schema v1 and at least twelve scenarios")
    required = {"id", "title", "request", "known_facts", "scope", "oracle", "traceability", "coverage"}
    identifiers = set()
    for scenario in value["scenarios"]:
        if not isinstance(scenario, dict) or set(scenario) != required:
            raise BenchmarkError("Scenario is missing required original-input fields")
        identifier = _nonempty_text(scenario["id"], "scenario id", 128)
        if identifier in identifiers:
            raise BenchmarkError("Scenario IDs must be unique")
        identifiers.add(identifier)
        for field in required - {"id", "known_facts"}:
            _nonempty_text(scenario[field], f"scenario {field}")
        if not isinstance(scenario["known_facts"], list) or not scenario["known_facts"]:
            raise BenchmarkError("Scenario known_facts must be a nonempty list")
        for fact in scenario["known_facts"]:
            _nonempty_text(fact, "known fact")
    return value["scenarios"], hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _validate_rubric(rubric: object) -> dict:
    if not isinstance(rubric, dict) or set(rubric) != set(RUBRIC_DIMENSIONS):
        raise BenchmarkError("Each response requires every shared rubric dimension")
    normalized = {}
    for dimension in RUBRIC_DIMENSIONS:
        row = rubric[dimension]
        if not isinstance(row, dict) or set(row) != {"score", "rationale", "evidence_ref"}:
            raise BenchmarkError(f"Invalid {dimension} rubric entry")
        if type(row["score"]) is not int or not 1 <= row["score"] <= 5:
            raise BenchmarkError(f"Invalid {dimension} score")
        normalized[dimension] = {
            "score": row["score"],
            "rationale": _nonempty_text(row["rationale"], f"{dimension} rationale", 10_000),
            "evidence_ref": _nonempty_text(row["evidence_ref"], f"{dimension} evidence reference", 10_000),
        }
    return normalized


def validate_submission(value: object, scenario_ids: set[str], scenario_hash: str, model: str, settings: object) -> dict:
    """Validate a submitted behavioral artifact without scoring it on its behalf."""
    required = {"schema_version", "participant_id", "participant_version", "model", "settings", "scenario_set_sha256", "responses"}
    if not isinstance(value, dict) or set(value) != required or value.get("schema_version") != 1:
        raise BenchmarkError("Invalid submission schema")
    if value["scenario_set_sha256"] != scenario_hash:
        raise BenchmarkError("Submission scenario input hash does not match")
    if value["model"] != model:
        raise BenchmarkError("Submission model does not match the paired run")
    if value["settings"] != settings:
        raise BenchmarkError("Submission settings do not match the paired run")
    participant_id = _nonempty_text(value["participant_id"], "participant ID", 256)
    participant_version = _nonempty_text(value["participant_version"], "participant version", 256)
    responses = value["responses"]
    if not isinstance(responses, list) or len(responses) != len(scenario_ids):
        raise BenchmarkError("Submission requires one response for every scenario")
    normalized_responses = []
    submitted_ids = set()
    for response in responses:
        if not isinstance(response, dict) or set(response) != {"scenario_id", "behavioral_output", "rubric"}:
            raise BenchmarkError("Invalid response schema")
        scenario_id = _nonempty_text(response["scenario_id"], "response scenario ID", 128)
        if scenario_id not in scenario_ids or scenario_id in submitted_ids:
            raise BenchmarkError("Responses must use every scenario exactly once")
        submitted_ids.add(scenario_id)
        normalized_responses.append(
            {
                "scenario_id": scenario_id,
                "behavioral_output": _nonempty_text(response["behavioral_output"], "behavioral output"),
                "rubric": _validate_rubric(response["rubric"]),
            }
        )
    return {
        "participant_id": participant_id,
        "participant_version": participant_version,
        "model": model,
        "settings": settings,
        "scenario_set_sha256": scenario_hash,
        "responses": normalized_responses,
    }


def evaluate_pair(scenarios_path, left_path, right_path, *, model: str, settings: object) -> dict:
    """Record a complete paired measurement; never assert superiority automatically."""
    model = _nonempty_text(model, "model", 512)
    if not isinstance(settings, dict):
        raise BenchmarkError("Settings must be a JSON object")
    scenarios, scenario_hash = load_scenarios(scenarios_path)
    scenario_ids = {scenario["id"] for scenario in scenarios}
    left_raw, left_sha256 = _read_json(left_path)
    right_raw, right_sha256 = _read_json(right_path)
    left = validate_submission(left_raw, scenario_ids, scenario_hash, model, settings)
    right = validate_submission(right_raw, scenario_ids, scenario_hash, model, settings)
    if left["participant_id"] == right["participant_id"]:
        raise BenchmarkError("Paired participants must be distinct")
    return {
        "schema_version": 1,
        "measurement_status": "MEASURED_PAIRED_SUBMITTED_UNVERIFIED",
        "claim_status": "HUMAN_REVIEW_REQUIRED",
        "claim": "No superiority assertion is generated by this tool.",
        "scenario_set_sha256": scenario_hash,
        "model": model,
        "settings": settings,
        "rubric_dimensions": list(RUBRIC_DIMENSIONS),
        "scores_source": "SUBMITTED_UNVERIFIED_HUMAN_RATINGS",
        "participants": [
            {"artifact_sha256": left_sha256, **left},
            {"artifact_sha256": right_sha256, **right},
        ],
    }


def write_result(path: str | os.PathLike[str], result: dict) -> None:
    destination = Path(path)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".qa-master-benchmark-", suffix=".json", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, destination)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate an offline paired QA capability benchmark")
    parser.add_argument("--scenarios", required=True)
    parser.add_argument("--left", required=True, help="First submitted behavioral-output JSON")
    parser.add_argument("--right", required=True, help="Second submitted behavioral-output JSON")
    parser.add_argument("--model", required=True)
    parser.add_argument("--settings", required=True, help="Fixed JSON object for both submissions")
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args(argv)
    try:
        settings = json.loads(arguments.settings)
        result = evaluate_pair(arguments.scenarios, arguments.left, arguments.right, model=arguments.model, settings=settings)
        write_result(arguments.output, result)
    except (BenchmarkError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps({"measurement_status": result["measurement_status"], "claim_status": result["claim_status"], "output": arguments.output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
