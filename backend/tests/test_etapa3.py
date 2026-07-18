"""Etapa 3 backend tests:
- training-examples GET/PUT
- import-censo end-to-end with strict Col5 classification & Col3 dx vs procedure split
- generate/note Piso vs UTI (formato mayúsculas, sin listas, WhatsApp header exacto)
- generate/no-changes con mismo formato
- regresiones
"""
import io
import os
import re
import time
import pytest
import requests
from docx import Document

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://surgeon-visit-helper.preview.emergentagent.com"
DEMO_EMAIL = "demo@surginote.app"
DEMO_PASS = "DemoSurgi2026!"


@pytest.fixture(scope="module")
def headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": DEMO_EMAIL, "password": DEMO_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json()["token"]
    return {"Authorization": f"Bearer {tok}"}


# ---------------- training examples ----------------
def test_training_examples_get_default_empty(headers):
    # First reset to empty to guarantee default state
    put = requests.put(f"{BASE_URL}/api/training-examples", headers=headers, json={
        "hospital_notes_examples": "",
        "uti_notes_examples": "",
        "whatsapp_examples": "",
    }, timeout=30)
    assert put.status_code == 200
    r = requests.get(f"{BASE_URL}/api/training-examples", headers=headers, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d.get("hospital_notes_examples") == ""
    assert d.get("uti_notes_examples") == ""
    assert d.get("whatsapp_examples") == ""


def test_training_examples_put_and_persist(headers):
    payload = {
        "hospital_notes_examples": "TEST_HOSP_EXAMPLE\nNOTA DE PISO EJEMPLO",
        "uti_notes_examples": "TEST_UTI_EXAMPLE\nNOTA UTI",
        "whatsapp_examples": "TEST_WA_EXAMPLE\nBUENOS DIAS DR X",
    }
    r = requests.put(f"{BASE_URL}/api/training-examples", headers=headers, json=payload, timeout=30)
    assert r.status_code == 200
    # GET back
    g = requests.get(f"{BASE_URL}/api/training-examples", headers=headers, timeout=30)
    assert g.status_code == 200
    d = g.json()
    assert d["hospital_notes_examples"] == payload["hospital_notes_examples"]
    assert d["uti_notes_examples"] == payload["uti_notes_examples"]
    assert d["whatsapp_examples"] == payload["whatsapp_examples"]

    # Cleanup: reset to empty
    requests.put(f"{BASE_URL}/api/training-examples", headers=headers, json={
        "hospital_notes_examples": "",
        "uti_notes_examples": "",
        "whatsapp_examples": "",
    }, timeout=30)


# ---------------- import-censo end-to-end ----------------
def _build_etapa3_docx():
    doc = Document()
    table = doc.add_table(rows=1, cols=6)
    row_data = [
        "S81\nDr. Ricardo Pérez López\nDr. Res1",
        "TEST JUAN MENDOZA GARCIA\n67\nDEIH 5 DPQX 3",
        (
            "ANTECEDENTE DE CARCINOMA RENAL DE CELULAS CLARAS\n"
            "ADENOCARCINOMA PULMONAR METASTASICO\n"
            "PADUA 7\nECOG 1\nT4N3M1\n"
            "12/06/26\nPANENDOSCOPIA + COLONOSCOPIA\n"
            "16/06/26\nPO LAPE + HEMICOLECTOMIA DERECHA + ITALLMR"
        ),
        "OMEPRAZOL 40 MG IV C/24H\nMETAMIZOL 1G IV PRN\nENOXAPARINA 40 MG SC C/24H",
        (
            "LABS 12/06/26\nHB 10.2 LEU 8.5 PLT 220\n"
            "TAC ABD 13/06/26\nSin colecciones.\n"
            "COLONOSCOPIA 15/06/26\nPólipos.\n"
            "HEMOCULTIVOS 14/06/26\nSin desarrollo."
        ),
        "TA 120/70 FC 85 T 36.8",
    ]
    cells = table.add_row().cells
    for i, v in enumerate(row_data):
        cells[i].text = v
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


@pytest.fixture(scope="module")
def imported_patient(headers):
    """Import a censo with confirm=true and return the created patient dict + today entry."""
    buf = _build_etapa3_docx()
    r = requests.post(f"{BASE_URL}/api/patients/import-censo?confirm=true",
                      headers=headers,
                      files={"file": ("censo.docx", buf, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
                      timeout=30)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    result = None
    for _ in range(30):
        time.sleep(1.5)
        s = requests.get(f"{BASE_URL}/api/patients/import-censo/status/{job_id}",
                         headers=headers, timeout=15)
        assert s.status_code == 200
        js = s.json()
        if js["status"] == "done":
            result = js["result"]
            break
        if js["status"] == "failed":
            pytest.fail(f"job failed: {js.get('error')}")
    assert result, "job never completed"
    new = result.get("new") or []
    # Find our test patient
    target = next((p for p in new if "TEST JUAN MENDOZA" in p["name"]), None)
    assert target, f"Test patient not in new list: {new}"
    pid = target["id"]

    # Fetch patient
    pr = requests.get(f"{BASE_URL}/api/patients/{pid}", headers=headers, timeout=15)
    assert pr.status_code == 200
    patient = pr.json()

    # Fetch today entry
    er = requests.get(f"{BASE_URL}/api/patients/{pid}/entries/today", headers=headers, timeout=15)
    assert er.status_code == 200
    entry = er.json()

    # Readmit any accidentally discharged
    for dp in (result.get("discharged") or []):
        requests.post(f"{BASE_URL}/api/patients/{dp['id']}/readmit", headers=headers, timeout=15)

    yield {"patient": patient, "entry": entry, "pid": pid}

    # Teardown: delete test patient
    requests.delete(f"{BASE_URL}/api/patients/{pid}", headers=headers, timeout=15)


def test_import_dx_short_excludes_procedure(imported_patient):
    dx_short = (imported_patient["patient"].get("dx_short") or "").upper()
    assert "CARCINOMA" in dx_short, f"dx_short must contain CARCINOMA: {dx_short!r}"
    assert "PANENDOSCOPIA" not in dx_short, f"dx_short must not contain procedure: {dx_short!r}"
    assert "LAPE" not in dx_short, f"dx_short must not contain LAPE: {dx_short!r}"


def test_import_dx_full_has_classifications(imported_patient):
    dx_full = (imported_patient["patient"].get("dx_full") or "").upper()
    assert "CLASIFICACIONES:" in dx_full, f"dx_full missing CLASIFICACIONES section: {dx_full!r}"
    assert "PADUA 7" in dx_full
    assert "ECOG 1" in dx_full
    assert "T4N3M1" in dx_full


def test_import_important_medications(imported_patient):
    meds = (imported_patient["patient"].get("important_medications") or "").upper()
    assert "OMEPRAZOL" in meds, f"expected OMEPRAZOL: {meds!r}"


def test_import_today_entry_buckets(imported_patient):
    e = imported_patient["entry"]
    labs = (e.get("labs") or "").upper()
    studies = (e.get("studies") or "").upper()
    procedures = (e.get("procedures") or "").upper()
    cultures = (e.get("cultures") or "").upper()

    # Buckets not all empty
    assert any([labs, studies, procedures, cultures]), "All 4 buckets are empty"

    # labs strict
    assert "LABS" in labs, f"labs missing LABS chunk: {labs!r}"
    assert "TAC" not in labs, f"labs must NOT contain TAC: {labs!r}"
    assert "COLONOSCOPIA" not in labs, f"labs must NOT contain COLONOSCOPIA: {labs!r}"
    assert "HEMOCULTIVO" not in labs, f"labs must NOT contain HEMOCULTIVO: {labs!r}"

    # studies has TAC, not COLONOSCOPIA
    assert "TAC" in studies, f"studies missing TAC: {studies!r}"
    assert "COLONOSCOPIA" not in studies, f"studies must NOT contain COLONOSCOPIA: {studies!r}"

    # procedures has PANENDOSCOPIA + HEMICOLECTOM + COLONOSCOPIA
    assert "PANENDOSCOPIA" in procedures, f"procedures missing PANENDOSCOPIA: {procedures!r}"
    assert "HEMICOLECTOM" in procedures, f"procedures missing HEMICOLECTOM: {procedures!r}"
    assert "COLONOSCOPIA" in procedures, f"procedures missing COLONOSCOPIA: {procedures!r}"

    # cultures has HEMOCULTIVO
    assert "HEMOCULTIVO" in cultures, f"cultures missing HEMOCULTIVO: {cultures!r}"


# ---------------- generate/note (Piso + UTI) ----------------
def _create_min_patient(headers, name, unit):
    body = {
        "name": name,
        "unit_classification": unit,
        "dx_short": "APENDICITIS AGUDA",
        "attending_physician": "Dr. Juan Pérez López",
        "bed": "801",
        "floor": "8",
        "age": 40,
        "sex": "M",
        "is_surgical": False,
        "is_pending_discharge": False,
    }
    r = requests.post(f"{BASE_URL}/api/patients", headers=headers, json=body, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _uppercase_ratio(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c.isupper()) / len(letters)


def _has_bullets(text):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("- ") or s.startswith("* ") or s.startswith("• "):
            return True
        if re.match(r"^\d+\.\s", s):
            return True
    return False


@pytest.fixture(scope="module")
def piso_patient_id(headers):
    pid = _create_min_patient(headers, "TEST_PISO_PATIENT", "Piso")
    yield pid
    requests.delete(f"{BASE_URL}/api/patients/{pid}", headers=headers, timeout=15)


@pytest.fixture(scope="module")
def uti_patient_id(headers):
    pid = _create_min_patient(headers, "TEST_UTI_PATIENT", "UTI")
    yield pid
    requests.delete(f"{BASE_URL}/api/patients/{pid}", headers=headers, timeout=15)


def _call_llm_or_skip(url, headers, json_body):
    r = requests.post(url, headers=headers, json=json_body, timeout=120)
    if r.status_code >= 500:
        body = r.text or ""
        if "budget" in body.lower() or "billing" in body.lower() or "quota" in body.lower():
            pytest.skip(f"LLM budget/quota exhausted: {body[:200]}")
    assert r.status_code == 200, f"{url} → {r.status_code}: {r.text[:400]}"
    return r.json()


def test_generate_note_piso(piso_patient_id, headers):
    data = _call_llm_or_skip(f"{BASE_URL}/api/patients/{piso_patient_id}/generate/note",
                             headers, {"date": None})
    note = data.get("note") or ""
    wa = data.get("whatsapp") or ""
    assert note.strip(), "note is empty"
    assert wa.strip(), "whatsapp is empty"

    # note in uppercase
    ratio = _uppercase_ratio(note)
    assert ratio >= 0.85, f"note not uppercase enough ({ratio:.2f}): {note[:200]}"
    # no bullets
    assert not _has_bullets(note), f"note has bullets/numbered lists: {note[:400]}"

    # WhatsApp header
    assert wa.upper().lstrip().startswith("BUENOS DÍAS DR.") or wa.upper().lstrip().startswith("BUENOS DIAS DR."), \
        f"whatsapp header wrong: {wa[:120]!r}"
    assert "PASE CON" in wa.upper(), f"whatsapp missing 'PASE CON': {wa[:200]!r}"
    assert "CAMA" in wa.upper(), f"whatsapp missing 'CAMA': {wa[:200]!r}"


def test_generate_note_uti(uti_patient_id, headers):
    data = _call_llm_or_skip(f"{BASE_URL}/api/patients/{uti_patient_id}/generate/note",
                             headers, {"date": None})
    note = (data.get("note") or "").upper()
    assert note.strip(), "note is empty"
    # UTI sections
    sections = ["NEUROLÓGICO", "CARDIOVASCULAR", "RESPIRATORIO", "RENAL", "INFECCIOSO"]
    matched = [s for s in sections if s in note or s.replace("Ó", "O") in note]
    assert len(matched) >= 3, f"UTI note missing typical sections; found={matched}. Note head: {note[:400]}"
    ratio = _uppercase_ratio(data.get("note") or "")
    assert ratio >= 0.85, f"UTI note not uppercase enough ({ratio:.2f})"


def test_generate_no_changes_format(piso_patient_id, headers):
    data = _call_llm_or_skip(f"{BASE_URL}/api/patients/{piso_patient_id}/generate/no-changes",
                             headers, {"date": None})
    note = data.get("note") or ""
    wa = data.get("whatsapp") or ""
    assert note.strip() and wa.strip()
    ratio = _uppercase_ratio(note)
    assert ratio >= 0.85, f"no-changes note not uppercase ({ratio:.2f}): {note[:200]}"
    assert not _has_bullets(note), f"no-changes note has bullets: {note[:400]}"
    assert wa.upper().lstrip().startswith("BUENOS DÍAS DR.") or wa.upper().lstrip().startswith("BUENOS DIAS DR."), \
        f"whatsapp header wrong: {wa[:120]!r}"


# ---------------- regressions ----------------
def test_auth_me(headers):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json().get("email") == DEMO_EMAIL


def test_list_patients(headers):
    r = requests.get(f"{BASE_URL}/api/patients", headers=headers, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_patient_by_id(headers, piso_patient_id):
    r = requests.get(f"{BASE_URL}/api/patients/{piso_patient_id}", headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.json().get("id") == piso_patient_id
