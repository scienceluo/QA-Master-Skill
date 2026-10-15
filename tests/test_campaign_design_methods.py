"""TASK-035 campaign integration; exact method algorithms have separate tests."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from qa_master.campaign_cli import prepare_campaign, write_campaign


EXAMPLE = Path(__file__).resolve().parents[1] / 'examples' / 'design-methods.json'


class CampaignDesignMethodsTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads(EXAMPLE.read_text(encoding='utf-8'))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def invoke(self, raw, *, output_exists=True):
        source = self.root / 'input.json'
        output = self.root / 'report.json'
        source.write_bytes(raw)
        if output_exists:
            output.write_bytes(b'prior-report')
        run = subprocess.run([sys.executable, '-m', 'qa_master.campaign_cli',
                              '--input', str(source), '--output', str(output)],
                             capture_output=True, timeout=20)
        return run, output

    def test_legacy_is_unchanged_and_does_not_call_engine(self):
        del self.bundle['design_models']
        with patch('qa_master.campaign_cli.design_methods', side_effect=AssertionError('must not call')):
            result = prepare_campaign(self.bundle)
        self.assertNotIn('method_design', result)
        self.assertEqual(len(result['test_cases']), 1)
        self.assertEqual(result['test_cases'][0]['id'], 'TC-REQ-EXAMPLE-FUNCTIONAL-001')
        self.assertEqual(result['workflow']['execution'], 'NOT_AUTHORIZED')

    def test_three_methods_are_separate_drafts_with_complete_links(self):
        result = prepare_campaign(self.bundle)
        baseline = deepcopy(self.bundle)
        del baseline['design_models']
        expected = prepare_campaign(baseline)
        for key in expected.keys() - {'input_sha256'}:
            self.assertEqual(expected[key], result[key], key)
        design = result['method_design']
        self.assertEqual({r['method'] for r in design['model_results']},
                         {'boundary', 'decision_table', 'state_transition'})
        self.assertEqual(design['execution'], 'NOT_EXECUTED')
        for case in design['candidates']:
            self.assertEqual(case['trace'], ['REQ-EXAMPLE'])
            self.assertEqual(case['approval'], 'DRAFT')
            self.assertEqual(case['validation_action'], 'NOT_EXECUTED')
            self.assertTrue(case['source_refs'])
            self.assertTrue(case['oracle_refs'])
        self.assertGreater(design['summary']['candidate_count'], 3)
        self.assertFalse(result['formal_baseline_approved'])

    def test_empty_models_have_explicit_empty_projection(self):
        self.bundle['design_models']['models'] = []
        result = prepare_campaign(self.bundle)['method_design']
        self.assertEqual(result['candidates'], [])
        self.assertEqual(result['obligations'], [])
        self.assertEqual(result['summary']['model_count'], 0)

    def test_instantiated_cli_summary_has_no_source_locators(self):
        run, output = self.invoke(json.dumps(self.bundle).encode(), output_exists=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        summary = json.loads(run.stdout)
        result = json.loads(output.read_bytes())
        self.assertEqual(summary['method_candidates'], len(result['method_design']['candidates']))
        self.assertEqual(summary['execution'], 'NOT_AUTHORIZED')
        for ref in self.bundle['design_models']['source_refs'] + self.bundle['design_models']['oracle_refs']:
            self.assertNotIn(ref['locator'].encode(), run.stdout)

    def test_invalid_model_does_not_replace_output_or_leak_value(self):
        self.bundle['design_models']['models'][0]['token'] = 'sensitive-fixture-marker'
        run, output = self.invoke(json.dumps(self.bundle).encode())
        self.assertEqual(run.returncode, 2)
        self.assertEqual(json.loads(run.stdout)['status'], 'REJECTED')
        self.assertEqual(output.read_bytes(), b'prior-report')
        self.assertNotIn(b'sensitive-fixture-marker', run.stdout + run.stderr)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['input.json', 'report.json'])

    def test_duplicate_keys_and_nonfinite_json_fail_before_output(self):
        for raw in (b'{"project":"a","project":"b","requirements":[]}',
                    b'{"project":"a","requirements":[],"unexpected":NaN}', b'\xff'):
            with self.subTest(raw=raw):
                run, output = self.invoke(raw)
                self.assertEqual(run.returncode, 2)
                self.assertEqual(output.read_bytes(), b'prior-report')
                self.assertNotIn(b'Traceback', run.stderr)

    def test_model_float_rejected_but_legacy_float_preserved(self):
        self.bundle['design_models']['models'][0]['spec']['step'] = 0.01
        run, output = self.invoke(json.dumps(self.bundle).encode())
        self.assertEqual(run.returncode, 2)
        self.assertEqual(output.read_bytes(), b'prior-report')
        del self.bundle['design_models']
        self.bundle['metadata'] = {'sample': 0.5}
        run, _ = self.invoke(json.dumps(self.bundle).encode())
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn('method_candidates', json.loads(run.stdout))

    def test_missing_oracle_yields_obligations_in_persisted_draft(self):
        model = self.bundle['design_models']['models'][0]
        model['spec']['oracle_by_class'] = {}
        self.bundle['design_models']['models'] = [model]
        run, output = self.invoke(json.dumps(self.bundle).encode())
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(output.read_bytes())['method_design']
        self.assertEqual(result['candidates'], [])
        self.assertTrue(result['obligations'])

    def test_failed_replace_retains_previous_report_and_cleans_temp(self):
        source = self.root / 'input.json'
        output = self.root / 'report.json'
        source.write_text(json.dumps(self.bundle), encoding='utf-8')
        output.write_bytes(b'prior-report')
        with patch('qa_master.campaign_cli.os.replace', side_effect=OSError('private-io-marker')):
            with self.assertRaises(OSError):
                write_campaign(source, output)
        self.assertEqual(output.read_bytes(), b'prior-report')
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['input.json', 'report.json'])

    def test_same_path_rejected_without_input_mutation(self):
        source = self.root / 'input.json'
        raw = json.dumps(self.bundle).encode()
        source.write_bytes(raw)
        with self.assertRaises(ValueError):
            write_campaign(source, source)
        self.assertEqual(source.read_bytes(), raw)

    def test_no_execution_or_network_port_called(self):
        with (patch('socket.create_connection', side_effect=AssertionError('network')),
              patch('subprocess.Popen', side_effect=AssertionError('process'))):
            result = prepare_campaign(self.bundle)
        self.assertEqual(result['workflow']['synapsert'], 'NOT_WRITTEN')
