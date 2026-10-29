"""Command-line entry point for the OSSustain pipeline scaffold."""

import argparse
from pathlib import Path

from ossustain_pipeline.cohort import select_cohort


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ossustain-pipeline",
        description="Run OSSustain's offline research pipeline stages.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("pipeline/config.yaml"),
        help="Path to the pipeline YAML configuration (default: pipeline/config.yaml).",
    )
    commands = parser.add_subparsers(dest="command")
    select_parser = commands.add_parser(
        "select-cohort",
        help="Select a reproducible, stratified repository cohort from screened candidates.",
    )
    select_parser.add_argument(
        "--candidate-config",
        type=Path,
        default=Path("config/cohort-candidates.yaml"),
        help="Candidate metadata and inclusion criteria YAML.",
    )
    select_parser.add_argument(
        "--output",
        type=Path,
        default=Path("config/cohort.yaml"),
        help="Path for the deterministic selected-cohort YAML.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "select-cohort":
        try:
            selected = select_cohort(args.candidate_config, args.output)
        except ValueError as error:
            parser.error(str(error))
        print(f"Selected {len(selected)} repositories into {args.output}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
