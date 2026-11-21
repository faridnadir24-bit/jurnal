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


def test_accept_political_meme(cleaner):
    rec = {
        "source": "meme_dataset",
        "caption": "Meme kocak respon debat capres cawapres pilpres 2024",
        "text": "Diskusi elektoral prabowo gibran anies ganjar mahfud di media sosial.",
        "author_username": "meme_creator",
        "published_at": "2024-02-14T12:00:00Z",
        "image_metadata": {"filename": "meme_capres.jpg"},
    }
    is_valid, reason = cleaner.evaluate(rec)
    assert is_valid is True
    assert reason is None


def test_reject_irrelevant_meme_cat(cleaner):
    rec = {
        "source": "meme_dataset",
        "caption": "Kucing lucu ini sangat menggemaskan saat tidur di atas kasur empuk.",
        "text": "Meme humor kucing lucu hari ini tidak ada kaitan sama sekali.",
        "author_username": "cat_lover",
        "published_at": "2024-02-14T12:00:00Z",
        "image_metadata": {"filename": "cat_meme.jpg"},
    }
    is_valid, reason = cleaner.evaluate(rec)
    assert is_valid is False
    assert reason == "IRRELEVANT_POLITICAL_CONTEXT"


def test_reject_empty_caption_meme(cleaner):
    rec = {
        "source": "meme_dataset",
        "caption": "",
        "text": "",
        "author_username": "user_empty",
        "published_at": "2024-02-14T12:00:00Z",
        "image_metadata": {"filename": "empty.jpg"},
    }
    is_valid, reason = cleaner.evaluate(rec)
    assert is_valid is False
    assert reason == "IRRELEVANT_POLITICAL_CONTEXT"


def test_reject_irrelevant_ocr_context_meme(cleaner):
    # False positive from CLIP (prob > 0.5) but OCR text is about days of the week ("Senin Selasa...")
    rec = {
        "source": "meme_dataset",
        "caption": "",
        "text": "",
        "author_username": "meme_user",
        "published_at": "2024-02-14T12:00:00Z",
        "image_metadata": {
            "filename": "monday_meme.jpg",
            "is_political_visual": True,
            "clip_political_prob": 0.88,
            "ocr_text": "Senin Selasa Rabu Kamis Jumat Sabtu Minggu libur selesai",
        },
    }
    is_valid, reason = cleaner.evaluate(rec)
    assert is_valid is False
    assert reason == "IRRELEVANT_OCR_CONTEXT"


def test_accept_meme_via_ocr_text(cleaner):
    # Meme with minimal caption but OCR text contains verified political election keyword
    rec = {
        "source": "meme_dataset",
        "caption": "",
        "text": "",
        "author_username": "meme_user",
        "published_at": "2024-02-14T12:00:00Z",
        "image_metadata": {
            "filename": "prabowo_meme.jpg",
            "is_political_visual": True,
            "clip_political_prob": 0.95,
            "ocr_text": "Ayo rakyat Indonesia nyoblos capres prabowo gibran pemilu 2024",
        },
    }
    is_valid, reason = cleaner.evaluate(rec)
    assert is_valid is True
    assert reason is None
    assert "Meme OCR:" in rec["text"]


def test_expanded_political_keywords_and_boundaries(cleaner):
    # Verify new election terms, candidate slang, and party names
    assert cleaner.contains_political_keyword("Dukungan penuh untuk paslon prabowo-gibran") is True
    assert cleaner.contains_political_keyword("Ayo kawal suara paslon AMIN di TPS") is True
    assert cleaner.contains_political_keyword("Caleg DPR kampanye dan bagi-bagi bansos") is True
    assert cleaner.contains_political_keyword("Perdebatan panas antara pendukung paslon 01 dan 02") is True
    assert cleaner.contains_political_keyword("Surat suara pilpres di coblos oleh warga") is True

    # Verify resistance to substring collisions and non-election topics
    assert cleaner.contains_political_keyword("Pemerintah menyarankan asupan vitamin harian") is False
    assert cleaner.contains_political_keyword("Warga panik saat mendengar suara sirine") is False
    assert cleaner.contains_political_keyword("Donald Trump mantan presiden Amerika Serikat") is False
    assert cleaner.contains_political_keyword("Makan siang di Marshanies Kitchen sangat lezat") is False


def test_reject_negative_keyword_memes(cleaner):
    # Reject poster buang sampah (even if visual prob high)
    rec_trash = {
        "source": "meme_dataset",
        "caption": "Gambar tersebut menunjukkan sebuah poster pesan tentang kebersihan dan membuang sampah pada tempatnya.",
        "text": "",
        "author_username": "user_trash",
        "published_at": "2024-02-14T12:00:00Z",
        "image_metadata": {
            "filename": "trash.jpg",
            "is_political_visual": True,
            "clip_political_prob": 0.99,
            "ocr_text": "ORANG SAMPAH Pada TEMPATNYA BUANG BIJAK",
        },
    }
    is_valid, reason = cleaner.evaluate(rec_trash)
    assert is_valid is False
    assert reason == "IRRELEVANT_POLITICAL_CONTEXT"



