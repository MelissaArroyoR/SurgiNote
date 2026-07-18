"""Backend tests for SurgiNote import-censo async job + no-changes button endpoint + regressions."""
import io
import os
import time
import pytest
import requests
from docx import Document

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://surgeon-visit-helper.preview.emergentagent.com"
DEMO_EMAIL = "demo@surginote.app"
DEMO_PASS = "DemoSurgi2026!"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def _make_docx(paragraphs):
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


# -------- Bug 1: import-censo async ---------
def test_import_censo_empty_docx_returns_400(headers):
    buf = _make_docx([""])  # empty
    r = requests.post(
        f"{BASE_URL}/api/patients/import-censo",
        headers=headers,
        files={"file": ("empty.docx", buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        timeout=30,
    )
    assert r.status_code == 400, f"expected 400 for empty docx, got {r.status_code} {r.text}"


def test_import_censo_wrong_extension_returns_400(headers):
    r = requests.post(
        f"{BASE_URL}/api/patients/import-censo",
        headers=headers,
        files={"file": ("censo.txt", b"hello world", "text/plain")},
        timeout=30,
    )
    assert r.status_code == 400


def test_import_censo_returns_quickly_and_completes(headers):
    """CRITICAL: POST must return < 5s with job_id, status running. Then poll until done."""
    paragraphs = [
        "CENSO DE PRUEBA - CIRUGIA GENERAL",
        "1. PACIENTE PRUEBA UNO edad 50 sexo M cama 998 piso 9 Dx apendicitis Cx 15/07/2026 apendicectomia",
        "2. PACIENTE PRUEBA DOS edad 62 sexo F cama 999 piso 9 Dx colecistitis aguda Cx 20/07/2026 colecistectomia laparoscopica",
    ]
    buf = _make_docx(paragraphs)

    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/patients/import-censo",
        headers=headers,
        files={"file": ("censo.docx", buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        timeout=15,
    )
    elapsed = time.time() - t0
    assert r.status_code == 200, f"import failed: {r.status_code} {r.text}"
    data = r.json()
    assert "job_id" in data
    assert data["status"] == "running"
    assert elapsed < 5, f"POST took {elapsed:.2f}s (must be <5s to avoid Cloudflare 520)"
    job_id = data["job_id"]

    # Poll status
    result = None
    for _ in range(40):  # up to ~80s
        time.sleep(2)
        sr = requests.get(f"{BASE_URL}/api/patients/import-censo/status/{job_id}", headers=headers, timeout=15)
        assert sr.status_code == 200, sr.text
        sd = sr.json()
        if sd["status"] == "done":
            result = sd["result"]
            break
        if sd["status"] == "failed":
            pytest.fail(f"Import job failed: {sd.get('error')}")
    assert result is not None, "Import job did not finish within 80s"
    # Structure
    for key in ("new", "updated", "discharged", "errors", "parsed_count"):
        assert key in result, f"result missing key {key}: {result}"
    assert result["parsed_count"] >= 1, f"Expected at least 1 parsed patient, got {result}"

    # Persist created patient ids for later cleanup
    created_ids = [p["id"] for p in result["new"]]
    discharged_ids = [p["id"] for p in result["discharged"]]

    # ---- Verify new admissions ----
    for pid in created_ids:
        gr = requests.get(f"{BASE_URL}/api/patients/{pid}", headers=headers, timeout=15)
        assert gr.status_code == 200
        p = gr.json()
        assert p.get("is_new_admission") is True, f"is_new_admission should be True for {p['name']}"
        assert p.get("active") is True

    # ---- Verify discharged has active=false ----
    dr = requests.get(f"{BASE_URL}/api/patients/discharged", headers=headers, timeout=15)
    assert dr.status_code == 200
    discharged_list = dr.json()
    d_ids = {p["id"] for p in discharged_list}
    for did in discharged_ids:
        assert did in d_ids, f"discharged patient {did} not in /patients/discharged"
    # Ordering desc by discharged_at
    if len(discharged_list) >= 2:
        for i in range(len(discharged_list) - 1):
            a = discharged_list[i].get("discharged_at") or ""
            b = discharged_list[i + 1].get("discharged_at") or ""
            assert a >= b

    # ---- Readmit all discharged patients (restore real user data) ----
    for did in discharged_ids:
        rr = requests.post(f"{BASE_URL}/api/patients/{did}/readmit", headers=headers, timeout=15)
        assert rr.status_code == 200, f"readmit failed {did}: {rr.text}"
        gr = requests.get(f"{BASE_URL}/api/patients/{did}", headers=headers, timeout=15)
        assert gr.status_code == 200
        assert gr.json().get("active") is True
        assert gr.json().get("discharged_at") in (None, "")

    # ---- Delete test-created patients ----
    for pid in created_ids:
        requests.delete(f"{BASE_URL}/api/patients/{pid}", headers=headers, timeout=15)

    # Save for other tests
    pytest.import_result = result


def test_import_censo_status_not_found_returns_404(headers):
    r = requests.get(f"{BASE_URL}/api/patients/import-censo/status/nonexistent-id", headers=headers, timeout=15)
    assert r.status_code == 404


# -------- Bug 1d: history preserved when moving to discharged --------
def test_history_preserved_on_discharge(headers):
    """Create a patient with a daily entry, discharge via import (omitting name), verify entries remain."""
    # Create test patient
    cr = requests.post(
        f"{BASE_URL}/api/patients",
        headers=headers,
        json={"name": "PACIENTE PRUEBA HISTORIAL", "age": 40, "sex": "M", "bed": "997", "floor": "9", "dx_short": "test"},
        timeout=15,
    )
    assert cr.status_code == 200
    pid = cr.json()["id"]

    # Create daily entry
    er = requests.patch(
        f"{BASE_URL}/api/patients/{pid}/entries/today",
        headers=headers,
        json={"dictation": "TEST DICTATION HISTORICAL", "labs": "Hb 12", "studies": "", "events": ""},
        timeout=15,
    )
    assert er.status_code == 200

    # Discharge directly via readmit inverse: use PATCH? Simpler: import a censo without this name to trigger discharge.
    buf = _make_docx([
        "CENSO DE PRUEBA",
        "1. PACIENTE PRUEBA OTRO edad 30 cama 996 piso 9 Dx colecistitis",
    ])
    ir = requests.post(
        f"{BASE_URL}/api/patients/import-censo",
        headers=headers,
        files={"file": ("censo.docx", buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        timeout=15,
    )
    assert ir.status_code == 200
    job_id = ir.json()["job_id"]
    for _ in range(40):
        time.sleep(2)
        sr = requests.get(f"{BASE_URL}/api/patients/import-censo/status/{job_id}", headers=headers, timeout=15)
        if sr.json()["status"] in ("done", "failed"):
            break
    result = sr.json().get("result") or {}
    # The pid should now be discharged (not in current active list). Verify entry persists
    entries_r = requests.get(f"{BASE_URL}/api/patients/{pid}/entries", headers=headers, timeout=15)
    assert entries_r.status_code == 200
    entries = entries_r.json()
    assert any("TEST DICTATION HISTORICAL" in (e.get("dictation") or "") for e in entries), (
        f"daily_entries were lost after discharge! entries={entries}"
    )

    # Cleanup: readmit and delete
    requests.post(f"{BASE_URL}/api/patients/{pid}/readmit", headers=headers, timeout=15)
    requests.delete(f"{BASE_URL}/api/patients/{pid}", headers=headers, timeout=15)
    # Cleanup any new ones created by this import
    for np in result.get("new", []):
        requests.delete(f"{BASE_URL}/api/patients/{np['id']}", headers=headers, timeout=15)
    # Readmit any real patients accidentally discharged
    for dp in result.get("discharged", []):
        if dp["id"] != pid:
            requests.post(f"{BASE_URL}/api/patients/{dp['id']}/readmit", headers=headers, timeout=15)


# -------- Regression: existing endpoints --------
def test_login(headers):
    # token fixture already exercised login; verify /auth/me works
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json().get("email") == DEMO_EMAIL


def test_list_patients_active(headers):
    r = requests.get(f"{BASE_URL}/api/patients", headers=headers, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_discharged(headers):
    r = requests.get(f"{BASE_URL}/api/patients/discharged", headers=headers, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_no_changes_endpoint_exists(headers):
    """Verify POST /patients/{id}/generate/no-changes returns 404 for bogus id (not 405)."""
    r = requests.post(
        f"{BASE_URL}/api/patients/bogus-id/generate/no-changes",
        headers=headers,
        json={"date": None},
        timeout=15,
    )
    assert r.status_code == 404, f"expected 404 for missing patient, got {r.status_code} {r.text}"
