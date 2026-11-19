import hashlib
import re
from typing import Dict, Any, List, Optional
from src.config import EthicsConfig


class Anonymizer:
    """
    Academic Data Ethics Anonymizer.
    Enforces pseudonymization via SHA-256 with cryptographic salt,
    strips sensitive metadata, and scrubs in-text PII (phone numbers, emails, handles).
    """

    def __init__(self, config: EthicsConfig):
        self.salt = config.salt
        self.algorithm = config.anonymization_algorithm
        self.strip_fields = set(config.strip_fields)
        self.anonymize_fields = set(config.anonymize_fields)
        self.scrub_pii_enabled = config.scrub_text_pii.get("enabled", True)

        # Regex patterns for Indonesian and general PII scrubbing
        self.phone_regex = re.compile(
            r"(\+62|62|0)8[1-9][0-9]{7,11}\b", re.IGNORECASE
        )
        self.email_regex = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
        )
        self.mention_regex = re.compile(
            r"@([A-Za-z0-9_]{3,25})\b"
        )

    def hash_identifier(self, identifier: Optional[str]) -> str:
        """
        Hashes an identifier using SHA-256 + salt.
        Returns a deterministic pseudonym e.g., 'anon_usr_3f4b8a91c2...'.
        Maintains consistent pseudonymization across the dataset for social network graph analysis.
        """
        if not identifier or identifier in ["[deleted]", "[removed]", "None"]:
            return "anon_usr_anonymous"

        salted_input = f"{self.salt}:{identifier.strip().lower()}".encode("utf-8")
        hash_digest = hashlib.sha256(salted_input).hexdigest()
        return f"anon_{hash_digest[:16]}"

    def scrub_text(self, text: str) -> str:
        """Removes emails, phone numbers, and pseudonymizes @mentions in post text."""
        if not text:
            return ""

        # Replace phone numbers
        text = self.phone_regex.sub("[REDACTED_PHONE]", text)

        # Replace email addresses
        text = self.email_regex.sub("[REDACTED_EMAIL]", text)

        # Pseudonymize social media mentions
        def replace_mention(match: re.Match) -> str:
            username = match.group(1)
            return f"@{self.hash_identifier(username)}"

        text = self.mention_regex.sub(replace_mention, text)
        return text

    def anonymize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Processes a single record for ethical academic release."""
        cleaned = dict(record)

        # 1. Strip sensitive metadata fields completely
        for field in self.strip_fields:
            cleaned.pop(field, None)

        # 2. Pseudonymize author identifiers
        for field in self.anonymize_fields:
            if field in cleaned and cleaned[field]:
                raw_val = str(cleaned[field])
                cleaned[f"{field}_hash"] = self.hash_identifier(raw_val)
                # Remove the raw identifier
                cleaned.pop(field, None)

        # 3. Scrub in-text PII
        if self.scrub_pii_enabled:
            for text_key in ["text", "title", "content", "caption", "comment_text"]:
                if text_key in cleaned and isinstance(cleaned[text_key], str):
                    cleaned[text_key] = self.scrub_text(cleaned[text_key])

        # 4. Attach ethical compliance flags
        cleaned["is_anonymized"] = True
        cleaned["anonymization_method"] = "SHA-256+Salt"

        return cleaned
