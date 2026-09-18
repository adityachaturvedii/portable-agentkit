"""Offline foundation and explicit Phase 2 diagnostics/smoke entry points."""

import argparse
import json
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
        else:
            print(json.dumps(check_pack(), indent=2))
        return 0
    except (ValidationError, OSError, KeyError, ValueError) as exc:
        print("agentkit: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
