"""Developer verification for TASK-041. Synthetic capture is never pilot evidence."""
import copy
import json
import platform
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qa_master import paired_evaluation as pe
from qa_master._paired_contract import canonical, digest, file_digest, PairedEvaluationError
from qa_master._paired_process import parse_trace, redact, environment, native_capture


def fixture(root):
    inputs = root/'inputs'; inputs.mkdir()
    def save(name, raw):
        (inputs/name).parent.mkdir(parents=True, exist_ok=True)
        (inputs/name).write_bytes(raw)
        return {'source_path': name, 'byte_count': len(raw), 'sha256': digest(raw)}
    exclusion = {'schema_version': 1, 'forbidden_locators': ['holdout/answers.json'],
                 'forbidden_sha256': [], 'fixture_markers': ['EVALUATOR_ONLY_SENTINEL_001']}
    excluded = root/'excluded.json'; excluded.write_bytes(canonical(exclusion))
    participants = []
    for arm in ('A', 'B'):
        asset = save(arm+'.md', ('Participant '+arm+' literal {{VISIBLE_INPUT}}').encode())
        asset.update({'path': 'SKILL.md', 'media_type': 'text/markdown'})
        participants.append({'arm_id': arm, 'participant_id': 'participant-'+arm,
            'source': {'repository_id': 'repo-'+arm, 'commit': '1'*40, 'tree_oid': '2'*40},
            'entry_asset': 'SKILL.md', 'assets': [asset]})
    scenarios = []; schedule = []
    for n, method in enumerate(('boundary', 'decision_table', 'state_transition')):
        sid = 'S'+str(n)
        visible = {'schema_version': 1, 'scenario_id': sid, 'method': method, 'title': 'Design',
            'request': 'Design only', 'known_facts': [{'id': 'F1', 'text': 'The exact value is one.'}],
            'scope': 'Draft', 'checks': [{'id': 'Q1', 'question': 'What is the value?', 'value_type': 'INTEGER'}]}
        scenarios.append({'id': sid, 'method': method, 'visible_input': save(sid+'.json', canonical(visible)), 'oracle_commitment_sha256': '3'*64})
        schedule.append({'attempt_id': 'T'+str(n), 'scenario_id': sid, 'order': ['A', 'B'] if n != 1 else ['B', 'A']})
    manifest = {'schema_version': 1, 'run_id': 'R1', 'profile': pe.PROFILE, 'created_at_utc': '2026-10-15T00:00:00Z',
        'participants': participants, 'scenarios': scenarios, 'schedule': schedule,
        'prompt_template': save('template.txt', pe.PROMPT_TEMPLATE_V1), 'response_schema': save('response.json', pe.NEUTRAL_RESPONSE_SCHEMA_V1),
        'evaluator_commitment_sha256': digest(canonical(exclusion)),
        'runtime': {'codex': {'executable_path': str(Path(sys.executable).resolve()), 'executable_sha256': file_digest(Path(sys.executable).resolve()), 'version': 'synthetic-native-test'},
            'model': {'alias': 'test-model', 'reasoning_effort': 'medium',
                'provider_revision': {'state': 'NOT_AVAILABLE', 'value': None, 'evidence_sha256': None},
                'system_baseline': {'state': 'UNVERIFIED', 'value': None, 'evidence_sha256': None},
                'temperature_state': 'NOT_AVAILABLE', 'seed_state': 'NOT_AVAILABLE'},
            'policy': {'sandbox': 'read-only', 'add_dirs': [], 'ignore_user_config': True, 'ephemeral': True,
                'skip_host_skill_discovery': True, 'requested_tool_policy': 'NO_TOOL_USE', 'disabled_features': pe.DISABLED_FEATURES,
                'isolation_level': pe.ISOLATION}, 'host': {'os': platform.system(), 'architecture': platform.machine()},
            'timeout_seconds': 1, 'retry_count': 0}}
    path = inputs/'manifest.json'; path.write_bytes(canonical(manifest))
    return path, excluded, manifest


def response(prompt):
    start = prompt.index(b'\nVISIBLE_INPUT\n') + len(b'\nVISIBLE_INPUT\n')
    visible = json.loads(prompt[start:prompt.index(b'\nRESPONSE_CONTRACT\n')])
    return {'schema_version': 1, 'scenario_id': visible['scenario_id'], 'response_status': 'COMPLETED', 'summary': 'Draft design',
        'cases': [], 'gaps': [], 'observations': [{'check_id': 'Q1', 'value_type': 'INTEGER', 'value': 1, 'evidence_refs': ['F1']}],
        'metadata': {'artifact_state': 'DRAFT', 'execution_state': 'NOT_EXECUTED'}, 'failure_reason': None}


