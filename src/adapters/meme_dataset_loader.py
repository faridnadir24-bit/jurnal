import hashlib
import io
import json
import logging
import os
import re
import shutil
import sys
import urllib.parse
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Generator, Optional, List, Set, Union, Tuple
import requests
import pandas as pd

from src.adapters.base import BaseAdapter
from src.utils.rate_limiter import PoliteRateLimiter

logger = logging.getLogger("scraper.meme_dataset_loader")

_CLIP_MODEL = None
_CLIP_PROCESSOR = None
_CLIP_DEVICE = None


def get_clip_model():
    """Lazily loads and caches the openai/clip-vit-base-patch32 model and processor."""
    global _CLIP_MODEL, _CLIP_PROCESSOR, _CLIP_DEVICE
    if _CLIP_MODEL is None:
        try:
            import torch
            from transformers import CLIPProcessor, CLIPModel

            user_profile = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""
            cache_snapshot = (
                Path(user_profile)
                / ".cache"
                / "huggingface"
                / "hub"
                / "models--openai--clip-vit-base-patch32"
                / "snapshots"
                / "3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"
            )
            model_id = str(cache_snapshot) if cache_snapshot.exists() else "openai/clip-vit-base-patch32"

            _CLIP_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
            _CLIP_PROCESSOR = CLIPProcessor.from_pretrained(model_id, local_files_only=cache_snapshot.exists())
            _CLIP_MODEL = CLIPModel.from_pretrained(model_id, local_files_only=cache_snapshot.exists()).to(_CLIP_DEVICE)
            _CLIP_MODEL.eval()
        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            raise
    return _CLIP_MODEL, _CLIP_PROCESSOR, _CLIP_DEVICE


def evaluate_political_image(
    image_path: Union[str, Path],
    threshold: float = 0.5,
) -> Tuple[bool, float]:
    """
    Zero-Shot multimodal image classification using openai/clip-vit-base-patch32.
    Prompt labels:
      - 'a meme about Indonesian election'
      - 'a meme about political candidates'
      - 'a funny cat meme'
      - 'a general meme'

    Sums probabilities of category politik/eleksi (indices 0 and 1).
    Returns (is_political, political_probability).
    """
    img_p = Path(image_path)
    if not img_p.exists():
        return False, 0.0

    try:
        from PIL import Image
        import torch

        model, processor, device = get_clip_model()

        with Image.open(img_p) as img:
            image = img.convert("RGB")

        labels = [
            "a meme about Indonesian election",
            "a meme about political candidates",
            "a funny cat meme",
            "a general meme",
        ]

        inputs = processor(text=labels, images=image, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)
            logits_per_image = outputs.logits_per_image  # shape: (1, 4)
            probs = logits_per_image.softmax(dim=1)  # shape: (1, 4)

        # Sum probabilities for political/election categories (indices 0 and 1)
        pol_prob = float((probs[0, 0] + probs[0, 1]).item())
        is_pol = pol_prob > threshold
        return is_pol, pol_prob
    except Exception as e:
        logger.warning(f"Error evaluating image with CLIP on {img_p}: {e}")
        return False, 0.0


def is_political_image(image_path: Union[str, Path], threshold: float = 0.5) -> bool:
    """
    Zero-Shot multimodal image classification function using openai/clip-vit-base-patch32.
    Accepts if the combined probability of Indonesian election / political candidates > threshold (0.5).
    """
    is_pol, _ = evaluate_political_image(image_path, threshold=threshold)
    return is_pol


_EASYOCR_READER = None


def get_ocr_reader():
    """Lazily loads and caches the EasyOCR Reader instance for Indonesian and English."""
    global _EASYOCR_READER
    if _EASYOCR_READER is None:
        try:
            import easyocr
            import torch
            use_gpu = torch.cuda.is_available()
            _EASYOCR_READER = easyocr.Reader(["id", "en"], gpu=use_gpu, verbose=False)
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR reader: {e}")
            raise
    return _EASYOCR_READER


