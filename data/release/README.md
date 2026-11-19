# Indonesian Presidential Election 2024 Political Polarization Dataset

**License:** [Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)](LICENSE)  
**Permanent DOI:** `https://doi.org/10.5281/zenodo.10242024`  
**Code Version (Git Commit):** `677f5aa0dd80acafd6639b69750bce4b5bef5de1`  
**Release Date:** 2026-11-19  

---

## 1. Overview & Data Availability Statement

### Data Availability Statement (for Journal Paper Submission)
> *"The complete dataset and reproducible scraping/cleaning pipeline supporting the findings of this study are openly available on Zenodo at https://doi.org/10.5281/zenodo.10242024 under a Creative Commons Attribution-NonCommercial 4.0 International license (CC BY-NC 4.0). In adherence to research data ethics, all personal identifiers have been pseudonymized via salted SHA-256 hashing, and direct contact information has been scrubbed. Full configuration parameters, inclusion criteria, and cryptographic manifest checksums are provided to ensure complete auditability and computational reproducibility."*

---

## 2. Methodology & Scraping Protocol (Paper Methods Section)

This dataset was harvested using an automated, configuration-driven multi-platform scraper designed specifically for academic transparency and peer review.

### A. Temporal Period
- **Start Date:** `2023-10-01`
- **End Date:** `2024-04-30`
- **Context:** Encompasses all critical phases of the 2024 Indonesian election: candidate registration (October 2023), campaign kick-off (November 2023), five official KPU presidential and vice-presidential debates (December 2023 - February 2024), voting day (14 February 2024), KPU national tabulation (March 2024), and Constitutional Court (*Mahkamah Konstitusi*) dispute rulings (April 2024).

### B. Platform Coverage & Query Strings
1. **YouTube (`text_comments_transcripts`)**:
   - Queries: `"debat capres 2024 pemilu anies prabowo ganjar"`, `"anies muhaimin pilpres 2024 koalisi perubahan"`, `"prabowo gibran pemilu 2024 gemoy dinasti"`, `"ganjar mahfud 2024 tabrak prof pemilu"`, `"sidang sengketa pilpres mahkamah konstitusi 2024"`.
   - Outlets: Accredited channels (*KompasTV*, *Mata Najwa*, *CNN Indonesia*, *tvOneNews*).
2. **Reddit r/indonesia (`text_posts_comments`)**:
   - Queries: `"pilpres 2024"`, `"debat capres"`, `"prabowo gibran"`, `"anies baswedan"`, `"ganjar mahfud"`, `"dinasti politik"`, `"bansos pemilu"`.
3. **Google News RSS (`news_articles`)**:
   - Queries: `"pilpres 2024 polarisasi opini"`, `"anies baswedan muhaimin iskandar"`, `"prabowo subianto gibran"`, `"ganjar pranowo mahfud md"`, `"mahkamah konstitusi sengketa hasil pilpres 2024"`.
4. **Multimodal Political Memes (`image_visual_multimodal`)**:
   - Queries: `"meme pemilu 2024"`, `"meme prabowo gemoy"`, `"meme anies abah"`, `"meme ganjar mahfud"`, `"meme fufufafa dinasti"`.

### C. Inclusion & Exclusion Criteria
- **Inclusion:** Posts containing substantive text (>= 15 characters) in Indonesian vernacular or standard register.
- **Exclusion Criteria:**
  - Automated retweets (`RT @...`).
  - URL-only posts without human commentary.
  - Known bots (`AutoModerator`, `RemindMeBot`).
  - Near-exact duplicates (deduplicated via normalized MD5 content hash).
  - Content falling outside the defined temporal window.

### D. Data Ethics & Anonymization
- **Pseudonymization:** User handles hashed as `sha256(salt + username)` -> `anon_{hash[:16]}`. The salt is preserved securely to enable intra-dataset co-reference and network graphs without exposing user identities.
- **In-Text PII Scrubbing:** Regular expressions replace Indonesian phone numbers with `[REDACTED_PHONE]`, email addresses with `[REDACTED_EMAIL]`, and `@mentions` with pseudonymized tokens.
- **Sensitive Metadata Elimination:** IP addresses, profile pictures, and exact geolocation coordinates were purged prior to dataset release.

### E. Limitations & Access Boundaries
- **Platform Constraints:** Direct API rate limits and terms of service prevented scraping platforms with closed authentication walls (e.g., private TikTok or Instagram feeds). For multimodal political memes, images were collected from public forums and representative curated templates.
- **Content Mutability:** Data represents a snapshot captured during the research run. Posts modified or deleted by users after the collection date (2026-11-19) are not retroactively updated.

---

## 3. Package Structure

```
data/release/
├── dataset.zip       # Compressed dataset (posts.jsonl, memes.jsonl, images)
├── README.md         # This documentation & Data Availability Statement
├── LICENSE           # CC BY-NC 4.0 Legal License
└── datasheet.md      # Gebru et al. Datasheet for Datasets specification
```

---

## 4. Citation

If you use this dataset or scraper in academic work, please cite:

```bibtex
@dataset{polarization_id_2024,
  author       = {{Computational Social Science Research Team}},
  title        = {{Indonesian 2024 Presidential Election Political Polarization Dataset (Multi-Platform)}},
  year         = {2026},
  publisher    = {{Zenodo}},
  version      = {{1.0.0}},
  doi          = {{10.5281/zenodo.10242024}},
  url          = {{https://doi.org/10.5281/zenodo.10242024}}
}
```
