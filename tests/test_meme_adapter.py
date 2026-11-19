import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.adapters.meme import MemeAdapter
from src.utils.rate_limiter import PoliteRateLimiter
import requests


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


def test_download_handles_http_error_gracefully(meme_adapter):
    # Mock requests.get raising an HTTP error
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error")
        mock_get.return_value = mock_response

        result = meme_adapter._download_original_image("https://i.redd.it/broken_link.jpg", "post_error_001")

        # Returns None on HTTP error (NEVER creates a dummy image)
        assert result is None
        # Verify no files were created in data/raw/memes
        assert not (meme_adapter.raw_img_dir / "post_error_001.jpg").exists()


def test_download_success_saves_genuine_image(meme_adapter):
    # Mock valid byte content representing a real image
    fake_image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRreal_image_bytes"

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.iter_content.return_value = [fake_image_bytes]
        mock_get.return_value = mock_response

        meta = meme_adapter._download_original_image("https://i.redd.it/genuine_meme.png", "post_success_100")

        assert meta is not None
        assert meta["filename"] == "post_success_100.png"
        assert meta["format"] == "PNG"
        assert len(meta["sha256"]) == 64

        # Real file saved in raw_img_dir
        saved_raw = meme_adapter.raw_img_dir / "post_success_100.png"
        assert saved_raw.exists()
        assert saved_raw.read_bytes() == fake_image_bytes
