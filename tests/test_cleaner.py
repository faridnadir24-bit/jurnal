import pytest
from src.config import PreprocessingConfig, TemporalWindowConfig
from src.cleaner import DataCleaner


@pytest.fixture
def cleaner():
    prep = PreprocessingConfig(
        min_char_length=15,
        max_char_length=500,
        drop_retweet_syntax=True,
        drop_url_only_posts=True,
        drop_duplicates=True,
        language_filtering={
            "enabled": True,
            "indonesian_markers": ["dan", "yang", "di", "pemilu", "pilpres", "capres", "kita"],
        },
        bot_blacklist=["AutoModerator", "RemindMeBot"],
    )
    temp = TemporalWindowConfig(
        start_date="2023-10-01",
        end_date="2024-04-30",
    )
    return DataCleaner(prep, temp)


def test_valid_record(cleaner):
    rec = {
        "text": "Diskusi yang sangat menarik tentang visi misi capres dan cawapres kita.",
        "author_username": "warga_demokrasi",
        "published_at": "2024-01-15T12:00:00Z",
    }
    is_valid, reason = cleaner.evaluate(rec)
    assert is_valid is True
    assert reason is None


def test_reject_short_text(cleaner):
    rec = {
        "text": "Setuju!",
        "author_username": "user1",
    }
    is_valid, reason = cleaner.evaluate(rec)
    assert is_valid is False
    assert "TEXT_TOO_SHORT" in reason


def test_reject_retweet(cleaner):
    rec = {
        "text": "RT @timses_capres: Ayo kawal suara pemilu dan jangan lupa ke TPS kita.",
        "author_username": "user1",
    }
    is_valid, reason = cleaner.evaluate(rec)
    assert is_valid is False
    assert "EXCLUDED_RETWEET_SYNTAX" in reason


def test_reject_url_only(cleaner):
    rec = {
        "text": "https://news.detik.com/pemilu2024/berita-terbaru-lengkap-hari-ini",
        "author_username": "user1",
    }
    is_valid, reason = cleaner.evaluate(rec)
    assert is_valid is False
    assert "URL_ONLY_WITHOUT_COMMENTARY" in reason


def test_reject_bot_account(cleaner):
    rec = {
        "text": "Ini adalah pengumuman otomatis yang dibuat untuk mengingatkan pemilu.",
        "author_username": "AutoModerator",
    }
    is_valid, reason = cleaner.evaluate(rec)
    assert is_valid is False
    assert "BOT_BLACKLIST_MATCH" in reason


def test_reject_outside_temporal_window(cleaner):
    rec = {
        "text": "Catatan sejarah tentang pelaksanaan pemilu yang berlangsung di Indonesia.",
        "author_username": "user1",
        "published_at": "2022-01-01T00:00:00Z",
    }
    is_valid, reason = cleaner.evaluate(rec)
    assert is_valid is False
    assert "OUTSIDE_TEMPORAL_WINDOW" in reason


def test_reject_duplicate_content(cleaner):
    rec1 = {
        "text": "Penting sekali bagi kita semua untuk menjaga perdamaian selama pemilu berlangsung.",
        "author_username": "user1",
    }
    rec2 = {
        "text": "Penting sekali bagi kita semua untuk menjaga perdamaian selama pemilu berlangsung!!!",
        "author_username": "user2",
    }
    valid1, _ = cleaner.evaluate(rec1)
    valid2, reason2 = cleaner.evaluate(rec2)
    assert valid1 is True
    assert valid2 is False
    assert "DUPLICATE_CONTENT" in reason2
