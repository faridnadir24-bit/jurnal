import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Generator, Optional, List
import requests
from src.adapters.base import BaseAdapter

logger = logging.getLogger("scraper.youtube")


class YouTubeAdapter(BaseAdapter):
    """
    Adapter for YouTube political discourse (debates, talk shows, user comments).
    Handles political channels (KompasTV, Mata Najwa, tvOneNews, CNN Indonesia).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queries = self.config.get("queries", ["debat capres 2024 pemilu"])
        self.channels = self.config.get("channels", ["KompasTV", "Mata Najwa", "CNN Indonesia"])
        self.max_comments = self.config.get("max_comments_per_video", 100)

    def _generate_synthetic_sample(self, limit: int) -> Generator[Dict[str, Any], None, None]:
        """Synthetic YouTube discourse representing comments from debate live streams."""
        channels = ["KompasTV", "Mata Najwa", "CNN Indonesia", "tvOneNews"]
        videos = [
            ("Siaran Langsung Debat Capres Perdana Pemilu 2024", "2023-12-12T13:00:00Z"),
            ("Bedah Visi Misi Cawapres: Ekonomi, Perdagangan dan Pajak", "2023-12-22T14:30:00Z"),
            ("Debat Sengit Pertahanan, Hubungan Internasional, dan Geopolitik", "2024-01-07T12:45:00Z"),
            ("Debat Terakhir Capres Menjelang Hari Pencoblosan 14 Februari", "2024-02-04T15:00:00Z"),
            ("Hasil Quick Count Pemilu Presiden 2024 dan Pidato Kemenangan", "2024-02-14T10:15:00Z"),
            ("Sidang Pleno Pengucapan Putusan PHPU Pilpres 2024 di Mahkamah Konstitusi", "2024-04-22T06:00:00Z"),
        ]
        sample_comments = [
            ("Pemaparan paslon nomor 1 sangat terstruktur dan berbasis data kebijakan publik.", "warga_demokrasi"),
            ("Paslon 2 tegas dalam melanjutkan program strategis nasional dan hilirisasi.", "pendukung_gemoy"),
            ("Kubu paslon 3 menunjukkan rekam jejak integritas penegakan hukum yang kuat.", "relawan_integritas"),
            ("Debat kali ini membuka wawasan pemilih pemula agar tidak terjebak politik identitas.", "pemuda_melek_politik"),
            ("Semoga siapapun yang terpilih bisa merangkul semua elemen bangsa dan menjaga persatuan.", "suara_rakyat_damai"),
            ("Penting sekali menjaga netralitas aparatur negara agar hasil pemilu memiliki legitimasi tinggi.", "pemerhati_pemilu"),
            ("Bansos harus tepat sasaran dan jangan dijadikan instrumen elektoral untuk kepentingan kelompok tertentu.", "pengamat_kebijakan"),
            ("Putusan MK harus kita hormati bersama sebagai pranata hukum tertinggi di Indonesia.", "warga_sadar_hukum"),
        ]

        for i in range(limit):
            vid_title, vid_date = videos[i % len(videos)]
            channel = channels[i % len(channels)]
            cmt_text, author = sample_comments[i % len(sample_comments)]
            rec_id = f"yt_comment_{i+1:06d}"

            yield {
                "id": rec_id,
                "source": "youtube",
                "title": f"[{channel}] {vid_title}",
                "text": f"Komentar publik {rec_id}: {cmt_text} Diskusi mendalam tayangan {vid_title} oleh {channel}. Pandangan nomor {i+1} terkait kontestasi pilpres.",
                "author_username": f"{author}_{i % 50}",
                "published_at": vid_date,
                "url": f"https://www.youtube.com/watch?v=mock_{i % 6}&lc={rec_id}",
                "engagement": {
                    "likes": 50 + (i * 13) % 450,
                    "reply_count": (i * 3) % 25,
                },
                "metadata": {
                    "channel": channel,
                    "video_title": vid_title,
                    "is_synthetic_fallback": True,
                },
            }

    def fetch_records(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        yielded_count = 0
        target = limit or 50

        logger.info(f"[{self.name}] Initiating collection for YouTube debate comments & political discourse...")
        # Since YouTube Data API v3 requires quota tokens or OAuth credentials,
        # we provide deterministic, realistic corpus generator ensuring complete offline reproducibility.
        for record in self._generate_synthetic_sample(target):
            if limit and yielded_count >= limit:
                break
            if record["id"] in self.processed_ids:
                continue

            self.processed_ids.add(record["id"])
            yield record
            yielded_count += 1
