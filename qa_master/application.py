"""Canonical local campaign service (DES-019 / TASK-020).

No execution or external-write port is installed. Legacy payloads are private
recovery data and must never be included in CLI projections.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from .approval import artifact_digest
from .intent import plan_task
from .skill_registry import select_skills
from .state_store import save_document
from .workflow import STEPS, Step, Workflow

SCHEMA = 'qa-master.campaign'
FIELDS = {'schema_name', 'schema_version', 'campaign_id', 'project', 'revision',
          'mode', 'pause', 'task_contract', 'answers', 'steps', 'approvals',
          'events', 'event_sequence', 'legacy_assertions', 'legacy_payload', 'migration', 'questions'}


def _contract():
    return {'schema_version': 1, 'stages': [], 'no_execution': False,
            'no_external_writes': False, 'capabilities': {'execute': False, 'external_write': False},
            'authority': 'PLANNING_ONLY'}


def _new(project, campaign_id=None):
    if not isinstance(project, str) or not project.strip():
        raise ValueError('Project required')
    return {'schema_name': SCHEMA, 'schema_version': 2,
            'campaign_id': campaign_id or str(uuid4()), 'project': project,
            'revision': 0, 'mode': 'ACTIVE', 'pause': None,
            'task_contract': _contract(), 'answers': {}, 'steps': {}, 'approvals': {},
            'events': [], 'event_sequence': 0, 'legacy_assertions': [], 'questions': [],
            'legacy_payload': None, 'migration': None}


def _revision(value):
    if type(value) is not int or value < 0:
        raise ValueError('Invalid state revision')
    return value


def _workflow(document):
    return Workflow(project=document['project'],
                    steps={key: Step(**value) for key, value in document['steps'].items()},
                    answers=deepcopy(document['answers']), approvals=deepcopy(document['approvals']),
                    events=deepcopy(document['events']), revision=document['revision'])


def _validate(document):
    if set(document) != FIELDS or document['schema_name'] != SCHEMA or type(document['schema_version']) is not int or document['schema_version'] != 2:
        raise ValueError('UNSUPPORTED_SCHEMA')
    _revision(document['revision'])
    _revision(document['event_sequence'])
    if not all(isinstance(document[key], str) and document[key].strip() for key in ('project', 'campaign_id')):
        raise ValueError('Invalid campaign identity')
    if document['mode'] not in ('ACTIVE', 'PAUSED'):
        raise ValueError('Invalid campaign mode')
    if document['mode'] == 'PAUSED':
        if not isinstance(document['pause'], dict) or not isinstance(document['pause'].get('reason'), str) or not document['pause']['reason'].strip():
            raise ValueError('Invalid pause record')
    elif document['pause'] is not None:
        raise ValueError('Invalid active pause record')
    for key in ('answers', 'steps', 'approvals', 'task_contract'):
        if not isinstance(document[key], dict):
            raise ValueError('Invalid state mapping')
    for key in ('events', 'legacy_assertions', 'questions'):
        if not isinstance(document[key], list):
            raise ValueError('Invalid state history')
    contract = document['task_contract']
    if (set(contract) != set(_contract())
            or type(contract.get('schema_version')) is not int or contract['schema_version'] != 1
            or contract.get('capabilities') != {'execute': False, 'external_write': False}
            or any(type(value) is not bool for value in contract['capabilities'].values())
            or contract.get('authority') != 'PLANNING_ONLY'
            or type(contract.get('no_execution')) is not bool
            or type(contract.get('no_external_writes')) is not bool
            or not isinstance(contract.get('stages'), list)
            or any(not isinstance(stage, str) or stage not in (*STEPS, 'discovery') for stage in contract['stages'])):
        raise ValueError('Unsupported task authority')
    if any(not isinstance(question, str) for question in document['questions']):
        raise ValueError('Invalid questions')
    for key, answer in document['answers'].items():
        if not isinstance(key, str) or not isinstance(answer, dict) or set(answer) != {'state', 'value'} or answer['state'] not in ('PROVIDED', 'CONFIRMED_NONE'):
            raise ValueError('Invalid answer')
        if answer['state'] == 'CONFIRMED_NONE' and answer['value'] is not None:
            raise ValueError('Invalid absent answer')
    for key, value in document['steps'].items():
        if key not in STEPS or not isinstance(value, dict):
            raise ValueError('Unknown workflow step')
        step = Step(**value)
        definition = STEPS[key]
        for attr in ('id', 'depends_on', 'required', 'approvals', 'side_effect'):
            if getattr(step, attr) != getattr(definition, attr):
                raise ValueError('Unsupported step definition')
        if step.status not in ('PENDING', 'DONE', 'NEEDS_REVALIDATION', 'STALE') or any(dep not in document['steps'] for dep in step.depends_on):
            raise ValueError('Invalid workflow dependency or status')
        if step.result_ref is not None and not isinstance(step.result_ref, str):
            raise ValueError('Invalid result reference')
        for attr in ('completion_binding', 'execution_receipt'):
            if getattr(step, attr) is not None and not isinstance(getattr(step, attr), dict):
                raise ValueError('Invalid completion metadata')
    if document['migration'] is not None and not isinstance(document['migration'], dict):
        raise ValueError('Invalid migration metadata')
    artifact_digest(document)  # Reject non-finite or non-JSON values.


def _event(document, action, **metadata):
    document['event_sequence'] = max([document['event_sequence']] + [
        event['sequence'] for event in document['events']
        if isinstance(event, dict) and type(event.get('sequence')) is int]) + 1
    document['events'].append({'sequence': document['event_sequence'], 'action': action, **metadata})


def _project_source(workflow):
    """Translate CLI input aliases without duplicating an authoritative answer store."""
    for key in ('requirements', 'gitlab', 'web_url'):
        answer = workflow.answers.get(key, {})
        if answer.get('state') == 'PROVIDED' and answer.get('value'):
            workflow.answer('source', answer['value'])
            return
    if any(key in workflow.answers for key in ('requirements', 'gitlab', 'web_url')):
        workflow.answer('source', None)


def _known(workflow):
    known = {key: answer['value'] for key, answer in workflow.answers.items()}
    if workflow.answers.get('requirements', {}).get('state') == 'CONFIRMED_NONE':
        known['requirements_status'] = 'CONFIRMED_NONE'
    return known


def migrate(raw, digest):
    """Pure, repeatable projection. Never authenticates historical assertions."""
    if not isinstance(raw, dict):
        raise ValueError('UNSUPPORTED_SCHEMA')
    _revision(raw.get('revision', 0))
    if 'schema_name' in raw or 'schema_version' in raw:
        raw = deepcopy(raw)
        # An optional projection added during the schema-v2 development cycle.
        # No legacy data is discarded and read-only loading still never saves.
        if raw.get('schema_name') == SCHEMA and raw.get('schema_version') == 2 and 'questions' not in raw:
            raw['questions'] = []
        _validate(raw)
        if raw['migration'] is not None:
            for step in raw['steps'].values():
                if step['status'] == 'DONE':
                    step['status'] = 'NEEDS_REVALIDATION'
        return deepcopy(raw), False
    campaign_markers = {'name', 'known', 'history'}
    workflow_markers = {'project', 'steps', 'answers', 'events'}
    if campaign_markers.intersection(raw) and workflow_markers.intersection(raw):
        raise ValueError('AMBIGUOUS_SCHEMA')
    if campaign_markers <= raw.keys():
        source_format = 'Campaign'
        if not isinstance(raw['known'], dict) or not isinstance(raw['history'], list):
            raise ValueError('UNSUPPORTED_SCHEMA')
        document = _new(raw['name'], str(uuid5(NAMESPACE_URL, SCHEMA + ':' + source_format + ':' + digest)))
        document['events'] = deepcopy(raw['history'])
        for key, value in raw['known'].items():
            if not isinstance(value, dict) or value.get('status') not in ('PROVIDED', 'CONFIRMED_NONE') or 'value' not in value:
                raise ValueError('Invalid legacy answer')
            document['answers'][key] = {'state': value['status'], 'value': deepcopy(value['value'])}
        old_contract = raw.get('task_contract', {})
        if not isinstance(old_contract, dict):
            raise ValueError('Invalid legacy task contract')
        for key in ('no_execution', 'no_external_writes'):
            if key in old_contract:
                if type(old_contract[key]) is not bool:
                    raise ValueError('Invalid legacy task contract')
                document['task_contract'][key] = old_contract[key]
        stages = old_contract.get('stages', [])
        if not isinstance(stages, list) or any(s not in STEPS and s != 'discovery' for s in stages):
            raise ValueError('Invalid legacy stages')
        document['task_contract']['stages'] = deepcopy(stages)
        workflow = _workflow(document)
        workflow.request([stage for stage in stages if stage in STEPS])
        _project_source(workflow)
        if 'build' in workflow.answers:
            workflow.answers['build_ref'] = deepcopy(workflow.answers['build'])
        document['steps'] = {key: asdict(value) for key, value in workflow.steps.items()}
        document['answers'] = workflow.answers
    elif workflow_markers <= raw.keys():
        source_format = 'Workflow'
        document = _new(raw['project'], str(uuid5(NAMESPACE_URL, SCHEMA + ':' + source_format + ':' + digest)))
        for key in ('steps', 'answers', 'events'):
            document[key] = deepcopy(raw[key])
        if not isinstance(document['events'], list):
            raise ValueError('Invalid legacy history')
        # Defaults from old Step revisions are retained explicitly.
        if not isinstance(document['steps'], dict):
            raise ValueError('Invalid legacy graph')
        document['steps'] = {key: asdict(Step(**value)) for key, value in document['steps'].items()}
        for step in document['steps'].values():
            if step['status'] == 'DONE':
                step['status'] = 'NEEDS_REVALIDATION'
    else:
        raise ValueError('UNSUPPORTED_SCHEMA')
    approvals = raw.get('approvals', {})
    if not isinstance(approvals, dict):
        raise ValueError('Invalid legacy approvals')
    document['legacy_assertions'] = [
        {'kind': key, 'value': deepcopy(value), 'assurance': 'UNVERIFIED_LEGACY'}
        for key, value in approvals.items()]
    document['revision'] = raw.get('revision', 0)
    document['event_sequence'] = len(document['events'])
    document['legacy_payload'] = deepcopy(raw)
    document['migration'] = {'source_format': source_format, 'source_sha256': digest,
                             'tool_version': '0.1.0', 'assurance': 'NOT_REVERIFIED'}
    # Old Step bytes/receipts remain in legacy_payload and active projection.
    # Readiness below never accepts legacy completions as new trusted evidence.
    _event(document, 'migrated', source_format=source_format, source_sha256=digest)
    document['questions'] = plan_task('discovery', _known(_workflow(document)))['questions']
    _validate(document)
    return document, True


class CampaignApplicationService:
    """One local state owner for the installed CLI; all mutations CAS-save."""
    def __init__(self, path, document, *, source_digest=None, needs_migration=False):
        self.path = Path(path)
        self.document = document
        self.source_digest = source_digest
        self.needs_migration = needs_migration

    @classmethod
    def initialize(cls, path, project):
        document = save_document(path, _new(project), expected_revision=0, create_if_absent=True)
        return cls.load(path)

    @classmethod
    def load(cls, path):
        try:
            original = Path(path).read_bytes()
            raw = json.loads(original.decode('utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError('State file cannot be read') from error
        digest = hashlib.sha256(original).hexdigest()
        document, migrated = migrate(raw, digest)
        return cls(path, document, source_digest=digest, needs_migration=migrated)

    def _save(self, document):
        _validate(document)
        persisted = save_document(self.path, document, expected_revision=self.document['revision'],
                                  expected_sha256=self.source_digest, backup_legacy=self.needs_migration)
        self.document = persisted
        self.source_digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.needs_migration = False

    def mutate(self, command, **payload):
        document = deepcopy(self.document)
        if document['mode'] == 'PAUSED' and command not in ('pause', 'resume'):
            raise PermissionError('CAMPAIGN_PAUSED')
        workflow = _workflow(document)
        output = None
        if command == 'answer':
            key, value = payload['key'], payload['value']
            workflow.answer(key, value)
            if key in ('requirements', 'gitlab', 'web_url'):
                _project_source(workflow)
            if key == 'build':
                workflow.answer('build_ref', value)
            document['questions'] = plan_task('discovery', _known(workflow))['questions']
        elif command == 'plan':
            output = plan_task(payload['prompt'], _known(workflow))
            document['questions'] = deepcopy(output['questions'])
            workflow.request([stage for stage in output['stages'] if stage in STEPS])
            contract = document['task_contract']
            old_contract = deepcopy(contract)
            for key in ('no_execution', 'no_external_writes'):
                contract[key] = contract[key] or output[key]
                output[key] = contract[key]
            contract['stages'] = output['stages']
            if contract != old_contract:
                for step in ('test_plan', 'execution'):
                    if step in workflow.steps:
                        workflow.invalidate(step)
            output['professional_guidance'] = select_skills(output['stages'])
            output['task_contract'] = deepcopy(contract)
        elif command == 'approve':
            if payload['kind'] not in ('requirements', 'cases', 'execution', 'report', 'plan', 'cycle', 'bug', 'regression', 'test_plan') or not payload['version']:
                raise ValueError('Invalid legacy approval')
            document['legacy_assertions'].append({'kind': payload['kind'], 'value': payload['version'], 'assurance': 'UNVERIFIED_LEGACY'})
            output = {'state': 'RECORDED_UNVERIFIED', 'execution_authorized': False}
        elif command == 'invalidate':
            roots = {'requirements': ('requirements',), 'code': ('case_review', 'code_refinement')}[payload['source']]
            for root in roots:
                if root in workflow.steps:
                    workflow.invalidate(root)
        elif command == 'pause':
            reason = payload.get('reason', '')
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError('Pause reason required')
            document['mode'], document['pause'] = 'PAUSED', {'reason': reason}
        elif command == 'resume':
            document['mode'], document['pause'] = 'ACTIVE', None
        else:
            raise ValueError('Unknown command')
        for key in ('answers', 'approvals', 'events'):
            document[key] = deepcopy(getattr(workflow, key))
        document['steps'] = {key: asdict(value) for key, value in workflow.steps.items()}
        document['event_sequence'] = max(document['event_sequence'], len(document['events']))
        _event(document, command)
        self._save(document)
        return output if output is not None else self.status()

    def _readiness(self, workflow, step, seen=None):
        seen = set() if seen is None else seen
        if step in seen:
            raise ValueError('Cyclic workflow')
        seen = seen | {step}
        item = workflow.steps[step]
        if item.status in ('NEEDS_REVALIDATION', 'STALE'):
            return item.status
        dependencies = [self._readiness(workflow, dep, seen) for dep in item.depends_on]
        if any(state in ('STALE', 'NEEDS_REVALIDATION') for state in dependencies):
            return 'STALE'
        # No persisted local assertion is a host-verified authorization. Legacy
        # completions remain visible but must be explicitly revalidated later.
        if item.status == 'DONE':
            if self.document['migration'] is not None or not item.completion_binding or item.approvals or item.side_effect:
                return 'NEEDS_REVALIDATION'
            if any(state != 'DONE' for state in dependencies):
                return 'STALE'
            return 'NEEDS_REVALIDATION'  # CLI has no exact-artifact provider yet.
        if any(state != 'DONE' for state in dependencies):
            return 'PENDING'
        state = workflow.evaluate(step)
        if state == 'READY' and item.approvals:
            return 'WAITING_APPROVAL'
        return state

    def check(self, intent):
        document = self.document
        workflow = _workflow(document)
        workflow.request([intent])
        if intent in ('execution', 'regression') and document['task_contract']['no_execution']:
            state = 'DENIED_BY_TASK_SCOPE'
        elif document['mode'] == 'PAUSED':
            state = 'PAUSED'
        else:
            state = self._readiness(workflow, intent)
            if intent in ('execution', 'regression') and state == 'READY':
                state = 'WAITING_TRUSTED_EXECUTOR'
        return {'state': state, 'question': None, 'mode': 'PLANNING_ONLY',
                'campaign_mode': document['mode'], 'schema_version': 2,
                'revision': document['revision'], 'execution_authorized': False}

    def status(self):
        document = self.document
        workflow = _workflow(document)
        return {'project': document['project'], 'schema_version': 2,
                'revision': document['revision'], 'mode': document['mode'],
                'pause': deepcopy(document['pause']),
                'known': {key: {'status': answer['state'], 'value': None if answer['state'] == 'CONFIRMED_NONE' else '[stored]'}
                          for key, answer in document['answers'].items()},
                'questions': deepcopy(document['questions']),
                'approvals': {}, 'legacy_assertion_count': len(document['legacy_assertions']),
                'task_contract': deepcopy(document['task_contract']), 'execution_authorized': False,
                'steps': {key: self._readiness(workflow, key) for key in workflow.steps}}
