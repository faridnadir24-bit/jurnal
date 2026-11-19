import hashlib
import re
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, Set
from src.config import PreprocessingConfig, TemporalWindowConfig


class DataCleaner:
    """
    Applies rigorous inclusion/exclusion filtering criteria for peer-reviewed publication.
    Tracks rejection reasons for the academic Methods section and manifest metadata.
    """

    def __init__(self, prep_config: PreprocessingConfig, temp_config: TemporalWindowConfig):
        self.config = prep_config
        self.start_date = datetime.strptime(temp_config.start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(temp_config.end_date, "%Y-%m-%d")

        self.min_length = prep_config.min_char_length
        self.max_length = prep_config.max_char_length
        self.drop_retweets = prep_config.drop_retweet_syntax
        self.drop_url_only = prep_config.drop_url_only_posts
        self.bot_blacklist = set(b.lower() for b in prep_config.bot_blacklist)

        # Indonesian linguistic markers
        self.lang_filter_enabled = prep_config.language_filtering.get("enabled", True)
        self.id_markers = set(
            w.lower() for w in prep_config.language_filtering.get("indonesian_markers", [])
        )

        # In-memory deduplication set (normalized text hashes)
        self.seen_content_hashes: Set[str] = set()

        # Regular expressions
        self.url_pattern = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
        self.retweet_pattern = re.compile(r"^\s*RT\s+@?\w+:", re.IGNORECASE)

    def normalize_for_dedup(self, text: str) -> str:
        """Removes punctuation and whitespace for fuzzy duplicate detection."""
        text_clean = re.sub(r"[^\w\s]", "", text.lower())
        return " ".join(text_clean.split())

    def compute_text_hash(self, text: str) -> str:
        norm = self.normalize_for_dedup(text)
        return hashlib.md5(norm.encode("utf-8")).hexdigest()

    def check_temporal_validity(self, date_val: Optional[str]) -> bool:
        """Validates if record's timestamp falls within 2023-10-01 to 2024-04-30."""
        if not date_val:
            return True  # If date is unavailable or relative, don't immediately reject unless strict

        try:
            # Handle ISO formats: 2024-01-15, 2024-01-15T12:00:00Z, etc.
            clean_date = date_val.split("T")[0]
            dt = datetime.strptime(clean_date, "%Y-%m-%d")
            return self.start_date <= dt <= self.end_date
        except Exception:
            # If parsing fails, allow through with warning
            return True

    def contains_indonesian_marker(self, text: str) -> bool:
        """Verifies presence of typical Indonesian vernacular / formal grammatical markers."""
        if not self.lang_filter_enabled or not self.id_markers:
            return True
        words = set(re.findall(r"\b[a-zA-Z]{2,}\b", text.lower()))
        return len(words.intersection(self.id_markers)) > 0

    def evaluate(self, record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Evaluates record against academic inclusion & exclusion criteria.
        Returns: (is_accepted, rejection_reason)
        """
        text = record.get("text") or record.get("caption") or record.get("title") or ""
        text = text.strip()

        # 1. Minimum & Maximum Length Filter
        if len(text) < self.min_length:
            return False, f"TEXT_TOO_SHORT (length={len(text)} < {self.min_length})"

        if len(text) > self.max_length:
            return False, f"TEXT_TOO_LONG (length={len(text)} > {self.max_length})"

        # 2. Exclude Retweet Syntax
        if self.drop_retweets and self.retweet_pattern.search(text):
            return False, "EXCLUDED_RETWEET_SYNTAX"

        # 3. Exclude URL-only posts (no substantive commentary)
        if self.drop_url_only:
            text_without_urls = self.url_pattern.sub("", text).strip()
            if len(text_without_urls) < 10:
                return False, "URL_ONLY_WITHOUT_COMMENTARY"

        # 4. Bot & Automated Account Filtering
        author = record.get("author_username") or record.get("author") or ""
        if str(author).lower() in self.bot_blacklist:
            return False, f"BOT_BLACKLIST_MATCH ({author})"

        # 5. Language Verification (Indonesian marker tokens)
        if not self.contains_indonesian_marker(text):
            return False, "NON_INDONESIAN_LANGUAGE"

        # 6. Temporal Window Filter
        date_str = record.get("published_at") or record.get("created_at") or record.get("date")
        if not self.check_temporal_validity(date_str):
            return False, f"OUTSIDE_TEMPORAL_WINDOW ({date_str})"

        # 7. Deduplication Filter (Astroturfing & spam bot detection)
        if self.config.drop_duplicates:
            content_hash = self.compute_text_hash(text)
            if content_hash in self.seen_content_hashes:
                return False, "DUPLICATE_CONTENT"
            self.seen_content_hashes.add(content_hash)

        return True, None
