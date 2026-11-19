import json
from datetime import datetime, timezone
from pathlib import Path
from src.manifest import ManifestManager, compute_file_sha256, get_git_info


def test_git_info():
    info = get_git_info()
    assert "commit_hash" in info
    assert "branch" in info
    assert "is_dirty" in info


def test_compute_file_sha256(tmp_path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("Hello Indonesian Pemilu 2024 Research!", encoding="utf-8")

    h = compute_file_sha256(test_file)
    assert h is not None
    assert len(h) == 64


def test_create_and_load_manifest(tmp_path):
    manifests_dir = tmp_path / "manifests"
    mgr = ManifestManager(manifests_dir=str(manifests_dir))

    sample_dataset = tmp_path / "posts.jsonl"
    sample_dataset.write_text('{"id": "p1"}\n', encoding="utf-8")

    start_time = datetime.now(timezone.utc)
    end_time = datetime.now(timezone.utc)

    manifest_path = mgr.create_manifest(
        run_id="run_test_001",
        start_time=start_time,
        end_time=end_time,
        config_hash="abc123hash",
        parameters={"experiment": {"title": "Test Title"}},
        stats_by_source={"youtube": {"raw": 10, "accepted": 8}},
        dataset_files={"processed_posts": sample_dataset},
    )

    assert manifest_path.exists()
    latest = mgr.load_latest_manifest()
    assert latest is not None
    assert latest["run_id"] == "run_test_001"
    assert latest["experiment_title"] == "Test Title"
    assert "dataset_checksums" in latest
    assert "processed_posts" in latest["dataset_checksums"]
