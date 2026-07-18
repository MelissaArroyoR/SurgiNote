# SurgiNote — Asistente Personal para Residente de Cirugía General

## Problem Statement (original)
Aplicación web personalizada para iPhone y iPad para un residente de cirugía general. Ayuda durante el pase de visita, elaboración de notas y creación de mensajes para médicos tratantes. No es un expediente clínico ni sustituye el juicio clínico. Organiza, resume y redacta información clínica a partir de los datos proporcionados por el usuario.

## Architecture

### Stack
- **Backend:** FastAPI + MongoDB (Motor async)
- **Frontend:** React (CRA + Craco) + Tailwind + Shadcn UI + Sonner + Framer Motion
- **AI:** GPT-5.2 vía `emergentintegrations.LlmChat` + OpenAI Whisper vía `emergentintegrations.OpenAISpeechToText` (ambos usan `EMERGENT_LLM_KEY`)
- **Auth:** JWT (email + password bcrypt)
- **Diseño:** Dark slate + amber, Manrope + IBM Plex Sans, bottom tab bar iOS-style, botones táctiles ≥60px

### Data Model (MongoDB collections)
- `users`: { id, email, password (bcrypt), name, created_at }
- `patients`: { id, user_id, name, age, sex, bed, floor, dx_short, dx_full, admission_date, surgery_date, surgery_procedure, surgery_findings, medical_history, consultants, oncology_treatment, active, created_at, updated_at }
- `daily_entries`: { id, patient_id, user_id, date, dictation, labs, studies, events, ai_pase_summary, ai_evolution_note, ai_whatsapp, saved_to_pase, created_at, updated_at }

Días de estancia (DEA) y días postoperatorios (DPQ) se calculan al vuelo desde las fechas fijas.

### Screens (4 tabs)
1. **PACIENTES** — Censo con tarjetas (nombre, cama, piso, DEA, DPQ, dx). Tap → detalle.
2. **PASE** — Documento único agregando resúmenes de todos los pacientes del día. Botón "Copiar".
3. **NOTAS** — Selector de paciente + botón "Generar Nota" → Nota SOAP formato MedSys + mensaje WhatsApp con botones "Copiar".
4. **INGRESOS** — Placeholder ("Próximamente" — reservado para nota de ingreso hospitalario).

### Patient Detail workflow
1. Header sticky con info fija (nombre, edad, cama, piso, DEA, DPQ). Expandible a info completa.
2. Zona de captura del día:
   - **Botón de micrófono** grande (Whisper real, transcripción en español)
   - Textarea de dictado (auto-guarda al perder foco/debounce)
   - Textarea de laboratorios
   - Textarea de estudios
   - Textarea de eventos
3. **Botón "Guardar al Pase"** → GPT genera:
   - Resumen estructurado (DX, QX, APP, INTERCONSULTAS)
   - Resumen clínico del día
   - Cambios de medicamentos
   - Comparación INTELIGENTE de labs (solo cambios clínicamente relevantes, no copia)
   - Sección "POR SISTEMAS" (solo si aplica en UTI/UTIM)
   - **⚡ SUGERENCIA DE IA — Plan Sugerido** (etiquetado explícitamente, requiere validación médica)
   - Pendientes / a discutir
4. Línea de tiempo con entradas previas.

## Implementation Status ✅

### 2026-07-18 — v1 Completo
- ✅ Login/registro con JWT + bcrypt
- ✅ Auto-seed usuario demo (`demo@surginote.app` / `DemoSurgi2026!`)
- ✅ CRUD completo de pacientes con soft-delete (alta)
- ✅ Cálculo automático DEA/DPQ desde fechas
- ✅ Entradas diarias (dictation, labs, studies, events) con auto-guardado
- ✅ **Transcripción por voz real** con OpenAI Whisper via Emergent proxy (probado con audio español)
- ✅ Generación de resumen del pase con GPT-5.2 (probado: identifica tendencias, marca "Sugerencia de IA")
- ✅ Generación de nota de evolución formato **MedSys** (Encabezado/Evolución/EF/Labs/Plan/Pronóstico)
- ✅ Generación de mensaje WhatsApp listo para copiar
- ✅ Documento único de pase agregado
- ✅ Línea de tiempo por paciente
- ✅ UI iOS-optimizada: dark slate + amber, Manrope, botones ≥60px, safe-area, bottom tabs

## Backlog (P1 / P2)

### P1
- [ ] Módulo **INGRESOS** — Generación de nota de ingreso usando info fija del paciente
- [ ] Editar / regenerar el resumen del pase después de generado
- [ ] Exportar pase como PDF/archivo compartible

### P2
- [ ] Importación desde Google Sheets del censo diario
- [ ] Calculadoras quirúrgicas (Alvarado, ASA, qSOFA, Child-Pugh)
- [ ] Búsqueda / filtros en el censo
- [ ] Modo iPad con layout de 2 columnas (md:grid-cols-2)
- [ ] Notificaciones para recordatorios de pendientes

## Test Credentials
See `/app/memory/test_credentials.md`
