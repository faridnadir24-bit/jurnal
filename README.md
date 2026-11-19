# Multi-Source Academic Scraper: Indonesian Political Polarization (Pemilu 2024)

[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)
[![Tests](https://img.shields.io/badge/pytest-20%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)]()
[![Reproducibility](https://img.shields.io/badge/peer--review-reproducible-success.svg)]()

Academic scraper and dataset curation pipeline for computational research on **Indonesian Political Polarization during the 2024 Presidential Election (Pemilu 2024)**. Designed specifically for peer review reproducibility, academic transparency, and adherence to international research ethics standards (**Data Availability Statement**, **Datasheets for Datasets**, and **CC-BY-NC 4.0** licensing).

---

## 📌 Architecture & Design Principles

Unlike ad-hoc scrapers, this system adheres to strict open science requirements:

1. **100% Config-Driven (`config/experiment.yaml`)**:
   Zero hardcoded queries, limits, or temporal intervals. Every parameter can be inspected or adjusted by peer reviewers to replicate the exact harvest.
2. **Cryptographic Run Manifests (`manifests/run_{timestamp}.json`)**:
   Every execution logs:
   - Git commit hash & working tree clean/dirty state.
   - SHA-256 hash of the configuration file.
   - Start/end timestamps and duration.
   - Per-source raw, accepted, and rejected counts with detailed rejection reason breakdown.
   - SHA-256 cryptographic checksums of generated datasets.
3. **Data Ethics & Pseudonymization**:
   - Usernames and user IDs are hashed using **SHA-256 with a secret cryptographic salt** (`anon_{hash[:16]}`).
   - Direct PII (phone numbers, email addresses, and `@mentions`) is redacted or scrubbed.
   - Sensitive metadata (IP addresses, avatar URLs, GPS coordinates) is stripped prior to storage.
   - Released under the open academic [CC-BY-NC 4.0 License](data/release/LICENSE).
4. **Publication-Ready Packaging (`python release.py`)**:
   Directly bundles the dataset into `data/release/dataset.zip` accompanied by Gebru et al.'s **Datasheets for Datasets** (`datasheet.md`), `README.md`, and `LICENSE` ready for deposit to **Zenodo** or **Figshare**.

---

## 📂 Directory Layout

```
├── config/
│   ├── experiment.yaml          # Master configuration (queries, quotas, ethics, filters)
│   └── credentials.example.yaml # Optional credentials template
├── data/
│   ├── raw/                     # Raw unreleased data (preserved for researcher audit trail)
│   ├── processed/               # Clean, pseudonymized datasets (posts.jsonl, memes.jsonl)
│   │   └── memes/               # PNG multimodal meme images
│   └── release/                 # Zenodo/Figshare publication-ready package
│       ├── dataset.zip          # Compressed dataset bundle
│       ├── README.md            # Data Availability Statement & Methods documentation
│       ├── LICENSE              # CC-BY-NC 4.0 International License
│       └── datasheet.md         # Gebru et al. Datasheets for Datasets specification
├── manifests/
│   └── run_{timestamp}.json     # Cryptographic execution audit manifest
├── src/
│   ├── adapters/                # Modular platform adapters (YouTube, Reddit, GNews, Memes)
│   ├── anonymizer.py            # SHA-256 + salt pseudonymization & PII scrubbing
│   ├── cleaner.py               # Inclusion/exclusion criteria & deduplication
│   ├── config.py                # Pydantic schema validation & config hash calculation
│   ├── manifest.py              # Manifest generator & git version tracker
│   ├── pipeline.py              # Master harvesting orchestrator
│   ├── release.py               # Zenodo packaging & datasheet generator
│   ├── verifier.py              # Dataset integrity, distribution, & anonymity auditor
│   └── utils/                   # Rate limiter with jitter & structured logger
├── tests/                       # Complete pytest unit & integration test suite
├── main.py                      # CLI entrypoint
├── release.py                   # Standalone release packaging script
└── requirements.txt             # Environment dependencies
```

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/your-lab/pemilu2024-polarization-scraper.git
cd pemilu2024-polarization-scraper
pip install -r requirements.txt
```

### 2. Run Tests (Verification of Test Suite)

```bash
python -m pytest -v
```

### 3. Run Pilot Mode (Smoke Test / 50 samples per source)

```bash
python main.py --pilot
```

### 4. Run Dry Run (Network and Filter Validation without disk writes)

```bash
python main.py --pilot --dry-run
```

### 5. Run Full Academic Harvesting Pipeline

```bash
python main.py
```
*(To run only specific sources, e.g. YouTube and Reddit: `python main.py --source youtube reddit`)*

### 6. Verify Dataset Integrity & Audit Anonymity

```bash
python main.py --verify
```

### 7. Export Publication Package (Zenodo / Figshare)

```bash
python release.py
# or:
python main.py --export-release
```

---

## 📝 Scraping Protocol & Methods Section Documentation

*(Template for inclusion in the "Methods" or "Data Collection" section of the journal manuscript)*

```markdown
### Data Collection and Ethics Protocol

Data was harvested across four digital communication channels: Google News RSS (accredited press), 
Reddit r/indonesia (long-form civic debate), YouTube (broadcast debate commentary), and digital 
political memes (visual rhetoric). The collection covered the entire 2024 Indonesian election cycle 
from 1 October 2023 to 30 April 2024, spanning candidate registration, five televised debates, 
voting day (14 February 2024), and the Constitutional Court (Mahkamah Konstitusi) dispute proceedings.

Inclusion and Exclusion Criteria:
- Inclusion: Human-authored Indonesian discourse containing >= 15 characters.
- Exclusion: Automated retweets ('RT @...'), URL-only entries without commentary, recognized 
  bots (e.g., AutoModerator), and near-duplicate text identified via normalized MD5 content hashing.
- Language Verification: Text must contain Indonesian grammatical or vernacular function words.

Ethics and Anonymization:
In compliance with research ethics for computational social science, all account usernames 
were pseudonymized using SHA-256 with a private cryptographic salt (anon_{hash[:16]}). 
Text was scrubbed of direct identifiers including Indonesian cellular numbers (+628...), email 
addresses, and social mentions. Sensitive metadata (IP addresses, profile pictures, GPS coordinates) 
was omitted. The curated dataset is licensed under Creative Commons Attribution-NonCommercial 4.0 (CC BY-NC 4.0).

Access Boundaries:
Scraping conformed to polite rate limiting (30 requests/minute with random jitter) and platform robots.txt 
guidelines. Walled-garden APIs requiring private authentication (e.g. private TikTok/Instagram feeds) 
were excluded in favor of publicly accessible discussion threads and curated political visual templates.
```

---

## 📋 Data Availability Statement (for Paper Submission)

> *"The datasets generated during and/or analyzed during the current study are available in the Zenodo repository at https://doi.org/10.5281/zenodo.10242024 under a Creative Commons Attribution-NonCommercial 4.0 International license (CC BY-NC 4.0). All data collection parameters, inclusion/exclusion criteria, and cryptographic audit manifests are provided for computational reproducibility."*
