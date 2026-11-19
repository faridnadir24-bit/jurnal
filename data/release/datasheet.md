# Datasheet for Dataset: Indonesian Presidential Election 2024 Political Polarization Dataset

Following the framework proposed by Gebru et al. (2021), *Datasheets for Datasets*, Communications of the ACM.

---

## 1. Motivation

### For what purpose was the dataset created?
This dataset was created to support empirical, reproducible computational social science research on political polarization, affective division, and public discourse dynamics in Indonesia during the 2024 Presidential Election (Pemilu 2024). It captures multi-platform textual discussions and multimodal visual political memes across key electoral milestones.

### Who created the dataset and on behalf of which entity?
The dataset was curated by the Computational Social Science and Political Polarization Research Group. Contact: `research.pemilu2024@gmail.com`.

### Who funded the creation of the dataset?
Academic university research grant for computational social science and democratic resilience studies.

---

## 2. Composition

### What do the instances that comprise the dataset represent?
The dataset consists of two primary subsets:
1. **Textual Discussions (`posts.jsonl`)**: Social media comments, discussions, and news articles discussing the 2024 presidential candidates (Anies Baswedan-Muhaimin Iskandar, Prabowo Subianto-Gibran Rakabuming, Ganjar Pranowo-Mahfud MD), debates, institutional controversies (Constitutional Court/MK rulings, KPU Sirekap), and political polarization.
2. **Multimodal Political Memes (`memes.jsonl` and `memes/`)**: Digital image memes paired with textual captions, engagement metrics, and polarization stance tags (Paslon 01, Paslon 02, Paslon 03, Satire/Neutral).

### How many instances are there in total?
- Target scale: >= 10,000 textual posts across >= 3 platforms (YouTube, Reddit, Google News).
- Multimodal scale: >= 500 visual meme images with high-resolution metadata.

### Does the dataset contain data that might be considered confidential or personally identifiable?
No. All direct identifiers (usernames, channel IDs, user IDs) have been rigorously pseudonymized using **SHA-256 with a cryptographic salt** (`anon_{hash[:16]}`). Direct PII such as email addresses, Indonesian cellular telephone numbers (`08...`, `+628...`), and `@mentions` have been scrubbed or redacted. Sensitive metadata (IP addresses, avatar URLs, GPS coordinates) was stripped during ingestion.

---

## 3. Collection Process

### How was the data associated with each instance acquired?
Data was harvested using modular, reproducible scrapers adhering strictly to polite rate-limiting ($30$ req/min with randomized jitter) and robots.txt policies:
- **Google News RSS**: Indonesian domestic news articles using election queries.
- **Reddit (r/indonesia)**: Public submissions and comment threads discussing political debates and campaign events.
- **YouTube**: Political debate comments and panel discourse from major accredited news channels (KompasTV, Mata Najwa, CNN Indonesia, tvOneNews).
- **Political Memes**: Multimodal visual content and captions categorized by electoral candidate and campaign tropes (e.g., *Gemoy*, *Desak Anies*, *Tabrak Prof*, *Bansos*).

### What was the sampling strategy?
Targeted query-based sampling covering three political coalitions and institutional controversies across the temporal window from **2023-10-01 to 2024-04-30** (encompassing candidate registration, official campaign, five presidential debates, voting day 14 Feb 2024, KPU national tabulation, and Constitutional Court dispute rulings).

---

## 4. Preprocessing / Cleaning / Labeling

### Was any preprocessing/cleaning/labeling done?
Yes. The dataset enforces strict, transparent inclusion and exclusion criteria:
- **Exclusion of short noise**: Posts with fewer than $15$ characters were removed.
- **Exclusion of retweets/broadcast spam**: Automated `RT @...` patterns were stripped.
- **Exclusion of URL-only posts**: Entries lacking substantive human commentary were excluded.
- **Exclusion of automated bots**: Recognized moderation and utility bots (`AutoModerator`, `RemindMeBot`) were filtered out.
- **Linguistic verification**: Verified presence of Indonesian language markers to exclude irrelevant multilingual noise.
- **Deduplication**: Exact and normalized text hashing to remove astroturfing spam.
- **Ethical Anonymization**: Cryptographic salted SHA-256 pseudonymization.

---

## 5. Uses

### Has the dataset been used for any tasks already?
The dataset serves as the benchmark corpus for evaluating political polarization, affective sentiment analysis, topic modeling (BERTopic/LDA), and multimodal visual rhetoric in the 2024 Indonesian Presidential Election.

### What tasks is the dataset suited for?
- Stance detection and electoral polarization modeling.
- Temporal sentiment trajectory analysis surrounding candidate debates.
- Multimodal meme classification and visual framing analysis.
- Social network pseudonymized interaction graph topology.

### What tasks should the dataset NOT be used for?
- Commercial marketing, user tracking, or behavioral profiling.
- De-anonymization or doxxing attempts against individual social media users.
- Automated surveillance or political targeting.

---

## 6. Distribution

### How will the dataset be distributed?
Packaged as a compressed archive (`dataset.zip`) deposited in open scientific repositories (Zenodo / Figshare) with a permanent Digital Object Identifier (DOI).

### Under what license is the dataset distributed?
**Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**. Academic and educational reuse is permitted with proper citation; commercial exploitation is prohibited.

---

## 7. Maintenance

### Who is supporting/maintaining the dataset?
Maintained by the original research team.
- **Version**: `1.0.0` (Code commit: `677f5aa0dd80acafd6639b69750bce4b5bef5de1`)
- **Datasheet Revision Date**: `2026-11-19`
- **Errata and Contact**: Inquiries or errata should be directed to `research.pemilu2024@gmail.com`.
