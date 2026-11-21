import io
import json
import zipfile
from pathlib import Path
import pytest
from PIL import Image

from src.adapters.meme_dataset_loader import MemeDatasetLoader
from src.utils.rate_limiter import PoliteRateLimiter


@pytest.fixture
def loader_fixture(tmp_path):
    raw_img = tmp_path / "raw_memes"
    proc_img = tmp_path / "proc_memes"
    raw_ext = tmp_path / "raw_ext"
    proc_dir = tmp_path / "proc"
    checkpoints = tmp_path / "checkpoints"

    loader = MemeDatasetLoader(
        name="meme_dataset",
        config={"user_agent": "AcademicTestBot/1.0"},
        rate_limiter=PoliteRateLimiter(requests_per_minute=1000, enabled=False),
        checkpoints_dir=checkpoints,
        dry_run=False,
        raw_img_dir=raw_img,
        processed_img_dir=proc_img,
        raw_dir=raw_ext,
        processed_dir=proc_dir,
    )
    return loader


def test_parse_timestamp_formats(loader_fixture):
    # Format 1: Filename timestamp (YYYY-MM-DD_HH-MM-SS_UTC)
    t1 = loader_fixture._parse_timestamp("2024-03-20_10-13-09_UTC.jpg")
    assert t1 == "2024-03-20T10:13:09Z"

    # Format 2: Simple date in string
    t2 = loader_fixture._parse_timestamp("meme_2024-02-14_pilpres.png")
    assert t2 == "2024-02-14T12:00:00Z"

    # Format 3: Twitter style date
    t3 = loader_fixture._parse_timestamp("Wed Sep 11 04:24:17 +0000 2024")
    assert t3.startswith("2024-09-11")


def test_compute_sha256(loader_fixture, tmp_path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("Indonesian political memes dataset integrity check", encoding="utf-8")
    hash_val = loader_fixture._compute_sha256(test_file)
    assert isinstance(hash_val, str)
    assert len(hash_val) == 64


def test_extract_from_zip_with_companion_metadata(loader_fixture, tmp_path):
    # Create a real test zip file containing a valid image file
    zip_path = tmp_path / "test_corpus.zip"
    img_filename = "2024-02-14_08-30-00_UTC.jpg"

    # Generate a real valid JPEG image binary
    img_buf = io.BytesIO()
    img = Image.new("RGB", (300, 300), color=(50, 100, 150))
    img.save(img_buf, format="JPEG")
    img_bytes = img_buf.getvalue()

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"data/labeled_image/{img_filename}", img_bytes)

    # Create companion CSV
    csv_path = tmp_path / "labeled_image.csv"
    csv_content = (
        "path,caption,target_caption,label\n"
        f"data/labeled_image/{img_filename},Meme politik pemilu coblosan 2024,Humor satire elektoral,Non Toxic\n"
    )
    csv_path.write_text(csv_content, encoding="utf-8")

    out_jsonl = tmp_path / "memes_extracted.jsonl"
    count = loader_fixture.extract_from_zip(
        zip_path=zip_path,
        csv_path=csv_path,
        companion_jsonl=out_jsonl,
        limit=10,
    )

    assert count == 1
    assert (loader_fixture.raw_img_dir / img_filename).exists()
    assert (loader_fixture.processed_img_dir / img_filename).exists()

    # Verify extracted JSONL content
    lines = [json.loads(l) for l in out_jsonl.read_text(encoding="utf-8").strip().split("\n")]
    assert len(lines) == 1
    rec = lines[0]
    assert rec["source"] == "meme_dataset"
    assert "Meme politik pemilu coblosan 2024" in rec["caption"]
    assert rec["label"] == "Non Toxic"
    assert rec["published_at"] == "2024-02-14T08:30:00Z"
    assert rec["engagement"]["upvotes"] == 100
    assert rec["image_metadata"]["filename"] == img_filename
    assert len(rec["image_metadata"]["sha256"]) == 64


def test_no_synthetic_image_generation(loader_fixture):
    # Attempting to download from invalid/empty URL must return None and NOT generate dummy images
    res = loader_fixture.download_real_image("", "dummy.jpg")
    assert res is None
    assert not (loader_fixture.raw_img_dir / "dummy.jpg").exists()

    res2 = loader_fixture.download_real_image("not_a_valid_url", "dummy2.jpg")
    assert res2 is None
    assert not (loader_fixture.raw_img_dir / "dummy2.jpg").exists()


