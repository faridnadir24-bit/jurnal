import hashlib
import logging
import os
import shutil
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Generator, Optional, List
import requests
import praw
from src.adapters.base import BaseAdapter

logger = logging.getLogger("scraper.meme")


class MemeAdapter(BaseAdapter):
    """
    Multimodal meme adapter using PRAW (Reddit API).
    Fetches genuine meme posts from r/indonesiameme and r/indonesia,
    filters by political keywords ('pemilu', 'pilpres', 'capres', 'ganjar', 'prabowo', 'anies'),
    and downloads original image assets directly to data/raw/memes/.
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

        # Initialize PRAW
        self.reddit = self._init_praw()

    def _init_praw(self) -> Optional[praw.Reddit]:
        """Initializes Reddit instance via PRAW in read-only mode."""
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
            logger.error(f"Failed to initialize PRAW: {e}")
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

    def _download_original_image(self, image_url: str, post_id: str) -> Optional[Dict[str, Any]]:
        """
        Downloads the real original image from direct URL and saves to data/raw/memes/.
        Logs HTTP errors and continues without creating dummy images.
        """
        parsed = urllib.parse.urlparse(image_url)
        ext = os.path.splitext(parsed.path)[1].lower()
        if not ext or ext not in self.ALLOWED_EXTENSIONS:
            ext = ".jpg"

        filename = f"{post_id}{ext}"
        raw_path = self.raw_img_dir / filename
        processed_path = self.processed_img_dir / filename

        try:
            self.rate_limiter.wait()
            resp = requests.get(
                image_url,
                headers={"User-Agent": self.user_agent},
                timeout=12,
                stream=True,
            )
            resp.raise_for_status()

            # Save real raw image
            sha256_hash = hashlib.sha256()
            with open(raw_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        sha256_hash.update(chunk)

            # Mirror genuine image to processed directory
            shutil.copyfile(raw_path, processed_path)

            return {
                "filename": filename,
                "relative_path": f"memes/{filename}",
                "raw_path": str(raw_path),
                "sha256": sha256_hash.hexdigest(),
                "format": ext.replace(".", "").upper(),
                "direct_url": image_url,
            }

        except requests.RequestException as e:
            logger.error(f"HTTP error downloading original meme from {image_url}: {e}")
            # Clean up partial file if any
            if raw_path.exists():
                raw_path.unlink()
            if processed_path.exists():
                processed_path.unlink()
            return None
        except Exception as e:
            logger.error(f"Unexpected error saving image from {image_url}: {e}")
            return None

    def fetch_records(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Harvests genuine memes from r/indonesiameme and r/indonesia using PRAW.
        Filters for election keywords and direct image URLs.
        """
        if not self.reddit:
            logger.error("PRAW Reddit client is not initialized. Skipping meme collection.")
            return

        yielded_count = 0
        target_limit = limit or 50

        # Subreddits: indonesiameme and indonesia
        subreddits = self.config.get("subreddits", self.TARGET_SUBREDDITS)

        logger.info(f"[{self.name}] Initiating genuine meme harvesting from subreddits: {subreddits}")

        for sub_name in subreddits:
            if limit and yielded_count >= limit:
                break

            logger.info(f"[{self.name}] Querying subreddit: r/{sub_name}")
            try:
                sub = self.reddit.subreddit(sub_name)

                # Search submissions matching election keywords
                search_query = " OR ".join(self.KEYWORDS)
                submissions_stream = sub.search(search_query, limit=target_limit, sort="relevance")

                for submission in submissions_stream:
                    if limit and yielded_count >= limit:
                        break

                    post_id = f"meme_{submission.id}"
                    if post_id in self.processed_ids:
                        continue

                    title = getattr(submission, "title", "")
                    selftext = getattr(submission, "selftext", "")
                    url = getattr(submission, "url", "")

                    # 1. Filter keywords on title or text
                    matched_kws = self._matches_keywords(title, selftext)
                    if not matched_kws:
                        continue

                    # 2. Filter direct image URLs only (.jpg, .png, .jpeg)
                    if not self._is_direct_image_url(url):
                        continue

                    # 3. Download the original image to data/raw/memes/
                    img_meta = self._download_original_image(url, post_id)
                    if not img_meta:
                        # HTTP error occurred - logged in _download_original_image, skip without dummy
                        continue

                    # 4. Extract author and timestamp
                    author_name = submission.author.name if submission.author else "[deleted]"
                    created_utc = getattr(submission, "created_utc", 0)
                    dt_str = datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                    full_text = f"{title}. {selftext}".strip()

                    record = {
                        "id": post_id,
                        "source": "memes",
                        "title": title,
                        "text": full_text,
                        "caption": title,
                        "author_username": author_name,
                        "published_at": dt_str,
                        "url": f"https://reddit.com{getattr(submission, 'permalink', '')}",
                        "engagement": {
                            "score": getattr(submission, "score", 0),
                            "upvote_ratio": getattr(submission, "upvote_ratio", 1.0),
                            "num_comments": getattr(submission, "num_comments", 0),
                        },
                        "image_metadata": {
                            **img_meta,
                            "matched_keywords": matched_kws,
                            "subreddit": sub_name,
                        },
                        "metadata": {
                            "platform": "reddit",
                            "subreddit": sub_name,
                            "flair": getattr(submission, "link_flair_text", None),
                            "matched_keywords": matched_kws,
                        },
                    }

                    self.processed_ids.add(post_id)
                    yield record
                    yielded_count += 1

            except Exception as e:
                logger.error(f"[{self.name}] HTTP or API error from r/{sub_name}: {e}. Continuing to next.")
                continue
