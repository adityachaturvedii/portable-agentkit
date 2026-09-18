"""Read-only CLI for the Phase 1 foundation."""

import argparse
import json
import sys

from .pack import catalog, check_pack, render, select
from .validation import ValidationError, read_json, validate_handoff


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline skill foundation; no provider or project execution")
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
        else:
            print(json.dumps(check_pack(), indent=2))
        return 0
    except (ValidationError, OSError, KeyError, ValueError) as exc:
        print("agentkit: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
