import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import shutil
from pathlib import Path

REAL_DOCX = Path("data/letters/district_administration/banking_cell/banking_cell_forwarding_letters.docx")


def _seed_letters(client):
    letters = [
        ("edu-1", "शिक्षकों की कमी के संबंध में जिला शिक्षा पदाधिकारी को पत्र", "education", "forwarding_request", "शिक्षकों की कमी"),
        ("edu-2", "विद्यालय भवन मरम्मत शिक्षक नियुक्ति के संबंध में पत्र", "education", "general_correspondence", "भवन मरम्मत"),
        ("rev-1", "भूमि अधिग्रहण के संबंध में राजस्व पदाधिकारी को पत्र", "revenue", "forwarding_request", "भूमि अधिग्रहण"),
        ("rev-2", "भूमि विवाद खाता संख्या सुधार के संबंध में राजस्व पदाधिकारी को पत्र", "revenue", "general_correspondence", "भूमि विवाद"),
        ("rev-3", "भूमि अधिग्रहण मुआवजा राशि के संबंध में राजस्व पदाधिकारी को पत्र", "revenue", "general_correspondence", "मुआवजा राशि"),
    ]
    ids = [l[0] for l in letters]
    texts = [l[1] for l in letters]
    metas = [
        {"department": l[2], "letter_type": l[3], "subject": l[4], "letter_id": l[0],
         "source_file": "data/letters/education/office/x.docx", "needs_review": False}
        for l in letters
    ]
    client.store.add_letters(ids, client.embedder.embed(texts), texts, metas)
    return ids


def test_departments_and_letter_types_empty_when_no_letters(api_client):
    assert api_client.get("/api/departments").json() == []
    assert api_client.get("/api/letter-types").json() == []


def test_departments_and_letter_types_after_seeding(api_client):
    _seed_letters(api_client)
    assert api_client.get("/api/departments").json() == ["education", "revenue"]
    assert set(api_client.get("/api/letter-types").json()) == {"forwarding_request", "general_correspondence"}


