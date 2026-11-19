import json
from pathlib import Path
from src.verifier import DatasetVerifier
from src.manifest import ManifestManager


def test_verifier_missing_files(tmp_path):
    proc_dir = tmp_path / "processed"
    proc_dir.mkdir(parents=True)
    man_dir = tmp_path / "manifests"
    man_dir.mkdir(parents=True)

    verifier = DatasetVerifier(processed_dir=str(proc_dir), manifests_dir=str(man_dir))
    passed, report = verifier.verify()
    assert passed is False
    assert report["checks"]["files_exist"] is False


def test_verifier_valid_dataset(tmp_path):
    proc_dir = tmp_path / "processed"
    proc_dir.mkdir(parents=True)
    man_dir = tmp_path / "manifests"
    man_dir.mkdir(parents=True)

    # Create valid posts.jsonl
    posts_path = proc_dir / "posts.jsonl"
    record = {
        "id": "p001",
        "source": "youtube",
        "text": "Diskusi debat capres yang sangat substantif dan mendidik bagi kita.",
        "author_username_hash": "anon_abcdef123456",
        "published_at": "2024-01-15T12:00:00Z",
        "is_anonymized": True,
    }
    posts_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    verifier = DatasetVerifier(processed_dir=str(proc_dir), manifests_dir=str(man_dir))
    passed, report = verifier.verify()

    assert passed is True
    assert report["overall_status"] == "PASSED"
    assert report["metrics"]["total_posts"] == 1
    assert report["anonymity_audit"]["total_violations"] == 0


def test_verifier_detects_anonymity_leak(tmp_path):
    proc_dir = tmp_path / "processed"
    proc_dir.mkdir(parents=True)
    man_dir = tmp_path / "manifests"
    man_dir.mkdir(parents=True)

    # Post with leaked author_username
    posts_path = proc_dir / "posts.jsonl"
    leaked_record = {
        "id": "p002",
        "source": "reddit",
        "author_username": "real_unhashed_user",
        "author_username_hash": "anon_abcdef123456",
        "text": "Teks diskusi politik pemilu 2024.",
        "published_at": "2024-01-15T12:00:00Z",
    }
    posts_path.write_text(json.dumps(leaked_record) + "\n", encoding="utf-8")

    verifier = DatasetVerifier(processed_dir=str(proc_dir), manifests_dir=str(man_dir))
    passed, report = verifier.verify()

    assert passed is False
    assert report["anonymity_audit"]["total_violations"] > 0
