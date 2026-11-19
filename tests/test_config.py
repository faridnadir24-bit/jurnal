import pytest
from pathlib import Path
from src.config import ExperimentConfig


def test_config_load_valid():
    config = ExperimentConfig.load("config/experiment.yaml")
    assert config.experiment["title"] != ""
    assert config.temporal_window.start_date == "2023-10-01"
    assert config.temporal_window.end_date == "2024-04-30"
    assert config.quotas.total_text_target >= 10000
    assert config.quotas.total_meme_target >= 500
    assert "youtube" in config.sources
    assert "reddit" in config.sources
    assert "gnews" in config.sources
    assert "memes" in config.sources


def test_config_compute_hash():
    config = ExperimentConfig.load("config/experiment.yaml")
    h = config.compute_hash("config/experiment.yaml")
    assert len(h) == 64  # SHA-256 hex string


def test_config_missing_file():
    with pytest.raises(FileNotFoundError):
        ExperimentConfig.load("non_existent_config.yaml")
