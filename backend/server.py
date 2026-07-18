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

Genera un RESUMEN ESTRUCTURADO PARA EL PASE DE VISITA con las siguientes secciones (texto plano, sin markdown):

▎ {patient.get('name','')}  |  Cama {patient.get('bed','ND')} · Piso {patient.get('floor','ND')}
▎ DEA: {dea} · DPQ: {dpq}

DX: (diagnóstico resumido)
QX: (procedimiento y fecha)
APP RELEVANTES: (antecedentes en 1 línea)
ONCOLÓGICO: (si aplica, en 1 línea; si no, omite la línea)
INTERCONSULTAS ACTIVAS: (lista breve)

CAMBIOS DEL DÍA:
- (bullets concisos con los cambios clínicos más importantes)

COMPARACIÓN DE LABS vs DÍA PREVIO:
- (compara valores clave: Hb, leucocitos, plaquetas, creatinina, urea, electrolitos, glucosa, PCR, procalcitonina, etc. Indica tendencia con ↑↓→ y magnitud. Si no hay previos, resume solo los actuales.)

ESTUDIOS/PROCEDIMIENTOS:
- (resumen conciso)

PENDIENTES / A DISCUTIR:
- (puntos clave para el pase)

Sé conciso, clínico y directo. Español médico. No inventes datos."""

    system = "Eres un asistente experto para un residente de cirugía general. Organizas y resumes información clínica proporcionada por el usuario. NO inventas datos. Si algo no está, escribes 'ND' o omites la línea. Nunca sustituyes el juicio clínico."
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

Redacta una NOTA DE EVOLUCIÓN completa y profesional en formato SOAP, español clínico:

NOTA DE EVOLUCIÓN — {target}
Paciente: (nombre, edad, sexo)
Cama: (cama · piso)
DEA/DPQ: (días de estancia · días postquirúrgicos)

Diagnósticos:
1. (dx resumido)

Antecedentes relevantes: (una línea)

Procedimiento quirúrgico: (fecha · procedimiento · hallazgos)

S (Subjetivo): (basado en el dictado)

O (Objetivo):
- Signos vitales / exploración (si se dictó)
- Laboratorios del día
- Estudios / procedimientos

A (Análisis): (impresión clínica breve y razonada, evolución esperada)

P (Plan):
- (plan por sistemas / problemas)
- (interconsultas pendientes)
- (estudios pendientes)

Firma: Cirugía General · Residente

No inventes datos. Usa exactamente la información proporcionada."""
    system = "Eres experto en redacción de notas médicas de cirugía general en español. Notas SOAP profesionales, precisas, concisas. No inventas datos."
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


_openai_client: Optional[AsyncOpenAI] = None


def get_openai():
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=EMERGENT_KEY,
            base_url="https://integrations.emergentagent.com/llm",
        )
    return _openai_client


@api.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), user: dict = Depends(get_user)):
    try:
        content = await audio.read()
        filename = audio.filename or "audio.webm"
        client_ai = get_openai()
        result = await client_ai.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, content, audio.content_type or "audio/webm"),
            language="es",
        )
        return {"text": result.text}
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
