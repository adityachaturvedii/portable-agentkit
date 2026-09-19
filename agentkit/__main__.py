"""Offline foundation and explicit Phase 2 diagnostics/smoke entry points."""

import argparse
import json
from pathlib import Path
import sys

from .pack import catalog, check_pack, render, select
from .validation import ValidationError, read_json, validate_handoff


def main(argv=None):
    parser = argparse.ArgumentParser(description="Portable skill foundation and bounded CLI integration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list available skills and explicit intents")
    selection = commands.add_parser("select", help="select a skill by explicit intent")
    selection.add_argument("intent")
    show = commands.add_parser("show", help="print skill and shared contract, optionally one domain")
    show.add_argument("skill")
    show.add_argument("--domain")
    validate = commands.add_parser("validate", help="validate an untrusted handoff without executing it")
    validate.add_argument("file")
    commands.add_parser("check", help="check pack references, notices and blocked examples offline")
    commands.add_parser("doctor", help="read-only version, feature, authentication and sandbox observations")
    smoke = commands.add_parser("smoke", help="one disposable model-only CLI smoke; blocked by default")
    smoke.add_argument("engine", choices=("codex", "claude"))
    smoke.add_argument("--output", required=True, help="fresh result directory")
    smoke.add_argument("--authorize-subscription-smoke", action="store_true",
                       help="trusted operator authorization; does not establish account billing settings")
    execution = commands.add_parser("execution-check", help="one disposable owned-code CLI check; blocked by default")
    execution.add_argument("engine", choices=("codex", "claude"))
    execution.add_argument("--output", required=True, help="fresh result directory")
    execution.add_argument("--authorize-subscription-smoke", action="store_true",
                           help="trusted operator authorization; does not establish account billing settings")
    lifecycle = commands.add_parser("lifecycle-check", help="offline owned-code timeout and cancellation fixtures")
    lifecycle.add_argument("--output", required=True, help="fresh result directory")
    boundary = commands.add_parser("boundary-check", help="offline owned-code filesystem boundary canaries")
    boundary.add_argument("--output", required=True, help="fresh result directory")
    delivery = commands.add_parser("controller-demo", help="run the Phase 3 disposable delivery workflow")
    delivery.add_argument("--output", required=True, help="fresh workflow root")
    delivery.add_argument("--live", action="store_true", help="use installed subscription CLIs instead of fake engines")
    delivery.add_argument("--implementer", choices=("codex", "claude"), default="codex",
                          help="live implementer; the other provider performs review")
    delivery.add_argument("--authorize-subscription-smoke", action="store_true",
                          help="authorize one bounded disposable implementer/reviewer demonstration")
    delivery.add_argument("--resume", action="store_true",
                          help="resume the exact stage at a verified authentication checkpoint")
    delivery.add_argument("--recover-review-format", action="store_true",
                          help="offline recovery of one hash-matched provider-success fenced JSON review")
    auth_status = commands.add_parser("auth-status", help="sanitized official CLI subscription status")
    auth_status.add_argument("provider", choices=("codex", "claude"))
    auth_login = commands.add_parser("auth-login", help="official interactive subscription login; output is not captured")
    auth_login.add_argument("provider", choices=("codex", "claude"))
    auth_login.add_argument("--method", choices=("browser", "device"), default="browser")
    auth_login.add_argument("--timeout", type=float, default=600)
    auth_login.add_argument("--workflow", help="existing workflow root with an authentication checkpoint")
    auth_login.add_argument("--task-id", default="phase3-demo")
    auth_reconcile = commands.add_parser(
        "auth-reconcile", help="record process-evidence resolution for an interrupted login owner")
    auth_reconcile.add_argument("--workflow", required=True)
    auth_reconcile.add_argument("--task-id", default="phase3-demo")
    auth_reconcile.add_argument("--resolution",
                                choices=("confirmed_ended", "uncertain"), required=True)
    auth_reconcile.add_argument("--basis", required=True,
                                choices=("process_exit_confirmed", "process_termination_unconfirmed"),
                                help="sanitized process evidence; free-form terminal output is not accepted")
    task = commands.add_parser("task", help="Phase 4 disposable task intake and orchestration")
    task_commands = task.add_subparsers(dest="task_command", required=True)
    task_commands.add_parser("fixtures", help="list supported controller-created disposable targets")
    task_submit = task_commands.add_parser("submit", help="normalize a request and propose a bounded plan")
    task_submit.add_argument("--root", required=True, help="fresh workflow directory")
    task_submit.add_argument("--task-id", required=True)
    task_submit.add_argument("--fixture", required=True)
    task_submit.add_argument("--request", required=True)
    task_submit.add_argument("--risk", choices=("routine", "material"))
    task_submit.add_argument("--max-calls", type=int)
    task_submit.add_argument("--max-elapsed-seconds", type=float)
    task_submit.add_argument("--max-concurrency", type=int, choices=(1, 2))
    task_submit.add_argument("--implementer-provider", choices=("codex", "claude"), default="codex",
                             help="account-default provider for implementation and bounded repair")
    task_submit.add_argument("--reviewer-provider", choices=("codex", "claude"), default="claude",
                             help="account-default provider for independent review")
    for name, help_text in (
            ("plan", "show the validated contract and proposed graph"),
            ("status", "show stage, assignments, routing, budget, blockers, and attention"),
            ("cancel", "request cancellation and prevent subsequent launches"),
            ("package", "read the final local approval package")):
        command = task_commands.add_parser(name, help=help_text)
        command.add_argument("--root", required=True)
        command.add_argument("--task-id", required=True)
    for name, help_text in (("start", "start or continue the proposed bounded workflow"),
                            ("resume", "resume an authentication checkpoint after verified login")):
        command = task_commands.add_parser(name, help=help_text)
        command.add_argument("--root", required=True)
        command.add_argument("--task-id", required=True)
        command.add_argument("--live", action="store_true")
        command.add_argument("--authorize-subscription-smoke", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            print(json.dumps(catalog(), indent=2))
        elif args.command == "select":
            print(json.dumps(select(args.intent), indent=2))
        elif args.command == "show":
            print(render(args.skill, args.domain))
        elif args.command == "validate":
            result = validate_handoff(read_json(args.file))
            print(json.dumps({"valid": True, "kind": result["kind"],
                              "status": result["status"], "authority": "none",
                              "note": "Structure and consistency only; claims are not authenticated."}))
        elif args.command == "doctor":
            from .doctor import doctor
            print(json.dumps(doctor(), indent=2))
        elif args.command == "smoke":
            from .smoke import smoke_test
            result = smoke_test(args.engine, args.output, args.authorize_subscription_smoke)
            print(json.dumps(result, indent=2))
            return 0 if result['acceptance']['passed'] else 1
        elif args.command == "execution-check":
            from .execution_check import run_execution_check
            result = run_execution_check(args.engine, args.output, args.authorize_subscription_smoke)
            print(json.dumps(result, indent=2))
            return 0 if result['acceptance']['passed'] else 1
        elif args.command == "lifecycle-check":
            from .execution_check import lifecycle_check
            result = lifecycle_check(args.output)
            print(json.dumps(result, indent=2))
            return 0 if result['passed'] else 1
        elif args.command == "boundary-check":
            from .execution_check import standalone_boundary_check
            result = standalone_boundary_check(args.output)
            print(json.dumps(result, indent=2))
            return 0 if result['passed'] else 1
        elif args.command == "controller-demo":
            from .delivery import (DeliveryWorkflow, LiveImplementer, LiveReviewer, run_demo)
            if args.resume and args.recover_review_format:
                raise ValueError('choose either authentication resume or review-format recovery')
            if args.recover_review_format:
                if not args.live or not args.authorize_subscription_smoke:
                    raise ValueError('review-format recovery requires the original live authorization context')
                workflow = DeliveryWorkflow.open(args.output, LiveImplementer(args.implementer),
                                                 LiveReviewer('claude' if args.implementer == 'codex' else 'codex'),
                                                 live_authorized=True)
                result = workflow.recover_review_format()
            else:
                result = run_demo(args.output, live=args.live, authorized=args.authorize_subscription_smoke,
                                  implementer_engine=args.implementer, resume=args.resume)
            print(json.dumps({'task': result['task'], 'approval_package': result['approval_package'],
                              'root': result['root']}, indent=2))
            return 0 if result['task']['state'] in ('awaiting_pr_approval', 'authentication_required') else 1
        elif args.command == "auth-status":
            from .auth import probe_authentication
            print(json.dumps(probe_authentication(args.provider).to_dict(), indent=2))
        elif args.command == "auth-login":
            from .auth import guided_login, safe_login_reason
            from .controller import ControllerStore
            if args.provider == 'claude' and args.method != 'browser':
                raise ValueError('Claude Code supports browser login with manual code handoff, not device mode')
            store = None
            claim = None
            if args.workflow:
                root = Path(args.workflow).resolve()
                store = ControllerStore(root / 'controller')
                if sys.stdin.isatty() and sys.stdout.isatty() and sys.stderr.isatty():
                    claim = store.claim_authentication_login(args.task_id, args.provider,
                                                              authority=store.authority)
                    if not claim['claimed'] and claim['status'] == 'in_progress':
                        print(json.dumps({
                            'provider': args.provider,
                            'status': 'login_ownership_requires_reconciliation',
                            'machine': 'this host',
                            'session_id': claim['session_id'],
                            'next_action': ('Confirm whether the prior official login process is still running. '
                                            'If it ended, use auth-reconcile --resolution confirmed_ended; '
                                            'if termination cannot be established, use --resolution uncertain.')
                        }, indent=2))
                        return 1
                    if not claim['claimed'] and claim['status'] == 'succeeded':
                        print(json.dumps({'provider': args.provider, 'status': 'already_authenticated',
                                          'machine': 'this host'}, indent=2))
                        return 0
            try:
                result = guided_login(args.provider, args.method, timeout_seconds=args.timeout)
            except KeyboardInterrupt:
                if store is not None and claim is not None and claim['claimed']:
                    store.reconcile_authentication_login(
                        claim['session_id'], 'uncertain',
                        'controller_interrupted',
                        authority=store.authority)
                print(json.dumps({'provider': args.provider, 'status': 'cancelled',
                                  'termination': 'uncertain'}, indent=2))
                return 130
            except Exception:
                if store is not None and claim is not None and claim['claimed']:
                    store.reconcile_authentication_login(
                        claim['session_id'], 'uncertain',
                        'launcher_exception',
                        authority=store.authority)
                raise
            if store is not None and claim is not None and claim['claimed']:
                if result.termination == 'uncertain':
                    store.reconcile_authentication_login(
                        claim['session_id'], 'uncertain',
                        'process_termination_unconfirmed',
                        authority=store.authority)
                else:
                    outcome = 'succeeded' if result.status in ('succeeded', 'already_authenticated') else (
                        'timed_out' if result.status == 'timed_out' else
                        'cancelled' if result.status == 'cancelled' else 'failed')
                    store.finish_authentication_login(
                        claim['session_id'], outcome, auth_mode=result.authentication.mode,
                        reason=safe_login_reason(result), owner_nonce=claim['owner_nonce'],
                        authority=store.authority)
            print(json.dumps(result.to_dict(), indent=2))
            return 0 if result.status in ('succeeded', 'already_authenticated') else 1
        elif args.command == "auth-reconcile":
            from .controller import ControllerStore
            root = Path(args.workflow).resolve()
            store = ControllerStore(root / 'controller')
            checkpoint = store.authentication_checkpoint(args.task_id)
            if not checkpoint:
                raise ValueError('task has no active authentication checkpoint')
            status = store.reconcile_authentication_login(
                checkpoint['login_session_id'], args.resolution, args.basis,
                authority=store.authority)
            print(json.dumps({'task_id': args.task_id, 'session_id': checkpoint['login_session_id'],
                              'status': status}, indent=2))
            return 0
        elif args.command == "task":
            from .orchestration import Phase4Workflow, phase4_fixture_catalog
            if args.task_command == 'fixtures':
                print(json.dumps({'execution_profile': 'trusted-disposable-macos',
                                  'fixtures': phase4_fixture_catalog()}, indent=2))
                return 0
            if args.task_command == 'submit':
                from .phase4_contracts import ModelRegistry
                registry = ModelRegistry.account_defaults(args.implementer_provider,
                                                          args.reviewer_provider)
                workflow = Phase4Workflow.submit(
                    args.root, args.task_id, args.request, args.fixture, risk=args.risk,
                    max_calls=args.max_calls, max_elapsed_seconds=args.max_elapsed_seconds,
                    max_concurrency=args.max_concurrency, registry=registry)
                print(json.dumps({'contract': json.loads((workflow.root / 'contract.json').read_text()),
                                  'plan': json.loads((workflow.root / 'plan.json').read_text()),
                                  'status': workflow.status(args.task_id)}, indent=2))
                return 0
            live = getattr(args, 'live', False)
            authorized = getattr(args, 'authorize_subscription_smoke', False)
            if live and not authorized:
                raise ValueError('live Phase 4 execution requires explicit subscription-smoke authorization')
            workflow = Phase4Workflow(args.root, live=live, authorized=authorized)
            if args.task_command == 'plan':
                print(json.dumps({'contract': json.loads((workflow.root / 'contract.json').read_text()),
                                  'plan': workflow.state.plan(args.task_id)['plan']}, indent=2))
            elif args.task_command == 'status':
                print(json.dumps(workflow.status(args.task_id), indent=2))
            elif args.task_command == 'start':
                print(json.dumps(workflow.start(args.task_id), indent=2))
            elif args.task_command == 'resume':
                print(json.dumps(workflow.resume(args.task_id), indent=2))
            elif args.task_command == 'cancel':
                print(json.dumps(workflow.cancel(args.task_id), indent=2))
            else:
                package = workflow.result(args.task_id)['approval_package']
                if package is None:
                    raise ValueError('local approval package is not available')
                print(json.dumps(package, indent=2))
            return 0
        else:
            print(json.dumps(check_pack(), indent=2))
        return 0
    except (ValidationError, OSError, KeyError, ValueError) as exc:
        print("agentkit: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
