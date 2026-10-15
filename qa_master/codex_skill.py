"""Install a self-contained Codex skill; no model or business-system calls."""
from __future__ import annotations

import hashlib
import json
import os
from importlib import resources
from pathlib import Path
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED
from uuid import uuid4

MANIFEST = '.qa-master-install.json'


class SkillInstallError(ValueError):
    pass


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _files(root, prefix=''):
    for item in sorted(root.iterdir(), key=lambda value: value.name):
        name = prefix + item.name
        if item.is_dir():
            yield from _files(item, name + '/')
        elif item.is_file() and item.name.endswith(('.md', '.py', '.json')):
            yield name, item.read_bytes()


def skill_bundle():
    """Use package resources, including when installed from a fresh wheel."""
    package = resources.files('qa_master')
    result = dict(_files(package.joinpath('skills', 'codex')))
    if 'SKILL.md' not in result:
        raise SkillInstallError('SKILL_RESOURCE_MISSING')
    for item in package.iterdir():
        if item.is_file() and item.name.endswith('.py'):
            result['scripts/qa_master/' + item.name] = item.read_bytes()
    for name, data in _files(package.joinpath('skills', 'professional')):
        result['scripts/qa_master/skills/professional/' + name] = data
    result['scripts/qa.py'] = (
        'from pathlib import Path\n'
        'import sys\n'
        'sys.path.insert(0, str(Path(__file__).resolve().parent))\n'
        'from qa_master.__main__ import main\n'
        'if __name__ == "__main__":\n'
        '    raise SystemExit(main())\n'
    ).encode('utf-8')
    return result


def default_target(*, user=False, project=None):
    base = Path.home() if user else Path(project or Path.cwd())
    return base / '.agents' / 'skills' / 'qa-master'


def _existing(target):
    if target.is_symlink() or not target.is_dir():
        raise SkillInstallError('SKILL_TARGET_CONFLICT')
    try:
        manifest_path = target / MANIFEST
        if manifest_path.is_symlink():
            raise ValueError()
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if (not isinstance(manifest, dict) or set(manifest) != {'schema_version', 'files'}
                or type(manifest['schema_version']) is not int or manifest['schema_version'] != 1
                or not isinstance(manifest['files'], dict) or not manifest['files']):
            raise ValueError()
        found = {}
        for item in target.rglob('*'):
            if item.is_symlink():
                raise ValueError()
            if item.is_file():
                name = item.relative_to(target).as_posix()
                if '__pycache__' in item.relative_to(target).parts:
                    continue
                if name != MANIFEST:
                    found[name] = _digest(item.read_bytes())
        if found != manifest['files']:
            raise ValueError()
    except (OSError, ValueError, TypeError, KeyError):
        raise SkillInstallError('SKILL_TARGET_MODIFIED') from None
    return found


def install_skill(target=None, *, user=False, project=None, update=False):
    target = Path(target) if target is not None else default_target(user=user, project=project)
    if target.is_symlink():
        raise SkillInstallError('SKILL_TARGET_CONFLICT')
    target = target.absolute()
    bundle = skill_bundle()
    hashes = {name: _digest(data) for name, data in sorted(bundle.items())}
    previous = None
    if target.exists():
        previous = _existing(target)
        if previous == hashes:
            return {'status': 'UNCHANGED', 'target': str(target), 'files': len(hashes)}
        if not update:
            raise SkillInstallError('SKILL_UPDATE_REQUIRED')
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with tempfile.TemporaryDirectory(prefix='.qa-master-stage-', dir=target.parent) as temporary:
        staged = Path(temporary) / 'qa-master'
        staged.mkdir()
        for name, data in bundle.items():
            output = staged / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        (staged / MANIFEST).write_text(json.dumps({'schema_version': 1, 'files': hashes},
                                                 sort_keys=True, indent=2) + '\n', encoding='utf-8')
        if target.exists():
            if _existing(target) != previous:
                raise SkillInstallError('SKILL_TARGET_MODIFIED')
            backup = target.with_name('qa-master.backup-' + uuid4().hex + '.zip')
            with ZipFile(backup, 'x', compression=ZIP_DEFLATED) as archive:
                for name in sorted(previous):
                    archive.writestr(name, (target / name).read_bytes())
                archive.writestr(MANIFEST, (target / MANIFEST).read_bytes())
            os.rename(target, Path(temporary) / 'previous')
        try:
            os.rename(staged, target)
        except OSError:
            if backup is not None and not target.exists():
                os.rename(Path(temporary) / 'previous', target)
            raise
    return {'status': 'UPDATED' if backup else 'INSTALLED', 'target': str(target),
            'files': len(hashes), 'backup': str(backup) if backup else None,
            'execution': 'NOT_EXECUTED'}
