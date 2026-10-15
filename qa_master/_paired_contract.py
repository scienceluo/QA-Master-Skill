"""Strict, process-free contracts for CR-011 (DES-040)."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path

LIMIT = 2 * 1024 * 1024
PROMPT_LIMIT = 6 * 1024 * 1024
SECRET_KEYS = frozenset(('password passwd token access_token refresh_token api_key '
                         'authorization cookie private_key client_secret credential presigned_url').split())
VALUE_TYPES = ['BOOLEAN', 'INTEGER', 'DECIMAL', 'STRING', 'STRING_SET', 'JSON']
CLAIM_KEYS = frozenset('rating score winner quality_grade approval execution_result superiority'.split())
DISABLED_FEATURES = sorted(('apps browser_use browser_use_external code_mode_host computer_use '
                           'hooks image_generation memories multi_agent plugins shell_tool skill_search '
                           'sleep_tool unbounded_connection_retries unified_exec view_image').split())
ISOLATION = 'WRITE_RESTRICTED_READ_SCOPE_UNVERIFIED'
PROFILE = 'EXPLORATORY_CONFIGURED_SAME_MODEL'


class PairedEvaluationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def fail(code):
    raise PairedEvaluationError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw, *, sensitive=True):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                fail('DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    def forbidden(_):
        fail('NON_INTEGER_JSON_NUMBER')
    try:
        if len(raw) > LIMIT:
            fail('SIZE_LIMIT')
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_float=forbidden, parse_constant=forbidden)
        canonical(value)  # reject unpaired Unicode surrogates
        if sensitive:
            check_keys(value, SECRET_KEYS)
        return value
    except (UnicodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, PairedEvaluationError):
            raise
        fail('INVALID_JSON')


def check_keys(value, forbidden):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold() in forbidden:
                fail('PROHIBITED_FIELD')
            check_keys(child, forbidden)
    elif isinstance(value, list):
        for child in value:
            check_keys(child, forbidden)


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        fail('INVALID_MEMBERS')
    return value


def text(value, maximum=20000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        fail('INVALID_TEXT')
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', value):
        fail('INVALID_ID')
    return value


def integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        fail('INVALID_INTEGER')
    return value


def hash_value(value, git=False):
    pattern = r'(?:[0-9a-f]{40}|[0-9a-f]{64})' if git else r'[0-9a-f]{64}'
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        fail('INVALID_HASH')
    return value


def array(value, maximum, minimum=0):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        fail('INVALID_ARRAY')
    return value


def unique(values):
    try:
        if len(values) != len(set(values)):
            fail('DUPLICATE_ID')
    except TypeError:
        fail('INVALID_IDENTIFIER_TYPE')


def relative(value):
    if not isinstance(value, str) or not value or any(
        not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', part) or part.endswith(('.', ' '))
        or part.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(n) for n in range(1, 10)), *('LPT'+str(n) for n in range(1, 10))}
        for part in value.split('/')
    ):
        fail('INVALID_PATH')
    return value


def no_links(path):
    path = Path(os.path.abspath(path))
    for part in [*reversed(path.parents), path]:
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            fail('LINK_FORBIDDEN')
    return path


def contained(root, rel):
    root = no_links(root)
    result = no_links(root / relative(rel))
    if not result.is_relative_to(root):
        fail('PATH_ESCAPE')
    return result


def read_bytes(path, limit=LIMIT):
    path = no_links(path)
    try:
        if not path.is_file():
            fail('MISSING_FILE')
        with path.open('rb') as stream:
            raw = stream.read(limit + 1)
        if len(raw) > limit:
            fail('SIZE_LIMIT')
        return raw
    except OSError:
        fail('FILE_READ_FAILED')


def file_digest(path):
    value = hashlib.sha256()
    try:
        with no_links(path).open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                value.update(chunk)
    except OSError:
        fail('FILE_READ_FAILED')
    return value.hexdigest()


def _object(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


_STRING = {'type': 'string', 'minLength': 1, 'maxLength': 20000}
def _array(items, maximum):
    return {'type': 'array', 'items': items, 'maxItems': maximum}


_REFS = _array(_STRING, 64)
RESPONSE_SCHEMA = _object({
    'schema_version': {'const': 1}, 'scenario_id': _STRING,
    'response_status': {'enum': ['COMPLETED', 'PARTICIPANT_FAILURE']},
    'summary': _STRING,
    'cases': _array(_object({'id': _STRING, 'title': _STRING, 'objective': _STRING,
        'preconditions': _REFS, 'data': _REFS,
        'steps': _array(_object({'action': _STRING, 'expected': _STRING}), 64), 'source_refs': _REFS}), 128),
    'gaps': _array(_object({'id': _STRING, 'description': _STRING, 'impact': _STRING,
        'needed_evidence': _STRING, 'source_refs': _REFS}), 128),
    'observations': _array(_object({'check_id': _STRING, 'value_type': {'enum': VALUE_TYPES},
        'value': {}, 'evidence_refs': _REFS}), 256),
    'metadata': _object({'artifact_state': {'const': 'DRAFT'}, 'execution_state': {'const': 'NOT_EXECUTED'}}),
    'failure_reason': {'anyOf': [_STRING, {'type': 'null'}]},
})
NEUTRAL_RESPONSE_SCHEMA_V1 = canonical(RESPONSE_SCHEMA) + b'\n'
PROMPT_TEMPLATE_V1 = (
    'Perform the visible QA design task using the participant instructions below. '
    'Do not use tools, read files, execute tests, or contact external systems. '
    'Return exactly one JSON object, without Markdown fences, following the neutral response contract. '
    'This is draft test design, never an executed test result. '
    'Answer the named checks with typed observations and source evidence references. '
    'INTEGER is a JSON integer (not boolean); DECIMAL is canonical plain decimal text; '
    'STRING_SET is a sorted unique string array; JSON contains no fractional numbers. '
    'References identify visible fact IDs or listed participant asset paths. '
    'Record uncertainty as gaps; do not invent requirements, execution, approval or quality ratings.\n'
    '{{PARTICIPANT_CONTEXT}}\nVISIBLE_INPUT\n{{VISIBLE_INPUT}}\n'
    'RESPONSE_CONTRACT\n{{RESPONSE_CONTRACT}}\n'
).encode('utf-8')


def typed(value_type, value):
    if value_type not in VALUE_TYPES:
        fail('UNKNOWN_VALUE_TYPE')
    if value_type == 'BOOLEAN' and type(value) is not bool:
        fail('VALUE_TYPE_MISMATCH')
    if value_type == 'INTEGER' and type(value) is not int:
        fail('VALUE_TYPE_MISMATCH')
    if value_type in ('STRING', 'DECIMAL'):
        text(value)
    if value_type == 'DECIMAL' and (not re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?', value) or value == '-0'):
        fail('NONCANONICAL_DECIMAL')
    if value_type == 'STRING_SET':
        for item in array(value, 256):
            text(item)
        if value != sorted(set(value)):
            fail('NONCANONICAL_SET')
    strict_json(canonical(value))
    check_keys(value, CLAIM_KEYS)


def parse_envelope(raw, visible, asset_paths):
    value = strict_json(raw)
    check_keys(value, CLAIM_KEYS)
    exact(value, 'schema_version scenario_id response_status summary cases gaps observations metadata failure_reason')
    integer(value['schema_version'], 1, 1)
    if value['scenario_id'] != visible['scenario_id']:
        fail('SCENARIO_MISMATCH')
    if value['response_status'] not in ('COMPLETED', 'PARTICIPANT_FAILURE'):
        fail('INVALID_RESPONSE_STATUS')
    text(value['summary'])
    if value['metadata'] != {'artifact_state': 'DRAFT', 'execution_state': 'NOT_EXECUTED'}:
        fail('CLAIM_POLICY')
    references = {fact['id'] for fact in visible['known_facts']} | set(asset_paths)
    def refs(rows):
        for item in array(rows, 64):
            text(item)
            if item not in references:
                fail('UNKNOWN_EVIDENCE_REF')
        unique(rows)
    for case in array(value['cases'], 128):
        exact(case, 'id title objective preconditions data steps source_refs')
        identifier(case['id'])
        for key in ('title', 'objective'):
            text(case[key])
        for key in ('preconditions', 'data'):
            for item in array(case[key], 64):
                text(item)
        for step in array(case['steps'], 64):
            exact(step, 'action expected')
            text(step['action']); text(step['expected'])
        refs(case['source_refs'])
    unique([case['id'] for case in value['cases']])
    for gap in array(value['gaps'], 128):
        exact(gap, 'id description impact needed_evidence source_refs')
        identifier(gap['id'])
        for key in ('description', 'impact', 'needed_evidence'):
            text(gap[key])
        refs(gap['source_refs'])
    unique([gap['id'] for gap in value['gaps']])
    checks = {check['id']: check['value_type'] for check in visible['checks']}
    for row in array(value['observations'], 256):
        exact(row, 'check_id value_type value evidence_refs')
        if checks.get(row['check_id']) != row['value_type']:
            fail('CHECK_MISMATCH')
        typed(row['value_type'], row['value'])
        refs(row['evidence_refs'])
    unique([row['check_id'] for row in value['observations']])
    if value['response_status'] == 'COMPLETED':
        if value['failure_reason'] is not None:
            fail('INVALID_FAILURE_REASON')
    else:
        text(value['failure_reason'])
        if value['cases'] or value['observations']:
            fail('INVALID_PARTICIPANT_FAILURE')
    return value
