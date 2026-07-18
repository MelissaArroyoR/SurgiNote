"""SurgiNote backend - FastAPI app for surgical resident personal assistant."""
import os
import io
import uuid
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone, date, timedelta
from typing import Optional

import jwt
import bcrypt
from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from openai import AsyncOpenAI
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAISpeechToText
from docx import Document as DocxDocument

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

EMERGENT_KEY = os.environ["EMERGENT_LLM_KEY"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_HOURS = 24 * 30

app = FastAPI(title="SurgiNote API")
api = APIRouter(prefix="/api")
security = HTTPBearer()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("surginote")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_iso() -> str:
    return now_utc().date().isoformat()


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class Patient(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    age: Optional[int] = None
    sex: Optional[str] = None
    bed: Optional[str] = None
    floor: Optional[str] = None
    service: Optional[str] = None
    attending_physician: Optional[str] = None
    dx_short: Optional[str] = None
    dx_full: Optional[str] = None
    surgery_date: Optional[str] = None
    surgery_procedure: Optional[str] = None
    surgery_findings: Optional[str] = None
    medical_history: Optional[str] = None
    allergies: Optional[str] = None
    important_medications: Optional[str] = None
    consultants: Optional[str] = None
    oncology_treatment: Optional[str] = None
    oncology_status: Optional[str] = None
    unit_classification: Optional[str] = None
    admission_date: Optional[str] = None
    admission_note_text: Optional[str] = None
    is_surgical: bool = True
    is_pending_discharge: bool = False
    censo_order: Optional[int] = None
    active: bool = True
    is_new_admission: bool = False
    discharged_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: now_utc().isoformat())
    updated_at: str = Field(default_factory=lambda: now_utc().isoformat())


class PatientCreate(BaseModel):
    name: str
    age: Optional[int] = None
    sex: Optional[str] = None
    bed: Optional[str] = None
    floor: Optional[str] = None
    service: Optional[str] = None
    attending_physician: Optional[str] = None
    dx_short: Optional[str] = None
    dx_full: Optional[str] = None
    surgery_date: Optional[str] = None
    surgery_procedure: Optional[str] = None
    surgery_findings: Optional[str] = None
    medical_history: Optional[str] = None
    allergies: Optional[str] = None
    important_medications: Optional[str] = None
    consultants: Optional[str] = None
    oncology_treatment: Optional[str] = None
    oncology_status: Optional[str] = None
    unit_classification: Optional[str] = None
    admission_date: Optional[str] = None
    is_surgical: Optional[bool] = None
    is_pending_discharge: Optional[bool] = None


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    bed: Optional[str] = None
    floor: Optional[str] = None
    service: Optional[str] = None
    attending_physician: Optional[str] = None
    dx_short: Optional[str] = None
    dx_full: Optional[str] = None
    surgery_date: Optional[str] = None
    surgery_procedure: Optional[str] = None
    surgery_findings: Optional[str] = None
    medical_history: Optional[str] = None
    allergies: Optional[str] = None
    important_medications: Optional[str] = None
    consultants: Optional[str] = None
    oncology_treatment: Optional[str] = None
    oncology_status: Optional[str] = None
    unit_classification: Optional[str] = None
    admission_date: Optional[str] = None
    active: Optional[bool] = None
    is_new_admission: Optional[bool] = None
    is_surgical: Optional[bool] = None
    is_pending_discharge: Optional[bool] = None


class DailyEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    patient_id: str
    user_id: str
    date: str
    dictation: str = ""
    labs: str = ""
    studies: str = ""
    events: str = ""
    ai_pase_summary: Optional[str] = None
    ai_lab_comparison: Optional[str] = None
    ai_evolution_note: Optional[str] = None
    ai_whatsapp: Optional[str] = None
    saved_to_pase: bool = False
    created_at: str = Field(default_factory=lambda: now_utc().isoformat())
    updated_at: str = Field(default_factory=lambda: now_utc().isoformat())


class DailyEntryUpsert(BaseModel):
    date: Optional[str] = None
    dictation: Optional[str] = None
    labs: Optional[str] = None
    studies: Optional[str] = None
    events: Optional[str] = None


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def make_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": now_utc() + timedelta(hours=JWT_EXPIRES_HOURS),
        "iat": now_utc(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return user


def days_between(iso_date: Optional[str]) -> Optional[int]:
    if not iso_date:
        return None
    try:
        d = date.fromisoformat(iso_date)
        return (now_utc().date() - d).days
    except Exception:
        return None


def enrich_patient(p: dict) -> dict:
    p["days_admission"] = days_between(p.get("admission_date"))
    p["days_postop"] = days_between(p.get("surgery_date"))
    return p


@api.post("/auth/register", response_model=AuthResponse)
async def register(body: UserRegister):
    existing = await db.users.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": body.email.lower(),
        "password": hash_pw(body.password),
        "name": body.name,
        "created_at": now_utc().isoformat(),
    }
    await db.users.insert_one(doc)
    token = make_token(user_id, body.email.lower())
    return AuthResponse(token=token, user={"id": user_id, "email": body.email.lower(), "name": body.name})


@api.post("/auth/login", response_model=AuthResponse)
async def login(body: UserLogin):
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not check_pw(body.password, user["password"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = make_token(user["id"], user["email"])
    return AuthResponse(token=token, user={"id": user["id"], "email": user["email"], "name": user["name"]})


@api.get("/auth/me")
async def me(user: dict = Depends(get_user)):
    return user


@api.get("/patients/discharged")
async def list_discharged(user: dict = Depends(get_user)):
    cur = db.patients.find({"user_id": user["id"], "active": False}, {"_id": 0})
    patients = await cur.to_list(1000)
    for p in patients:
        enrich_patient(p)
    patients.sort(key=lambda x: x.get("discharged_at") or "", reverse=True)
    return patients


@api.get("/patients")
async def list_patients(user: dict = Depends(get_user)):
    cur = db.patients.find({"user_id": user["id"], "active": True}, {"_id": 0})
    patients = await cur.to_list(500)
    for p in patients:
        enrich_patient(p)
    # Preserve censo order (from last import). Patients without censo_order go to end sorted alphabetically.
    def _key(p):
        co = p.get("censo_order")
        if co is None:
            return (1, (p.get("name") or "").lower())
        return (0, co)
    patients.sort(key=_key)
    return patients


@api.post("/patients", response_model=Patient)
async def create_patient(body: PatientCreate, user: dict = Depends(get_user)):
    patient = Patient(user_id=user["id"], **body.model_dump())
    await db.patients.insert_one(patient.model_dump())
    return patient


@api.get("/patients/{patient_id}")
async def get_patient(patient_id: str, user: dict = Depends(get_user)):
    p = await db.patients.find_one({"id": patient_id, "user_id": user["id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return enrich_patient(p)


@api.patch("/patients/{patient_id}")
async def update_patient(patient_id: str, body: PatientUpdate, user: dict = Depends(get_user)):
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    update["updated_at"] = now_utc().isoformat()
    result = await db.patients.update_one(
        {"id": patient_id, "user_id": user["id"]}, {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    p = await db.patients.find_one({"id": patient_id}, {"_id": 0})
    return enrich_patient(p)


@api.delete("/patients/{patient_id}")
async def delete_patient(patient_id: str, user: dict = Depends(get_user)):
    result = await db.patients.update_one(
        {"id": patient_id, "user_id": user["id"]},
        {"$set": {"active": False, "discharged_at": today_iso(), "updated_at": now_utc().isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return {"ok": True}


@api.get("/patients/{patient_id}/entries")
async def list_entries(patient_id: str, user: dict = Depends(get_user)):
    cur = db.daily_entries.find({"patient_id": patient_id, "user_id": user["id"]}, {"_id": 0})
    entries = await cur.to_list(365)
    entries.sort(key=lambda x: x.get("date", ""), reverse=True)
    return entries


@api.get("/patients/{patient_id}/entries/today")
async def get_today_entry(patient_id: str, user: dict = Depends(get_user)):
    today = today_iso()
    entry = await db.daily_entries.find_one(
        {"patient_id": patient_id, "user_id": user["id"], "date": today}, {"_id": 0}
    )
    if not entry:
        e = DailyEntry(patient_id=patient_id, user_id=user["id"], date=today)
        await db.daily_entries.insert_one(e.model_dump())
        return e.model_dump()
    return entry


@api.patch("/patients/{patient_id}/entries/today")
async def update_today_entry(patient_id: str, body: DailyEntryUpsert, user: dict = Depends(get_user)):
    target_date = body.date or today_iso()
    update = {k: v for k, v in body.model_dump().items() if v is not None and k != "date"}
    update["updated_at"] = now_utc().isoformat()

    existing = await db.daily_entries.find_one(
        {"patient_id": patient_id, "user_id": user["id"], "date": target_date}
    )
    if not existing:
        entry = DailyEntry(patient_id=patient_id, user_id=user["id"], date=target_date, **update)
        await db.daily_entries.insert_one(entry.model_dump())
        return entry.model_dump()
    await db.daily_entries.update_one(
        {"patient_id": patient_id, "user_id": user["id"], "date": target_date}, {"$set": update}
    )
    e = await db.daily_entries.find_one(
        {"patient_id": patient_id, "user_id": user["id"], "date": target_date}, {"_id": 0}
    )
    return e


def build_patient_context(patient: dict) -> str:
    days_a = days_between(patient.get("admission_date"))
    days_p = days_between(patient.get("surgery_date"))
    lines = [
        f"Nombre: {patient.get('name', '')}",
        f"Edad: {patient.get('age', 'ND')}   Sexo: {patient.get('sex', 'ND')}",
        f"Cama: {patient.get('bed', 'ND')}   Piso: {patient.get('floor', 'ND')}   Servicio: {patient.get('service', 'ND')}",
        f"Unidad: {patient.get('unit_classification', 'Piso')}",
        f"Días de estancia (DEIH): {days_a if days_a is not None else 'ND'}   Días postoperatorios (DPQX): {days_p if days_p is not None else 'ND'}",
        f"Diagnóstico resumido: {patient.get('dx_short', '')}",
        f"Diagnóstico completo: {patient.get('dx_full', '')}",
        f"Procedimiento quirúrgico ({patient.get('surgery_date', 'ND')}): {patient.get('surgery_procedure', '')}",
        f"Hallazgos quirúrgicos: {patient.get('surgery_findings', '')}",
        f"Antecedentes personales patológicos: {patient.get('medical_history', '')}",
        f"Alergias: {patient.get('allergies', 'Ninguna referida')}",
        f"Medicamentos importantes: {patient.get('important_medications', '')}",
        f"Interconsultantes: {patient.get('consultants', '')}",
        f"Tratamiento oncológico: {patient.get('oncology_treatment', '')}",
        f"Estado oncológico: {patient.get('oncology_status', '')}",
    ]
    return "\n".join(lines)


async def llm_generate(system_prompt: str, user_prompt: str) -> str:
    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=f"surginote-{uuid.uuid4()}",
        system_message=system_prompt,
    ).with_model("openai", "gpt-5.2")
    response = await chat.send_message(UserMessage(text=user_prompt))
    return response if isinstance(response, str) else str(response)


class GenerateBody(BaseModel):
    date: Optional[str] = None


@api.post("/patients/{patient_id}/generate/pase")
async def generate_pase(patient_id: str, body: GenerateBody, user: dict = Depends(get_user)):
    patient = await db.patients.find_one({"id": patient_id, "user_id": user["id"]}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    target = body.date or today_iso()
    today_entry = await db.daily_entries.find_one(
        {"patient_id": patient_id, "user_id": user["id"], "date": target}, {"_id": 0}
    ) or {"dictation": "", "labs": "", "studies": "", "events": ""}

    prev_cur = db.daily_entries.find(
        {"patient_id": patient_id, "user_id": user["id"], "date": {"$lt": target}, "labs": {"$ne": ""}}, {"_id": 0}
    )
    prev_list = await prev_cur.to_list(30)
    prev_list.sort(key=lambda x: x.get("date", ""), reverse=True)
    prev_entry = prev_list[0] if prev_list else None

    ctx = build_patient_context(patient)
    prev_labs_block = (
        f"\n\nLABORATORIOS DEL DÍA PREVIO ({prev_entry['date']}):\n{prev_entry['labs']}"
        if prev_entry else "\n\n(No hay laboratorios previos registrados para comparar.)"
    )

    dea = days_between(patient.get('admission_date'))
    dpq = days_between(patient.get('surgery_date'))

    user_prompt = f"""INFORMACIÓN FIJA DEL PACIENTE:
{ctx}

INFORMACIÓN DEL DÍA ({target}):
- Dictado del residente: {today_entry.get('dictation', '')}
- Laboratorios del día: {today_entry.get('labs', '')}
- Estudios de imagen / procedimientos: {today_entry.get('studies', '')}
- Eventos del día: {today_entry.get('events', '')}
{prev_labs_block}

Genera un RESUMEN ESTRUCTURADO PARA EL PASE DE VISITA en texto plano (sin markdown), siguiendo EXACTAMENTE esta estructura:

▎ {patient.get('name','')}  |  Cama {patient.get('bed','ND')} · Piso {patient.get('floor','ND')}
▎ DEA: {dea} · DPQ: {dpq}

DX: (diagnóstico resumido)
QX: (procedimiento y fecha)
APP RELEVANTES: (antecedentes en 1 línea; si no hay, omite)
ONCOLÓGICO: (si aplica; si no, omite la línea completa)
INTERCONSULTAS ACTIVAS: (lista breve; si no hay, omite)

RESUMEN CLÍNICO DEL DÍA:
- (2-4 bullets con los eventos y cambios clínicamente más relevantes del día)

CAMBIOS DE MEDICAMENTOS:
- (solo si se mencionaron; escalada/desescalada de antibióticos, ajustes de analgesia, anticoagulación, etc. Si no hay cambios, escribe "Sin cambios en el esquema.")

ESTUDIOS / PROCEDIMIENTOS:
- (resumen conciso de imágenes o procedimientos; si no hay, escribe "Ninguno.")

POR SISTEMAS: (INCLUYE esta sección SOLO si el paciente está en UTI, UTIM o con múltiples sistemas comprometidos. Si es piso general y estable, OMITE esta sección completa)
- Neurológico: ...
- Respiratorio: ...
- Hemodinámico: ...
- Renal / metabólico: ...
- Gastrointestinal / nutricional: ...
- Infeccioso: ...
- Hematológico: ...

CAMBIOS RELEVANTES EN LABORATORIOS:
- (NO copies valores completos. Identifica SOLO tendencias clínicamente relevantes comparando vs día previo cuando exista. Ejemplos del estilo requerido: "Leucocitos en descenso (14 → 9.8 mil, mejoría)", "Creatinina estable", "Hipokalemia corregida (3.1 → 4.0)", "PCR en aumento (45 → 78)", "Hb estable sin datos de sangrado". Si no hay previos, indica solo los valores actuales anormales; los normales se omiten o mencionas "Sin alteraciones relevantes".)

⚡ SUGERENCIA DE IA — PLAN SUGERIDO:
- (2-5 bullets con propuestas concretas de manejo basadas en la información disponible. Formato claro y accionable. Al final agrega la línea: "— Requiere validación del médico responsable —")

PENDIENTES / A DISCUTIR:
- (puntos concretos para conversar en el pase; interconsultas pendientes, definiciones, estudios por solicitar)

Reglas estrictas:
1. NO inventes datos. Si algo no está en la información entregada, escribe "ND" o omite la línea.
2. Toda propuesta terapéutica debe ir SOLO bajo la sección "⚡ SUGERENCIA DE IA".
3. El resto de secciones deben ser factuales, extraídas exclusivamente del dictado/labs/estudios/eventos.
4. Español médico. Terminología precisa. Sin adornos ni saludos."""

    system = "Eres un asistente experto para un residente de cirugía general. Organizas y resumes información clínica proporcionada por el usuario. NO inventas datos clínicos ni sustituyes el juicio médico. Las propuestas terapéuticas van únicamente bajo la etiqueta 'SUGERENCIA DE IA'. El resto es organización factual de lo que el usuario dictó."
    text = await llm_generate(system, user_prompt)

    await db.daily_entries.update_one(
        {"patient_id": patient_id, "user_id": user["id"], "date": target},
        {"$set": {"ai_pase_summary": text, "saved_to_pase": True, "updated_at": now_utc().isoformat()}},
        upsert=True,
    )
    # Al generar el primer pase, quitar el badge "Nuevo ingreso"
    if patient.get("is_new_admission"):
        await db.patients.update_one(
            {"id": patient_id, "user_id": user["id"]},
            {"$set": {"is_new_admission": False, "updated_at": now_utc().isoformat()}},
        )
    return {"summary": text}


@api.post("/patients/{patient_id}/generate/note")
async def generate_note(patient_id: str, body: GenerateBody, user: dict = Depends(get_user)):
    patient = await db.patients.find_one({"id": patient_id, "user_id": user["id"]}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    target = body.date or today_iso()
    entry = await db.daily_entries.find_one(
        {"patient_id": patient_id, "user_id": user["id"], "date": target}, {"_id": 0}
    ) or {"dictation": "", "labs": "", "studies": "", "events": ""}

    ctx = build_patient_context(patient)
    user_prompt = f"""INFORMACIÓN FIJA DEL PACIENTE:
{ctx}

INFORMACIÓN DEL DÍA ({target}):
- Dictado: {entry.get('dictation', '')}
- Laboratorios: {entry.get('labs', '')}
- Estudios: {entry.get('studies', '')}
- Eventos: {entry.get('events', '')}

Redacta una NOTA DE EVOLUCIÓN completa en español clínico, LISTA PARA COPIAR Y PEGAR EN MEDSYS, siguiendo EXACTAMENTE este formato en texto plano (sin markdown, sin asteriscos, sin comillas extra):

NOTA DE EVOLUCIÓN — {target}
Servicio: Cirugía General

ENCABEZADO
Paciente: (nombre completo, edad, sexo)
Cama / Piso: (cama · piso)
Días de estancia: (DEA) | Días postoperatorios: (DPQ)
Diagnóstico: (dx resumido)
Cirugía: (fecha · procedimiento realizado)
Antecedentes relevantes: (una línea; si no hay, escribe "Sin antecedentes de relevancia")
Interconsultas activas: (lista; si no hay, escribe "Ninguna")

EVOLUCIÓN
(2-4 párrafos redactados con base en el dictado. Incluye lo subjetivo, lo objetivo del día, cambios de manejo, eventos relevantes, respuesta al tratamiento, comportamiento hemodinámico, ventilatorio, dolor, tolerancia a la vía oral, drenajes, herida quirúrgica cuando aplique.)

EXPLORACIÓN FÍSICA
Signos vitales: (TA, FC, FR, T, SatO2 — solo si están en el dictado; si no, "ND")
Estado general: (impresión clínica según dictado)
Cabeza y cuello: (según dictado; si no, "sin alteraciones referidas")
Cardiopulmonar: (según dictado)
Abdomen: (según dictado — herida, ruidos, dolor, drenajes)
Extremidades: (según dictado)
Neurológico: (según dictado)

LABORATORIOS Y ESTUDIOS
Laboratorios del día: (organiza los valores del día en línea)
Cambios relevantes: (bullets con las tendencias clínicamente importantes vs previos si el dictado los menciona)
Estudios / procedimientos: (resumen; si no hay, "Sin estudios el día de hoy")

PLAN
1. (plan por problema/sistema, concreto y accionable)
2. ...
3. ...
(Incluye: dieta, líquidos, medicamentos, analgesia, profilaxis, movilización, retiro de dispositivos, curaciones, interconsultas pendientes, estudios pendientes.)

PRONÓSTICO
(Una línea: reservado / bueno para la función / bueno para la vida — según corresponda clínicamente. Justifica en máximo una frase.)

—
Firma: Residente de Cirugía General

Reglas estrictas:
1. NO inventes datos, signos vitales, medicamentos, dosis, ni valores que no estén en el dictado/labs/eventos.
2. Si un dato no está presente, escribe "ND" o "sin datos referidos".
3. Español médico profesional.
4. Formato texto plano sin markdown, listo para copiar y pegar."""
    system = "Eres experto en redacción de notas médicas de cirugía general en español para el expediente MedSys. Produces notas profesionales, precisas, con formato ENCABEZADO / EVOLUCIÓN / EXPLORACIÓN FÍSICA / LABORATORIOS Y ESTUDIOS / PLAN / PRONÓSTICO. Nunca inventas datos clínicos."
    note = await llm_generate(system, user_prompt)

    wa_prompt = f"""Con base en la siguiente información, redacta un MENSAJE BREVE Y PROFESIONAL para WhatsApp al médico tratante:

INFORMACIÓN:
{ctx}

DÍA ({target}):
- Dictado: {entry.get('dictation', '')}
- Laboratorios: {entry.get('labs', '')}
- Estudios: {entry.get('studies', '')}
- Eventos: {entry.get('events', '')}

Formato (texto plano, ≤10 líneas):

Buenos días Dr(a). [Apellido].
Reporte del paciente [Nombre], cama [Cama·Piso], DPQ [días].
Dx: [dx resumido].
QX: [procedimiento] ([fecha]).
Evolución: [1-2 líneas]
Labs: [lo relevante]
Estudios: [si aplica]
Plan: [lo que se hará hoy]
Pendientes: [si hay]
Saludos cordiales."""
    system_wa = "Redactas mensajes clínicos breves, corteses y precisos para WhatsApp en español. Sin markdown, listos para copiar."
    wa = await llm_generate(system_wa, wa_prompt)

    await db.daily_entries.update_one(
        {"patient_id": patient_id, "user_id": user["id"], "date": target},
        {"$set": {"ai_evolution_note": note, "ai_whatsapp": wa, "updated_at": now_utc().isoformat()}},
        upsert=True,
    )
    return {"note": note, "whatsapp": wa}


@api.post("/pase/today")
async def generate_full_pase(user: dict = Depends(get_user)):
    target = today_iso()
    patients = await db.patients.find({"user_id": user["id"], "active": True}, {"_id": 0}).to_list(500)
    patients.sort(key=lambda x: ((x.get("floor") or ""), (x.get("bed") or "")))

    sections = []
    for p in patients:
        entry = await db.daily_entries.find_one(
            {"patient_id": p["id"], "user_id": user["id"], "date": target}, {"_id": 0}
        )
        summary = entry.get("ai_pase_summary") if entry else None
        if summary:
            sections.append(summary.strip())

    header = f"PASE DE VISITA — {target}\nCirugía General\n{'=' * 40}\n"
    body = "\n\n" + ("\n\n" + ("-" * 40) + "\n\n").join(sections) if sections else "\n\n(No hay pacientes con pase generado hoy.)\n"
    return {"pase": header + body, "patient_count": len(sections)}


# ---------------- Discharged patients ----------------
@api.post("/patients/{patient_id}/readmit")
async def readmit_patient(patient_id: str, user: dict = Depends(get_user)):
    result = await db.patients.update_one(
        {"id": patient_id, "user_id": user["id"]},
        {"$set": {"active": True, "discharged_at": None, "updated_at": now_utc().isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    return {"ok": True}


# ---------------- CENSO IMPORT (Word .docx) ----------------
CENSO_FIELDS = [
    "name", "age", "sex", "bed", "floor", "service",
    "attending_physician", "admission_date",
    "surgery_date", "dx_short", "dx_full", "surgery_procedure",
    "surgery_findings", "medical_history", "allergies",
    "important_medications", "oncology_treatment",
    "oncology_status", "unit_classification",
    "is_surgical", "is_pending_discharge",
]

CENSO_DAILY_FIELDS = ["labs", "studies", "events"]


def _extract_docx_text(content: bytes) -> str:
    """Extract all text from a .docx file (paragraphs + tables)."""
    buf = io.BytesIO(content)
    doc = DocxDocument(buf)
    parts = []
    # Paragraphs
    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text)
    # Tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                parts.append(row_text)
    return "\n".join(parts)


async def _parse_censo_with_gpt(raw_text: str) -> list[dict]:
    """Use GPT-5.2 to parse the raw census text into a structured list of patients."""
    system = (
        "Eres un asistente experto en extraer información clínica de censos hospitalarios en español. "
        "Devuelves EXCLUSIVAMENTE JSON válido, sin markdown ni texto adicional. "
        "Nunca inventas datos: si un campo no está presente, lo omites o lo dejas en null. "
        "MUY IMPORTANTE: distingues claramente entre el MÉDICO TRATANTE (adscrito responsable del paciente, "
        "que suele estar destacado como 'Tratante', 'Dr.', 'Adscrito', 'Médico responsable') "
        "de los INTERCONSULTANTES (que NO debes extraer del censo — quedarán vacíos)."
    )
    prompt = f"""Del siguiente TEXTO DE CENSO HOSPITALARIO extrae la lista de TODOS los pacientes en el ORDEN EXACTO en que aparecen (preservando la secuencia del documento).

TEXTO DEL CENSO:
{raw_text}

Devuelve un objeto JSON con esta forma exacta:
{{
  "patients": [
    {{
      "name": "Nombre Apellido Apellido",
      "age": 45,
      "sex": "M" | "F",
      "bed": "305",
      "floor": "3",
      "service": "Cirugía General",
      "attending_physician": "Dr. Apellido / Dra. Apellido (SOLO médico tratante/adscrito responsable — NUNCA interconsultantes)",
      "admission_date": "YYYY-MM-DD",
      "surgery_date": "YYYY-MM-DD",
      "dx_short": "Diagnóstico resumido (una línea)",
      "dx_full": "Diagnóstico completo con detalles",
      "surgery_procedure": "Procedimiento quirúrgico realizado",
      "surgery_findings": "Hallazgos quirúrgicos importantes",
      "medical_history": "Antecedentes personales patológicos relevantes",
      "allergies": "Alergias específicas o 'Ninguna referida'",
      "important_medications": "Medicamentos crónicos importantes",
      "oncology_treatment": "Tratamiento oncológico actual si aplica",
      "oncology_status": "Estado / estadio oncológico si aplica",
      "unit_classification": "UTI" | "UTIM" | "Piso",
      "is_surgical": true | false,
      "is_pending_discharge": true | false,
      "labs": "Todos los laboratorios recientes del paciente en el censo (Hb, leucocitos, plaquetas, Cr, electrolitos, PCR, etc.)",
      "studies": "Estudios de imagen y procedimientos recientes (USG, TAC, endoscopias, RMN, etc.)",
      "events": "Hallazgos importantes / eventos relevantes / cambios clínicos del día mencionados en el censo"
    }}
  ]
}}

Reglas ESTRICTAS:
1. Extrae UN objeto por cada paciente EN EL MISMO ORDEN que aparecen en el censo. Preserva la secuencia exacta.
2. Si un campo NO está en el texto → null. NO inventes datos.
3. Fechas SIEMPRE en formato ISO YYYY-MM-DD. Si solo hay día/mes, usa el año actual ({now_utc().year}).
4. name es OBLIGATORIO. Sin nombre válido, omite ese paciente.
5. `attending_physician`: SOLO el médico TRATANTE / adscrito responsable del paciente (buscar palabras clave: "Tratante", "Adscrito", "Dr.", "Dra." junto al paciente). NUNCA incluir aquí interconsultantes.
6. NO extraigas interconsultantes. NO devuelvas el campo "consultants". El usuario los capturará manualmente.
7. `is_surgical`: true si el paciente tiene procedimiento quirúrgico realizado o programado; false si es paciente no quirúrgico (manejo médico, en observación por otro servicio, sin cirugía en el episodio actual).
8. `is_pending_discharge`: true si el censo menciona "alta pendiente", "en espera de alta", "alta hoy", "candidato a egreso"; false en cualquier otro caso.
9. `unit_classification`: "UTI" si Terapia Intensiva; "UTIM" si Terapia Intermedia; "Piso" en cualquier otro caso.
10. `labs`, `studies`, `events`: extrae TODO el contenido clínico de la columna correspondiente del censo (quinta columna o similar). Esta información se usará para el pase del día. NO omitas ninguna información clínica útil aunque parezca larga.
11. Devuelve SOLO el JSON, sin ```json``` ni explicaciones."""

    text = await llm_generate(system, prompt)
    # Strip potential markdown fences
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        text = parts[1] if len(parts) > 1 else ""
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("`").strip()
    import json as _json
    try:
        data = _json.loads(text)
    except Exception as e:
        import re
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise HTTPException(status_code=422, detail=f"No se pudo parsear el censo: {e}")
        data = _json.loads(m.group(0))
    patients = data.get("patients", [])
    if not isinstance(patients, list):
        raise HTTPException(status_code=422, detail="El censo parseado no contiene lista de pacientes.")
    return patients


def _norm_name(s: str) -> str:
    import unicodedata
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return " ".join(s.lower().strip().split())


# In-memory job store for async .docx imports (per-process, sufficient for single-user app)
IMPORT_JOBS: dict[str, dict] = {}


@api.post("/patients/import-censo")
async def import_censo(
    file: UploadFile = File(...),
    confirm: bool = False,
    user: dict = Depends(get_user),
):
    """Kick off async census import job. If confirm=false → preview mode (no changes applied)."""
    filename = (file.filename or "").lower()
    if not filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un .docx")
    try:
        content = await file.read()
        raw_text = _extract_docx_text(content)
        if not raw_text or len(raw_text.strip()) < 20:
            raise HTTPException(status_code=400, detail="El documento parece estar vacío.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo leer el .docx: {e}")

    job_id = str(uuid.uuid4())
    IMPORT_JOBS[job_id] = {
        "status": "running",
        "user_id": user["id"],
        "started_at": now_utc().isoformat(),
        "confirm": confirm,
        "result": None,
        "error": None,
    }
    asyncio.create_task(_run_import_job(job_id, raw_text, user["id"], confirm))
    return {"job_id": job_id, "status": "running", "confirm": confirm}


@api.get("/patients/import-censo/status/{job_id}")
async def import_censo_status(job_id: str, user: dict = Depends(get_user)):
    job = IMPORT_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo no encontrado")
    if job["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="No autorizado")
    return {
        "status": job["status"],
        "result": job.get("result"),
        "error": job.get("error"),
        "confirm": job.get("confirm"),
        "started_at": job.get("started_at"),
    }


async def _run_import_job(job_id: str, raw_text: str, user_id: str, confirm: bool):
    """Background task that parses the census with GPT and (optionally) upserts patients."""
    try:
        errors: list[str] = []
        try:
            parsed = await _parse_censo_with_gpt(raw_text)
        except Exception as e:
            logger.exception("GPT parsing failed for job %s", job_id)
            IMPORT_JOBS[job_id] = {
                **IMPORT_JOBS[job_id],
                "status": "failed",
                "error": f"Error al analizar el censo con IA: {str(e)[:300]}",
            }
            return

        existing = await db.patients.find({"user_id": user_id, "active": True}, {"_id": 0}).to_list(2000)
        name_to_patient = {_norm_name(p["name"]): p for p in existing}
        seen_names: set[str] = set()

        new_ones: list[dict] = []
        updated_ones: list[dict] = []
        today = today_iso()

        for order_idx, entry in enumerate(parsed):
            try:
                if not isinstance(entry, dict):
                    errors.append(f"Registro inválido (no es objeto): {str(entry)[:80]}")
                    continue
                name = (entry.get("name") or "").strip()
                if not name:
                    errors.append("Registro sin nombre — omitido.")
                    continue
                key = _norm_name(name)
                seen_names.add(key)
                payload = {k: entry.get(k) for k in CENSO_FIELDS if entry.get(k) not in (None, "")}
                if "age" in payload:
                    try:
                        payload["age"] = int(payload["age"])
                    except Exception:
                        payload.pop("age", None)
                # Always update the censo_order for each imported patient
                payload["censo_order"] = order_idx

                prev = name_to_patient.get(key)
                if prev:
                    update = {k: v for k, v in payload.items() if v not in (None, "")}
                    if update:
                        update["updated_at"] = now_utc().isoformat()
                        if confirm:
                            await db.patients.update_one(
                                {"id": prev["id"], "user_id": user_id}, {"$set": update}
                            )
                        merged = {**prev, **update}
                        updated_ones.append({"id": prev["id"], "name": merged["name"]})
                    # Store labs/studies/events of the day (5th column) if present
                    if confirm:
                        await _upsert_daily_from_censo(prev["id"], user_id, today, entry)
                else:
                    if confirm:
                        new_patient = Patient(
                            user_id=user_id,
                            name=name,
                            is_new_admission=True,
                            **{k: v for k, v in payload.items() if k != "name"},
                        )
                        await db.patients.insert_one(new_patient.model_dump())
                        await _upsert_daily_from_censo(new_patient.id, user_id, today, entry)
                        new_ones.append({"id": new_patient.id, "name": new_patient.name})
                    else:
                        new_ones.append({"id": None, "name": name})
            except Exception as e:
                logger.exception("Failed processing entry %s", entry)
                errors.append(f"Error procesando '{entry.get('name', '?')}': {str(e)[:120]}")

        discharged_ones: list[dict] = []
        for key, p in name_to_patient.items():
            if key not in seen_names:
                try:
                    if confirm:
                        await db.patients.update_one(
                            {"id": p["id"], "user_id": user_id},
                            {"$set": {"active": False, "discharged_at": today_iso(), "updated_at": now_utc().isoformat()}},
                        )
                    discharged_ones.append({"id": p["id"], "name": p["name"]})
                except Exception as e:
                    errors.append(f"Error al mover a egresados '{p.get('name')}': {str(e)[:120]}")

        IMPORT_JOBS[job_id] = {
            **IMPORT_JOBS[job_id],
            "status": "done",
            "result": {
                "new": new_ones,
                "updated": updated_ones,
                "discharged": discharged_ones,
                "errors": errors,
                "parsed_count": len(parsed),
                "confirm": confirm,
            },
        }
    except Exception as e:
        logger.exception("Import job %s crashed", job_id)
        IMPORT_JOBS[job_id] = {
            **IMPORT_JOBS[job_id],
            "status": "failed",
            "error": f"Error inesperado: {str(e)[:300]}",
        }


async def _upsert_daily_from_censo(patient_id: str, user_id: str, target_date: str, entry: dict):
    """Merge labs/studies/events from a census row into the day's daily_entry (append, don't overwrite)."""
    labs = entry.get("labs")
    studies = entry.get("studies")
    events = entry.get("events")
    if not any([labs, studies, events]):
        return
    existing = await db.daily_entries.find_one(
        {"patient_id": patient_id, "user_id": user_id, "date": target_date}
    )
    now_iso = now_utc().isoformat()
    if not existing:
        de = DailyEntry(
            patient_id=patient_id, user_id=user_id, date=target_date,
            labs=labs or "", studies=studies or "", events=events or "",
        )
        await db.daily_entries.insert_one(de.model_dump())
        return
    update = {"updated_at": now_iso}
    for field, val in (("labs", labs), ("studies", studies), ("events", events)):
        if not val:
            continue
        existing_val = (existing.get(field) or "").strip()
        if existing_val and val.strip() not in existing_val:
            update[field] = existing_val + "\n" + val.strip()
        elif not existing_val:
            update[field] = val.strip()
    if len(update) > 1:
        await db.daily_entries.update_one(
            {"patient_id": patient_id, "user_id": user_id, "date": target_date},
            {"$set": update},
        )


# ---------------- Paciente sin cambios ----------------
@api.post("/patients/{patient_id}/generate/no-changes")
async def generate_no_changes(patient_id: str, body: GenerateBody, user: dict = Depends(get_user)):
    patient = await db.patients.find_one({"id": patient_id, "user_id": user["id"]}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    target = body.date or today_iso()

    today_entry = await db.daily_entries.find_one(
        {"patient_id": patient_id, "user_id": user["id"], "date": target}, {"_id": 0}
    ) or {"labs": "", "studies": "", "events": "", "dictation": ""}

    # Previous pase (most recent with ai_pase_summary before today)
    prev_cur = db.daily_entries.find(
        {"patient_id": patient_id, "user_id": user["id"], "date": {"$lt": target}, "ai_pase_summary": {"$ne": None}},
        {"_id": 0},
    )
    prev_list = await prev_cur.to_list(60)
    prev_list.sort(key=lambda x: x.get("date", ""), reverse=True)
    prev_pase = prev_list[0] if prev_list else None

    # Previous labs for comparison
    prev_labs_cur = db.daily_entries.find(
        {"patient_id": patient_id, "user_id": user["id"], "date": {"$lt": target}, "labs": {"$ne": ""}},
        {"_id": 0},
    )
    prev_labs_list = await prev_labs_cur.to_list(60)
    prev_labs_list.sort(key=lambda x: x.get("date", ""), reverse=True)
    prev_labs_entry = prev_labs_list[0] if prev_labs_list else None

    ctx = build_patient_context(patient)
    prev_pase_block = (
        f"\n\nPASE DEL DÍA PREVIO ({prev_pase['date']}):\n{prev_pase['ai_pase_summary']}"
        if prev_pase else "\n\n(No hay pase previo registrado.)"
    )
    prev_labs_block = (
        f"\n\nLABORATORIOS DEL DÍA PREVIO ({prev_labs_entry['date']}):\n{prev_labs_entry['labs']}"
        if prev_labs_entry else ""
    )

    # 1) PASE SIN CAMBIOS
    pase_prompt = f"""Este paciente NO tuvo eventualidades relevantes en las últimas 24 horas. NO se dictó nueva información porque el residente confirmó que continúa estable.

INFORMACIÓN FIJA DEL PACIENTE:
{ctx}

LABORATORIOS DE HOY ({target}): {today_entry.get('labs', '') or 'Sin nuevos laboratorios el día de hoy.'}
ESTUDIOS DE HOY: {today_entry.get('studies', '') or 'Ninguno.'}
{prev_labs_block}
{prev_pase_block}

Genera un RESUMEN DEL PASE (texto plano, sin markdown) con la MISMA estructura que se usa habitualmente:

▎ {patient.get('name','')}  |  Cama {patient.get('bed','ND')} · Piso {patient.get('floor','ND')}
▎ DEIH: {days_between(patient.get('admission_date'))} · DPQX: {days_between(patient.get('surgery_date'))}

DX: (dx resumido)
QX: (procedimiento y fecha)
APP RELEVANTES: (una línea; si no hay, omite)
ONCOLÓGICO: (si aplica; si no, omite)
INTERCONSULTAS ACTIVAS: (si hay; si no, omite)

RESUMEN CLÍNICO DEL DÍA:
- Paciente sin eventualidades durante las últimas 24 horas. (Adapta esta frase al contexto clínico específico: p. ej. "Paciente estable postquirúrgico, sin nuevos eventos.", "Continúa asintomática, sin cambios en el manejo.", etc.)
- (Menciona si continúa con esquema previo, tolerancia a dieta, control del dolor, herida, drenajes, según lo esperable si no hubo eventos.)

CAMBIOS DE MEDICAMENTOS:
- Sin cambios en el esquema.

ESTUDIOS / PROCEDIMIENTOS:
- {'Ver estudios cargados' if today_entry.get('studies') else 'Ninguno el día de hoy.'}

CAMBIOS RELEVANTES EN LABORATORIOS:
- (Si hay labs de hoy y previos, identifica SOLO cambios clínicamente relevantes con tendencias. Si NO hay labs de hoy, escribe: "Sin nuevos laboratorios el día de hoy.")

⚡ SUGERENCIA DE IA — PLAN SUGERIDO:
- (2-4 bullets con propuestas de continuidad. Ej: "Continuar mismo plan terapéutico", "Vigilar tolerancia a la vía oral", "Progresar según protocolo".)
— Requiere validación del médico responsable —

PENDIENTES / A DISCUTIR:
- (Reutiliza pendientes del pase previo si aplican; si ya se resolvieron, indica: "Sin pendientes activos.")

Reglas estrictas:
1. NO inventes eventos, complicaciones, signos ni síntomas que no estén en el pase previo o en los nuevos labs.
2. La consigna es "continúa igual"; refleja estabilidad clínica.
3. Español médico profesional. Sin adornos."""

    system_pase = "Eres un asistente experto para un residente de cirugía general. Redactas pases para pacientes ESTABLES sin eventualidades, reutilizando el contexto previo. Nunca inventas eventos ni complicaciones."
    pase_text = await llm_generate(system_pase, pase_prompt)

    # 2) NOTA MEDSYS
    note_prompt = f"""Genera la NOTA DE EVOLUCIÓN correspondiente a este paciente ESTABLE (sin eventualidades en las últimas 24 h). Formato MedSys exacto:

INFORMACIÓN FIJA:
{ctx}

RESUMEN DEL PASE DE HOY (recién generado):
{pase_text}

LABS DE HOY: {today_entry.get('labs', '') or 'Sin nuevos laboratorios.'}
ESTUDIOS DE HOY: {today_entry.get('studies', '') or 'Ninguno.'}

Formato exacto (texto plano):

NOTA DE EVOLUCIÓN — {target}
Servicio: Cirugía General

ENCABEZADO
Paciente: (nombre completo, edad, sexo)
Cama / Piso: (cama · piso)
Días de estancia: (DEIH) | Días postoperatorios: (DPQX)
Diagnóstico: (dx resumido)
Cirugía: (fecha · procedimiento)
Antecedentes relevantes: (una línea o "Sin antecedentes de relevancia")
Interconsultas activas: (lista o "Ninguna")

EVOLUCIÓN
Paciente que se encuentra sin eventualidades durante las últimas 24 horas. (Adapta al contexto: postquirúrgico, oncológico, etc.) Continúa con manejo establecido, sin complicaciones referidas. (2-3 párrafos breves reflejando estabilidad clínica.)

EXPLORACIÓN FÍSICA
Signos vitales: ND
Estado general: estable, sin datos de descompensación referidos
Cabeza y cuello: sin alteraciones referidas
Cardiopulmonar: sin datos referidos
Abdomen: sin cambios respecto a lo previo (herida, drenajes si aplica)
Extremidades: sin datos referidos
Neurológico: sin datos referidos

LABORATORIOS Y ESTUDIOS
Laboratorios del día: (valores si hay; si no, "Sin nuevos laboratorios el día de hoy")
Cambios relevantes: (tendencias si hay comparación; si no, "N/A")
Estudios / procedimientos: (si hay; si no, "Sin estudios el día de hoy")

PLAN
1. Continuar mismo plan terapéutico.
2. (dieta / analgesia / profilaxis según info fija disponible)
3. Vigilancia clínica.
4. (interconsultas y pendientes si aplican)

PRONÓSTICO
(Una línea acorde a estabilidad clínica.)

—
Firma: Residente de Cirugía General

Reglas: no inventes datos, refleja estabilidad; español médico profesional; sin markdown."""
    system_note = "Redactas notas MedSys para pacientes estables sin cambios. No inventas datos. Reflejas estabilidad. Español médico."
    note_text = await llm_generate(system_note, note_prompt)

    # 3) WHATSAPP
    wa_prompt = f"""Redacta un MENSAJE BREVE para el médico tratante (WhatsApp) informando que el paciente continúa estable.

INFORMACIÓN:
{ctx}

Contexto: paciente ESTABLE, sin eventualidades en 24 h. {'Nuevos labs disponibles.' if today_entry.get('labs') else ''}

Formato texto plano (≤10 líneas, listo para copiar):

Buenos días Dr(a). [Apellido].
Reporte del paciente [Nombre], cama [Cama·Piso], DPQX [días].
Dx: [dx resumido].
QX: [procedimiento] ([fecha]).
Evolución: Paciente sin eventualidades en las últimas 24 horas, continúa estable con manejo establecido.
Labs: {today_entry.get('labs', '') or 'Sin nuevos laboratorios el día de hoy.'}
Plan: Continuar mismo esquema y vigilancia clínica.
Pendientes: [si aplican, si no "Sin pendientes activos"]
Saludos cordiales."""
    system_wa = "Redactas mensajes breves y corteses para WhatsApp en español médico. Sin markdown."
    wa_text = await llm_generate(system_wa, wa_prompt)

    # Save all
    await db.daily_entries.update_one(
        {"patient_id": patient_id, "user_id": user["id"], "date": target},
        {"$set": {
            "ai_pase_summary": pase_text,
            "ai_evolution_note": note_text,
            "ai_whatsapp": wa_text,
            "saved_to_pase": True,
            "updated_at": now_utc().isoformat(),
        }},
        upsert=True,
    )
    # First pase clears "nuevo ingreso" badge
    if patient.get("is_new_admission"):
        await db.patients.update_one(
            {"id": patient_id, "user_id": user["id"]},
            {"$set": {"is_new_admission": False, "updated_at": now_utc().isoformat()}},
        )
    return {"summary": pase_text, "note": note_text, "whatsapp": wa_text}


# ---------------- INGRESOS: nota de ingreso ----------------
@api.post("/patients/{patient_id}/generate/admission")
async def generate_admission_note(patient_id: str, body: GenerateBody, user: dict = Depends(get_user)):
    patient = await db.patients.find_one({"id": patient_id, "user_id": user["id"]}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    ctx = build_patient_context(patient)
    target = body.date or today_iso()

    prompt = f"""Redacta una NOTA DE INGRESO hospitalario completa para este paciente, en español médico profesional, formato MedSys exacto listo para copiar. Usa exclusivamente la información fija almacenada.

INFORMACIÓN FIJA:
{ctx}

Formato (texto plano, sin markdown):

NOTA DE INGRESO — {target}
Servicio: Cirugía General

FICHA DE IDENTIFICACIÓN
Paciente: (nombre completo, edad, sexo)
Cama / Piso / Servicio: (cama · piso · servicio)
Fecha de ingreso: ({patient.get('admission_date', 'ND')})

MOTIVO DE INGRESO
(1-2 líneas basadas en el dx resumido y completo)

PADECIMIENTO ACTUAL
(3-6 líneas describiendo el cuadro que motiva el ingreso, basado en dx completo. NO inventes fechas ni síntomas específicos que no estén en la info fija.)

ANTECEDENTES DE IMPORTANCIA
- Personales patológicos: (según info fija; si no hay, "Sin antecedentes de importancia")
- Quirúrgicos: (si aplica cirugía previa/planeada)
- Alérgicos: ({patient.get('allergies', 'Ninguna referida')})
- Medicamentos crónicos: ({patient.get('important_medications', 'Ninguno referido')})
- Oncológico: ({patient.get('oncology_status', 'No aplica')} / {patient.get('oncology_treatment', '')})

EXPLORACIÓN FÍSICA AL INGRESO
Signos vitales: ND
Estado general: (impresión clínica al ingreso — general)
Cabeza y cuello: sin alteraciones referidas
Cardiopulmonar: sin alteraciones referidas
Abdomen: (según dx si aplica dolor, distensión, defensa)
Extremidades: sin alteraciones referidas
Neurológico: consciente, orientado, sin déficit referido

DIAGNÓSTICOS DE INGRESO
1. {patient.get('dx_short', 'ND')}
(Si hay dx_full, expandir en subincisos numerados con los diagnósticos secundarios relevantes.)

PLAN DE MANEJO INICIAL
1. Ingreso a servicio de Cirugía General.
2. (Ayuno / dieta según dx; ej. NPO si es abdomen agudo)
3. Soluciones parenterales / hidratación IV.
4. Analgesia según protocolo institucional.
5. Antibiótico si aplica según dx (mencionar si el dx sugiere infección).
6. Solicitar exámenes de laboratorio de ingreso (BH, QS, ES, TP/TTP, EGO, cultivos si aplica).
7. Estudios de imagen según dx (USG / TC abdominal si aplica).
8. Preparación quirúrgica si aplica.
9. Vigilancia clínica estrecha.
10. Interconsultas según requerimientos: ({patient.get('consultants', 'Ninguna al momento')})

⚡ SUGERENCIA DE IA — PLAN QUIRÚRGICO PROPUESTO:
- (1-3 bullets con la propuesta más razonable basada en dx; solo si el dx lo justifica.)
— Requiere validación del médico responsable —

PRONÓSTICO INICIAL
Reservado a evolución. (Ajusta según severidad del dx.)

—
Firma: Residente de Cirugía General

Reglas estrictas:
1. NO inventes signos vitales, fechas, medicamentos específicos ni valores.
2. Basa todo en la INFORMACIÓN FIJA proporcionada.
3. Si un dato no está, usa "ND" o "sin datos".
4. Todo lo terapéutico específico va en el PLAN o en la SUGERENCIA DE IA claramente etiquetada."""

    system = "Eres experto en redacción de notas de ingreso hospitalario de cirugía general para MedSys. No inventas datos clínicos. Español médico profesional."
    note = await llm_generate(system, prompt)
    return {"note": note}


# ---------------- NOTA DE INGRESO (pegada desde MedSys) ----------------
class AdmissionNotePaste(BaseModel):
    text: str


@api.post("/patients/{patient_id}/admission-note")
async def paste_admission_note(
    patient_id: str, body: AdmissionNotePaste, user: dict = Depends(get_user)
):
    """Guarda la nota de ingreso pegada desde MedSys y usa GPT para extraer campos fijos
    (merge no-destructivo — nunca borra información previa)."""
    patient = await db.patients.find_one({"id": patient_id, "user_id": user["id"]}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    text = (body.text or "").strip()
    if not text or len(text) < 20:
        raise HTTPException(status_code=400, detail="El texto de la nota está vacío o es demasiado corto")

    # Always save the raw text first (permanent)
    await db.patients.update_one(
        {"id": patient_id, "user_id": user["id"]},
        {"$set": {"admission_note_text": text, "updated_at": now_utc().isoformat()}},
    )

    # Extract structured fields with GPT
    system = (
        "Eres un asistente que EXTRAE información clínica de una nota de ingreso hospitalario pegada literalmente. "
        "Devuelves EXCLUSIVAMENTE JSON válido. Nunca inventas datos. Si un campo no está, usas null."
    )
    prompt = f"""Extrae de esta NOTA DE INGRESO los siguientes campos.

NOTA DE INGRESO (texto tal como fue pegado):
{text}

Devuelve JSON con esta forma exacta:
{{
  "admission_reason": "Motivo de ingreso (una línea si está presente)",
  "current_illness": "Padecimiento actual completo tal como está escrito",
  "admission_diagnosis": "Diagnóstico(s) de ingreso principal(es)",
  "medical_history": "Antecedentes personales patológicos importantes (crónicos, degenerativos, etc.)",
  "previous_surgeries": "Cirugías previas si están mencionadas",
  "allergies": "Alergias específicas (medicamentos o sustancias)",
  "important_medications": "Medicamentos habituales / crónicos",
  "surgery_procedure": "Procedimiento quirúrgico realizado / planeado si está en la nota",
  "surgery_findings": "Hallazgos quirúrgicos si están mencionados",
  "oncology_status": "Estado oncológico si aplica (estadio, tipo, actividad de la enfermedad)"
}}

Reglas ESTRICTAS:
1. NO inventes nada. Si un campo NO está en la nota → null.
2. Copia el texto literal cuando corresponda; no reformules ni resumas en exceso.
3. NO extraigas ni menciones interconsultantes (esos los captura el usuario manualmente).
4. Devuelve SOLO el JSON, sin ```json``` ni explicaciones."""

    try:
        raw = await llm_generate(system, prompt)
    except Exception as e:
        return {
            "ok": True,
            "extracted": {},
            "merged_fields": [],
            "warning": f"Nota guardada, pero la extracción con IA falló: {str(e)[:200]}",
        }

    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```", 2)
        raw = parts[1] if len(parts) > 1 else ""
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip("`").strip()

    import json as _json
    try:
        data = _json.loads(raw)
    except Exception:
        import re
        m = re.search(r"\{.*\}", raw, re.S)
        data = _json.loads(m.group(0)) if m else {}

    # Non-destructive merge: only fill fields that are currently empty/null
    FIELD_MAP = {
        "current_illness": "dx_full",
        "admission_diagnosis": "dx_short",
        "medical_history": "medical_history",
        "allergies": "allergies",
        "important_medications": "important_medications",
        "surgery_procedure": "surgery_procedure",
        "surgery_findings": "surgery_findings",
        "oncology_status": "oncology_status",
    }
    merged_fields: list[str] = []
    to_update: dict = {}
    for src, dst in FIELD_MAP.items():
        val = data.get(src)
        if not val or not isinstance(val, str) or not val.strip():
            continue
        current = (patient.get(dst) or "").strip()
        if not current:
            to_update[dst] = val.strip()
            merged_fields.append(dst)
        elif val.strip() != current and len(val.strip()) > len(current):
            # Append if new content adds substantially more info
            to_update[dst] = current + "\n\n[Nota de ingreso]: " + val.strip()
            merged_fields.append(dst)

    if to_update:
        to_update["updated_at"] = now_utc().isoformat()
        await db.patients.update_one(
            {"id": patient_id, "user_id": user["id"]}, {"$set": to_update}
        )

    return {"ok": True, "extracted": data, "merged_fields": merged_fields}


# ---------------- NOTAS ADICIONALES (otros servicios) ----------------
class AdditionalNoteCreate(BaseModel):
    source: str  # e.g. "Medicina Interna", "UTI", "Oncología"
    text: str


@api.get("/patients/{patient_id}/additional-notes")
async def list_additional_notes(patient_id: str, user: dict = Depends(get_user)):
    patient = await db.patients.find_one({"id": patient_id, "user_id": user["id"]}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    cur = db.additional_notes.find(
        {"patient_id": patient_id, "user_id": user["id"]}, {"_id": 0}
    )
    notes = await cur.to_list(500)
    notes.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return notes


@api.post("/patients/{patient_id}/additional-notes")
async def add_additional_note(
    patient_id: str, body: AdditionalNoteCreate, user: dict = Depends(get_user)
):
    patient = await db.patients.find_one({"id": patient_id, "user_id": user["id"]}, {"_id": 0})
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    text = (body.text or "").strip()
    source = (body.source or "Otro servicio").strip() or "Otro servicio"
    if not text or len(text) < 20:
        raise HTTPException(status_code=400, detail="El texto de la nota está vacío o es demasiado corto")

    # AI executive summary — does NOT modify patient's fixed information
    system = (
        "Eres un asistente que genera resúmenes ejecutivos de notas médicas de otros servicios. "
        "Solo resumes lo que aparece en la nota; NO inventas ni modificas información. "
        "Español médico profesional."
    )
    prompt = f"""Genera un RESUMEN EJECUTIVO breve de esta nota clínica proveniente de otro servicio médico ({source}).

NOTA COMPLETA:
{text}

Formato (texto plano, sin markdown), máximo 12 líneas:

RESUMEN — {source}
Impresión diagnóstica: (1-2 líneas)
Cambios importantes: (bullets con lo relevante clínicamente)
Recomendaciones: (bullets del servicio)
Pendientes: (bullets)

Reglas:
1. NO inventes. Solo lo que está en la nota.
2. Si algo no está, escribe "ND" o omite la línea.
3. Español médico. Sin comentarios extra."""

    ai_summary = None
    warning = None
    try:
        ai_summary = await llm_generate(system, prompt)
    except Exception as e:
        warning = f"Nota guardada, pero el resumen con IA falló: {str(e)[:200]}"

    note = {
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "user_id": user["id"],
        "source": source,
        "text": text,
        "ai_summary": ai_summary,
        "created_at": now_utc().isoformat(),
    }
    await db.additional_notes.insert_one(note)
    note.pop("_id", None)
    return {"note": note, "warning": warning}


@api.delete("/patients/{patient_id}/additional-notes/{note_id}")
async def delete_additional_note(
    patient_id: str, note_id: str, user: dict = Depends(get_user)
):
    result = await db.additional_notes.delete_one(
        {"id": note_id, "patient_id": patient_id, "user_id": user["id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Nota no encontrada")
    return {"ok": True}


_stt_client: Optional[OpenAISpeechToText] = None


def get_stt():
    global _stt_client
    if _stt_client is None:
        _stt_client = OpenAISpeechToText(api_key=EMERGENT_KEY)
    return _stt_client


@api.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), user: dict = Depends(get_user)):
    """Real transcription via OpenAI Whisper (routed through Emergent proxy)."""
    try:
        content = await audio.read()
        if len(content) < 1000:
            raise HTTPException(status_code=400, detail="Audio demasiado corto")
        # litellm expects a tuple (filename, bytes, mime) or a file-like object
        filename = audio.filename or "audio.webm"
        # Ensure filename has a supported extension for validator
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"):
            filename = "audio.webm"
        stt = get_stt()
        result = await stt.transcribe(
            file=(filename, content, audio.content_type or "audio/webm"),
            model="whisper-1",
            response_format="text",
            language="es",
            prompt="Transcripción médica en español. Terminología de cirugía general, laboratorios, medicamentos.",
        )
        text = result if isinstance(result, str) else getattr(result, "text", str(result))
        return {"text": text.strip()}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=f"Error al transcribir: {str(e)}")


@api.get("/")
async def root():
    return {"app": "SurgiNote", "status": "ok"}


async def seed_demo_user():
    existing = await db.users.find_one({"email": "demo@surginote.app"})
    if existing:
        return
    user_id = str(uuid.uuid4())
    await db.users.insert_one({
        "id": user_id,
        "email": "demo@surginote.app",
        "password": hash_pw("DemoSurgi2026!"),
        "name": "Dr. Demo",
        "created_at": now_utc().isoformat(),
    })
    logger.info("Seeded demo user")


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_start():
    await seed_demo_user()


@app.on_event("shutdown")
async def on_stop():
    client.close()
