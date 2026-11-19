#!/usr/bin/env python3
"""
Master CLI Entrypoint for Academic Multi-Source Political Polarization Scraper.
Supports reproducible pipeline execution, pilot sampling, integrity verification,
and publication packaging.
"""

import sys
import argparse
from pathlib import Path
from src.config import ExperimentConfig
from src.pipeline import ScraperPipeline
from src.verifier import DatasetVerifier
from src.release import ReleasePackager
from src.utils.logger import setup_logger

logger = setup_logger("main")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Source Scraper for Indonesian Political Polarization Research (Pemilu 2024)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/experiment.yaml",
        help="Path to YAML experiment configuration file (default: config/experiment.yaml)",
    )
    parser.add_argument(
        "--source",
        type=str,
        nargs="+",
        choices=["youtube", "reddit", "gnews", "memes"],
        help="Specific source(s) to harvest. Defaults to all enabled sources in config.",
    )
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="Run pilot mode with a small quota (e.g., 50 per platform) for validation & smoke testing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate scraping and evaluation without writing dataset files or manifests to disk.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Audit and verify processed dataset integrity, manifest checksums, schema, and anonymity.",
    )
    parser.add_argument(
        "--export-release",
        action="store_true",
        help="Generate Zenodo/Figshare publication bundle (dataset.zip + README + LICENSE + datasheet.md).",
    )

    args = parser.parse_args()

    # Load and validate experiment config
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path.resolve()}")
        sys.exit(1)

    try:
        config = ExperimentConfig.load(str(config_path))
    except Exception as e:
        logger.error(f"Failed to parse experiment configuration: {e}")
        sys.exit(1)

    # 1. Action: Dataset Verification (--verify)
    if args.verify:
        logger.info("Executing dataset verification and integrity audit...")
        verifier = DatasetVerifier(
            processed_dir=config.paths.processed_dir,
            manifests_dir=config.paths.manifests_dir,
        )
        passed, report = verifier.verify()
        verifier.print_summary(passed, report)
        sys.exit(0 if passed else 1)

    # 2. Action: Export Publication Release (--export-release)
    if args.export_release:
        logger.info("Exporting publication release package...")
        # Verify first
        verifier = DatasetVerifier(
            processed_dir=config.paths.processed_dir,
            manifests_dir=config.paths.manifests_dir,
        )
        passed, report = verifier.verify()
        if not passed:
            logger.warning("Dataset verification flagged issues. Printing report before export:")
            verifier.print_summary(passed, report)

        packager = ReleasePackager(config)
        res = packager.export()
        print("\n" + "=" * 65)
        print("          PUBLICATION RELEASE PACKAGE GENERATED")
        print("=" * 65)
        print(f"Directory   : {res['release_dir']}")
        print(f"Zip Archive : {res['zip_path']} ({res['zip_size_bytes']:,} bytes)")
        print(f"Zip SHA256  : {res['zip_sha256']}")
        print(f"License     : {res['license_file']}")
        print(f"Datasheet   : {res['datasheet_file']}")
        print(f"README      : {res['readme_file']}")
        print("=" * 65 + "\n")
        sys.exit(0)

    # 3. Action: Run Scraping Pipeline
    pipeline = ScraperPipeline(
        config=config,
        config_path=str(config_path),
        pilot_mode=args.pilot,
        dry_run=args.dry_run,
        sources_filter=args.source,
    )
    summary = pipeline.run()

    print("\n" + "=" * 65)
    print("                 PIPELINE RUN SUMMARY")
    print("=" * 65)
    print(f"Run ID        : {summary['run_id']}")
    print(f"Manifest File : {summary['manifest_path'] or 'None (Dry Run)'}")
    print("-" * 65)
    print("Platform Statistics:")
    for src, stats in summary["stats"].items():
        print(f"  [{src.upper()}] Raw: {stats['raw_collected']} | Accepted: {stats['processed_accepted']} | Rejected: {stats['rejected']}")
        if stats["rejection_breakdown"]:
            for reason, cnt in stats["rejection_breakdown"].items():
                print(f"       -> Rejection: {reason} ({cnt})")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
