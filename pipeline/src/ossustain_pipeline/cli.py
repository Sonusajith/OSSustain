"""Command-line entry point for the OSSustain pipeline scaffold."""

import argparse
from datetime import UTC, datetime
from pathlib import Path

from ossustain_pipeline.cohort import select_cohort
from ossustain_pipeline.collect.collaboration import run_collaboration_collection
from ossustain_pipeline.collect.models import load_cohort
from ossustain_pipeline.collect.runner import run_collection
from ossustain_pipeline.collect.store import PostgresCollectionStore
from ossustain_pipeline.collect.validation import build_quality_report
from ossustain_pipeline.config import load_config
from ossustain_pipeline.db import connect
from ossustain_pipeline.experiment import load_experiment_config
from ossustain_pipeline.features.runner import build_features
from ossustain_pipeline.github.cache import JsonResponseCache
from ossustain_pipeline.github.client import GitHubClient
from ossustain_pipeline.modeling.config import load_modeling_config
from ossustain_pipeline.modeling.runner import train_and_evaluate
from ossustain_pipeline.predictions.runner import generate_explanations, generate_predictions
from ossustain_pipeline.snapshots.runner import build_snapshots


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
    collaboration_parser = commands.add_parser(
        "collect-collaboration",
        help="Collect pull requests, reviews, issues, and first responses under request caps.",
    )
    collaboration_parser.add_argument(
        "--cohort",
        type=Path,
        default=Path("config/cohort.yaml"),
        help="Selected cohort YAML file.",
    )
    collaboration_parser.add_argument(
        "--report", type=Path, help="Optional collaboration quality report path."
    )
    collaboration_parser.add_argument(
        "--limit", type=int, help="Optional repository limit for a development smoke run."
    )
    collaboration_parser.add_argument(
        "--pr-request-cap",
        type=int,
        default=12_500,
        help="Hard cap for PR, review, and PR-response API requests (default: 12500).",
    )
    collaboration_parser.add_argument(
        "--issue-request-cap",
        type=int,
        default=25_000,
        help="Hard cap for non-PR issue and response API requests (default: 25000).",
    )
    validate_parser = commands.add_parser(
        "validate",
        help="Check collection completeness and write a per-repository quality report.",
    )
    validate_parser.add_argument(
        "--cohort",
        type=Path,
        default=Path("config/cohort.yaml"),
        help="Selected cohort YAML file.",
    )
    validate_parser.add_argument(
        "--issue-screen",
        type=Path,
        default=Path("pipeline/data/reports/phase4-issue-budget.json"),
        help="Optional issue-count screen used to check collection completeness.",
    )
    validate_parser.add_argument(
        "--report",
        type=Path,
        default=Path("pipeline/data/reports/phase4-validation.json"),
        help="Quality report output path.",
    )
    snapshots_parser = commands.add_parser(
        "build-snapshots",
        help="Build versioned snapshots, labels, splits, and prevalence summaries.",
    )
    snapshots_parser.add_argument("--cohort", type=Path, default=Path("config/cohort.yaml"))
    snapshots_parser.add_argument("--experiment", type=Path, default=Path("config/experiment.yaml"))
    snapshots_parser.add_argument(
        "--quality-report", type=Path, default=Path("pipeline/data/reports/phase4-validation.json")
    )
    snapshots_parser.add_argument(
        "--report", type=Path, default=Path("pipeline/data/reports/phase5-snapshots.json")
    )
    features_parser = commands.add_parser(
        "build-features", help="Build versioned leakage-safe snapshot features and display metrics."
    )
    features_parser.add_argument(
        "--dataset-version-id",
        type=int,
        help="Phase 5 dataset version (default: the most recently created version).",
    )
    features_parser.add_argument(
        "--report", type=Path, default=Path("pipeline/data/reports/phase6-features.json")
    )
    train_parser = commands.add_parser(
        "train",
        help="Tune models on validation, evaluate final models on test, and store results.",
    )
    train_parser.add_argument("--model-config", type=Path, default=Path("config/modeling.yaml"))
    train_parser.add_argument("--dataset-version-id", type=int)
    train_parser.add_argument("--feature-set-id", type=int)
    train_parser.add_argument(
        "--report", type=Path, default=Path("pipeline/data/reports/phase7-models.json")
    )
    predict_parser = commands.add_parser(
        "predict", help="Score each repository's latest snapshot with a validation-selected model."
    )
    predict_parser.add_argument("--dataset-version-id", type=int)
    predict_parser.add_argument(
        "--report", type=Path, default=Path("pipeline/data/reports/phase8-predictions.json")
    )
    explain_parser = commands.add_parser(
        "explain", help="Store ranked per-prediction feature indicators and their direction."
    )
    explain_parser.add_argument("--dataset-version-id", type=int)
    explain_parser.add_argument(
        "--report", type=Path, default=Path("pipeline/data/reports/phase8-explanations.json")
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
    elif args.command == "collect-collaboration":
        if args.limit is not None and args.limit < 1:
            parser.error("--limit must be at least 1")
        if args.pr_request_cap < 1 or args.issue_request_cap < 1:
            parser.error("request caps must be at least 1")
        try:
            config = load_config(args.config)
            if not config.github_token or not config.github_token.get_secret_value():
                raise ValueError("GITHUB_TOKEN is required; add it to the local .env file")
            if not config.hash_secret or len(config.hash_secret.get_secret_value()) < 32:
                raise ValueError("OSSUSTAIN_HASH_SECRET must contain at least 32 characters")
            cohort = load_cohort(args.cohort)
            client = GitHubClient(
                config.github_token.get_secret_value(),
                JsonResponseCache(Path("pipeline/data/github-cache")),
            )
            report_path = args.report or Path("pipeline/data/reports/phase4-quality.json")
            with connect(config) as connection:
                report = run_collaboration_collection(
                    cohort,
                    client,
                    PostgresCollectionStore(connection),
                    hash_secret=config.hash_secret.get_secret_value(),
                    report_path=report_path,
                    pr_request_cap=args.pr_request_cap,
                    issue_request_cap=args.issue_request_cap,
                    repository_limit=args.limit,
                )
        except ValueError as error:
            parser.error(str(error))
        print(
            f"Collaboration report: {report_path}; "
            f"{report['repositories_processed']}/{report['repositories_requested']} "
            "repositories processed; "
            f"{report['repositories_failed']} failed; "
            f"PR requests {report['pr_requests_used_lifetime']}/{args.pr_request_cap} lifetime "
            f"(+{report['pr_requests_used']} this run); "
            f"issue requests {report['issue_requests_used_lifetime']}/{args.issue_request_cap} "
            f"lifetime (+{report['issue_requests_used']} this run)."
        )
        if report["repositories_failed"]:
            raise SystemExit(1)
    elif args.command == "validate":
        try:
            config = load_config(args.config)
            cohort = load_cohort(args.cohort)
            issue_screen = args.issue_screen if args.issue_screen.exists() else None
            with connect(config) as connection:
                report = build_quality_report(
                    cohort,
                    PostgresCollectionStore(connection),
                    report_path=args.report,
                    issue_screen_path=issue_screen,
                )
        except ValueError as error:
            parser.error(str(error))
        print(
            f"Validation report: {args.report}; "
            f"{report['repositories_complete']}/{report['repositories_expected']} repositories "
            f"complete; {report['repositories_flagged']} flagged."
        )
        if report["repositories_flagged"]:
            raise SystemExit(1)
    elif args.command == "build-snapshots":
        try:
            config = load_config(args.config)
            cohort = load_cohort(args.cohort)
            experiment = load_experiment_config(args.experiment)
            with connect(config) as connection:
                report = build_snapshots(
                    connection,
                    cohort,
                    experiment,
                    quality_report=args.quality_report,
                    report_path=args.report,
                )
        except ValueError as error:
            parser.error(str(error))
        print(
            f"Snapshot report: {args.report}; dataset {report['dataset_version_id']}; "
            f"{report['overall']['snapshots']} snapshots, {report['overall']['labeled']} labeled."
        )
    elif args.command == "build-features":
        if args.dataset_version_id is not None and args.dataset_version_id < 1:
            parser.error("--dataset-version-id must be at least 1")
        try:
            config = load_config(args.config)
            with connect(config) as connection:
                report = build_features(
                    connection,
                    dataset_version_id=args.dataset_version_id,
                    report_path=args.report,
                )
        except ValueError as error:
            parser.error(str(error))
        print(
            f"Feature report: {args.report}; feature set {report['feature_set_id']}; "
            f"{report['snapshots']} snapshots, {report['features']} features; "
            f"{report['labeled_train_validation_test_snapshots']} eligible labeled snapshots."
        )
    elif args.command == "train":
        if args.dataset_version_id is not None and args.dataset_version_id < 1:
            parser.error("--dataset-version-id must be at least 1")
        if args.feature_set_id is not None and args.feature_set_id < 1:
            parser.error("--feature-set-id must be at least 1")
        try:
            pipeline_config = load_config(args.config)
            modeling_config = load_modeling_config(args.model_config)
            with connect(pipeline_config) as connection:
                report = train_and_evaluate(
                    connection,
                    modeling_config,
                    dataset_version_id=args.dataset_version_id,
                    feature_set_id=args.feature_set_id,
                    report_path=args.report,
                )
        except ValueError as error:
            parser.error(str(error))
        selected = sum(model["selected"] for model in report["models"])
        print(
            f"Model report: {args.report}; dataset {report['dataset_version_id']}; "
            f"{len(report['models'])} model runs, {selected} selected feature-family models."
        )
    elif args.command in {"predict", "explain"}:
        if args.dataset_version_id is not None and args.dataset_version_id < 1:
            parser.error("--dataset-version-id must be at least 1")
        try:
            pipeline_config = load_config(args.config)
            with connect(pipeline_config) as connection:
                if args.command == "predict":
                    report = generate_predictions(
                        connection,
                        dataset_version_id=args.dataset_version_id,
                        report_path=args.report,
                    )
                    print(
                        f"Prediction report: {args.report}; model {report['model_version_id']}; "
                        f"{report['predicted_count']} predicted, {report['skipped_count']} skipped."
                    )
                else:
                    report = generate_explanations(
                        connection,
                        dataset_version_id=args.dataset_version_id,
                        report_path=args.report,
                    )
                    print(
                        f"Explanation report: {args.report}; model {report['model_version_id']}; "
                        f"{report['predictions_explained']} predictions explained."
                    )
        except (ValueError, OSError) as error:
            parser.error(str(error))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
