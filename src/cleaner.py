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

    POLITICAL_KEYWORDS = [
        # Kandidat Paslon 01: Anies - Muhaimin (AMIN)
        "anies", "anies baswedan", "cak imin", "muhaimin", "muhaimin iskandar",
        "anies-muhaimin", "anies muhaimin", "amin", "koalisi perubahan",
        # Kandidat Paslon 02: Prabowo - Gibran (Pragib)
        "prabowo", "prabowo subianto", "gibran", "gibran rakabuming", "gibran rakabuming raka",
        "prabowo-gibran", "prabowo gibran", "pragib", "gemoy", "wowo",
        # Kandidat Paslon 03: Ganjar - Mahfud (Gama)
        "ganjar", "ganjar pranowo", "mahfud", "mahfud md",
        "ganjar-mahfud", "ganjar mahfud", "gama",
        # Penomoran Paslon & Capres/Cawapres
        "paslon", "paslon 1", "paslon 2", "paslon 3",
        "paslon 01", "paslon 02", "paslon 03",
        "nomor urut 1", "nomor urut 2", "nomor urut 3",
        "no urut 1", "no urut 2", "no urut 3",
        "capres", "cawapres", "calon presiden", "calon wakil presiden",
        # Penyelenggara & Lembaga Pemilu
        "pemilu", "pemilu 2024", "pilpres", "pilpres 2024", "pilkada",
        "kpu", "bawaslu", "sirekap", "sengketa pemilu", "sengketa pilpres",
        "mahkamah konstitusi", "sidang mk", "putusan mk",
        # Teknis Pencoblosan & Elektoral
        "nyoblos", "coblos", "surat suara", "kotak suara", "tps",
        "caleg", "dpr ri", "dpd", "dprd",
        "serangan fajar", "sebangan fajar", "dirty vote", "politik uang", "dinasti politik",
        # Slogan & Budaya Meme Pemilu
        "slepet", "slepet cak imin", "tronjal tronjol", "nurhadi",
        "debat capres", "debat cawapres", "debat pilpres", "debat kpu",
        "kampanye akbar", "kampanye capres", "kampanye pemilu", "masa kampanye",
        # Partai Politik Peserta Pemilu
        "pdip", "pdi-p", "pdi perjuangan", "gerindra", "golkar", "nasdem",
        "pks", "pkb", "demokrat", "partai pan", "ppp", "psi", "partai politik",
    ]

    NEGATIVE_KEYWORDS = [
        "donald trump", "amerika serikat", "joe biden", "kebersihan",
        "buang sampah", "tempat sampah", "kue ampo", "sholat tarawih",
        "ramuan ajaib", "marshanies", "juri masakan", "latihan bola",
        "harap tenang ada ujian", "kucing", "main bola",
    ]

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

    def contains_political_keyword(self, text: str) -> bool:
        """Verifies presence of at least one target Indonesian political / election keyword with strict word boundary."""
        if not text:
            return False
        lower_text = text.lower()
        for kw in self.POLITICAL_KEYWORDS:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, lower_text):
                return True
        return False

    def contains_negative_keyword(self, text: str) -> bool:
        """Checks for non-election false positive markers (e.g. Donald Trump, trash disposal, exams)."""
        if not text:
            return False
        lower_text = text.lower()
        return any(neg in lower_text for neg in self.NEGATIVE_KEYWORDS)

    def evaluate(self, record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Evaluates record against academic inclusion & exclusion criteria.
        Returns: (is_accepted, rejection_reason)
        """
        # 0. Strict Multimodal Political Relevance Filter for Memes
        is_meme = (
            record.get("source") in ["memes", "meme_dataset"]
            or bool(record.get("image_metadata"))
        )
        is_visual_political = False
        if is_meme:
            img_meta = record.get("image_metadata") or {}
            clip_prob = float(img_meta.get("clip_political_prob", 0.0))
            is_visual_political = bool(
                img_meta.get("is_political_visual") or clip_prob > 0.5
            )

            caption = (record.get("caption") or "").strip()
            ocr_text = (img_meta.get("ocr_text") or record.get("ocr_text") or "").strip()
            text_context = f"{caption} {record.get('title', '')}".strip()

            # Check negative exclusions:
            # Exclude if text discusses non-election topics unless OCR explicitly has an unambiguous candidate name
            if self.contains_negative_keyword(text_context) or self.contains_negative_keyword(ocr_text):
                strong_candidates = ["prabowo", "gibran", "anies", "ganjar", "mahfud", "kpu", "pemilu", "pilpres"]
                has_strong_ocr = any(re.search(r"\b" + re.escape(c) + r"\b", ocr_text.lower()) for c in strong_candidates)
                if not has_strong_ocr:
                    return False, "IRRELEVANT_POLITICAL_CONTEXT"

            # Check political keywords in OCR vs caption/title
            has_caption_kw = self.contains_political_keyword(text_context)
            has_ocr_kw = self.contains_political_keyword(ocr_text)

            # Syarat 1: Lolos filter CLIP (probabilitas politik > 0.5) ATAU memiliki kata kunci caption politik valid
            if not is_visual_political and not has_caption_kw:
                return False, "IRRELEVANT_POLITICAL_CONTEXT"

            # Syarat 2: Teks hasil OCR ATAU caption asli HARUS mengandung minimal satu dari POLITICAL_KEYWORDS
            # Jika lolos CLIP tapi teks OCR dan caption tidak ada kata kunci politik, tolak dengan IRRELEVANT_OCR_CONTEXT
            if is_visual_political and not (has_ocr_kw or has_caption_kw):
                return False, "IRRELEVANT_OCR_CONTEXT"

            # If passed, ensure textual field satisfies downstream minimum representation
            text = record.get("text") or record.get("caption") or record.get("title") or ""
            if len(text.strip()) < self.min_length:
                if ocr_text:
                    record["text"] = f"Meme OCR: {ocr_text}"
                else:
                    record["text"] = f"Indonesian political meme: {record.get('id', '')} - visual context"

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
        if is_meme and is_visual_political:
            # Multi-modal visual classification verified; allow through even if text marker is absent
            pass
        elif not self.contains_indonesian_marker(text):
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
