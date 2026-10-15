import argparse
import json
from .application import CampaignApplicationService
from .skill_registry import discover_skills
from .state_store import StateConflictError


def main():
    p = argparse.ArgumentParser(description='QA Master local workflow CLI (planning only)')
    p.add_argument('--state', default='.qa-master/campaign.json')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init').add_argument('name')
    sub.add_parser('status')
    sub.add_parser('skills')
    install = sub.add_parser('install-codex', help='Install the self-contained Codex skill')
    destination = install.add_mutually_exclusive_group()
    destination.add_argument('--user', action='store_true', help='Install under ~/.agents/skills')
    destination.add_argument('--project', help='Install under PROJECT/.agents/skills')
    destination.add_argument('--target', help='Explicit skill directory')
    install.add_argument('--update', action='store_true', help='Update an unchanged managed install; keep backup')
    sub.add_parser('plan').add_argument('prompt')
    a = sub.add_parser('answer'); a.add_argument('key'); a.add_argument('value')
    a = sub.add_parser('approve'); a.add_argument('kind'); a.add_argument('version')
    sub.add_parser('check').add_argument('intent', choices=('execution','regression','design','review','report'))
    sub.add_parser('invalidate').add_argument('source', choices=('requirements','code'))
    sub.add_parser('pause').add_argument('reason')
    sub.add_parser('resume')
    args = p.parse_args()
    try:
        if args.cmd == 'install-codex':
            from .codex_skill import install_skill, SkillInstallError
            try:
                output = install_skill(args.target, user=args.user, project=args.project, update=args.update)
            except SkillInstallError as error:
                print(json.dumps({'error': str(error)}, ensure_ascii=True))
                return 2
            except OSError:
                print(json.dumps({'error': 'SKILL_INSTALL_IO_ERROR'}, ensure_ascii=True))
                return 2
        elif args.cmd == 'skills':
            output = discover_skills()
        elif args.cmd == 'init':
            output = CampaignApplicationService.initialize(args.state, args.name).status()
        else:
            service = CampaignApplicationService.load(args.state)
            if args.cmd == 'status':
                output = service.status()
            elif args.cmd == 'check':
                output = service.check(args.intent)
            else:
                payload = {key: value for key, value in vars(args).items() if key not in ('state', 'cmd')}
                output = service.mutate(args.cmd, **payload)
    except (ValueError, TypeError, PermissionError, StateConflictError) as error:
        # Exception text is deliberately fixed by our domain, never raw payloads.
        code = 'STATE_CONFLICT' if isinstance(error, StateConflictError) else 'COMMAND_REJECTED'
        if str(error) in ('CAMPAIGN_PAUSED', 'UNSUPPORTED_SCHEMA', 'AMBIGUOUS_SCHEMA'):
            code = str(error)
        print(json.dumps({'error': code}, ensure_ascii=True))
        return 2
    print(json.dumps(output, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
