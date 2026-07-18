"""SurgiNote backend - FastAPI app for surgical resident personal assistant."""
import os
import io
import uuid
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
    dx_short: Optional[str] = None
    dx_full: Optional[str] = None
    surgery_date: Optional[str] = None
    surgery_procedure: Optional[str] = None
    surgery_findings: Optional[str] = None
    medical_history: Optional[str] = None
    consultants: Optional[str] = None
    oncology_treatment: Optional[str] = None
    admission_date: Optional[str] = None
    active: bool = True
    created_at: str = Field(default_factory=lambda: now_utc().isoformat())
    updated_at: str = Field(default_factory=lambda: now_utc().isoformat())


class PatientCreate(BaseModel):
    name: str
    age: Optional[int] = None
    sex: Optional[str] = None
    bed: Optional[str] = None
    floor: Optional[str] = None
    dx_short: Optional[str] = None
    dx_full: Optional[str] = None
    surgery_date: Optional[str] = None
    surgery_procedure: Optional[str] = None
    surgery_findings: Optional[str] = None
    medical_history: Optional[str] = None
    consultants: Optional[str] = None
    oncology_treatment: Optional[str] = None
    admission_date: Optional[str] = None


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    bed: Optional[str] = None
    floor: Optional[str] = None
    dx_short: Optional[str] = None
    dx_full: Optional[str] = None
    surgery_date: Optional[str] = None
    surgery_procedure: Optional[str] = None
    surgery_findings: Optional[str] = None
    medical_history: Optional[str] = None
    consultants: Optional[str] = None
    oncology_treatment: Optional[str] = None
    admission_date: Optional[str] = None
    active: Optional[bool] = None


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


@api.get("/patients")
async def list_patients(user: dict = Depends(get_user)):
    cur = db.patients.find({"user_id": user["id"], "active": True}, {"_id": 0})
    patients = await cur.to_list(500)
    for p in patients:
        enrich_patient(p)
    patients.sort(key=lambda x: (x.get("floor") or "", x.get("bed") or ""))
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
        {"id": patient_id, "user_id": user["id"]}, {"$set": {"active": False, "updated_at": now_utc().isoformat()}}
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
        f"Cama: {patient.get('bed', 'ND')}   Piso: {patient.get('floor', 'ND')}",
        f"Días de estancia: {days_a if days_a is not None else 'ND'}   Días postquirúrgicos: {days_p if days_p is not None else 'ND'}",
        f"Diagnóstico resumido: {patient.get('dx_short', '')}",
        f"Diagnóstico completo: {patient.get('dx_full', '')}",
        f"Procedimiento quirúrgico ({patient.get('surgery_date', 'ND')}): {patient.get('surgery_procedure', '')}",
        f"Hallazgos quirúrgicos: {patient.get('surgery_findings', '')}",
        f"Antecedentes personales patológicos: {patient.get('medical_history', '')}",
        f"Interconsultantes: {patient.get('consultants', '')}",
        f"Tratamiento oncológico: {patient.get('oncology_treatment', '')}",
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
