import json
import zipfile
from pathlib import Path
from src.config import ExperimentConfig
from src.release import ReleasePackager


def test_release_packager(tmp_path):
    # Setup dummy paths in config
    config = ExperimentConfig.load("config/experiment.yaml")
    config.paths.processed_dir = str(tmp_path / "processed")
    config.paths.release_dir = str(tmp_path / "release")
    config.paths.manifests_dir = str(tmp_path / "manifests")

    proc_dir = Path(config.paths.processed_dir)
    proc_dir.mkdir(parents=True)

    # Write dummy posts.jsonl
    posts_path = proc_dir / "posts.jsonl"
    record = {
        "id": "rel_001",
        "source": "gnews",
        "text": "Berita terkini seputar tahapan pemilu presiden 2024.",
        "author_username_hash": "anon_12345678",
        "published_at": "2024-02-14T08:00:00Z",
    }
    posts_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    packager = ReleasePackager(config)
    res = packager.export()

    rel_dir = Path(res["release_dir"])
    assert (rel_dir / "dataset.zip").exists()
    assert (rel_dir / "LICENSE").exists()
    assert (rel_dir / "README.md").exists()
    assert (rel_dir / "datasheet.md").exists()

    # Check zip contents
    with zipfile.ZipFile(res["zip_path"], "r") as zf:
        namelist = zf.namelist()
        assert "posts.jsonl" in namelist

    # Check license content
    license_content = (rel_dir / "LICENSE").read_text(encoding="utf-8")
    assert "Creative Commons Attribution-NonCommercial 4.0" in license_content

    # Check datasheet structure
    datasheet_content = (rel_dir / "datasheet.md").read_text(encoding="utf-8")
    assert "## 1. Motivation" in datasheet_content
    assert "## 2. Composition" in datasheet_content
    assert "## 3. Collection Process" in datasheet_content
    assert "## 4. Preprocessing" in datasheet_content
    assert "## 5. Uses" in datasheet_content
    assert "## 6. Distribution" in datasheet_content
    assert "## 7. Maintenance" in datasheet_content