def test_political_keywords_matching(loader_fixture):
    # Valid political phrases
    assert loader_fixture.contains_political_keyword("Meme tentang capres dan cawapres pilpres 2024") is True
    assert loader_fixture.contains_political_keyword("Aksi prabowo gibran gemoy di panggung kampanye") is True
    assert loader_fixture.contains_political_keyword("Sidang sengketa hasil pilpres di MK dan sirekap KPU") is True
    assert loader_fixture.contains_political_keyword("Anies dan cak imin orasi politik partai") is True
    assert loader_fixture.contains_political_keyword("Ganjar mahfud ajak warga nyoblos bawaslu") is True

    # Slang, candidate names, typos, and election terms
    assert loader_fixture.contains_political_keyword("Poster dukungan prabowo-gibran menang satu putaran") is True
    assert loader_fixture.contains_political_keyword("Gerakan AMIN perubahan bersama anies baswedan") is True
    assert loader_fixture.contains_political_keyword("Debat paslon 01 vs 02 vs 03 di televisi") is True
    assert loader_fixture.contains_political_keyword("Caleg DPR bagi bansos dan serangan fajar") is True
    assert loader_fixture.contains_political_keyword("Surat suara pilpres di coblos warga di TPS") is True

    # Non-political phrases (e.g. meme umum / kucing / benign substrings / foreign politics)
    assert loader_fixture.contains_political_keyword("Meme kucing lucu tidur di kamar") is False
    assert loader_fixture.contains_political_keyword("Resep membuat kopi susu enak di pagi hari") is False
    assert loader_fixture.contains_political_keyword("Jangan lupa minum vitamin C setiap hari") is False
    assert loader_fixture.contains_political_keyword("Warga panik saat gempa terjadi di pegunungan") is False
    assert loader_fixture.contains_political_keyword("Makan siang di Marshanies Kitchen sangat lezat") is False
    assert loader_fixture.contains_political_keyword("Donald Trump mantan presiden Amerika Serikat") is False
    assert loader_fixture.contains_political_keyword("") is False


def test_extract_from_zip_skips_non_political(loader_fixture, tmp_path):
    zip_path = tmp_path / "mixed_corpus.zip"
    img_pol = "2024-02-14_08-30-00_UTC.jpg"
    img_cat = "2024-02-14_09-00-00_UTC.jpg"

    img_buf = io.BytesIO()
    Image.new("RGB", (200, 200), color=(10, 20, 30)).save(img_buf, format="JPEG")
    img_bytes = img_buf.getvalue()

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"data/{img_pol}", img_bytes)
        zf.writestr(f"data/{img_cat}", img_bytes)

    csv_path = tmp_path / "mixed_labels.csv"
    csv_content = (
        "path,caption,target_caption,label\n"
        f"data/{img_pol},Meme debat capres pemilu gemoy,Politik,Non Toxic\n"
        f"data/{img_cat},Kucing lucu sedang mengeong minta makan,Hewan,Netral\n"
    )
    csv_path.write_text(csv_content, encoding="utf-8")

    out_jsonl = tmp_path / "extracted.jsonl"
    count = loader_fixture.extract_from_zip(
        zip_path=zip_path,
        csv_path=csv_path,
        companion_jsonl=out_jsonl,
    )

    # Only political meme should be extracted
    assert count == 1
    assert (loader_fixture.raw_img_dir / img_pol).exists()
    assert not (loader_fixture.raw_img_dir / img_cat).exists()


def test_is_political_image_nonexistent_file():
    from src.adapters.meme_dataset_loader import is_political_image, evaluate_political_image
    assert is_political_image("nonexistent_image_path_12345.jpg") is False
    is_pol, prob = evaluate_political_image("nonexistent_image_path_12345.jpg")
    assert is_pol is False
    assert prob == 0.0


def test_is_political_image_with_clip(monkeypatch, tmp_path):
    from src.adapters.meme_dataset_loader import is_political_image, evaluate_political_image
    import torch

    test_img_path = tmp_path / "test_pol.jpg"
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img.save(test_img_path)

    # Test 1: Mock model output where political prob > 0.5
    class MockOutputsPol:
        logits_per_image = torch.tensor([[10.0, 5.0, 1.0, 1.0]])  # High probability on index 0 and 1

    class MockProcessor:
        def __call__(self, text, images, return_tensors, padding):
            return {"input_ids": torch.tensor([[1, 2]])}

    class MockModel:
        def to(self, device):
            return self
        def eval(self):
            return self
        def __call__(self, **kwargs):
            return MockOutputsPol()

    monkeypatch.setattr("src.adapters.meme_dataset_loader.get_clip_model", lambda: (MockModel(), MockProcessor(), "cpu"))

    is_pol, prob = evaluate_political_image(test_img_path)
    assert is_pol is True
    assert prob > 0.5
    assert is_political_image(test_img_path) is True

    # Test 2: Mock model output where political prob < 0.5 (e.g. cat meme)
    class MockOutputsCat:
        logits_per_image = torch.tensor([[1.0, 1.0, 15.0, 5.0]])  # High prob on index 2 (cat meme)

    class MockModelCat:
        def to(self, device):
            return self
        def eval(self):
            return self
        def __call__(self, **kwargs):
            return MockOutputsCat()

    monkeypatch.setattr("src.adapters.meme_dataset_loader.get_clip_model", lambda: (MockModelCat(), MockProcessor(), "cpu"))

    is_pol_cat, prob_cat = evaluate_political_image(test_img_path)
    assert is_pol_cat is False
    assert prob_cat < 0.5
    assert is_political_image(test_img_path) is False


def test_extract_text_from_image(monkeypatch, tmp_path):
    from src.adapters.meme_dataset_loader import extract_text_from_image

    assert extract_text_from_image("nonexistent_1234.jpg") == ""

    test_img = tmp_path / "test_ocr_meme.jpg"
    img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    img.save(test_img)

    class MockReader:
        def readtext(self, img_input, detail=0):
            return ["Coblos", "Prabowo", "Gibran", "Pemilu", "2024"]

    monkeypatch.setattr("src.adapters.meme_dataset_loader.get_ocr_reader", lambda: MockReader())

    res = extract_text_from_image(test_img)
    assert res == "Coblos Prabowo Gibran Pemilu 2024"


