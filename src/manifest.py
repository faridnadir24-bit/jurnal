import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


def get_git_info() -> Dict[str, Any]:
    """Retrieves current Git commit SHA and working tree status."""
    try:
        # Check git commit hash
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()

        # Check if dirty
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        is_dirty = len(status) > 0

        # Branch
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()

        return {
            "commit_hash": commit,
            "branch": branch,
            "is_dirty": is_dirty,
        }
    except Exception:
        return {
            "commit_hash": "unversioned_git_repo",
            "branch": "unknown",
            "is_dirty": True,
        }


def compute_file_sha256(filepath: Path) -> Optional[str]:
    """Calculates SHA-256 checksum of a file for academic verification."""
    if not filepath.exists() or not filepath.is_file():
        return None

    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


class ManifestManager:
    """Creates, saves, and verifies run manifests for experiment reproducibility."""

    def __init__(self, manifests_dir: str = "manifests"):
        self.manifests_dir = Path(manifests_dir)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)

    def create_manifest(
        self,
        run_id: str,
        start_time: datetime,
        end_time: datetime,
        config_hash: str,
        parameters: Dict[str, Any],
        stats_by_source: Dict[str, Any],
        dataset_files: Dict[str, Path],
    ) -> Path:
        """Generates manifests/run_{timestamp}.json."""
        # Calculate checksums of generated dataset files
        dataset_checksums = {}
        for key, path in dataset_files.items():
            if path.exists():
                dataset_checksums[key] = {
                    "path": str(path.as_posix()),
                    "sha256": compute_file_sha256(path),
                    "size_bytes": path.stat().st_size,
                }

        manifest_data = {
            "run_id": run_id,
            "experiment_title": parameters.get("experiment", {}).get("title"),
            "timestamps": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration_seconds": round((end_time - start_time).total_seconds(), 2),
            },
            "code_version": get_git_info(),
            "config_sha256": config_hash,
            "parameters": {
                "temporal_window": parameters.get("temporal_window"),
                "sources_queried": parameters.get("sources"),
                "preprocessing_criteria": parameters.get("preprocessing"),
                "ethics_criteria": parameters.get("ethics"),
            },
            "statistics_by_source": stats_by_source,
            "dataset_checksums": dataset_checksums,
            "environment": {
                "python_version": sys.version,
                "platform": platform.platform(),
                "os": platform.system(),
            },
        }

        output_path = self.manifests_dir / f"{run_id}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)

        return output_path

    def load_latest_manifest(self) -> Optional[Dict[str, Any]]:
        """Loads the most recent manifest for verification."""
        manifest_files = sorted(self.manifests_dir.glob("run_*.json"))
        if not manifest_files:
            return None
        with open(manifest_files[-1], "r", encoding="utf-8") as f:
            return json.load(f)
