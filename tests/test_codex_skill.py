import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from qa_master.codex_skill import default_target, install_skill, skill_bundle, SkillInstallError, MANIFEST


class CodexSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'project with spaces' / '.agents' / 'skills' / 'qa-master'

    def run_helper(self, *args):
        working = self.root / 'other-project'
        working.mkdir(exist_ok=True)
        return subprocess.run([sys.executable, '-I', str(self.target / 'scripts' / 'qa.py'), *args],
                              cwd=working, capture_output=True, text=True, timeout=15)

    def test_complete_install_runs_outside_checkout(self):
        install_skill(self.target)
        result = self.run_helper('skills')
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(len(value['guides']), 6)
        self.assertEqual(value['gaps'], [])
        for guide in value['guides']:
            # Windows TEMP may use an 8.3 alias; the helper resolves __file__.
            # Compare existing canonical paths, retaining the containment check.
            guide_path = Path(guide['path']).resolve(strict=True)
            self.assertTrue(guide_path.is_relative_to(self.target.resolve(strict=True)))

    def test_installed_cli_preserves_no_execution_and_pause(self):
        install_skill(self.target)
        for args in [('init', 'sample'), ('plan', '只评审需求并生成测试用例，不执行测试'),
                     ('pause', '等待内部发布')]:
            result = self.run_helper(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
        status = json.loads(self.run_helper('status').stdout)
        self.assertEqual(status['mode'], 'PAUSED')
        self.assertFalse(status['execution_authorized'])
        self.assertTrue(status['task_contract']['no_execution'])
        check = json.loads(self.run_helper('check', 'execution').stdout)
        self.assertIn(check['state'], ('PAUSED', 'DENIED_BY_TASK_SCOPE'))

    def test_idempotent_after_real_helper_execution(self):
        install_skill(self.target)
        self.run_helper('skills')
        before = (self.target / MANIFEST).stat().st_mtime_ns
        self.assertEqual(install_skill(self.target)['status'], 'UNCHANGED')
        self.assertEqual((self.target / MANIFEST).stat().st_mtime_ns, before)

    def test_unmanaged_target_preserved(self):
        self.target.mkdir(parents=True)
        marker = self.target / 'SKILL.md'
        marker.write_text('user-owned', encoding='utf-8')
        with self.assertRaises(SkillInstallError):
            install_skill(self.target, update=True)
        self.assertEqual(marker.read_text(encoding='utf-8'), 'user-owned')

    def test_local_changes_block_even_explicit_update(self):
        install_skill(self.target)
        marker = self.target / 'references' / 'domains.md'
        marker.write_text('local customization', encoding='utf-8')
        with self.assertRaisesRegex(SkillInstallError, 'SKILL_TARGET_MODIFIED'):
            install_skill(self.target, update=True)
        self.assertEqual(marker.read_text(encoding='utf-8'), 'local customization')

    def test_managed_upgrade_keeps_restorable_archive(self):
        install_skill(self.target)
        previous = (self.target / 'SKILL.md').read_bytes()
        bundle = skill_bundle()
        bundle['SKILL.md'] += b'\nUpdated guidance.\n'
        with patch('qa_master.codex_skill.skill_bundle', return_value=bundle):
            with self.assertRaisesRegex(SkillInstallError, 'SKILL_UPDATE_REQUIRED'):
                install_skill(self.target)
            result = install_skill(self.target, update=True)
        self.assertEqual(result['status'], 'UPDATED')
        with ZipFile(result['backup']) as archive:
            self.assertEqual(archive.read('SKILL.md'), previous)
        self.assertEqual((self.target / 'SKILL.md').read_bytes(), bundle['SKILL.md'])

    def test_upgrade_rename_failure_restores_original(self):
        install_skill(self.target)
        previous = (self.target / MANIFEST).read_bytes()
        bundle = skill_bundle()
        bundle['SKILL.md'] += b'\nUpdate.\n'
        import os
        rename = os.rename
        def fail_publication(source, destination):
            if Path(source).name == 'qa-master' and Path(source).parent.name.startswith('.qa-master-stage-'):
                raise OSError('synthetic publication failure')
            return rename(source, destination)
        with patch('qa_master.codex_skill.skill_bundle', return_value=bundle), \
                patch('qa_master.codex_skill.os.rename', side_effect=fail_publication):
            with self.assertRaises(OSError):
                install_skill(self.target, update=True)
        self.assertEqual((self.target / MANIFEST).read_bytes(), previous)
        self.assertEqual(install_skill(self.target)['status'], 'UNCHANGED')

    def test_manifest_hashes_match_installed_bytes(self):
        install_skill(self.target)
        manifest = json.loads((self.target / MANIFEST).read_text(encoding='utf-8'))
        for name, expected in manifest['files'].items():
            self.assertEqual(hashlib.sha256((self.target / name).read_bytes()).hexdigest(), expected)

    def test_project_and_user_discovery_locations(self):
        self.assertEqual(default_target(project=self.root), self.root / '.agents' / 'skills' / 'qa-master')
        self.assertEqual(default_target(user=True), Path.home() / '.agents' / 'skills' / 'qa-master')


if __name__ == '__main__':
    unittest.main()
