import abc
import json
import logging
from pathlib import Path
from typing import Dict, Any, Generator, Optional, Set
from src.utils.rate_limiter import PoliteRateLimiter

logger = logging.getLogger("scraper.adapter")


class BaseAdapter(abc.ABC):
    """
    Abstract Base Adapter for multi-platform data harvesting.
    Handles polite rate limiting, checkpointing, and output standardization.
    """

    def __init__(
        self,
        name: str,
        config: Dict[str, Any],
        rate_limiter: PoliteRateLimiter,
        checkpoints_dir: Path,
        dry_run: bool = False,
    ):
        self.name = name
        self.config = config
        self.rate_limiter = rate_limiter
        self.checkpoints_dir = checkpoints_dir
        self.dry_run = dry_run

        self.checkpoint_file = checkpoints_dir / f"{self.name}_checkpoint.json"
        self.processed_ids: Set[str] = self._load_checkpoint()

    def _load_checkpoint(self) -> Set[str]:
        """Loads processed IDs from previous runs to enable idempotent resume."""
        if self.dry_run or not self.checkpoint_file.exists():
            return set()
        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("processed_ids", []))
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to load checkpoint: {e}")
            return set()

    def save_checkpoint(self) -> None:
        """Persists processed IDs to checkpoint file."""
        if self.dry_run:
            return
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump({"processed_ids": list(self.processed_ids)}, f, indent=2)
        except Exception as e:
            logger.error(f"[{self.name}] Failed to save checkpoint: {e}")

    @abc.abstractmethod
    def fetch_records(self, limit: Optional[int] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Abstract generator yielding raw harvested records.
        Must yield standardized dictionaries.
        """
        pass
