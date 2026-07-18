"""Prompt 4 test: generate real MedSys notes + WhatsApp using the built-in
few-shot examples and verify they match the target style.
"""
import os
import re
import sys
import json
import time
import asyncio
import aiohttp

BASE = os.environ.get("BASE") or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split("\n")[0].strip()
EMAIL = "demo@surginote.app"
PASSWORD = "DemoSurgi2026!"


async def login(session):
    async with session.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}) as r:
        d = await r.json()
        return d["token"]


async def create_patient(session, token, **kwargs):
    async with session.post(
        f"{BASE}/api/patients",
        headers={"Authorization": f"Bearer {token}"},
        json=kwargs,
    ) as r:
        assert r.status == 200, f"create failed: {await r.text()}"
        return await r.json()


async def upsert_today_entry(session, token, patient_id, **kwargs):
    async with session.patch(
        f"{BASE}/api/patients/{patient_id}/entries/today",
        headers={"Authorization": f"Bearer {token}"},
        json=kwargs,
    ) as r:
        assert r.status == 200, f"upsert failed: {await r.text()}"
        return await r.json()


async def generate_note(session, token, patient_id):
    async with session.post(
        f"{BASE}/api/patients/{patient_id}/generate/note",
        headers={"Authorization": f"Bearer {token}"},
        json={},
        timeout=aiohttp.ClientTimeout(total=180),
    ) as r:
        assert r.status == 200, f"generate failed: {await r.text()}"
        return await r.json()


async def delete_patient(session, token, patient_id):
    async with session.delete(
        f"{BASE}/api/patients/{patient_id}",
        headers={"Authorization": f"Bearer {token}"},
    ) as r:
        return r.status


