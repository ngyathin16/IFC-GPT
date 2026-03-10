"""Interactive CLI for the IFC building generation agent.

Usage:
    uv run scripts/run_agent.py
    uv run scripts/run_agent.py --message "I want a 5 storey office building"
    uv run scripts/run_agent.py --no-interactive

Options:
    --message TEXT      Initial building request (prompts if omitted)
    --no-interactive    Skip questions and use built-in defaults
    --log-level LEVEL   DEBUG / INFO / WARNING / ERROR  (default: WARNING)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the project root (parent of scripts/) is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IFC Building Generation Agent — interactive CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--message", "-m",
        default="",
        help="Initial building request (will prompt if omitted)",
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="Apply defaults for all missing fields without asking",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log verbosity (default: WARNING)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    from agent.graph import run_pipeline
    from langchain_core.messages import AIMessage

    message = args.message.strip()
    if not message:
        print("IFC Building Generation Agent")
        print("=" * 40)
        message = input("Describe the building you want: ").strip()
        if not message:
            print("No input — exiting.")
            sys.exit(0)

    print()
    result = run_pipeline(
        user_message=message,
        mcp_client=None,
        interactive=not args.no_interactive,
    )

    msgs = result.get("messages", [])
    for m in reversed(msgs):
        if isinstance(m, AIMessage):
            print()
            print(m.content)
            break


if __name__ == "__main__":
    main()
