#!/usr/bin/env python3
"""
Standalone release packaging script for Zenodo / Figshare repository deposit.
Generates:
  - data/release/dataset.zip
  - data/release/README.md
  - data/release/LICENSE (CC-BY-NC 4.0)
  - data/release/datasheet.md (Datasheets for Datasets)
"""

import sys
import argparse
from pathlib import Path
from src.config import ExperimentConfig
from src.release import ReleasePackager
from src.verifier import DatasetVerifier
from src.utils.logger import setup_logger

logger = setup_logger("release_tool")


def main():
    parser = argparse.ArgumentParser(
        description="Package curated Pemilu 2024 political polarization dataset for Zenodo / Figshare."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/experiment.yaml",
        help="Path to experiment configuration YAML file (default: config/experiment.yaml)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip integrity and anonymity pre-verification check before packaging",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path.resolve()}")
        sys.exit(1)

    config = ExperimentConfig.load(str(config_path))

    # Pre-verification check
    if not args.no_verify:
        logger.info("Running pre-flight dataset verification before export...")
        verifier = DatasetVerifier(
            processed_dir=config.paths.processed_dir,
            manifests_dir=config.paths.manifests_dir,
        )
        passed, report = verifier.verify()
        verifier.print_summary(passed, report)

        if not passed:
            logger.error("Pre-release verification failed! Fix dataset errors before releasing.")
            sys.exit(1)

    logger.info("Packaging dataset for publication release...")
    packager = ReleasePackager(config)
    result = packager.export()

    print("\n" + "=" * 65)
    print("      DATASET RELEASE PACKAGE CREATED SUCCESSFULLY")
    print("=" * 65)
    print(f"Target Directory : {result['release_dir']}")
    print(f"Zip Archive      : {result['zip_path']}")
    print(f"Zip SHA-256      : {result['zip_sha256']}")
    print(f"Zip Size (Bytes) : {result['zip_size_bytes']:,}")
    print(f"License File     : {result['license_file']}")
    print(f"Datasheet File   : {result['datasheet_file']}")
    print(f"README File      : {result['readme_file']}")
    print("=" * 65)
    print("\nThe dataset is now 100% ready for upload to Zenodo or Figshare.\n")


if __name__ == "__main__":
    main()
