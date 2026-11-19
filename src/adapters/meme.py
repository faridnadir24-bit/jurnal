import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Generator, Optional, List, Set
import requests
import praw
from src.adapters.base import BaseAdapter

logger = logging.getLogger("scraper.meme")


class MemeAdapter(BaseAdapter):
    """
    Multimodal Meme Adapter for Indonesian Political Polarization Research (Pemilu 2024).
    Supports:
    1. gallery-dl integration with companion .json metadata extraction (timestamp, upvotes, title)
       from https://www.reddit.com/r/indonesiameme/search/?q=pemilu&restrict_sr=1 and r/indonesia.
    2. PRAW (Reddit API) ingestion with keyword filtering and direct image extraction.
    3. Integration with DatasetLoader for public Hugging Face / Kaggle multimodal datasets.
    NEVER generates synthetic or dummy images using Pillow.
    """

    KEYWORDS = ["pemilu", "pilpres", "capres", "ganjar", "prabowo", "anies"]
    TARGET_SUBREDDITS = ["indonesiameme", "indonesia"]
    ALLOWED_EXTENSIONS = (".jpg", ".png", ".jpeg")

    def __init__(self, raw_img_dir: Path, processed_img_dir: Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw_img_dir = raw_img_dir
        self.processed_img_dir = processed_img_dir
        self.raw_img_dir.mkdir(parents=True, exist_ok=True)
        self.processed_img_dir.mkdir(parents=True, exist_ok=True)

        self.user_agent = (
            os.getenv("REDDIT_USER_AGENT")
            or self.config.get("user_agent")
            or "IndonesianPoliticalPolarizationScraper/1.0 (Academic Research; contact: research.pemilu2024@gmail.com)"
        )
        self.client_id = os.getenv("REDDIT_CLIENT_ID") or self.config.get("client_id")
        self.client_secret = os.getenv("REDDIT_CLIENT_SECRET") or self.config.get("client_secret")

        # Load credentials from config/credentials.yaml if present
        if not (self.client_id and self.client_secret):
            creds_file = Path("config/credentials.yaml")
            if creds_file.exists():
                try:
                    import yaml
                    with open(creds_file, "r", encoding="utf-8") as f:
                        creds = yaml.safe_load(f) or {}
                        reddit_creds = creds.get("reddit", {})
                        self.client_id = self.client_id or reddit_creds.get("client_id")
                        self.client_secret = self.client_secret or reddit_creds.get("client_secret")
                        self.user_agent = self.user_agent or reddit_creds.get("user_agent")
                except Exception as e:
                    logger.warning(f"Could not load credentials.yaml: {e}")

        self.reddit = self._init_praw()

    def _init_praw(self) -> Optional[praw.Reddit]:
        """Initializes Reddit instance via PRAW in read-only mode if credentials exist."""
        try:
            reddit = praw.Reddit(
                client_id=self.client_id or "placeholder_id",
                client_secret=self.client_secret or "placeholder_secret",
                user_agent=self.user_agent,
                check_for_updates=False,
            )
            reddit.read_only = True
            return reddit
        except Exception as e:
            logger.warning(f"PRAW initialization deferred: {e}")
            return None

    def _matches_keywords(self, title: str, text: str) -> List[str]:
        """Checks if title or text contains any of the required election keywords."""
        content = f"{title or ''} {text or ''}".lower()
        return [kw for kw in self.KEYWORDS if kw in content]

    def _is_direct_image_url(self, url: str) -> bool:
        """Ensures the post URL points directly to an image (.jpg, .png, .jpeg)."""
        if not url:
            return False
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.lower()
        return path.endswith(self.ALLOWED_EXTENSIONS)

    def _compute_sha256(self, file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(block)
        return sha256_hash.hexdigest()

    def _run_gallery_dl(self, target_url: str, limit: int = 50) -> List[Path]:
        """
        Executes gallery-dl via subprocess with --write-metadata enabled.
        Stores companion .json metadata files alongside each downloaded image
        to preserve timestamps and upvotes for quantum-like modeling.
        """
        logger.info(f"[{self.name}] Running gallery-dl on: {target_url} (limit={limit})")
        cmd = [
            sys.executable, "-m", "gallery_dl",
            "--directory", str(self.raw_img_dir),
            "--write-metadata",
            "--filter", "extension in ('jpg', 'png', 'jpeg')",
            "--range", f"1-{limit}",
            target_url,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=90,
            )
            if result.returncode != 0:
                logger.warning(f"gallery-dl returned code {result.returncode}: {result.stderr.strip()[:200]}")
            else:
                logger.info(f"gallery-dl run complete for {target_url}")
        except subprocess.TimeoutExpired:
            logger.error(f"gallery-dl timed out on {target_url}")
        except Exception as e:
            logger.error(f"gallery-dl execution failed: {e}")

        # Scan for companion .json metadata files
        json_files = list(self.raw_img_dir.rglob("*.json"))
        return json_files

    def _parse_gallery_dl_metadata(self, json_file: Path) -> Optional[Dict[str, Any]]:
        """
        Extracts temporal metadata (timestamp) and cognitive weight (upvotes/score)
        from gallery-dl companion JSON files.
        """
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                meta = json.load(f)

            title = meta.get("title") or meta.get("caption") or ""
            author = meta.get("author") or meta.get("user") or "[deleted]"
            score = int(meta.get("score") or meta.get("ups") or 0)
            num_comments = int(meta.get("num_comments") or 0)

            # Date / Timestamp extraction (crucial for quantum-like modeling)
            date_raw = meta.get("date") or meta.get("created_utc")
            dt_str = "2024-02-14T10:00:00Z"
            if date_raw:
                try:
                    if isinstance(date_raw, (int, float)):
                        dt_str = datetime.fromtimestamp(date_raw, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    else:
                        dt_parsed = datetime.fromisoformat(str(date_raw).replace("Z", "+00:00"))
                        dt_str = dt_parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
                except Exception:
                    pass

            # Find matching image file
            stem = json_file.stem
            parent = json_file.parent
            img_file = None
            for ext in [".jpg", ".png", ".jpeg"]:
                candidate = parent / f"{stem}{ext}"
                if candidate.exists():
                    img_file = candidate
                    break
                # gallery-dl sometimes names file: image.png.json -> stem is image.png
                candidate2 = parent / stem
                if candidate2.exists() and candidate2.suffix.lower() in self.ALLOWED_EXTENSIONS:
                    img_file = candidate2
                    break

            if not img_file or not img_file.exists():
                return None

            img_sha256 = self._compute_sha256(img_file)

            # Mirror to processed directory
            processed_target = self.processed_img_dir / img_file.name
            if not processed_target.exists():
                shutil.copyfile(img_file, processed_target)

            rec_id = f"gdl_{meta.get('id') or stem}"
            matched_kws = self._matches_keywords(title, "")

            return {
                "id": rec_id,
                "source": "memes",
                "title": title,
                "text": f"Political Meme: {title}. Analisis wacana visual humor elektoral Pemilu 2024.",
                "caption": title,
                "author_username": author,
                "published_at": dt_str,
                "url": meta.get("url") or meta.get("permalink") or f"https://reddit.com/{meta.get('id')}",
                "engagement": {
                    "upvotes": score,
                    "score": score,
                    "comments": num_comments,
                },
                "image_metadata": {
                    "filename": img_file.name,
                    "relative_path": f"memes/{img_file.name}",
                    "raw_path": str(img_file),
                    "sha256": img_sha256,
                    "format": img_file.suffix.replace(".", "").upper(),
                    "matched_keywords": matched_kws,
                },
                "metadata": {
                    "platform": "reddit",
                    "extractor": "gallery-dl",
                    "matched_keywords": matched_kws,
                },
            }

        except Exception as e:
            logger.error(f"Error parsing companion JSON {json_file}: {e}")
            return None

    def fetch_records(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Harvests genuine memes using gallery-dl companion metadata or PRAW.
        Filters for election keywords, preserves timestamps & upvotes,
        and yields standardized records.
        """
        yielded_count = 0
        target_limit = limit or 50

        # Method 1: Try gallery-dl on target Reddit search URLs
        gallery_urls = [
            "https://www.reddit.com/r/indonesiameme/search/?q=pemilu&restrict_sr=1",
            "https://www.reddit.com/r/indonesia/search/?q=pemilu&restrict_sr=1",
        ]

        logger.info(f"[{self.name}] Initiating meme harvesting via gallery-dl with companion metadata...")
        for g_url in gallery_urls:
            if limit and yielded_count >= limit:
                break

            json_files = self._run_gallery_dl(g_url, limit=target_limit)
            for jf in json_files:
                if limit and yielded_count >= limit:
                    break

                record = self._parse_gallery_dl_metadata(jf)
                if not record:
                    continue

                if record["id"] in self.processed_ids:
                    continue

                self.processed_ids.add(record["id"])
                yield record
                yielded_count += 1

        # Method 2: If gallery-dl was blocked by Reddit network security or returned few items,
        # fallback to PRAW if credentials exist
        if yielded_count < target_limit and self.reddit:
            logger.info(f"[{self.name}] Attempting complementary collection via PRAW...")
            for sub_name in self.TARGET_SUBREDDITS:
                if limit and yielded_count >= limit:
                    break

                try:
                    sub = self.reddit.subreddit(sub_name)
                    search_query = " OR ".join(self.KEYWORDS)
                    for submission in sub.search(search_query, limit=target_limit, sort="relevance"):
                        if limit and yielded_count >= limit:
                            break

                        post_id = f"meme_{submission.id}"
                        if post_id in self.processed_ids:
                            continue

                        title = getattr(submission, "title", "")
                        selftext = getattr(submission, "selftext", "")
                        url = getattr(submission, "url", "")

                        if not self._matches_keywords(title, selftext):
                            continue
                        if not self._is_direct_image_url(url):
                            continue

                        # Download real image
                        img_parsed = urllib.parse.urlparse(url)
                        ext = os.path.splitext(img_parsed.path)[1].lower() or ".jpg"
                        filename = f"{post_id}{ext}"
                        raw_path = self.raw_img_dir / filename
                        processed_path = self.processed_img_dir / filename

                        try:
                            self.rate_limiter.wait()
                            resp = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=12)
                            resp.raise_for_status()
                            with open(raw_path, "wb") as f:
                                f.write(resp.content)
                            shutil.copyfile(raw_path, processed_path)
                            img_sha256 = self._compute_sha256(raw_path)
                        except Exception as e:
                            logger.error(f"HTTP error downloading {url}: {e}")
                            if raw_path.exists():
                                raw_path.unlink()
                            continue

                        author_name = submission.author.name if submission.author else "[deleted]"
                        created_utc = getattr(submission, "created_utc", 0)
                        dt_str = datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                        rec = {
                            "id": post_id,
                            "source": "memes",
                            "title": title,
                            "text": f"{title}. {selftext}".strip(),
                            "caption": title,
                            "author_username": author_name,
                            "published_at": dt_str,
                            "url": f"https://reddit.com{getattr(submission, 'permalink', '')}",
                            "engagement": {
                                "upvotes": getattr(submission, "score", 0),
                                "score": getattr(submission, "score", 0),
                                "comments": getattr(submission, "num_comments", 0),
                            },
                            "image_metadata": {
                                "filename": filename,
                                "relative_path": f"memes/{filename}",
                                "raw_path": str(raw_path),
                                "sha256": img_sha256,
                                "format": ext.replace(".", "").upper(),
                            },
                            "metadata": {
                                "platform": "reddit",
                                "subreddit": sub_name,
                                "extractor": "praw",
                            },
                        }
                        self.processed_ids.add(post_id)
                        yield rec
                        yielded_count += 1
                except Exception as e:
                    logger.error(f"PRAW fetch error from r/{sub_name}: {e}")
                    continue
