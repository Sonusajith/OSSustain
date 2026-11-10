"""Command-line entry point for the OSSustain pipeline scaffold."""

import argparse
from datetime import UTC, datetime
from pathlib import Path

from ossustain_pipeline.cohort import select_cohort
from ossustain_pipeline.collect.models import load_cohort
from ossustain_pipeline.collect.runner import run_collection
from ossustain_pipeline.collect.store import PostgresCollectionStore
from ossustain_pipeline.config import load_config
from ossustain_pipeline.db import connect
from ossustain_pipeline.github.cache import JsonResponseCache
from ossustain_pipeline.github.client import GitHubClient


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
    collect_parser = commands.add_parser(
        "collect",
        help="Collect repository metadata and full commit history for the selected cohort.",
    )
    collect_parser.add_argument(
        "--cohort",
        type=Path,
        default=Path("config/cohort.yaml"),
        help="Selected cohort YAML file (default: config/cohort.yaml).",
    )
    collect_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("pipeline/data/github-cache"),
        help="Privacy-filtered GitHub JSON cache directory.",
    )
    collect_parser.add_argument(
        "--report",
        type=Path,
        help="Optional collection-report output path.",
    )
    collect_parser.add_argument(
        "--limit",
        type=int,
        help="Optional repository limit for a development smoke run.",
    )
    collect_parser.add_argument(
        "--refresh",
        action="store_true",
        help="Restart commit pagination from the newest commit snapshot.",
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
    elif args.command == "collect":
        if args.limit is not None and args.limit < 1:
            parser.error("--limit must be at least 1")
        try:
            config = load_config(args.config)
            if not config.github_token or not config.github_token.get_secret_value():
                raise ValueError("GITHUB_TOKEN is required; add it to the local .env file")
            if not config.hash_secret or len(config.hash_secret.get_secret_value()) < 32:
                raise ValueError("OSSUSTAIN_HASH_SECRET must contain at least 32 characters")
            cohort = load_cohort(args.cohort)
            client = GitHubClient(
                config.github_token.get_secret_value(),
                JsonResponseCache(args.cache_dir),
            )
            report_path = args.report
            if report_path is None:
                report_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
                report_path = Path("pipeline/data/reports") / f"collection_{report_stamp}.json"
            with connect(config) as connection:
                report = run_collection(
                    cohort,
                    client,
                    PostgresCollectionStore(connection),
                    hash_secret=config.hash_secret.get_secret_value(),
                    report_path=report_path,
                    refresh=args.refresh,
                    repository_limit=args.limit,
                )
        except ValueError as error:
            parser.error(str(error))
        print(
            f"Collection report: {report_path}; "
            f"{report['repositories_succeeded']}/{report['repositories_requested']} "
            "repositories complete; "
            f"{report['repositories_failed']} failed."
        )
        if report["repositories_failed"]:
            raise SystemExit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