def trace_for(envelope):
    return b'\n'.join(canonical(row) for row in [
        {'type': 'thread.started', 'thread_id': 'test'},
        {'type': 'item.completed', 'item': {'id': 'warning', 'type': 'error', 'message': 'Code Mode is unavailable because code-mode host is disabled'}},
        {'type': 'turn.started'},
        {'type': 'item.completed', 'item': {'id': 'message', 'type': 'agent_message', 'text': canonical(envelope).decode()}},
        {'type': 'turn.completed', 'usage': dict.fromkeys(('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens'), 0)}]) + b'\n'


def capture(**kwargs):
    envelope = response(kwargs['prompt'])
    return {'process_outcome': 'EXITED_ZERO', 'termination_outcome': 'NOT_REQUESTED', 'termination': None,
        'exit_code': 0, 'pid': 123, 'stdout': trace_for(envelope), 'stderr': b'', 'final': canonical(envelope),
        'integrity_failure': False, 'cleanup_outcome': 'DELETED', 'environment': {'policy_id': 'TEST_DOUBLE'},
        'duration_ms': 1, 'command': ['TEST_DOUBLE'], 'stdin_outcome': 'SENT_COMPLETE',
        'stdin_bytes_sent': len(kwargs['prompt']), 'stream_observations': {}}


class PairedEvaluationDeveloperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path, self.excluded, self.manifest = fixture(self.root)
        self.output = self.root/'output'

    def write_manifest(self):
        self.path.write_bytes(canonical(self.manifest))

    def run_fake(self, launcher=capture):
        return pe._run_pair_with_ports(self.path, self.excluded, self.output, launcher=launcher)

    def test_validate_preview_zero_process(self):
        with patch('subprocess.Popen', side_effect=AssertionError('spawn')):
            self.assertEqual(pe.validate_run_manifest(self.path.read_bytes(), manifest_dir=self.path.parent)['status'], 'VALIDATED_NOT_EXECUTED')
            self.assertEqual(pe.materialize_preview(self.path, self.excluded, self.root/'preview')['call_count'], 6)
            self.assertEqual(pe.inspect_run(self.root/'preview')['status'], 'INTACT')

    def test_six_calls_order_projection_and_test_provenance(self):
        calls = []
        def launch(**kwargs):
            calls.append(kwargs); return capture(**kwargs)
        result = self.run_fake(launch)
        self.assertEqual([r['arm_id'] for r in result['attempts']], ['A', 'B', 'B', 'A', 'A', 'B'])
        self.assertEqual(len(calls), 6)
        self.assertEqual(result['execution_backend'], 'TEST_DOUBLE')
        self.assertEqual(result['evidence_class'], 'TEST_DOUBLE')
        self.assertEqual(result['pilot_status'], 'NOT_EXECUTED')
        self.assertTrue(all(r['terminal_status'] == 'COMPLETED_PROCESS' for r in result['attempts']))
        self.assertIn(b'literal {{VISIBLE_INPUT}}', calls[0]['prompt'])
        self.assertEqual(result['attempts'][0]['common_request_sha256'], result['attempts'][1]['common_request_sha256'])
        self.assertNotEqual(result['attempts'][0]['stdin_sha256'], result['attempts'][1]['stdin_sha256'])
        self.assertEqual(pe.inspect_run(self.output/'R1')['status'], 'INTACT')

    def test_reject_malformed_duplicate_float_unknown(self):
        for raw in (b'{"a":1,"a":2}', b'{"x":0.5}', b'{"x":NaN}', b'\xef\xbb\xbf{}'):
            with self.subTest(raw=raw), self.assertRaises(PairedEvaluationError):
                pe.load_run_manifest(raw, manifest_dir=self.path.parent)
        self.manifest['extra'] = 1; self.write_manifest()
        with self.assertRaisesRegex(PairedEvaluationError, 'INVALID_MEMBERS'):
            self.run_fake()

    def test_asset_drift_prevents_launch(self):
        (self.path.parent/'A.md').write_bytes(b'drift')
        with self.assertRaisesRegex(PairedEvaluationError, 'SOURCE_INTEGRITY_FAILURE'):
            self.run_fake(lambda **kw: self.fail('spawn'))

    def test_existing_run_never_overwritten(self):
        self.run_fake()
        before = (self.output/'R1/result.json').read_bytes()
        with self.assertRaisesRegex(PairedEvaluationError, 'RUN_ID_EXISTS'):
            self.run_fake()
        self.assertEqual(before, (self.output/'R1/result.json').read_bytes())

    def test_strict_and_untrusted_attestation_denied(self):
        self.manifest['profile'] = 'STRICT_COMPARISON_CANDIDATE'; self.write_manifest()
        with self.assertRaisesRegex(PairedEvaluationError, 'STRICT_PROFILE_NOT_SUPPORTED'):
            self.run_fake()
        self.manifest['profile'] = pe.PROFILE
        self.manifest['runtime']['model']['provider_revision']['state'] = 'VERIFIED'; self.write_manifest()
        with self.assertRaisesRegex(PairedEvaluationError, 'ATTESTATION_NOT_SUPPORTED'):
            self.run_fake()

    def test_custom_neutral_contract_rejected(self):
        path = self.path.parent/'response.json'; raw = b'{"winner":true}'
        path.write_bytes(raw)
        self.manifest['response_schema'].update(byte_count=len(raw), sha256=digest(raw)); self.write_manifest()
        with self.assertRaisesRegex(PairedEvaluationError, 'COMMON_CONTRACT_MISMATCH'):
            self.run_fake()

    def test_leakage_marker_rejected_before_any_call(self):
        raw = b'EVALUATOR_ONLY_SENTINEL_001'; (self.path.parent/'A.md').write_bytes(raw)
        self.manifest['participants'][0]['assets'][0].update(byte_count=len(raw), sha256=digest(raw)); self.write_manifest()
        with self.assertRaisesRegex(PairedEvaluationError, 'EVALUATOR_LEAKAGE'):
            self.run_fake()

    def test_missing_final_preserves_exit_zero_and_continues(self):
        def launch(**kwargs):
            result = capture(**kwargs); result['final'] = None; return result
        result = self.run_fake(launch)
        self.assertEqual(len(result['attempts']), 6)
        for row in result['attempts']:
            self.assertEqual(row['process_outcome'], 'EXITED_ZERO')
            self.assertEqual(row['output_outcome'], 'NOT_AVAILABLE')
            self.assertEqual(row['terminal_status'], 'OUTPUT_INVALID')

    def test_nonzero_valid_output_is_unattributed(self):
        def launch(**kwargs):
            result = capture(**kwargs); result.update(process_outcome='EXITED_NONZERO', exit_code=7); return result
        result = self.run_fake(launch)
        self.assertTrue(all(row['terminal_status'] == 'RUN_FAILURE_UNATTRIBUTED' for row in result['attempts']))

    def test_timeout_and_unconfirmed_termination_stop(self):
        def launch(**kwargs):
            result = capture(**kwargs); result.update(process_outcome='TIMED_OUT', termination_outcome='TERMINATION_UNCONFIRMED'); return result
        result = self.run_fake(launch)
        self.assertEqual(result['attempts'][0]['terminal_status'], 'TIMED_OUT')
        self.assertTrue(all(row['terminal_status'] == 'NOT_EXECUTED' for row in result['attempts'][1:]))

    def test_policy_violation_stops_and_keeps_process_outcome(self):
        def launch(**kwargs):
            result = capture(**kwargs)
            result['stdout'] += canonical({'type': 'item.started', 'item': {'id': 'tool', 'type': 'command_execution', 'command': 'noop'}})+b'\n'
            return result
        result = self.run_fake(launch)
        first = result['attempts'][0]
        self.assertEqual(first['process_outcome'], 'EXITED_ZERO')
        self.assertEqual(first['terminal_status'], 'POLICY_VIOLATION')
        self.assertTrue(all(row['terminal_status'] == 'NOT_EXECUTED' for row in result['attempts'][1:]))

    def test_sensitive_capture_is_withheld_and_stops(self):
        def launch(**kwargs):
            result = capture(**kwargs); result['stderr'] = b'Authorization: Bearer synthetic-secret-marker'; return result
        result = self.run_fake(launch)
        row = result['attempts'][0]
        self.assertEqual(row['output_outcome'], 'INTEGRITY_FAILURE')
        entry = next(item for item in row['ledger'] if item['role'] == 'stderr')
        self.assertEqual(entry['capture_state'], 'REDACTED')
        self.assertNotIn(b'synthetic-secret-marker', (self.output/'R1'/entry['relative_path']).read_bytes())

    def test_typed_grade_and_integrity(self):
        result = self.run_fake()
        bundle = {'schema_version': 1, 'run_manifest_sha256': result['run_manifest_sha256'], 'response_schema_sha256': result['response_schema_sha256'],
            'assertions': [{'id': 'AS1', 'scenario_id': 'S0', 'check_id': 'Q1', 'expected': {'value_type': 'INTEGER', 'value': 1},
                           'required_evidence_refs': ['F1'], 'oracle_ref': 'oracle/example'}]}
        source = self.root/'assertions.json'; source.write_bytes(canonical(bundle))
        with patch('subprocess.Popen', side_effect=AssertionError('spawn')):
            report = pe.grade_run(self.output/'R1', source, self.root/'grade.json')
        self.assertEqual([row['status'] for row in report['assertions']], ['SATISFIED', 'SATISFIED'])
        bundle['assertions'][0]['expected'] = {'value_type': 'BOOLEAN', 'value': True}
        source.write_bytes(canonical(bundle))
        report = pe.grade_run(self.output/'R1', source, self.root/'grade2.json')
        self.assertEqual([row['status'] for row in report['assertions']], ['VIOLATED', 'VIOLATED'])
        (self.output/'R1/calls/T0-A/assets/SKILL.md').write_bytes(b'tampered')
        self.assertEqual(pe.inspect_run(self.output/'R1')['status'], 'INTEGRITY_FAILURE')
        with self.assertRaisesRegex(PairedEvaluationError, 'RUN_INTEGRITY_FAILURE'):
            pe.grade_run(self.output/'R1', source, self.root/'grade3.json')

    def test_process_environment_drops_provider_keys(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'synthetic', 'HTTP_PROXY': 'synthetic', 'HOME': '/tmp/test'}):
            env, record = environment()
        self.assertNotIn('OPENAI_API_KEY', env)
        self.assertNotIn('HTTP_PROXY', env)
        self.assertNotIn('synthetic', json.dumps(record))

    def test_trace_warning_success_and_malformed(self):
        raw = trace_for(response(pe._prompt(b'context', (self.path.parent/'S0.json').read_bytes())))
        self.assertTrue(parse_trace(raw)['valid'])
        self.assertFalse(parse_trace(raw+b'{}\n')['valid'])

    def test_path_traversal_rejected(self):
        self.manifest['participants'][0]['assets'][0]['source_path'] = '../excluded.json'; self.write_manifest()
        with self.assertRaisesRegex(PairedEvaluationError, 'INVALID_PATH'):
            self.run_fake()

    def test_bool_not_integer_observation(self):
        def launch(**kwargs):
            result = capture(**kwargs)
            value = json.loads(result['final']); value['observations'][0]['value'] = True
            result['final'] = canonical(value); result['stdout'] = trace_for(value); return result
        result = self.run_fake(launch)
        self.assertTrue(all(row['terminal_status'] == 'OUTPUT_INVALID' for row in result['attempts']))

    def test_json_claim_fields_rejected_recursively(self):
        visible = json.loads((self.path.parent/'S0.json').read_bytes())
        visible['checks'][0]['value_type'] = 'JSON'
        envelope = response(pe._prompt(b'context', canonical(visible)))
        envelope['observations'][0].update(value_type='JSON', value={'nested': {'winner': 'A'}})
        with self.assertRaisesRegex(PairedEvaluationError, 'PROHIBITED_FIELD'):
            pe.parse_envelope(canonical(envelope), visible, ['SKILL.md'])

    def test_escaped_and_malformed_secret_artifacts_withheld(self):
        for raw in (b'{"to\\u006ben":"synthetic-secret"}', b'{"to\\u006ben":"synthetic-secret"',
                    b'junk {"to\\u006ben":"synthetic-secret"} junk',
                    b'{"summary":"https:\\/\\/user:pass@example.invalid"}',
                    b'{"summary":"https:\\/\\/user:pass@example.invalid'):
            with self.subTest(raw=raw):
                safe, transformation = redact(raw)
                self.assertEqual(transformation['state'], 'REDACTED')
                self.assertNotIn(b'synthetic-secret', safe)

    def test_incomplete_stdin_stops_schedule(self):
        def launch(**kwargs):
            value = capture(**kwargs); value['stdin_bytes_sent'] = 0; value['stdin_outcome'] = 'WRITE_FAILED'; return value
        result = self.run_fake(launch)
        self.assertEqual(result['attempts'][0]['terminal_status'], 'INFRASTRUCTURE_FAILURE')
        self.assertEqual(result['attempts'][1]['terminal_status'], 'NOT_EXECUTED')

    def test_corrupt_result_schema_stable_error(self):
        self.run_fake()
        path = self.output/'R1/result.json'; value = json.loads(path.read_bytes()); del value['ledger']; path.write_bytes(canonical(value))
        with self.assertRaisesRegex(PairedEvaluationError, '^RUN_INTEGRITY_FAILURE$'):
            pe.inspect_run(self.output/'R1')

    def test_nested_ledger_tampering_rejected(self):
        self.run_fake()
        path = self.output/'R1/result.json'; value = json.loads(path.read_bytes())
        value['attempts'][0]['ledger'][0]['relative_path'] = value['attempts'][1]['ledger'][0]['relative_path']; path.write_bytes(canonical(value))
        with self.assertRaisesRegex(PairedEvaluationError, '^RUN_INTEGRITY_FAILURE$'):
            pe.inspect_run(self.output/'R1')

    def test_coherently_hashed_but_contradictory_outcome_rejected(self):
        self.run_fake()
        root = self.output/'R1'; value = json.loads((root/'result.json').read_bytes())
        value['attempts'][0]['terminal_status'] = 'RUN_FAILURE_UNATTRIBUTED'
        raw = canonical(value['attempts'][0])+b'\n'; locator = 'attempts/T0-A/record.json'
        (root/locator).write_bytes(raw)
        for entry in value['ledger']:
            if entry['relative_path'] == locator:
                entry.update(byte_count=len(raw), sha256=digest(raw))
        (root/'result.json').write_bytes(canonical(value))
        with self.assertRaisesRegex(PairedEvaluationError, '^RUN_INTEGRITY_FAILURE$'):
            pe.inspect_run(root)

    def test_redaction_and_stop_chain_cannot_be_relabelled(self):
        def launch(**kwargs):
            value = capture(**kwargs); value['stderr'] = b'Authorization: Bearer synthetic-test-secret'; return value
        self.run_fake(launch)
        root = self.output/'R1'
        self.assertEqual(pe.inspect_run(root)['status'], 'INTACT')
        value = json.loads((root/'result.json').read_bytes())
        value['attempts'][0].update(output_outcome='OUTPUT_INVALID', terminal_status='OUTPUT_INVALID')
        raw = canonical(value['attempts'][0])+b'\n'; locator = 'attempts/T0-A/record.json'; (root/locator).write_bytes(raw)
        for entry in value['ledger']:
            if entry['relative_path'] == locator:
                entry.update(byte_count=len(raw), sha256=digest(raw))
        (root/'result.json').write_bytes(canonical(value))
        with self.assertRaisesRegex(PairedEvaluationError, '^RUN_INTEGRITY_FAILURE$'):
            pe.inspect_run(root)

    def test_unknown_assertion_binding_rejected(self):
        result = self.run_fake()
        value = {'schema_version': 1, 'run_manifest_sha256': result['run_manifest_sha256'], 'response_schema_sha256': result['response_schema_sha256'],
                 'assertions': [{'id': 'AS1', 'scenario_id': 'UNKNOWN', 'check_id': 'Q1', 'expected': {'value_type': 'INTEGER', 'value': 1},
                                 'required_evidence_refs': ['F1'], 'oracle_ref': 'oracle/example'}]}
        source = self.root/'assertions.json'; source.write_bytes(canonical(value))
        with self.assertRaisesRegex(PairedEvaluationError, 'UNKNOWN_ASSERTION_BINDING'):
            pe.grade_run(self.output/'R1', source, self.root/'grade.json')

    def test_documented_capacity_32_and_33(self):
        base = json.loads((self.path.parent/'S0.json').read_bytes())
        for n in range(3, 33):
            sid = 'S'+str(n); value = copy.deepcopy(base); value['scenario_id'] = sid
            raw = canonical(value); (self.path.parent/(sid+'.json')).write_bytes(raw)
            self.manifest['scenarios'].append({'id': sid, 'method': 'boundary', 'oracle_commitment_sha256': '3'*64,
                'visible_input': {'source_path': sid+'.json', 'byte_count': len(raw), 'sha256': digest(raw)}})
            self.manifest['schedule'].append({'attempt_id': 'T'+str(n), 'scenario_id': sid, 'order': ['A', 'B']})
            if n == 31:
                self.write_manifest()
                self.assertEqual(len(pe.load_run_manifest(self.path.read_bytes(), manifest_dir=self.path.parent)['scenarios']), 32)
                pe.materialize_preview(self.path, self.excluded, self.root/'max-preview')
                self.assertEqual(pe.inspect_run(self.root/'max-preview')['status'], 'INTACT')
                for participant in self.manifest['participants']:
                    original = participant['assets'][0]
                    participant['assets'] = [original] + [dict(original, path=('asset'+str(i).zfill(2)+'x'*120+'.md')) for i in range(63)]
                    participant['assets'].sort(key=lambda row: row['path'])
                self.write_manifest()
                with self.assertRaisesRegex(PairedEvaluationError, 'CONTROL_RECORD_CAPACITY_LIMIT'):
                    pe.materialize_preview(self.path, self.excluded, self.root/'joint-over-preview')
                self.assertFalse((self.root/'joint-over-preview').exists())
        self.write_manifest()
        with self.assertRaisesRegex(PairedEvaluationError, 'INVALID_ARRAY'):
            pe.materialize_preview(self.path, self.excluded, self.root/'over-preview')
        self.assertFalse((self.root/'over-preview').exists())

    def test_manifest_sensitive_string_rejects_before_reservation(self):
        self.manifest['runtime']['codex']['version'] = 'Bearer ABCDEFGHIJKL'; self.write_manifest()
        with self.assertRaisesRegex(PairedEvaluationError, 'PROHIBITED_INPUT_PATTERN'):
            pe.materialize_preview(self.path, self.excluded, self.root/'bad-preview')
        self.assertFalse((self.root/'bad-preview').exists())

    def native_local(self, body, timeout=2):
        # Exercise real pipes/threads/timeout/cleanup with a local Python child.
        # Intercept argv only; no Codex/model invocation or comparison occurs.
        original = subprocess.Popen
        commands = []
        def local(command, **kwargs):
            if '--output-last-message' not in command:
                return original(command, **kwargs)  # real OS tree-termination helper
            commands.append((command, kwargs))
            output = command[command.index('--output-last-message')+1]
            code = 'from pathlib import Path\nimport sys,time\np=Path(sys.argv[1])\n' + body
            return original([sys.executable, '-c', code, output], **kwargs)
        with patch('qa_master._paired_process.subprocess.Popen', side_effect=local):
            result = native_capture(executable=sys.executable, model={'alias': 'test', 'reasoning_effort': 'medium'},
                                    features=pe.DISABLED_FEATURES, prompt=b'hello', timeout_seconds=timeout)
        self.assertFalse(commands[0][1]['shell'])
        self.assertNotIn('--add-dir', commands[0][0])
        self.assertNotIn('--output-schema', commands[0][0])
        self.assertEqual(result['cleanup_outcome'], 'DELETED')
        return result

    def test_real_local_capture_pipes_and_cleanup(self):
        result = self.native_local("assert sys.stdin.buffer.read()==b'hello'\np.write_bytes(b'final')\nprint('trace')\nprint('diagnostic',file=sys.stderr)\n")
        self.assertEqual(result['process_outcome'], 'EXITED_ZERO')
        self.assertEqual(result['final'], b'final')
        self.assertEqual(result['stdout'].strip(), b'trace')
        self.assertFalse(result['integrity_failure'])

    def test_real_local_stream_overflow_terminates(self):
        result = self.native_local("sys.stdout.buffer.write(b'x'*(3*1024*1024))\nsys.stdout.flush()\ntime.sleep(20)\n")
        self.assertTrue(result['integrity_failure'])
        self.assertIsNone(result['stdout'])
        self.assertTrue(result['stream_observations']['stdout']['overflow'])
        self.assertEqual(result['termination_outcome'], 'TERMINATION_OBSERVED')

    def test_real_local_timeout_distinct_from_termination(self):
        result = self.native_local('time.sleep(20)\n', timeout=1)
        self.assertEqual(result['process_outcome'], 'TIMED_OUT')
        self.assertEqual(result['termination_outcome'], 'TERMINATION_OBSERVED')

    def test_real_local_final_file_limit(self):
        result = self.native_local("p.write_bytes(b'x'*(pe_size:=3*1024*1024))\ntime.sleep(20)\n")
        self.assertTrue(result['integrity_failure'])
        self.assertIsNone(result['final'])


if __name__ == '__main__':
    unittest.main()
