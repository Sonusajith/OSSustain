"""Command-line entry point for the OSSustain pipeline scaffold."""

import argparse
from pathlib import Path


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
    return parser


def main() -> None:
    parser = build_parser()
    parser.parse_args()
    parser.print_help()


if __name__ == "__main__":
    main()
