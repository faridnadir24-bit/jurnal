import json
import logging
import statistics
from pathlib import Path
from typing import Dict, Any, List, Tuple
from PIL import Image
from src.manifest import compute_file_sha256, ManifestManager

logger = logging.getLogger("scraper.verifier")


class DatasetVerifier:
    """
    Dataset Integrity & Reproducibility Verifier.
    Performs cryptographic hash audits, schema validation, anonymity leak checks,
    and statistical distribution profiling across platforms and timelines.
    """

    def __init__(self, processed_dir: str = "data/processed", manifests_dir: str = "manifests"):
        self.processed_dir = Path(processed_dir)
        self.manifest_mgr = ManifestManager(manifests_dir=manifests_dir)

    def verify(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Runs comprehensive integrity, anonymity, and distribution checks.
        Returns: (success_status, detailed_report)
        """
        report = {
            "checks": {},
            "metrics": {},
            "anonymity_audit": {},
            "temporal_distribution": {},
            "source_distribution": {},
            "overall_status": "PENDING",
        }

        posts_file = self.processed_dir / "posts.jsonl"
        memes_file = self.processed_dir / "memes.jsonl"

        # Check 1: File Existence
        if not posts_file.exists():
            report["checks"]["files_exist"] = False
            report["overall_status"] = "FAILED (Missing posts.jsonl)"
            return False, report

        report["checks"]["files_exist"] = True

        # Check 2: Checksum Verification against Manifest
        latest_manifest = self.manifest_mgr.load_latest_manifest()
        if latest_manifest and "dataset_checksums" in latest_manifest:
            manifest_checksums = latest_manifest["dataset_checksums"]
            hash_verified = True
            mismatches = []

            if "processed_posts" in manifest_checksums:
                expected = manifest_checksums["processed_posts"]["sha256"]
                actual = compute_file_sha256(posts_file)
                if expected != actual:
                    hash_verified = False
                    mismatches.append(f"posts.jsonl expected {expected}, got {actual}")

            if memes_file.exists() and "processed_memes" in manifest_checksums:
                expected = manifest_checksums["processed_memes"]["sha256"]
                actual = compute_file_sha256(memes_file)
                if expected != actual:
                    hash_verified = False
                    mismatches.append(f"memes.jsonl expected {expected}, got {actual}")

            report["checks"]["manifest_checksums_match"] = hash_verified
            if not hash_verified:
                report["checks"]["checksum_mismatches"] = mismatches
        else:
            report["checks"]["manifest_checksums_match"] = "SKIPPED_NO_MANIFEST"

        # Check 3: Schema & Anonymity Audit on Text Posts
        post_count = 0
        sources_tally = {}
        dates_tally = {}
        lengths = []
        anonymity_violations = []

        with open(posts_file, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                post_count += 1
                try:
                    record = json.loads(line)
                except Exception as e:
                    anonymity_violations.append(f"Line {idx+1}: Invalid JSON ({e})")
                    continue

                # Audit raw username leak
                if "author_username" in record and record["author_username"]:
                    anonymity_violations.append(f"Line {idx+1}: Unhashed author_username found!")

                # Audit anonymized hash prefix
                author_hash = record.get("author_username_hash", "")
                if not str(author_hash).startswith("anon_"):
                    anonymity_violations.append(f"Line {idx+1}: Missing 'anon_' prefix in author hash: {author_hash}")

                # Check for sensitive stripped fields
                for sensitive in ["author_email", "phone_number", "author_ip"]:
                    if sensitive in record:
                        anonymity_violations.append(f"Line {idx+1}: Sensitive field '{sensitive}' leaked!")

                # Source tally
                src = record.get("source", "unknown")
                sources_tally[src] = sources_tally.get(src, 0) + 1

                # Date tally (Month-level)
                dt = record.get("published_at")
                if dt:
                    month_key = dt[:7]
                    dates_tally[month_key] = dates_tally.get(month_key, 0) + 1

                # Length metrics
                text = record.get("text", "")
                lengths.append(len(text))

        report["anonymity_audit"]["total_violations"] = len(anonymity_violations)
        report["anonymity_audit"]["violations_sample"] = anonymity_violations[:5]
        report["source_distribution"] = sources_tally
        report["temporal_distribution"] = dict(sorted(dates_tally.items()))

        if lengths:
            report["metrics"]["total_posts"] = post_count
            report["metrics"]["min_length"] = min(lengths)
            report["metrics"]["max_length"] = max(lengths)
            report["metrics"]["mean_length"] = round(statistics.mean(lengths), 1)
            report["metrics"]["median_length"] = statistics.median(lengths)

        # Check 4: Multimodal Meme Integrity
        meme_count = 0
        corrupt_images = 0
        if memes_file.exists():
            with open(memes_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    meme_count += 1
                    try:
                        meme_rec = json.loads(line)
                        img_meta = meme_rec.get("image_metadata", {})
                        rel_path = img_meta.get("relative_path")
                        if rel_path:
                            full_img_path = self.processed_dir / rel_path
                            if not full_img_path.exists():
                                corrupt_images += 1
                                continue
                            # Verify image can be opened and dimensions match
                            with Image.open(full_img_path) as im:
                                if im.width < 100 or im.height < 100:
                                    corrupt_images += 1
                    except Exception:
                        corrupt_images += 1

            report["metrics"]["total_memes"] = meme_count
            report["checks"]["corrupt_or_missing_images"] = corrupt_images
        else:
            report["metrics"]["total_memes"] = 0

        # Overall Status Determination
        is_success = (
            report["checks"]["files_exist"]
            and len(anonymity_violations) == 0
            and corrupt_images == 0
            and post_count > 0
        )

        report["overall_status"] = "PASSED" if is_success else "FAILED"
        return is_success, report

    def print_summary(self, success: bool, report: Dict[str, Any]) -> None:
        """Prints a human-readable and reviewer-friendly audit report."""
        print("\n" + "=" * 65)
        print("         ACADEMIC DATASET INTEGRITY & VERIFICATION REPORT")
        print("=" * 65)
        print(f"Overall Status          : {'[PASS] PASSED' if success else '[FAIL] FAILED'}")
        print(f"Total Text Posts        : {report.get('metrics', {}).get('total_posts', 0)}")
        print(f"Total Multimodal Memes  : {report.get('metrics', {}).get('total_memes', 0)}")
        print(f"Anonymity Violations    : {report.get('anonymity_audit', {}).get('total_violations', 0)}")
        print(f"Corrupt Images          : {report.get('checks', {}).get('corrupt_or_missing_images', 0)}")
        print("-" * 65)
        print("Distribution by Platform Source:")
        for src, count in report.get("source_distribution", {}).items():
            print(f"  - {src:<15}: {count:>6} items")
        print("-" * 65)
        print("Temporal Distribution (Timeline):")
        for month, count in report.get("temporal_distribution", {}).items():
            print(f"  - {month:<15}: {count:>6} items")
        print("-" * 65)
        if "mean_length" in report.get("metrics", {}):
            m = report["metrics"]
            print(f"Text Length Profile (chars): Min={m['min_length']}, Mean={m['mean_length']}, Median={m['median_length']}, Max={m['max_length']}")
        print("=" * 65 + "\n")
