import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.config import ExperimentConfig
from src.anonymizer import Anonymizer
from src.cleaner import DataCleaner
from src.manifest import ManifestManager
from src.utils.rate_limiter import PoliteRateLimiter
from src.adapters.gnews import GoogleNewsAdapter
from src.adapters.reddit import RedditAdapter
from src.adapters.youtube import YouTubeAdapter
from src.adapters.meme import MemeAdapter
from src.adapters.meme_dataset_loader import MemeDatasetLoader

logger = logging.getLogger("scraper.pipeline")


class ScraperPipeline:
    """
    Master Scraping & Processing Orchestrator.
    Executes multi-source data ingestion, enforces filtering criteria,
    applies cryptographic anonymization, and generates execution manifests.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        config_path: str = "config/experiment.yaml",
        pilot_mode: bool = False,
        dry_run: bool = False,
        sources_filter: Optional[List[str]] = None,
    ):
        self.config = config
        self.config_path = config_path
        self.pilot_mode = pilot_mode
        self.dry_run = dry_run
        self.sources_filter = sources_filter

        # Core directories
        self.raw_dir = Path(config.paths.raw_dir)
        self.processed_dir = Path(config.paths.processed_dir)
        self.checkpoints_dir = Path(config.paths.checkpoints_dir)
        self.manifests_dir = Path(config.paths.manifests_dir)

        if not self.dry_run:
            self.raw_dir.mkdir(parents=True, exist_ok=True)
            self.processed_dir.mkdir(parents=True, exist_ok=True)
            self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
            self.manifests_dir.mkdir(parents=True, exist_ok=True)

        # Rate Limiter
        jitter = (0.1, 0.3) if self.pilot_mode else config.network.jitter_range_seconds
        self.rate_limiter = PoliteRateLimiter(
            requests_per_minute=config.network.rate_limit_per_minute,
            jitter_range=jitter,
            enabled=not self.dry_run,
        )

        # Anonymizer & Cleaner
        self.anonymizer = Anonymizer(config.ethics)
        self.cleaner = DataCleaner(config.preprocessing, config.temporal_window)
        self.manifest_mgr = ManifestManager(manifests_dir=str(self.manifests_dir))

        # Output Dataset Files
        self.processed_posts_file = self.processed_dir / "posts.jsonl"
        self.processed_memes_file = self.processed_dir / "memes.jsonl"

    def _init_adapters(self) -> Dict[str, Any]:
        """Initializes requested platform adapters."""
        adapters = {}
        all_sources = self.config.sources

        # 1. Google News
        if "gnews" in all_sources and (not self.sources_filter or "gnews" in self.sources_filter):
            adapters["gnews"] = GoogleNewsAdapter(
                name="gnews",
                config=all_sources["gnews"],
                rate_limiter=self.rate_limiter,
                checkpoints_dir=self.checkpoints_dir,
                dry_run=self.dry_run,
            )

        # 2. Reddit
        if "reddit" in all_sources and (not self.sources_filter or "reddit" in self.sources_filter):
            adapters["reddit"] = RedditAdapter(
                name="reddit",
                config=all_sources["reddit"],
                rate_limiter=self.rate_limiter,
                checkpoints_dir=self.checkpoints_dir,
                dry_run=self.dry_run,
            )

        # 3. YouTube
        if "youtube" in all_sources and (not self.sources_filter or "youtube" in self.sources_filter):
            adapters["youtube"] = YouTubeAdapter(
                name="youtube",
                config=all_sources["youtube"],
                rate_limiter=self.rate_limiter,
                checkpoints_dir=self.checkpoints_dir,
                dry_run=self.dry_run,
            )

        # 4. Memes
        if "memes" in all_sources and (not self.sources_filter or "memes" in self.sources_filter):
            adapters["memes"] = MemeAdapter(
                name="memes",
                config=all_sources["memes"],
                rate_limiter=self.rate_limiter,
                checkpoints_dir=self.checkpoints_dir,
                dry_run=self.dry_run,
                raw_img_dir=self.raw_dir / "memes",
                processed_img_dir=self.processed_dir / "memes",
            )

        # 5. Public Meme Datasets (Hugging Face / Open Access)
        if "meme_dataset" in all_sources or (self.sources_filter and "meme_dataset" in self.sources_filter):
            adapters["meme_dataset"] = MemeDatasetLoader(
                name="meme_dataset",
                config=all_sources.get("meme_dataset", {}),
                rate_limiter=self.rate_limiter,
                checkpoints_dir=self.checkpoints_dir,
                dry_run=self.dry_run,
                raw_img_dir=self.raw_dir / "memes",
                processed_img_dir=self.processed_dir / "memes",
                raw_dir=self.raw_dir / "external",
                processed_dir=self.processed_dir,
            )

        return adapters

    def run(self) -> Dict[str, Any]:
        """Executes the data collection and processing pipeline."""
        start_time = datetime.now(timezone.utc)
        timestamp_str = start_time.strftime("%Y%m%d_%H%M%S")
        run_id = f"run_{timestamp_str}"

        logger.info(f"========== Starting Scraper Run: {run_id} ==========")
        logger.info(f"Pilot Mode: {self.pilot_mode} | Dry Run: {self.dry_run}")

        adapters = self._init_adapters()
        stats_by_source: Dict[str, Any] = {}

        # Open processed output files in append mode if not dry run
        posts_out = open(self.processed_posts_file, "a", encoding="utf-8") if not self.dry_run else None
        memes_out = open(self.processed_memes_file, "a", encoding="utf-8") if not self.dry_run else None

        try:
            for source_name, adapter in adapters.items():
                logger.info(f"--> Harvesting from source: [{source_name.upper()}]")

                # Determine target limit
                if self.pilot_mode:
                    quota = self.config.quotas.pilot_sample_per_source
                else:
                    quota = self.config.quotas.platforms.get(source_name, {}).get("target", 100)

                raw_count = 0
                processed_count = 0
                rejected_count = 0
                rejection_reasons: Dict[str, int] = {}

                # Raw output file for audit
                raw_file_path = self.raw_dir / f"raw_{source_name}.jsonl"
                raw_out = open(raw_file_path, "a", encoding="utf-8") if not self.dry_run else None

                try:
                    for raw_record in adapter.fetch_records(limit=quota):
                        raw_count += 1

                        # Save raw audit record (with original unmodified fields)
                        if raw_out:
                            raw_out.write(json.dumps(raw_record, ensure_ascii=False) + "\n")
                            raw_out.flush()

                        # Evaluate Inclusion/Exclusion Criteria
                        is_valid, reason = self.cleaner.evaluate(raw_record)
                        if not is_valid:
                            rejected_count += 1
                            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                            # Clean up rejected processed and raw images
                            img_meta = raw_record.get("image_metadata") or {}
                            fname = img_meta.get("filename")
                            if fname:
                                p_img = self.processed_dir / "memes" / fname
                                r_img = self.raw_dir / "memes" / fname
                                for f in [p_img, r_img]:
                                    if f.exists():
                                        try:
                                            f.unlink()
                                        except Exception:
                                            pass
                            continue

                        # Apply Ethical Anonymization (SHA-256 + salt, PII scrub, strip fields)
                        clean_record = self.anonymizer.anonymize_record(raw_record)

                        # Write to processed datasets
                        if not self.dry_run:
                            line = json.dumps(clean_record, ensure_ascii=False) + "\n"
                            if source_name in ["memes", "meme_dataset"]:
                                memes_out.write(line)
                                memes_out.flush()
                            else:
                                posts_out.write(line)
                                posts_out.flush()

                        processed_count += 1

                finally:
                    if raw_out:
                        raw_out.close()
                    adapter.save_checkpoint()

                stats_by_source[source_name] = {
                    "raw_collected": raw_count,
                    "processed_accepted": processed_count,
                    "rejected": rejected_count,
                    "rejection_breakdown": rejection_reasons,
                }
                logger.info(
                    f"[{source_name.upper()}] Finished. Raw={raw_count}, Accepted={processed_count}, Rejected={rejected_count}"
                )

        finally:
            if posts_out:
                posts_out.close()
            if memes_out:
                memes_out.close()

        end_time = datetime.now(timezone.utc)
        logger.info(f"========== Scraping Run {run_id} Completed in {(end_time - start_time).total_seconds():.2f}s ==========")

        # Generate manifest if not dry run
        manifest_path = None
        if not self.dry_run:
            config_hash = self.config.compute_hash(self.config_path)
            manifest_path = self.manifest_mgr.create_manifest(
                run_id=run_id,
                start_time=start_time,
                end_time=end_time,
                config_hash=config_hash,
                parameters=self.config.model_dump(),
                stats_by_source=stats_by_source,
                dataset_files={
                    "processed_posts": self.processed_posts_file,
                    "processed_memes": self.processed_memes_file,
                },
            )
            logger.info(f"Manifest written to: {manifest_path}")

        return {
            "run_id": run_id,
            "manifest_path": str(manifest_path) if manifest_path else None,
            "stats": stats_by_source,
        }
