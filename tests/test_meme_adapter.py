import json
import pytest
from pathlib import Path
from src.adapters.meme import MemeAdapter
from src.utils.rate_limiter import PoliteRateLimiter


@pytest.fixture
def meme_adapter(tmp_path):
    raw_dir = tmp_path / "raw_memes"
    proc_dir = tmp_path / "proc_memes"
    ck_dir = tmp_path / "checkpoints"

    limiter = PoliteRateLimiter(requests_per_minute=60, enabled=False)
    adapter = MemeAdapter(
        raw_img_dir=raw_dir,
        processed_img_dir=proc_dir,
        name="memes",
        config={
            "subreddits": ["indonesiameme", "indonesia"],
            "client_id": "mock_id",
            "client_secret": "mock_secret",
            "user_agent": "TestBot/1.0",
        },
        rate_limiter=limiter,
        checkpoints_dir=ck_dir,
        dry_run=False,
    )
    return adapter


def test_keyword_filtering(meme_adapter):
    # Matches any of: 'pemilu', 'pilpres', 'capres', 'ganjar', 'prabowo', 'anies'
    assert len(meme_adapter._matches_keywords("Meme debat pilpres kemarin malam", "")) > 0
    assert len(meme_adapter._matches_keywords("Capres pilihan rakyat", "")) > 0
    assert len(meme_adapter._matches_keywords("Reaksi saat liat pak prabowo joget", "")) > 0
    assert len(meme_adapter._matches_keywords("", "Pidato anies soal kebijakan publik")) > 0
    assert len(meme_adapter._matches_keywords("Program kerja ganjar mahfud", "")) > 0
    assert len(meme_adapter._matches_keywords("Bansos dan pemilu 2024", "")) > 0

    # Non-political posts rejected
    assert len(meme_adapter._matches_keywords("Kucing comel di pinggir jalan", "Makan ikan")) == 0
    assert len(meme_adapter._matches_keywords("Info loker IT Jakarta", "Dicari backend dev")) == 0


def test_direct_image_url_filtering(meme_adapter):
    # Direct image URLs (.jpg, .png, .jpeg) accepted
    assert meme_adapter._is_direct_image_url("https://i.redd.it/sample_image.jpg") is True
    assert meme_adapter._is_direct_image_url("https://i.redd.it/meme_pemilu.PNG") is True
    assert meme_adapter._is_direct_image_url("https://i.imgur.com/prabowo_anies.jpeg") is True
    assert meme_adapter._is_direct_image_url("https://i.redd.it/pic.jpg?width=960&crop=smart") is True

    # Non-direct image URLs rejected
    assert meme_adapter._is_direct_image_url("https://www.reddit.com/r/indonesia/comments/123/meme/") is False
    assert meme_adapter._is_direct_image_url("https://v.redd.it/video_clip_123") is False
    assert meme_adapter._is_direct_image_url("https://imgur.com/gallery/album123") is False
    assert meme_adapter._is_direct_image_url("https://youtube.com/watch?v=abc") is False
    assert meme_adapter._is_direct_image_url("") is False


def test_parse_gallery_dl_companion_metadata(meme_adapter, tmp_path):
    # Create companion JSON and image file as produced by gallery-dl --write-metadata
    img_file = meme_adapter.raw_img_dir / "sample_meme_123.jpg"
    img_file.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01test_image_data")

    json_file = meme_adapter.raw_img_dir / "sample_meme_123.jpg.json"
    meta_content = {
        "id": "post_123",
        "title": "Meme lucu debat capres 2024 putaran kedua",
        "author": "redditor_indonesia",
        "score": 350,
        "num_comments": 42,
        "date": "2024-01-08 14:30:00",
        "url": "https://i.redd.it/sample_meme_123.jpg",
    }
    json_file.write_text(json.dumps(meta_content), encoding="utf-8")

    record = meme_adapter._parse_gallery_dl_metadata(json_file)

    assert record is not None
    assert record["id"] == "gdl_post_123"
    assert record["title"] == "Meme lucu debat capres 2024 putaran kedua"
    assert record["published_at"] == "2024-01-08T14:30:00Z"
    assert record["engagement"]["upvotes"] == 350
    assert record["engagement"]["comments"] == 42
    assert record["image_metadata"]["filename"] == "sample_meme_123.jpg"
    assert len(record["image_metadata"]["sha256"]) == 64

    # Verify mirrored to processed directory
    assert (meme_adapter.processed_img_dir / "sample_meme_123.jpg").exists()
