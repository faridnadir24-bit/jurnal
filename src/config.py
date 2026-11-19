import hashlib
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import yaml
from pydantic import BaseModel, Field


class TemporalWindowConfig(BaseModel):
    start_date: str
    end_date: str
    key_milestones: List[Dict[str, str]] = Field(default_factory=list)


class QuotasConfig(BaseModel):
    total_text_target: int = 10000
    total_meme_target: int = 500
    pilot_sample_per_source: int = 50
    platforms: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class PreprocessingConfig(BaseModel):
    min_char_length: int = 15
    max_char_length: int = 20000
    drop_retweet_syntax: bool = True
    drop_url_only_posts: bool = True
    drop_duplicates: bool = True
    similarity_threshold: float = 0.95
    language_filtering: Dict[str, Any] = Field(default_factory=dict)
    bot_blacklist: List[str] = Field(default_factory=list)


class EthicsConfig(BaseModel):
    anonymization_algorithm: str = "SHA-256"
    salt: str = "academic_salt_pemilu_2024"
    salt_length: int = 32
    strip_fields: List[str] = Field(default_factory=list)
    anonymize_fields: List[str] = Field(default_factory=list)
    scrub_text_pii: Dict[str, Any] = Field(default_factory=dict)


class NetworkConfig(BaseModel):
    rate_limit_per_minute: int = 30
    jitter_range_seconds: Tuple[float, float] = (0.5, 2.0)
    max_retries: int = 5
    backoff_multiplier: float = 2.0
    timeout_seconds: int = 15
    user_agent: str = "AcademicPoliticalPolarizationScraper/1.0"
    respect_robots_txt: bool = True


class PathsConfig(BaseModel):
    raw_dir: str = "data/raw"
    processed_dir: str = "data/processed"
    release_dir: str = "data/release"
    checkpoints_dir: str = "data/checkpoints"
    manifests_dir: str = "manifests"


class ExperimentConfig(BaseModel):
    experiment: Dict[str, Any]
    temporal_window: TemporalWindowConfig
    quotas: QuotasConfig
    sources: Dict[str, Any]
    preprocessing: PreprocessingConfig
    ethics: EthicsConfig
    network: NetworkConfig
    paths: PathsConfig

    @classmethod
    def load(cls, config_path: str = "config/experiment.yaml") -> "ExperimentConfig":
        path = Path(config_path)
        if not path.is_file():
            raise FileNotFoundError(f"Experiment config file not found: {path.resolve()}")

        with open(path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)

        # Allow environment variable override for salt
        env_salt = os.getenv("SCRAPER_SALT")
        if env_salt and "ethics" in raw_data:
            raw_data["ethics"]["salt"] = env_salt

        return cls(**raw_data)

    def compute_hash(self, config_path: str = "config/experiment.yaml") -> str:
        """Computes the SHA-256 hash of the experiment config file for tracking."""
        with open(config_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
