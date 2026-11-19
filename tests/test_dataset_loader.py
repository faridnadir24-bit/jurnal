import json
import pytest
from pathlib import Path
import pandas as pd
from src.adapters.dataset_loader import DatasetLoader


@pytest.fixture
def dataset_loader(tmp_path):
    raw_dir = tmp_path / "raw_ext"
    proc_dir = tmp_path / "proc"
    img_dir = tmp_path / "memes"
    return DatasetLoader(raw_dir=raw_dir, processed_dir=proc_dir, images_dir=img_dir)


def test_extract_csv_to_jsonl(dataset_loader, tmp_path):
    # Create sample CSV resembling Hugging Face / Kaggle election datasets
    sample_csv = tmp_path / "pemilu_sample.csv"
    df = pd.DataFrame([
        {
            "caption": "Meme reaksi debat capres ketiga pertahanan dan keamanan",
            "tanggal": "2024-01-08 12:00:00",
            "jumlah_like": 540,
            "author": "analis_politik",
            "image_url": "https://example.com/memes/capres_debat.jpg",
        },
        {
            "caption": "Bansos turun jelang pilpres menjadi perbincangan warganet",
            "tanggal": "2024-02-05 09:30:00",
            "jumlah_like": 890,
            "author": "netizen_kritis",
            "image_url": "https://example.com/memes/bansos_pilpres.jpg",
        },
    ])
    df.to_csv(sample_csv, index=False)

    out_jsonl = tmp_path / "output.jsonl"
    count = dataset_loader.extract_to_jsonl(sample_csv, out_jsonl, source_name="huggingface_pemilu")

    assert count == 2
    assert out_jsonl.exists()

    # Read extracted jsonl records
    lines = [json.loads(l) for l in out_jsonl.read_text(encoding="utf-8").strip().split("\n")]
    assert len(lines) == 2

    # Verify temporal metadata and engagement preserved
    rec1 = lines[0]
    assert "Meme reaksi debat capres" in rec1["caption"]
    assert rec1["published_at"] == "2024-01-08T12:00:00Z"
    assert rec1["engagement"]["upvotes"] == 540
    assert rec1["image_metadata"]["direct_url"] == "https://example.com/memes/capres_debat.jpg"

    rec2 = lines[1]
    assert rec2["published_at"] == "2024-02-05T09:30:00Z"
    assert rec2["engagement"]["upvotes"] == 890


def test_extract_jsonl_to_jsonl(dataset_loader, tmp_path):
    sample_jsonl = tmp_path / "sample_memes.jsonl"
    item = {
        "caption": "Desak Anies vs Tabrak Prof vs Gemoy Prabowo",
        "published_at": "2024-01-20T15:00:00Z",
        "engagement": {"upvotes": 1200, "comments": 85},
        "author": "indonesiameme_creator",
    }
    sample_jsonl.write_text(json.dumps(item) + "\n", encoding="utf-8")

    out_jsonl = tmp_path / "final.jsonl"
    count = dataset_loader.extract_to_jsonl(sample_jsonl, out_jsonl, source_name="kaggle_memes")

    assert count == 1
    extracted = json.loads(out_jsonl.read_text(encoding="utf-8").strip())
    assert extracted["published_at"] == "2024-01-20T15:00:00Z"
    assert extracted["engagement"]["upvotes"] == 1200
    assert extracted["engagement"]["comments"] == 85
