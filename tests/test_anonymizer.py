import pytest
from src.config import EthicsConfig
from src.anonymizer import Anonymizer


@pytest.fixture
def anonymizer():
    ethics = EthicsConfig(
        anonymization_algorithm="SHA-256",
        salt="test_secret_salt_12345",
        strip_fields=["author_email", "author_ip", "phone_number"],
        anonymize_fields=["author_username", "author_id"],
        scrub_text_pii={"enabled": True},
    )
    return Anonymizer(ethics)


def test_hash_identifier_deterministic(anonymizer):
    h1 = anonymizer.hash_identifier("anies_fan123")
    h2 = anonymizer.hash_identifier("anies_fan123")
    h3 = anonymizer.hash_identifier("prabowo_supporter")

    assert h1 == h2
    assert h1 != h3
    assert h1.startswith("anon_")


def test_scrub_text_pii(anonymizer):
    text = "Hubungi posko pemilu di 081234567890 atau email kami di timses@pemilu2024.id dan mention @relawan_ganjar"
    scrubbed = anonymizer.scrub_text(text)

    assert "081234567890" not in scrubbed
    assert "[REDACTED_PHONE]" in scrubbed
    assert "timses@pemilu2024.id" not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "@relawan_ganjar" not in scrubbed
    assert "@anon_" in scrubbed


def test_anonymize_record(anonymizer):
    record = {
        "id": "post_001",
        "author_username": "budi_santoso",
        "author_email": "budi@gmail.com",
        "author_ip": "192.168.1.1",
        "text": "Diskusi debat capres 2024 sangat seru dan mencerahkan.",
    }
    anonymized = anonymizer.anonymize_record(record)

    # Sensitive fields stripped
    assert "author_email" not in anonymized
    assert "author_ip" not in anonymized
    assert "author_username" not in anonymized

    # Pseudonymized hash added
    assert "author_username_hash" in anonymized
    assert anonymized["author_username_hash"].startswith("anon_")
    assert anonymized["is_anonymized"] is True
    assert anonymized["anonymization_method"] == "SHA-256+Salt"