async def main():
    async with aiohttp.ClientSession() as session:
        token = await login(session)
        print(f"Logged in: {token[:30]}...\n")

        # ========== 1) NOTA HOSPITALIZACIÓN ==========
        p1 = await create_patient(
            session, token,
            name="PACIENTE PRUEBA PISO",
            age=58, sex="Masculino", bed="512",
            attending_physician="Dr. Roberto Sánchez",
            unit_classification="Piso",
            dx_short="APENDICITIS AGUDA COMPLICADA + PERITONITIS LOCALIZADA",
            dx_full="APENDICITIS AGUDA COMPLICADA + PERITONITIS LOCALIZADA",
            surgery_date="2026-02-15",
            surgery_procedure="APENDICECTOMIA LAPAROSCOPICA + LAVADO DE CAVIDAD",
            surgery_findings="APENDICE PERFORADO CON MATERIAL PURULENTO EN FONDO DE SACO",
            admission_date="2026-02-14",
            important_medications="MEROPENEM 1G IV C/8H, PARACETAMOL 1G IV C/8H",
        )
        await upsert_today_entry(
            session, token, p1["id"],
            dictation="Paciente en su POD3 apendicectomia. Refiere adecuado control analgésico. Tolerando dieta líquida sin nauseas ni vomito. Uresis por miccion espontanea. Canaliza gases pero sin evacuaciones aún. Drenaje penrose con gasto seroso escaso. Abdomen blando depresible, no doloroso a palpación, peristalsis presente. Herida quirúrgica sin datos de infección.",
            labs="LABS 16/02/26 HB 12.8 LEU 9.5 PLT 240 CR 0.8 PCR 4.2",
            studies="",
            vital_signs="TA 118/72 FC 78 T 36.6 SatO2 98%",
        )
        print("=" * 80)
        print("TEST 1: NOTA HOSPITALIZACIÓN")
        print("=" * 80)
        t0 = time.time()
        r1 = await generate_note(session, token, p1["id"])
        print(f"[{time.time()-t0:.1f}s] Generated")
        note1 = r1["note"]
        wa1 = r1["whatsapp"]

        print("\n--- NOTA PISO ---")
        print(note1)
        print("\n--- WHATSAPP PISO ---")
        print(wa1)

        # Assertions Piso
        assert note1.startswith("NOTA DE EVOLUCIÓN POR CIRUGÍA GENERAL"), \
            f"Nota Piso debe iniciar con encabezado exacto. Inicia con: {note1[:60]!r}"
        assert "SE TRATA DE" in note1.upper()
        assert "AL PASE DE VISITA" in note1.upper()
        assert "A LA EXPLORACIÓN FÍSICA" in note1.upper()
        assert "PLAN" in note1.upper()
        assert "PRONÓSTICO RESERVADO A EVOLUCIÓN" in note1.upper() or "PRONOSTICO RESERVADO A EVOLUCION" in note1.upper()
        # No bullets/numeración
        assert not re.search(r"^\s*[-•*]\s", note1, re.MULTILINE), "Nota Piso NO debe tener bullets"
        assert not re.search(r"^\s*\d+[\.\)]\s", note1, re.MULTILINE), "Nota Piso NO debe tener numeración"
        # Mostly uppercase
        letters = [c for c in note1 if c.isalpha()]
        upper_ratio = sum(1 for c in letters if c.isupper()) / max(len(letters), 1)
        assert upper_ratio >= 0.85, f"Nota Piso debe estar en mayúsculas (ratio {upper_ratio:.2f})"

        # WhatsApp: capitalización NORMAL (no mayúsculas)
        wa_letters = [c for c in wa1 if c.isalpha()]
        wa_upper_ratio = sum(1 for c in wa_letters if c.isupper()) / max(len(wa_letters), 1)
        assert wa_upper_ratio < 0.40, f"WhatsApp NO debe estar en mayúsculas (ratio {wa_upper_ratio:.2f})"
        # Debe iniciar con Buenos días / Hola doctor / Pasé / etc.
        assert any(wa1.strip().lower().startswith(s) for s in [
            "buenos días", "buenos dias", "hola doctor", "pasé", "pase"
        ]), f"WhatsApp debe iniciar con saludo natural. Inicia: {wa1[:50]!r}"
        # No bullets
        assert not re.search(r"^\s*[-•*]\s", wa1, re.MULTILINE), "WhatsApp NO debe tener bullets"

        # ========== 2) NOTA UTI ==========
        p2 = await create_patient(
            session, token,
            name="PACIENTE PRUEBA UTI",
            age=68, sex="Femenino", bed="UTI-3",
            attending_physician="Dra. Ana Rodríguez",
            unit_classification="UTI",
            dx_short="CHOQUE SEPTICO SECUNDARIO A PERITONITIS TERCIARIA + PO LAPE",
            dx_full="CHOQUE SEPTICO SECUNDARIO A PERITONITIS TERCIARIA + PO LAPE",
            surgery_date="2026-02-10",
            surgery_procedure="LAPAROTOMIA EXPLORADORA + LAVADO DE CAVIDAD + COLECTOMIA IZQUIERDA + HARTMANN",
            surgery_findings="MATERIAL FECAL EN CAVIDAD, PERFORACIÓN DE COLON SIGMOIDES",
            admission_date="2026-02-09",
            important_medications="MEROPENEM 1G IV C/8H, VANCOMICINA 1G IV C/12H, NOREPINEFRINA 0.15 GAMMAS",
        )
        await upsert_today_entry(
            session, token, p2["id"],
            dictation="Paciente en su POD6. En lo neurológico bajo sedación con propofol a 1.5 mg/kg/hr, fentanilo a 1.5 mcg/kg/hr. Respiratorio en VMI con PEEP 8, FIO2 60%, saturando 96%. Cardiovascular con norepinefrina 0.15 gammas, TAMs perfusorias en 68-72 mmHg, FC 92 lpm. Gastro metabólico en ayuno, sonda nasogastrica con gasto minimo. Cuenta con 2 drenajes Blake pélvicos con gasto seroso 30cc cada uno. Hídrico urinario con Foley 800cc claras. Hematoinfeccioso febril hasta 38.5 en manejo con meropenem y vancomicina.",
            labs="LABS 16/02/26 HB 9.8 LEU 15.3 PLT 180 CR 1.2 PCR 12.5",
            studies="",
            vital_signs="TA 92/58 FC 92 T 38.5",
        )
        print("\n" + "=" * 80)
        print("TEST 2: NOTA UTI")
        print("=" * 80)
        t0 = time.time()
        r2 = await generate_note(session, token, p2["id"])
        print(f"[{time.time()-t0:.1f}s] Generated")
        note2 = r2["note"]
        wa2 = r2["whatsapp"]

        print("\n--- NOTA UTI ---")
        print(note2)
        print("\n--- WHATSAPP UTI ---")
        print(wa2)

        # Assertions UTI
        assert re.search(r"NOTA DE EVOLUCIÓN POR CIRUG[IÍ]A GENERAL EN UTI", note2, re.IGNORECASE), \
            f"Nota UTI debe iniciar con encabezado 'EN UTI'. Inicia: {note2[:80]!r}"
        # UTI: debe contener las secciones "EN LO NEUROLÓGICO", "EN LO RESPIRATORIO", etc.
        n2_upper = note2.upper()
        for kw in ["NEUROLÓGICO", "RESPIRATORIO", "CARDIOVASCULAR", "GASTRO", "HÍDRICO", "HEMATOINFECCIOSO"]:
            assert kw in n2_upper or kw.replace("Ó","O").replace("Í","I") in n2_upper, \
                f"Nota UTI debe contener sección {kw}"
        assert "A LA EXPLORACIÓN FÍSICA" in n2_upper or "A LA EXPLORACION FISICA" in n2_upper
        assert "PRONÓSTICO RESERVADO" in n2_upper or "PRONOSTICO RESERVADO" in n2_upper
        # No bullets
        assert not re.search(r"^\s*[-•*]\s", note2, re.MULTILINE), "Nota UTI NO debe tener bullets"
        # Mayúsculas
        letters = [c for c in note2 if c.isalpha()]
        upper_ratio = sum(1 for c in letters if c.isupper()) / max(len(letters), 1)
        assert upper_ratio >= 0.85, f"Nota UTI debe estar en mayúsculas (ratio {upper_ratio:.2f})"

        # ========== CLEANUP ==========
        await delete_patient(session, token, p1["id"])
        await delete_patient(session, token, p2["id"])
        print("\n✅ TODAS LAS PRUEBAS PASARON — Prompt 4 funciona correctamente.")


if __name__ == "__main__":
    asyncio.run(main())
