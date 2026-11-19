import csv
import json
import logging
import os
import shutil
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Generator, Optional, List
import requests
import pandas as pd

logger = logging.getLogger("scraper.dataset_loader")


class DatasetLoader:
    """
    Public Dataset Loader for Indonesian Political Memes and Pemilu 2024 Discourse.
    Downloads and extracts datasets from Hugging Face or Kaggle, preserving
    crucial temporal metadata (timestamps) and engagement metrics (upvotes/likes)
    necessary for quantum-like cognitive opinion modeling.
    Outputs structured records to .jsonl format.
    """

    HUGGINGFACE_API_BASE = "https://huggingface.co/api/datasets"
    HUGGINGFACE_RESOLVE_BASE = "https://huggingface.co/datasets"

    DEFAULT_HF_DATASETS = [
        {
            "repo_id": "emkr-13/berita_pemilu_2024",
            "filename": "data_pemilu_label.csv",
            "type": "csv",
            "description": "Indonesian 2024 Election labeled public discourse with timestamps and outlets",
        }
    ]

    def __init__(
        self,
        raw_dir: Path = Path("data/raw/external"),
        processed_dir: Path = Path("data/processed"),
        images_dir: Path = Path("data/raw/memes"),
    ):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.images_dir = Path(images_dir)

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def search_huggingface(self, query: str = "pemilu 2024") -> List[Dict[str, Any]]:
        """Searches Hugging Face Hub API for relevant Indonesian election datasets."""
        try:
            url = f"{self.HUGGINGFACE_API_BASE}?search={urllib.parse.quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AcademicResearch/1.0"}
            resp = requests.get(url, headers=headers, timeout=12)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Error searching Hugging Face datasets: {e}")
            return []

    def download_from_huggingface(
        self,
        repo_id: str,
        filename: str,
        revision: str = "main",
    ) -> Optional[Path]:
        """
        Downloads a dataset file directly from Hugging Face Hub via raw/resolve endpoint.
        Does not require a Hugging Face API token for public open-access datasets.
        """
        url = f"{self.HUGGINGFACE_RESOLVE_BASE}/{repo_id}/resolve/{revision}/{filename}"
        target_path = self.raw_dir / f"{repo_id.replace('/', '_')}_{filename}"

        if target_path.exists() and target_path.stat().st_size > 0:
            logger.info(f"Dataset file already exists at: {target_path}")
            return target_path

        logger.info(f"Downloading dataset from Hugging Face: {url}")
        try:
            headers = {"User-Agent": "AcademicResearch/1.0 (Mozilla/5.0)"}
            with requests.get(url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(target_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=16384):
                        if chunk:
                            f.write(chunk)

            logger.info(f"Downloaded successfully: {target_path} ({target_path.stat().st_size:,} bytes)")
            return target_path
        except Exception as e:
            logger.error(f"Failed to download from Hugging Face ({url}): {e}")
            if target_path.exists():
                target_path.unlink()
            return None

    def extract_to_jsonl(
        self,
        input_file: Path,
        output_jsonl: Path,
        source_name: str = "huggingface",
        limit: Optional[int] = None,
    ) -> int:
        """
        Parses CSV, Parquet, or JSON dataset and extracts metadata:
        - timestamp (published_at) -> crucial for quantum state evolution
        - engagement (upvotes / score / likes) -> crucial for cognitive amplitude weight
        - caption / title / text
        - image path or URL if present
        Writes records to .jsonl.
        """
        records_written = 0
        output_jsonl.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Extracting metadata from {input_file} to {output_jsonl}...")

        # 1. Parse CSV
        if input_file.suffix.lower() == ".csv":
            try:
                # Read via pandas for robust chunking and encoding detection
                df = pd.read_csv(input_file, nrows=limit if limit else None)
                with open(output_jsonl, "a", encoding="utf-8") as out_f:
                    for idx, row in df.iterrows():
                        row_dict = row.to_dict()
                        
                        # Identify text / caption
                        text_val = ""
                        for col in ["text", "content", "caption", "title", "berita", "tweet", "pesan"]:
                            if col in row_dict and pd.notna(row_dict[col]):
                                text_val = str(row_dict[col]).strip()
                                break
                        
                        if not text_val or len(text_val) < 10:
                            continue

                        # Identify timestamp
                        dt_val = "2024-02-14T10:00:00Z"
                        for date_col in ["date", "created_at", "published_at", "timestamp", "tanggal"]:
                            if date_col in row_dict and pd.notna(row_dict[date_col]):
                                dt_raw = str(row_dict[date_col]).strip()
                                try:
                                    dt_parsed = pd.to_datetime(dt_raw)
                                    dt_val = dt_parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
                                    break
                                except Exception:
                                    pass

                        # Identify engagement metrics (upvotes, likes, score, retweets)
                        score = 0
                        for score_col in ["upvotes", "score", "likes", "favorite_count", "jumlah_like"]:
                            if score_col in row_dict and pd.notna(row_dict[score_col]):
                                try:
                                    score = int(row_dict[score_col])
                                    break
                                except Exception:
                                    pass

                        rec_id = f"ext_{source_name}_{idx+1:06d}"
                        record = {
                            "id": rec_id,
                            "source": source_name,
                            "title": text_val[:80],
                            "text": text_val,
                            "caption": text_val[:120],
                            "author_username": str(row_dict.get("author") or row_dict.get("username") or row_dict.get("source") or "public_dataset"),
                            "published_at": dt_val,
                            "url": str(row_dict.get("url") or row_dict.get("link") or ""),
                            "engagement": {
                                "upvotes": score,
                                "score": score,
                                "comments": int(row_dict.get("comments") or row_dict.get("reply_count") or 0),
                            },
                            "metadata": {
                                "dataset_file": input_file.name,
                                "source_platform": source_name,
                                "raw_attributes": {k: str(v) for k, v in row_dict.items() if k not in ["text", "content", "berita"]},
                            },
                        }

                        # Check for image URL or path
                        for img_col in ["image_url", "image", "img", "media_url", "foto"]:
                            if img_col in row_dict and pd.notna(row_dict[img_col]):
                                img_val = str(row_dict[img_col]).strip()
                                record["image_metadata"] = {
                                    "direct_url": img_val,
                                    "relative_path": f"memes/{rec_id}.jpg",
                                }
                                break

                        out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                        records_written += 1

            except Exception as e:
                logger.error(f"Error parsing CSV dataset {input_file}: {e}")

        # 2. Parse JSON / JSONL
        elif input_file.suffix.lower() in [".json", ".jsonl"]:
            try:
                with open(input_file, "r", encoding="utf-8") as in_f, open(output_jsonl, "a", encoding="utf-8") as out_f:
                    for line_idx, line in enumerate(in_f):
                        if limit and records_written >= limit:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                        except Exception:
                            continue

                        # Extract caption / title / text
                        text_val = item.get("caption") or item.get("text") or item.get("title") or ""
                        if not text_val or len(text_val) < 10:
                            continue

                        dt_val = item.get("published_at") or item.get("created_at") or item.get("date") or "2024-02-14T00:00:00Z"
                        upvotes = item.get("engagement", {}).get("upvotes") or item.get("score") or item.get("likes") or 0

                        record = {
                            "id": item.get("id") or f"ext_{source_name}_{line_idx+1:06d}",
                            "source": source_name,
                            "title": item.get("title") or text_val[:80],
                            "text": text_val,
                            "caption": text_val[:120],
                            "author_username": item.get("author_username") or item.get("author") or "public_dataset",
                            "published_at": dt_val,
                            "url": item.get("url") or "",
                            "engagement": {
                                "upvotes": int(upvotes),
                                "score": int(upvotes),
                                "comments": int(item.get("engagement", {}).get("comments") or item.get("comments") or 0),
                            },
                            "image_metadata": item.get("image_metadata") or {},
                            "metadata": {
                                "source_file": input_file.name,
                                "source_platform": source_name,
                            },
                        }
                        out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                        records_written += 1
            except Exception as e:
                logger.error(f"Error parsing JSONL dataset {input_file}: {e}")

        logger.info(f"Successfully extracted {records_written} records with timestamps and upvotes to {output_jsonl}")
        return records_written


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download and extract public Indonesian Pemilu 2024 / Meme datasets.")
    parser.add_argument("--repo-id", type=str, default="emkr-13/berita_pemilu_2024", help="Hugging Face repo ID")
    parser.add_argument("--filename", type=str, default="data_pemilu_label.csv", help="Dataset filename inside the repo")
    parser.add_argument("--output", type=str, default="data/processed/external_pemilu.jsonl", help="Output .jsonl path")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum records to extract")
    args = parser.parse_args()

    loader = DatasetLoader()
    print(f"--> Downloading dataset: {args.repo_id}/{args.filename}")
    dl_path = loader.download_from_huggingface(args.repo_id, args.filename)
    if dl_path:
        count = loader.extract_to_jsonl(dl_path, Path(args.output), source_name="huggingface", limit=args.limit)
        print(f"[OK] Successfully extracted {count} records with timestamps and engagement to {args.output}")
    else:
        print("[FAIL] Download failed. Verify repo_id or network connectivity.")


if __name__ == "__main__":
    main()
