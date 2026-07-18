"""Test the deterministic .docx parser (Etapa 3 corrections):
- Col3: separate diagnoses, procedures with date, and classifications.
- Col5: strict Labs=LABS/GASA/GASV/EGO only; imaging separated;
        procedures separated; cultures separated.
"""
import io
import sys
sys.path.insert(0, "/app/backend")

from docx import Document
from server import _parse_censo_docx_deterministic, _classify_col5_text


def _build_docx():
    doc = Document()
    table = doc.add_table(rows=1, cols=6)
    # No header row → parser will skip header if it contains labels; keep as data.
    # Two patients
    for row_data in [
        [
            "S81\nDr. Ricardo Pérez López\nDr. Res1 / Dr. Res2",
            "JUAN MENDOZA GARCIA\n67\nDEIH 5 DPQX 3",
            (
                "ANTECEDENTE DE CARCINOMA RENAL DE CELULAS CLARAS\n"
                "ADENOCARCINOMA PULMONAR METASTASICO\n"
                "PADUA 7\n"
                "ECOG 1\n"
                "T4N3M1\n"
                "12/06/26\n"
                "PANENDOSCOPIA + COLONOSCOPIA\n"
                "16/06/26\n"
                "PO LAPE + HEMICOLECTOMIA DERECHA + ITALLMR"
            ),
            "OMEPRAZOL 40 MG IV C/24H\nMETAMIZOL 1G IV PRN\nENOXAPARINA 40 MG SC C/24H",
            (
                "LABS 12/06/26\n"
                "HB 10.2 LEU 8.5 PLT 220\n"
                "TAC ABD 13/06/26\n"
                "Sin evidencia de colecciones, drenajes correctos.\n"
                "COLONOSCOPIA 15/06/26\n"
                "Hallazgos: pólipos pequeños en sigmoides.\n"
                "HEMOCULTIVOS 14/06/26\n"
                "Sin desarrollo a 48 h."
            ),
            "TA 120/70 FC 85 T 36.8",
        ],
        [
            "812\nDra. Ana Torres\nDr. Res3",
            "MARIA ELENA RUIZ\n45\nDEIH 2 DPQX 1",
            (
                "STDB + DIVERTICULITIS ULCERADA EN COLON ASCENDENTE\n"
                "ISQ SUPERFICIAL + FEC\n"
                "ROCKALL 6\n"
                "EC IVA"
            ),
            "CIPROFLOXACINO 400 MG IV C/12H\nOMEPRAZOL 40 MG IV C/24H",
            (
                "EGO 13/06/26\n"
                "Leucocitos +++, nitritos positivos.\n"
                "GASA 13/06/26\n"
                "pH 7.35 HCO3 22\n"
                "USG ABD 12/06/26\n"
                "Colecciones libres, no dilatación.\n"
                "UROCULTIVO 14/06/26\n"
                "E. coli BLEE positivo."
            ),
            "TA 110/60 FC 92 T 37.5",
        ],
    ]:
        cells = table.add_row().cells
        for i, v in enumerate(row_data):
            cells[i].text = v

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def main():
    print("=" * 80)
    print("TEST PARSER ETAPA 3")
    print("=" * 80)
    content = _build_docx()
    patients = _parse_censo_docx_deterministic(content)
    assert len(patients) == 2, f"Expected 2 patients, got {len(patients)}"

    for i, p in enumerate(patients):
        print(f"\n--- Paciente {i+1}: {p.get('name')} (cama {p.get('bed')}) ---")
        print(f"  DX_SHORT:   {p.get('dx_short')!r}")
        print(f"  DX_FULL:")
        for line in (p.get("dx_full") or "").split("\n"):
            print(f"    {line}")
        print(f"  IMPORTANT_MEDS: {p.get('important_medications')!r}")
        print(f"  LABS:")
        for line in (p.get("labs") or "").split("\n"):
            print(f"    {line}")
        print(f"  STUDIES:")
        for line in (p.get("studies") or "").split("\n"):
            print(f"    {line}")
        print(f"  PROCEDURES:")
        for line in (p.get("procedures") or "").split("\n"):
            print(f"    {line}")
        print(f"  CULTURES:")
        for line in (p.get("cultures") or "").split("\n"):
            print(f"    {line}")
        print(f"  VITAL_SIGNS: {p.get('vital_signs')!r}")

    # --- Assertions ---
    p1 = patients[0]

    # DX_SHORT should be a real diagnosis, NOT a procedure
    assert "PANENDOSCOPIA" not in (p1.get("dx_short") or "").upper(), \
        f"dx_short must NOT contain procedure: {p1.get('dx_short')}"
    assert "LAPE" not in (p1.get("dx_short") or "").upper(), \
        f"dx_short must NOT contain PO LAPE: {p1.get('dx_short')}"
    assert "CARCINOMA" in (p1.get("dx_short") or "").upper(), \
        f"dx_short should contain the first real diagnosis: {p1.get('dx_short')}"

    # DX_FULL must contain CLASIFICACIONES section
    assert "CLASIFICACIONES:" in (p1.get("dx_full") or ""), \
        "dx_full must contain CLASIFICACIONES section"
    assert "PADUA 7" in (p1.get("dx_full") or "").upper()
    assert "ECOG 1" in (p1.get("dx_full") or "").upper()
    assert "T4N3M1" in (p1.get("dx_full") or "").upper()

    # PROCEDURES must contain the QX procedures (from Col3 dates + PO LAPE / PANENDOSCOPIA)
    proc = (p1.get("procedures") or "").upper()
    assert "PANENDOSCOPIA" in proc, f"procedures must contain PANENDOSCOPIA: {proc!r}"
    assert "HEMICOLECTOM" in proc, f"procedures must contain HEMICOLECTOMIA: {proc!r}"
    # AND COLONOSCOPIA from Col5
    assert "COLONOSCOPIA" in proc, f"procedures must contain COLONOSCOPIA: {proc!r}"

    # LABS must contain ONLY LABS/GASA/GASV/EGO chunks — NOT TAC/COLONOSCOPIA/HEMOCULTIVOS
    labs = (p1.get("labs") or "").upper()
    assert "TAC" not in labs, f"labs must NOT contain TAC: {labs!r}"
    assert "COLONOSCOPIA" not in labs, f"labs must NOT contain COLONOSCOPIA: {labs!r}"
    assert "HEMOCULTIVO" not in labs, f"labs must NOT contain HEMOCULTIVOS: {labs!r}"
    assert "LABS" in labs, f"labs must contain LABS chunk: {labs!r}"

    # STUDIES must contain TAC, NOT the procedure
    studies = (p1.get("studies") or "").upper()
    assert "TAC" in studies, f"studies must contain TAC: {studies!r}"
    assert "COLONOSCOPIA" not in studies, f"studies must NOT contain COLONOSCOPIA: {studies!r}"

    # CULTURES must contain hemocultivos
    cult = (p1.get("cultures") or "").upper()
    assert "HEMOCULTIVO" in cult, f"cultures must contain HEMOCULTIVOS: {cult!r}"

    # important_medications from Col4
    im = (p1.get("important_medications") or "").upper()
    assert "OMEPRAZOL" in im, f"important_medications must contain OMEPRAZOL: {im!r}"

    # --- P2 ---
    p2 = patients[1]
    # Classifications
    assert "ROCKALL 6" in (p2.get("dx_full") or "").upper()
    assert "EC IVA" in (p2.get("dx_full") or "").upper()

    labs2 = (p2.get("labs") or "").upper()
    assert "EGO" in labs2 and "GASA" in labs2, f"labs must contain EGO and GASA: {labs2!r}"
    assert "USG" not in labs2, f"labs must NOT contain USG: {labs2!r}"

    studies2 = (p2.get("studies") or "").upper()
    assert "USG" in studies2, f"studies must contain USG: {studies2!r}"

    cult2 = (p2.get("cultures") or "").upper()
    assert "UROCULTIVO" in cult2, f"cultures must contain UROCULTIVO: {cult2!r}"
    assert "BLEE" in cult2, f"cultures must contain BLEE: {cult2!r}"

    # Regla mandatoria: si Col5 tenía info, los 4 buckets NO pueden estar todos vacíos
    for pi in (p1, p2):
        four_buckets_empty = (
            not pi.get("labs") and not pi.get("studies")
            and not pi.get("procedures") and not pi.get("cultures")
        )
        assert not four_buckets_empty, f"Los 4 buckets están vacíos: {pi.get('name')}"

    print("\n✅ TODAS LAS ASSERCIONES PASARON")


if __name__ == "__main__":
    main()