def test_generate_returns_draft_and_references(api_client):
    _seed_letters(api_client)
    resp = api_client.post("/api/generate", json={
        "request": "शिक्षकों की कमी के संबंध में पत्र तैयार करें।",
        "department": "education",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["draft"] == api_client.ollama_client.canned_response
    assert body["department_used"] == "education"
    assert body["department_auto_detected"] is False
    assert len(body["references"]) > 0
    assert all(r["department"] == "education" for r in body["references"])


def test_generate_auto_detects_department_when_omitted(api_client):
    _seed_letters(api_client)
    resp = api_client.post("/api/generate", json={
        "request": "भूमि अधिग्रहण के संबंध में राजस्व पदाधिकारी को पत्र तैयार करें",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["department_used"] == "revenue"
    assert body["department_auto_detected"] is True


def test_generate_prompt_sent_to_ollama_separates_trust_sections(api_client):
    _seed_letters(api_client)
    api_client.post("/api/generate", json={"request": "शिक्षकों की कमी के संबंध में पत्र", "department": "education"})
    messages = api_client.ollama_client.last_messages
    assert messages[0]["role"] == "system"
    assert "उपयोगकर्ता द्वारा दिए गए तथ्य" in messages[1]["content"]


def test_export_docx_returns_file(api_client):
    resp = api_client.post("/api/export/docx", json={"draft": "सारण समाहरणालय\n\nविषय: परीक्षण"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert len(resp.content) > 100


def test_export_pdf_returns_file_or_clean_503(api_client):
    resp = api_client.post("/api/export/pdf", json={"draft": "सारण समाहरणालय\n\nविषय: परीक्षण"})
    # soffice may or may not be installed wherever this suite runs --
    # both outcomes are acceptable, a silent crash is not.
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert resp.content[:4] == b"%PDF"


def test_admin_documents_empty_initially(api_client):
    assert api_client.get("/api/admin/documents").json() == []


def test_admin_upload_ingests_and_indexes_real_docx(api_client):
    with REAL_DOCX.open("rb") as f:
        resp = api_client.post(
            "/api/admin/upload",
            files={"file": ("banking_cell_forwarding_letters.docx", f,
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"department": "district_administration", "office": "banking_cell"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["letters_found"] == 45
    assert body["letters_indexed"] == 45

    docs = api_client.get("/api/admin/documents").json()
    assert len(docs) == 1
    assert docs[0]["segment_count"] == 45


def test_admin_upload_rejects_unsafe_department_slug(api_client):
    with REAL_DOCX.open("rb") as f:
        resp = api_client.post(
            "/api/admin/upload",
            files={"file": ("x.docx", f, "application/octet-stream")},
            data={"department": "../../etc", "office": "x"},
        )
    assert resp.status_code == 400


def test_admin_get_and_delete_document(api_client):
    with REAL_DOCX.open("rb") as f:
        api_client.post(
            "/api/admin/upload",
            files={"file": ("letter.docx", f, "application/octet-stream")},
            data={"department": "education", "office": "test_office"},
        )
    doc_id = api_client.get("/api/admin/documents").json()[0]["doc_id"]

    detail = api_client.get(f"/api/admin/documents/{doc_id}")
    assert detail.status_code == 200
    assert len(detail.json()) == 45

    delete_resp = api_client.delete(f"/api/admin/documents/{doc_id}")
    assert delete_resp.status_code == 200
    assert api_client.get("/api/admin/documents").json() == []
    assert api_client.store.count() == 0


def test_admin_delete_document_rejects_path_traversal(api_client):
    resp = api_client.delete("/api/admin/documents/Li4vLi4vZXRjL3Bhc3N3ZA==")
    assert resp.status_code == 400


def test_admin_letters_list_and_delete_one_segment(api_client):
    ids = _seed_letters(api_client)
    letters = api_client.get("/api/admin/letters").json()
    assert len(letters) == 5

    resp = api_client.delete(f"/api/admin/letters/{ids[0]}")
    assert resp.status_code == 200
    assert api_client.store.count() == 4


def test_admin_letters_filter_by_department(api_client):
    _seed_letters(api_client)
    letters = api_client.get("/api/admin/letters", params={"department": "education"}).json()
    assert len(letters) == 2
    assert all(l["department"] == "education" for l in letters)


def test_admin_delete_letter_not_found(api_client):
    resp = api_client.delete("/api/admin/letters/does-not-exist")
    assert resp.status_code == 404


def test_admin_update_letter_metadata_writes_sidecar_and_reembeds(api_client, tmp_path):
    with REAL_DOCX.open("rb") as f:
        api_client.post(
            "/api/admin/upload",
            files={"file": ("letter.docx", f, "application/octet-stream")},
            data={"department": "education", "office": "test_office"},
        )
    letter_id = api_client.get("/api/admin/letters").json()[0]["letter_id"]

    resp = api_client.patch(f"/api/admin/letters/{letter_id}/metadata", json={"department": "revenue"})
    assert resp.status_code == 200
    assert resp.json()["metadata"]["department"] == "revenue"

    updated = api_client.get("/api/admin/letters", params={"department": "revenue"}).json()
    assert any(l["letter_id"] == letter_id for l in updated)

    sidecar_path = api_client.data_dir / "education" / "test_office" / ".meta" / f"{letter_id}.meta.json"
    assert sidecar_path.exists()
    assert "revenue" in sidecar_path.read_text(encoding="utf-8")


def test_admin_reindex_rebuilds_from_disk(api_client):
    dest_dir = api_client.data_dir / "district_administration" / "banking_cell"
    dest_dir.mkdir(parents=True)
    shutil.copy(REAL_DOCX, dest_dir / REAL_DOCX.name)

    resp = api_client.post("/api/admin/reindex")
    assert resp.status_code == 200
    body = resp.json()
    assert body["letters_found"] == 45
    assert api_client.store.count() == 45


def test_admin_search(api_client):
    _seed_letters(api_client)
    resp = api_client.get("/api/admin/search", params={"q": "भूमि अधिग्रहण राजस्व पदाधिकारी"})
    assert resp.status_code == 200
    results = resp.json()
    assert results[0]["letter_id"] == "rev-1"
