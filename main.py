import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.state import ArchitectureState  # noqa: E402 — must come after load_dotenv
from src.graph import build_graph  # noqa: E402
from src.utils.output_writer import write_outputs  # noqa: E402

DEFAULT_OUTPUT = "./output"


def _prompt_for_requirements() -> str:
    print("Enter your business requirements below.")
    print("When you're done, press Enter twice (blank line) to continue.\n")
    lines = []
    consecutive_blanks = 0
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "":
            consecutive_blanks += 1
            if consecutive_blanks >= 2:
                break
            lines.append(line)
        else:
            consecutive_blanks = 0
            lines.append(line)
    # Strip trailing blank lines added by the double-Enter sentinel
    requirements = "\n".join(lines).strip()
    return requirements


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a solution architecture deliverable from business requirements."
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Path to a requirements markdown file. If omitted, you will be prompted to type requirements.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output directory (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        default=False,
        help="Pause for human review after the business brief and candidate approaches",
    )
    args = parser.parse_args()

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        requirements = input_path.read_text(encoding="utf-8").strip()
        if not requirements:
            print(f"Error: input file is empty: {input_path}", file=sys.stderr)
            sys.exit(1)
    else:
        requirements = _prompt_for_requirements()
        if not requirements:
            print("Error: no requirements provided.", file=sys.stderr)
            sys.exit(1)

    print()
    graph = build_graph(interactive=args.interactive)
    initial_state = ArchitectureState(requirements_input=requirements)

    final_state = graph.invoke(initial_state)

    write_outputs(final_state, args.output)
    print(f"\n✓ Complete. Output written to {args.output}/")


if __name__ == "__main__":
    main()