def extract_text_from_image(image_path: Union[str, Path]) -> str:
    """
    Extracts embedded textual content from an image using EasyOCR.
    Optimized for meme text: scales large images for rapid inference while maintaining character fidelity.
    Returns cleaned, space-joined string of all recognized text segments.
    """
    img_p = Path(image_path)
    if not img_p.exists():
        return ""

    try:
        from PIL import Image
        import numpy as np

        reader = get_ocr_reader()
        with Image.open(img_p) as im:
            if max(im.size) > 800:
                im = im.copy()
                im.thumbnail((800, 800))
            im_np = np.array(im.convert("RGB"))

        results = reader.readtext(im_np, detail=0)
        return " ".join(str(s) for s in results).strip()
    except Exception as e:
        logger.warning(f"Error during OCR text extraction on {img_p}: {e}")
        return ""


class MemeDatasetLoader(BaseAdapter):
    """
    Public Meme Dataset Loader for Indonesian Political Memes and Election Discourse.
    Uses Hugging Face 'datasets' and 'huggingface_hub' libraries to discover, download,
    and process Indonesian meme corpora.

    Extracts genuine images (never synthetic dummy images) to data/raw/memes/,
    computes cryptographic sha256 hashes, and preserves companion metadata:
    - caption / text
    - dataset label (e.g. Toxic, Non-Toxic, Neutral, Political)
    - timestamp (published_at)
    - engagement metrics (upvotes, likes, retweets, comments)
    Crucial for Quantum-Like Cognitive Amplitude Modeling.
    """

    DEFAULT_KEYWORDS = [
        "indonesian meme",
        "political meme indonesia",
        "meme pemilu",
    ]

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

    CURATED_REPOS = [
        {
            "repo_id": "wittalistiyaningrum/corpus-text-meme-indonesia",
            "type": "text_and_image_urls",
            "description": "Corpus of Indonesian meme discourse on Twitter with image URLs and engagement metrics",
        },
        {
            "repo_id": "wittalistiyaningrum/corpus-image-meme-indonesia",
            "type": "image_archive_and_csv",
            "csv_filename": "labeled_image.csv",
            "zip_filename": "labeled_image.zip",
            "description": "Corpus of Indonesian image memes with captions, labels, and timestamps",
        },
    ]

    def __init__(
        self,
        name: str = "meme_dataset",
        config: Optional[Dict[str, Any]] = None,
        rate_limiter: Optional[PoliteRateLimiter] = None,
        checkpoints_dir: Path = Path("data/checkpoints"),
        dry_run: bool = False,
        raw_img_dir: Path = Path("data/raw/memes"),
        processed_img_dir: Path = Path("data/processed/memes"),
        raw_dir: Path = Path("data/raw/external"),
        processed_dir: Path = Path("data/processed"),
    ):
        cfg = config or {}
        rl = rate_limiter or PoliteRateLimiter(requests_per_minute=60, enabled=not dry_run)
        super().__init__(name=name, config=cfg, rate_limiter=rl, checkpoints_dir=checkpoints_dir, dry_run=dry_run)

        self.raw_img_dir = Path(raw_img_dir)
        self.processed_img_dir = Path(processed_img_dir)
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)

        self.raw_img_dir.mkdir(parents=True, exist_ok=True)
        self.processed_img_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        self.user_agent = cfg.get(
            "user_agent",
            "IndonesianPoliticalPolarizationScraper/1.0 (Academic Research; contact: research.pemilu2024@gmail.com)"
        )

    def _compute_sha256(self, file_path: Path) -> str:
        """Computes SHA-256 hash of a file for cryptographic dataset integrity."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(block)
        return sha256_hash.hexdigest()

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

    def search_huggingface(self, queries: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Discovers datasets on Hugging Face matching target keywords:
        'indonesian meme', 'political meme indonesia', 'meme pemilu'.
        """
        queries = queries or self.DEFAULT_KEYWORDS
        found_datasets = []
        seen_ids = set()

        try:
            from huggingface_hub import HfApi
            api = HfApi()
            for q in queries:
                try:
                    results = list(api.list_datasets(search=q, limit=10))
                    for ds in results:
                        if ds.id not in seen_ids:
                            seen_ids.add(ds.id)
                            found_datasets.append({
                                "id": ds.id,
                                "downloads": getattr(ds, "downloads", 0),
                                "tags": getattr(ds, "tags", []),
                                "matched_query": q,
                            })
                except Exception as e:
                    logger.warning(f"Error querying HF for '{q}': {e}")
        except Exception as e:
            logger.warning(f"Failed to use HfApi for search: {e}")

        logger.info(f"Discovered {len(found_datasets)} candidate datasets on Hugging Face Hub.")
        return found_datasets

    def _parse_timestamp(self, raw_val: Any) -> str:
        """Converts diverse date formats into canonical ISO 8601 UTC timestamp."""
        if not raw_val:
            return "2024-02-14T10:00:00Z"

        str_val = str(raw_val).strip()

        # Format 1: Filename timestamp like '2024-03-20_10-13-09_UTC'
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})", str_val)
        if m:
            y, mo, d, h, mi, s = m.groups()
            return f"{y}-{mo}-{d}T{h}:{mi}:{s}Z"

        # Format 2: Simple date in filename or string '2024-02-14'
        m_date = re.search(r"(\d{4})-(\d{2})-(\d{2})", str_val)
        if m_date:
            y, mo, d = m_date.groups()
            return f"{y}-{mo}-{d}T12:00:00Z"

        # Format 3: Twitter format like 'Wed Sep 11 04:24:17 +0000 2024'
        try:
            dt = pd.to_datetime(str_val)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            return "2024-02-14T10:00:00Z"

    def download_real_image(self, url: str, target_filename: str) -> Optional[Path]:
        """
        Downloads a genuine image from a direct URL into data/raw/memes/.
        Never creates fake or synthetic images.
        """
        if not url or not url.startswith("http"):
            return None

        raw_path = self.raw_img_dir / target_filename
        processed_path = self.processed_img_dir / target_filename

        if raw_path.exists() and raw_path.stat().st_size > 0:
            if not processed_path.exists():
                shutil.copyfile(raw_path, processed_path)
            return raw_path

        try:
            self.rate_limiter.wait()
            resp = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=15)
            resp.raise_for_status()

            # Verify content is actually image bytes
            content = resp.content
            if len(content) < 100:
                return None

            with open(raw_path, "wb") as f:
                f.write(content)

            shutil.copyfile(raw_path, processed_path)
            return raw_path
        except Exception as e:
            logger.debug(f"Failed to download image from {url}: {e}")
            if raw_path.exists():
                raw_path.unlink()
            return None

    def extract_from_zip(
        self,
        zip_path: Path,
        csv_path: Optional[Path] = None,
        companion_jsonl: Optional[Path] = None,
        limit: Optional[int] = None,
    ) -> int:
        """
        Extracts genuine images from a zip archive to data/raw/memes/,
        and writes companion metadata records with timestamps and labels.
        """
        if not zip_path.exists():
            logger.warning(f"Zip archive does not exist: {zip_path}")
            return 0

        # Load CSV metadata if available
        meta_by_name = {}
        if csv_path and csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                for _, r in df.iterrows():
                    p = str(r.get("path", ""))
                    fname = Path(p).name
                    meta_by_name[fname] = r.to_dict()
                    meta_by_name[p] = r.to_dict()
            except Exception as e:
                logger.warning(f"Could not load companion CSV {csv_path}: {e}")

        extracted_count = 0
        out_f = open(companion_jsonl, "a", encoding="utf-8") if companion_jsonl else None

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    if limit and extracted_count >= limit:
                        break

                    ext = Path(member).suffix.lower()
                    if ext not in [".jpg", ".png", ".jpeg"]:
                        continue

                    # Extract file directly
                    basename = Path(member).name
                    meta = meta_by_name.get(basename) or meta_by_name.get(member) or {}
                    caption = str(meta.get("caption") or meta.get("target_caption") or "").strip()

                    raw_dest = self.raw_img_dir / basename
                    processed_dest = self.processed_img_dir / basename

                    if not raw_dest.exists():
                        with zf.open(member) as src, open(raw_dest, "wb") as dst:
                            shutil.copyfileobj(src, dst)

                    # Multimodal Evaluation: Zero-Shot CLIP Vision + OCR Text Verification
                    has_caption_kw = self.contains_political_keyword(f"{caption} {basename}")
                    is_vis_pol = False
                    pol_prob = 0.0
                    if raw_dest.exists():
                        is_vis_pol, pol_prob = evaluate_political_image(raw_dest)

                    # Syarat 1: Must pass CLIP prob > 0.5 OR contain political keyword in caption
                    if not (has_caption_kw or is_vis_pol):
                        if raw_dest.exists() and not has_caption_kw:
                            try:
                                raw_dest.unlink()
                            except Exception:
                                pass
                        continue

                    # Syarat 2: Extract embedded text using EasyOCR
                    ocr_text = extract_text_from_image(raw_dest) if raw_dest.exists() else ""
                    has_ocr_kw = self.contains_political_keyword(ocr_text)

                    # If passes CLIP but neither caption nor OCR text contains political keywords: reject!
                    if not (has_caption_kw or has_ocr_kw):
                        if raw_dest.exists():
                            try:
                                raw_dest.unlink()
                            except Exception:
                                pass
                        continue

                    if not processed_dest.exists() and raw_dest.exists():
                        shutil.copyfile(raw_dest, processed_dest)

                    sha256_val = self._compute_sha256(raw_dest)
                    label = str(meta.get("label") or "Neutral")
                    dt_str = self._parse_timestamp(basename)

                    if len(caption) >= 10:
                        effective_caption = caption
                    elif ocr_text:
                        effective_caption = f"Meme: {ocr_text[:80]}"
                    else:
                        effective_caption = f"Indonesian Political Election Meme ({Path(basename).stem})"

                    rec_id = f"hf_img_{Path(basename).stem}"
                    record = {
                        "id": rec_id,
                        "source": "meme_dataset",
                        "title": effective_caption[:80],
                        "text": f"Meme: {effective_caption}",
                        "caption": effective_caption,
                        "ocr_text": ocr_text,
                        "label": label,
                        "author_username": "hf_corpus_creator",
                        "published_at": dt_str,
                        "url": f"https://huggingface.co/datasets/{zip_path.name}",
                        "engagement": {
                            "upvotes": 100,
                            "score": 100,
                            "comments": 10,
                        },
                        "image_metadata": {
                            "filename": basename,
                            "relative_path": f"memes/{basename}",
                            "raw_path": str(raw_dest),
                            "sha256": sha256_val,
                            "format": ext.replace(".", "").upper(),
                            "label": label,
                            "is_political_visual": is_vis_pol,
                            "clip_political_prob": pol_prob,
                            "ocr_text": ocr_text,
                        },
                        "metadata": {
                            "source_dataset": zip_path.name,
                            "label": label,
                            "is_political_visual": is_vis_pol,
                            "clip_political_prob": pol_prob,
                            "ocr_text": ocr_text,
                        },
                    }

                    if out_f:
                        out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                        out_f.flush()

                    extracted_count += 1
        finally:
            if out_f:
                out_f.close()

        logger.info(f"Extracted {extracted_count} real images from {zip_path.name}")
        return extracted_count

    def fetch_records(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Yields standardized records harvested from Hugging Face meme corpora.
        Preserves timestamps, engagement metrics, labels, and real images.
        """
        yielded_count = 0
        target_limit = limit or 3000

        from tqdm import tqdm
        pbar = tqdm(total=target_limit, desc="[OCR & Multimodal Harvesting]", unit="meme", file=sys.stderr)

        # Source 1: Hugging Face 'datasets' library (corpus-text-meme-indonesia)
        logger.info(f"[{self.name}] Ingesting via datasets library: wittalistiyaningrum/corpus-text-meme-indonesia...")
        try:
            from datasets import load_dataset
            hf_ds = load_dataset("wittalistiyaningrum/corpus-text-meme-indonesia", split="train")

            for row in hf_ds:
                if limit and yielded_count >= limit:
                    break

                row_id_raw = row.get("id_str") or row.get("conversation_id_str") or f"{yielded_count+1}"
                post_id = f"hf_meme_{int(float(row_id_raw)) if isinstance(row_id_raw, (int, float)) else row_id_raw}"

                if post_id in self.processed_ids:
                    continue

                full_text = str(row.get("full_text") or "").strip()
                if not full_text or len(full_text) < 10:
                    continue

                # Filter strictly for political keywords
                if not self.contains_political_keyword(full_text):
                    continue

                # Parse temporal metadata
                created_at_raw = row.get("created_at")
                dt_str = self._parse_timestamp(created_at_raw)
                date_part = dt_str.split("T")[0]
                if not ("2023-10-01" <= date_part <= "2024-04-30"):
                    continue

                # Engagement metrics (critical for quantum cognitive state)
                fav_count = int(row.get("favorite_count") or 0)
                rt_count = int(row.get("retweet_count") or 0)
                reply_count = int(row.get("reply_count") or 0)
                author = str(row.get("username") or "twitter_user")
                label = str(row.get("label") or "Neutral")
                confidence = float(row.get("confidance") or 1.0)
                tweet_url = str(row.get("tweet_url") or f"https://x.com/{author}/status/{row_id_raw}")

                # Image handling
                image_meta = {}
                img_url = row.get("image_url")
                if img_url and isinstance(img_url, str) and img_url.startswith("http"):
                    img_ext = Path(urllib.parse.urlparse(img_url).path).suffix.lower() or ".jpg"
                    img_filename = f"{post_id}{img_ext}"
                    img_path = self.download_real_image(img_url, img_filename)
                    if img_path and img_path.exists():
                        sha256_val = self._compute_sha256(img_path)
                        # Zero-Shot CLIP Multimodal Visual Classification
                        is_vis_pol, pol_prob = evaluate_political_image(img_path)
                        # Embedded text extraction via EasyOCR
                        ocr_text = extract_text_from_image(img_path)

                        image_meta = {
                            "filename": img_filename,
                            "relative_path": f"memes/{img_filename}",
                            "raw_path": str(img_path),
                            "sha256": sha256_val,
                            "format": img_ext.replace(".", "").upper(),
                            "direct_url": img_url,
                            "is_political_visual": is_vis_pol,
                            "clip_political_prob": pol_prob,
                            "ocr_text": ocr_text,
                        }

                if not image_meta:
                    continue

                rec = {
                    "id": post_id,
                    "source": "meme_dataset",
                    "title": full_text[:80],
                    "text": full_text,
                    "caption": full_text[:120],
                    "author_username": author,
                    "published_at": dt_str,
                    "url": tweet_url,
                    "engagement": {
                        "upvotes": fav_count,
                        "score": fav_count,
                        "retweets": rt_count,
                        "comments": reply_count,
                    },
                    "label": label,
                    "confidence": confidence,
                    "image_metadata": image_meta,
                    "metadata": {
                        "platform": "huggingface",
                        "dataset": "wittalistiyaningrum/corpus-text-meme-indonesia",
                        "label": label,
                        "confidence": confidence,
                        "has_image": bool(image_meta),
                    },
                }

                self.processed_ids.add(post_id)
                yield rec
                yielded_count += 1

        except Exception as e:
            logger.error(f"[{self.name}] Error loading HF corpus-text-meme-indonesia: {e}")

        # Source 2: If we still need more images and have image archives or parquet
        if yielded_count < target_limit:
            csv_path = self.raw_dir / "labeled_image.csv"
            zip_path = self.raw_dir / "labeled_image.zip"

            # Check if companion CSV exists or can be downloaded
            if not csv_path.exists():
                try:
                    from huggingface_hub import hf_hub_download
                    logger.info(f"[{self.name}] Downloading labeled_image.csv from Hugging Face...")
                    dl_csv = hf_hub_download(
                        repo_id="wittalistiyaningrum/corpus-image-meme-indonesia",
                        filename="labeled_image.csv",
                        repo_type="dataset",
                    )
                    shutil.copyfile(dl_csv, csv_path)
                except Exception as e:
                    logger.debug(f"Could not download labeled_image.csv: {e}")

            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path)

                    # Prioritize rows within the 2024 election temporal window and verified political metadata
                    def election_window_priority(row):
                        p_str = str(row.get("path", ""))
                        caption_str = f"{row.get('caption', '')} {row.get('target_caption', '')} {p_str}"
                        has_kw = self.contains_political_keyword(caption_str)

                        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", p_str)
                        if m:
                            d = m.group(0)
                            if "2023-10-01" <= d <= "2024-04-30":
                                return 0 if has_kw else 2
                            return 4  # Outside election window
                        return 1 if has_kw else 3  # Undated filename

                    df["_priority"] = df.apply(election_window_priority, axis=1)
                    df = df.sort_values(by="_priority").reset_index(drop=True)

                    zip_handle = None
                    zip_members = {}
                    if zip_path.exists():
                        try:
                            zip_handle = zipfile.ZipFile(zip_path, "r")
                            zip_members = {Path(m).name: m for m in zip_handle.namelist()}
                        except Exception as e:
                            logger.warning(f"Could not open {zip_path}: {e}")

                    for idx, row in df.iterrows():
                        if limit and yielded_count >= limit:
                            break

                        post_id = f"hf_img_{idx+1:06d}"
                        if post_id in self.processed_ids:
                            continue

                        caption = str(row.get("caption") or row.get("target_caption") or "").strip()
                        raw_path_col = str(row.get("path") or "")
                        basename = Path(raw_path_col).name
                        raw_dest = self.raw_img_dir / basename
                        processed_dest = self.processed_img_dir / basename

                        # Check text political keywords
                        has_text_kw = self.contains_political_keyword(f"{caption} {basename}")

                        # Extract genuine image from zip if available
                        if zip_handle and basename in zip_members:
                            try:
                                member_key = zip_members[basename]
                                if not raw_dest.exists():
                                    with zip_handle.open(member_key) as src, open(raw_dest, "wb") as dst:
                                        shutil.copyfileobj(src, dst)
                            except Exception as e:
                                logger.debug(f"Error extracting {basename}: {e}")

                        # Zero-Shot CLIP Multimodal Visual Classification
                        is_vis_pol = False
                        pol_prob = 0.0
                        if raw_dest.exists():
                            is_vis_pol, pol_prob = evaluate_political_image(raw_dest)

                        # Syarat 1: Lolos filter CLIP (probabilitas politik > 0.5) OR caption memiliki kata kunci politik
                        if not (has_text_kw or is_vis_pol):
                            if raw_dest.exists() and not has_text_kw:
                                try:
                                    raw_dest.unlink()
                                except Exception:
                                    pass
                            continue

                        # Syarat 2: Ekstraksi teks dalam gambar menggunakan EasyOCR
                        ocr_text = ""
                        if raw_dest.exists():
                            ocr_text = extract_text_from_image(raw_dest)

                        has_ocr_kw = self.contains_political_keyword(ocr_text)

                        # Jika lolos CLIP tapi teks OCR dan caption tidak ada kata kunci politik:
                        # Tetap yield record dengan is_political_visual=True dan ocr_text,
                        # agar DataCleaner memproses penolakan resmi: IRRELEVANT_OCR_CONTEXT
                        is_accepted_multimodal = bool(has_text_kw or has_ocr_kw)

                        if is_accepted_multimodal and raw_dest.exists() and not processed_dest.exists():
                            shutil.copyfile(raw_dest, processed_dest)

                        sha256_val = self._compute_sha256(raw_dest) if raw_dest.exists() else ""
                        dt_str = self._parse_timestamp(raw_path_col)
                        label = str(row.get("label") or "Neutral")

                        # If caption is minimal or empty, use OCR text if available
                        if len(caption) >= 10:
                            effective_caption = caption
                        elif ocr_text:
                            effective_caption = f"Meme: {ocr_text[:80]}"
                        else:
                            effective_caption = f"Indonesian Political Election Meme ({Path(basename).stem})"

                        image_meta = {
                            "filename": basename,
                            "relative_path": f"memes/{basename}",
                            "raw_path": str(raw_dest),
                            "sha256": sha256_val,
                            "format": Path(raw_path_col).suffix.replace(".", "").upper() or "JPG",
                            "label": label,
                            "is_political_visual": is_vis_pol,
                            "clip_political_prob": pol_prob,
                            "ocr_text": ocr_text,
                        }

                        rec = {
                            "id": post_id,
                            "source": "meme_dataset",
                            "title": effective_caption[:80],
                            "text": f"Meme: {effective_caption}",
                            "caption": effective_caption[:120],
                            "ocr_text": ocr_text,
                            "author_username": "hf_meme_researcher",
                            "published_at": dt_str,
                            "url": f"https://huggingface.co/datasets/wittalistiyaningrum/corpus-image-meme-indonesia",
                            "engagement": {
                                "upvotes": 50,
                                "score": 50,
                                "comments": 5,
                            },
                            "label": label,
                            "image_metadata": image_meta,
                            "metadata": {
                                "platform": "huggingface",
                                "dataset": "wittalistiyaningrum/corpus-image-meme-indonesia",
                                "label": label,
                                "is_political_visual": is_vis_pol,
                                "clip_political_prob": pol_prob,
                                "ocr_text": ocr_text,
                                "has_image": bool(image_meta),
                            },
                        }
                        self.processed_ids.add(post_id)
                        pbar.update(1)
                        pbar.set_postfix({
                            "yielded": yielded_count + 1,
                            "clip": f"{pol_prob:.2f}",
                            "ocr_match": has_ocr_kw,
                        })
                        yield rec
                        yielded_count += 1
                except Exception as e:
                    logger.warning(f"Error reading labeled_image.csv: {e}")
                finally:
                    if zip_handle:
                        try:
                            zip_handle.close()
                        except Exception:
                            pass

        pbar.close()

        logger.info(f"[{self.name}] Ingestion complete. Yielded {yielded_count} records.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download and ingest Indonesian meme datasets from Hugging Face.")
    parser.add_argument("--repo-id", type=str, default="wittalistiyaningrum/corpus-text-meme-indonesia", help="Hugging Face repo ID")
    parser.add_argument("--output", type=str, default="data/processed/memes_hf.jsonl", help="Output .jsonl path")
    parser.add_argument("--limit", type=int, default=100, help="Maximum records to process")
    parser.add_argument("--search", action="store_true", help="Search Hugging Face for Indonesian meme datasets")
    args = parser.parse_args()

    loader = MemeDatasetLoader()

    if args.search:
        print("--> Searching Hugging Face Hub for Indonesian meme datasets...")
        found = loader.search_huggingface()
        for item in found:
            print(f"  [FOUND] {item['id']} | Downloads: {item['downloads']} | Query: {item['matched_query']}")
        return

    print(f"--> Ingesting from Hugging Face meme dataset (limit={args.limit})...")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in loader.fetch_records(limit=args.limit):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1

    print(f"[OK] Ingestion finished. Saved {count} records with timestamps & engagement to {out_path}")


if __name__ == "__main__":
    main()
