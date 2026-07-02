#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from pawly_test_suite.self_hosted import (  # noqa: E402
    load_declaration,
    load_json,
    validate_healthcheck_example,
    validate_invoke_example,
    validate_self_hosted_declaration,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate minimal self-hosted worker onboarding artifacts.")
    parser.add_argument("--agent", required=True, help="Path to the self-hosted Pawprint worker card YAML")
    parser.add_argument("--invoke-example", required=True, help="Path to a mock HTTP invocation request JSON")
    parser.add_argument("--healthcheck-example", required=True, help="Path to a mock healthcheck request JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    declaration_errors = validate_self_hosted_declaration(args.agent)
    declaration = load_declaration(args.agent)
    invoke_errors = validate_invoke_example(declaration, load_json(args.invoke_example))
    healthcheck_errors = validate_healthcheck_example(declaration, load_json(args.healthcheck_example))

    errors = declaration_errors + invoke_errors + healthcheck_errors
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print(f"validated self-hosted Pawprint worker card {args.agent}")
    print(f"validated invocation example {args.invoke_example}")
    print(f"validated healthcheck example {args.healthcheck_example}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
