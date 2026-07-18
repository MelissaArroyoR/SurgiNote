import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft, Pencil, BedDouble, UserRound, Calendar, Activity,
  ClipboardCheck, Sparkles, Copy, Trash2, ChevronDown, ChevronUp,
  Clock, Zap, FileText, MessageSquarePlus, X, Loader2, ClipboardList,
} from "lucide-react";
import { api } from "@/lib/api";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import PatientFormDialog from "@/components/PatientFormDialog";
import VoiceDictation from "@/components/VoiceDictation";

function copyText(t) {
  navigator.clipboard?.writeText(t).then(
    () => toast.success("Copiado al portapapeles"),
    () => toast.error("No se pudo copiar")
  );
}

function Field({ label, value }) {
  if (!value) return null;
  return (
    <div className="py-1.5">
      <div className="text-[10px] font-bold uppercase tracking-widest text-blue-600 mb-0.5">{label}</div>
      <div className="text-slate-800 text-sm leading-snug whitespace-pre-wrap">{value}</div>
    </div>
  );
}

export default function PatientDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [patient, setPatient] = useState(null);
  const [entry, setEntry] = useState(null);
  const [entries, setEntries] = useState([]);
  const [additional, setAdditional] = useState([]);
  const [expandedInfo, setExpandedInfo] = useState(false);
  const [editing, setEditing] = useState(false);
  const [generatingPase, setGeneratingPase] = useState(false);
  const [generatingNoChanges, setGeneratingNoChanges] = useState(false);
  const [pase, setPase] = useState("");
  const [admissionOpen, setAdmissionOpen] = useState(false);
  const [addlOpen, setAddlOpen] = useState(false);
  const [interconsultants, setInterconsultants] = useState("");
  const debounceRef = useRef(null);
  const interDebounceRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const [p, e, es, an] = await Promise.all([
        api.getPatient(id),
        api.getTodayEntry(id),
        api.listEntries(id),
        api.listAdditionalNotes(id).catch(() => []),
      ]);
      setPatient(p);
      setEntry(e);
      setEntries(es);
      setAdditional(an);
      setPase(e.ai_pase_summary || "");
      setInterconsultants(p.consultants || "");
    } catch {
      toast.error("Error al cargar paciente");
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const patchEntry = (patch) => {
    setEntry((prev) => ({ ...prev, ...patch }));
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try { await api.updateTodayEntry(id, patch); } catch { toast.error("Error al guardar"); }
    }, 600);
  };

  const patchInterconsultants = (v) => {
    setInterconsultants(v);
    if (interDebounceRef.current) clearTimeout(interDebounceRef.current);
    interDebounceRef.current = setTimeout(async () => {
      try { await api.updatePatient(id, { consultants: v }); } catch { toast.error("Error al guardar"); }
    }, 700);
  };

  const doGeneratePase = async () => {
    setGeneratingPase(true);
    setPase("");
    try {
      await api.updateTodayEntry(id, {
        dictation: entry.dictation || "", labs: entry.labs || "",
        studies: entry.studies || "", events: entry.events || "",
      });
      const { summary } = await api.generatePase(id);
      setPase(summary);
      setEntry((e) => ({ ...e, ai_pase_summary: summary, saved_to_pase: true }));
      toast.success("Resumen generado y guardado al pase");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al generar resumen");
    } finally { setGeneratingPase(false); }
  };

  const doGenerateNoChanges = async () => {
    if (!window.confirm("¿Confirmar que el paciente NO tuvo eventualidades en las últimas 24 horas?")) return;
    setGeneratingNoChanges(true);
    setPase("");
    try {
      await api.updateTodayEntry(id, {
        dictation: entry.dictation || "", labs: entry.labs || "",
        studies: entry.studies || "", events: entry.events || "",
      });
      const { summary } = await api.generateNoChanges(id);
      setPase(summary);
      setEntry((e) => ({ ...e, ai_pase_summary: summary, saved_to_pase: true }));
      toast.success("Paciente sin cambios: pase, nota y WhatsApp generados");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al generar");
    } finally { setGeneratingNoChanges(false); }
  };

  const discharge = async () => {
    if (!window.confirm(`¿Dar de alta a ${patient.name}?`)) return;
    try {
      await api.dischargePatient(id);
      toast.success("Paciente dado de alta");
      nav("/pacientes");
    } catch { toast.error("Error"); }
  };

  if (!patient || !entry) {
    return <div className="text-slate-500 py-16 text-center text-sm">Cargando…</div>;
  }

  const fieldCls = "bg-white border-slate-300 text-slate-900 focus-visible:ring-blue-500 focus-visible:border-blue-500";

  return (
    <div className="py-2">
      <div className="flex items-center justify-between mb-4">
        <button
          data-testid="btn-back"
          onClick={() => nav("/pacientes")}
          className="w-11 h-11 rounded-full border border-slate-200 bg-white flex items-center justify-center text-slate-600 hover:border-blue-500 hover:text-blue-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex gap-2">
          <button
            data-testid="btn-edit-patient"
            onClick={() => setEditing(true)}
            className="h-11 px-4 rounded-full border border-slate-200 bg-white flex items-center gap-2 text-slate-600 hover:border-blue-500 hover:text-blue-600 transition-colors text-sm"
          >
            <Pencil className="w-4 h-4" /> Editar
          </button>
          <button
            data-testid="btn-discharge"
            onClick={discharge}
            className="w-11 h-11 rounded-full border border-slate-200 bg-white flex items-center justify-center text-slate-500 hover:border-red-500 hover:text-red-500 transition-colors"
            aria-label="Dar de alta"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-5 mb-5 shadow-sm" data-testid="patient-header">
        <h1 className="font-heading font-extrabold text-2xl text-slate-900 mb-1">{patient.name}</h1>
        <p className="text-slate-500 text-sm mb-4">
          {patient.age ? `${patient.age} años` : "Edad ND"}{patient.sex ? ` · ${patient.sex}` : ""}
        </p>
        <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-sm">
          <div className="flex items-center gap-2 text-slate-700"><BedDouble className="w-4 h-4 text-blue-600" />Cama {patient.bed || "ND"}</div>
          <div className="flex items-center gap-2 text-slate-700 truncate"><UserRound className="w-4 h-4 text-blue-600 flex-shrink-0" />{patient.attending_physician || "Tratante ND"}</div>
          <div className="flex items-center gap-2 text-slate-700"><Calendar className="w-4 h-4 text-blue-600" />DEIH {patient.days_admission ?? "ND"}</div>
          <div className="flex items-center gap-2 text-slate-700"><Activity className="w-4 h-4 text-blue-600" />DPQX {patient.days_postop ?? "ND"}</div>
        </div>

        <button
          data-testid="btn-toggle-info"
          onClick={() => setExpandedInfo((v) => !v)}
          className="mt-4 w-full h-11 rounded-lg border border-slate-200 flex items-center justify-center gap-2 text-slate-600 hover:border-blue-500 hover:text-blue-600 transition-colors text-sm bg-slate-50"
        >
          {expandedInfo ? <>Ocultar información fija <ChevronUp className="w-4 h-4" /></> : <>Ver información fija completa <ChevronDown className="w-4 h-4" /></>}
        </button>

        {expandedInfo && (
          <div className="mt-4 pt-4 border-t border-slate-200 space-y-1" data-testid="patient-fixed-info">
            <Field label="Servicio" value={patient.service} />
            <Field label="Tratante" value={patient.attending_physician} />
            <Field label="Unidad" value={patient.unit_classification} />
            <Field label="Diagnóstico resumido" value={patient.dx_short} />
            <Field label="Diagnóstico completo" value={patient.dx_full} />
            <Field label="Cirugía" value={patient.surgery_date ? `${patient.surgery_date} — ${patient.surgery_procedure || ""}` : patient.surgery_procedure} />
            <Field label="Hallazgos quirúrgicos" value={patient.surgery_findings} />
            <Field label="Antecedentes personales" value={patient.medical_history} />
            <Field label="Alergias" value={patient.allergies} />
            <Field label="Medicamentos importantes" value={patient.important_medications} />
            <Field label="Estado oncológico" value={patient.oncology_status} />
            <Field label="Tratamiento oncológico" value={patient.oncology_treatment} />
          </div>
        )}

        <div className="mt-4 pt-4 border-t border-slate-200 space-y-2">
          <div className="text-[10px] font-bold uppercase tracking-widest text-blue-600">Interconsultantes (solo visualización)</div>
          <Textarea
            data-testid="input-interconsultants"
            value={interconsultants}
            onChange={(e) => patchInterconsultants(e.target.value)}
            placeholder="Ej. Cardiología (Dr. X), Infectología (Dra. Y)…"
            rows={2}
            className={fieldCls}
          />
          <p className="text-[11px] text-slate-500">Este campo se guarda pero NO se usa para generar pases, notas o mensajes.</p>
        </div>

        <div className="mt-4 pt-4 border-t border-slate-200 flex flex-col gap-2">
          <button
            data-testid="btn-open-admission-note"
            onClick={() => setAdmissionOpen(true)}
            className="w-full h-12 rounded-lg bg-white border border-blue-200 text-blue-700 font-semibold text-sm flex items-center justify-center gap-2 hover:bg-blue-50 transition-colors"
          >
            <FileText className="w-4 h-4" /> {patient.admission_note_text ? "Ver / editar nota de ingreso" : "Agregar nota de ingreso"}
          </button>
        </div>
      </div>

      {/* Daily entry zone */}
      <div className="mb-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-heading font-bold text-lg text-slate-900">Hoy — {entry.date}</h2>
          {entry.saved_to_pase && (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-600 font-semibold">
              <ClipboardCheck className="w-3.5 h-3.5" /> En pase
            </span>
          )}
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5 mb-4 flex flex-col items-center shadow-sm">
          <div className="text-xs font-bold uppercase tracking-widest text-blue-600 mb-3">Dictado del día</div>
          <VoiceDictation
            testid="btn-voice-dictation"
            onTranscribed={(t) => patchEntry({ dictation: (entry.dictation ? entry.dictation + "\n" : "") + t })}
          />
          <p className="text-slate-500 text-xs mt-3 text-center max-w-xs">Presiona para dictar. La transcripción se agregará abajo automáticamente.</p>
          <Textarea
            data-testid="input-dictation"
            value={entry.dictation}
            onChange={(e) => patchEntry({ dictation: e.target.value })}
            placeholder="O escribe aquí el dictado del día…"
            rows={4}
            className={`${fieldCls} mt-4 w-full`}
          />
        </div>

        <div className="mb-3">
          <div className="text-xs font-bold uppercase tracking-widest text-blue-600 mb-1.5">Laboratorios</div>
          <Textarea data-testid="input-labs" value={entry.labs} onChange={(e) => patchEntry({ labs: e.target.value })}
            placeholder="Pega aquí los laboratorios del día…" rows={4} className={fieldCls} />
        </div>

        <div className="mb-3">
          <div className="text-xs font-bold uppercase tracking-widest text-blue-600 mb-1.5">Estudios / procedimientos</div>
          <Textarea data-testid="input-studies" value={entry.studies} onChange={(e) => patchEntry({ studies: e.target.value })}
            placeholder="Pega o describe estudios de imagen, endoscopias…" rows={3} className={fieldCls} />
        </div>

        <div className="mb-5">
          <div className="text-xs font-bold uppercase tracking-widest text-blue-600 mb-1.5">Eventos del día</div>
          <Textarea data-testid="input-events" value={entry.events} onChange={(e) => patchEntry({ events: e.target.value })}
            placeholder="Fiebre, sangrado, cambios en el manejo, complicaciones…" rows={3} className={fieldCls} />
        </div>

        <button
          data-testid="btn-generate-pase"
          onClick={doGeneratePase}
          disabled={generatingPase || generatingNoChanges}
          className="w-full h-14 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-base flex items-center justify-center gap-2 transition-colors active:scale-[0.98] disabled:opacity-60"
        >
          {generatingPase ? "Generando resumen…" : <><Sparkles className="w-5 h-5" /> Guardar al Pase</>}
        </button>

        <button
          data-testid="btn-no-changes"
          onClick={doGenerateNoChanges}
          disabled={generatingPase || generatingNoChanges}
          className="w-full h-12 mt-3 rounded-xl border border-emerald-300 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-heading font-semibold text-sm flex items-center justify-center gap-2 transition-colors active:scale-[0.98] disabled:opacity-60"
        >
          {generatingNoChanges ? "Generando (sin dictado)…" : <><Zap className="w-4 h-4" /> ✨ Paciente sin cambios · Generar todo</>}
        </button>

        {pase && (
          <div className="mt-4 bg-white border border-slate-200 rounded-xl p-5 shadow-sm" data-testid="pase-summary">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-bold uppercase tracking-widest text-blue-600">Resumen del pase</div>
              <button data-testid="btn-copy-pase" onClick={() => copyText(pase)}
                className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full border border-slate-200 text-slate-600 hover:border-blue-500 hover:text-blue-600 text-xs transition-colors bg-white">
                <Copy className="w-3.5 h-3.5" /> Copiar
              </button>
            </div>
            <div className="text-slate-800 text-sm leading-relaxed pre-wrap font-mono">{pase}</div>
          </div>
        )}
      </div>

      {/* Notas adicionales */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-blue-600" />
            <h3 className="font-heading font-bold text-base text-slate-900">Notas adicionales</h3>
          </div>
          <button
            data-testid="btn-open-additional"
            onClick={() => setAddlOpen(true)}
            className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-colors"
          >
            <MessageSquarePlus className="w-3.5 h-3.5" /> Agregar
          </button>
        </div>
        {additional.length === 0 ? (
          <p className="text-slate-500 text-xs bg-slate-50 border border-dashed border-slate-200 rounded-lg p-4 text-center">
            Notas de otros servicios (Medicina Interna, UTI, Oncología…) con resumen IA. No modifican la información fija.
          </p>
        ) : (
          <div className="space-y-2">
            {additional.map((n) => (
              <AdditionalNoteCard key={n.id} note={n} onDelete={async () => {
                if (!window.confirm("¿Eliminar esta nota?")) return;
                try {
                  await api.deleteAdditionalNote(id, n.id);
                  setAdditional(a => a.filter(x => x.id !== n.id));
                  toast.success("Nota eliminada");
                } catch { toast.error("Error"); }
              }} />
            ))}
          </div>
        )}
      </div>

      {/* Timeline */}
      {entries.length > 0 && (
        <div className="mt-6">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-blue-600" />
            <h3 className="font-heading font-bold text-base text-slate-900">Línea de tiempo</h3>
          </div>
          <div className="space-y-2">
            {entries.map((e) => (
              <div key={e.id} className="bg-white border border-slate-200 rounded-lg p-3" data-testid={`timeline-entry-${e.date}`}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="text-xs font-bold text-blue-600">{e.date}</div>
                  {e.saved_to_pase && <span className="text-[10px] uppercase tracking-widest text-emerald-600">En pase</span>}
                </div>
                {(e.dictation || e.events || e.labs) && (
                  <div className="text-slate-700 text-xs leading-snug line-clamp-3 pre-wrap">
                    {e.dictation || e.events || e.labs}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <PatientFormDialog open={editing} onOpenChange={setEditing} patient={patient}
        onSaved={() => { setEditing(false); load(); }} />

      <AdmissionNoteDialog open={admissionOpen} onOpenChange={setAdmissionOpen} patient={patient}
        onSaved={() => { setAdmissionOpen(false); load(); }} />

      <AdditionalNoteDialog open={addlOpen} onOpenChange={setAddlOpen} patientId={id}
        onCreated={(n) => { setAdditional(a => [n, ...a]); setAddlOpen(false); }} />
    </div>
  );
}

function AdditionalNoteCard({ note, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3" data-testid={`additional-note-${note.id}`}>
      <div className="flex items-center justify-between mb-2">
        <div>
          <div className="text-xs font-bold text-blue-600 uppercase tracking-widest">{note.source}</div>
          <div className="text-[10px] text-slate-500">{note.created_at?.split("T")[0]}</div>
        </div>
        <div className="flex gap-1">
          <button onClick={() => copyText(note.ai_summary || note.text)}
            className="w-8 h-8 rounded-full border border-slate-200 flex items-center justify-center text-slate-500 hover:text-blue-600 hover:border-blue-500">
            <Copy className="w-3 h-3" />
          </button>
          <button onClick={onDelete}
            className="w-8 h-8 rounded-full border border-slate-200 flex items-center justify-center text-slate-500 hover:text-red-600 hover:border-red-500">
            <X className="w-3 h-3" />
          </button>
        </div>
      </div>
      {note.ai_summary && (
        <div className="text-slate-800 text-sm leading-relaxed pre-wrap font-mono">{note.ai_summary}</div>
      )}
      <button onClick={() => setExpanded(v => !v)} className="mt-2 text-[11px] text-slate-500 hover:text-blue-600">
        {expanded ? "Ocultar" : "Ver"} texto original
      </button>
      {expanded && (
        <div className="mt-2 text-slate-600 text-xs leading-snug pre-wrap p-2 bg-slate-50 rounded border border-slate-200">{note.text}</div>
      )}
    </div>
  );
}

function AdmissionNoteDialog({ open, onOpenChange, patient, onSaved }) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => { if (open) setText(patient?.admission_note_text || ""); }, [open, patient]);

  const save = async () => {
    if (text.trim().length < 20) { toast.error("La nota es demasiado corta"); return; }
    setLoading(true);
    try {
      const res = await api.pasteAdmissionNote(patient.id, text);
      const n = (res.merged_fields || []).length;
      toast.success(n > 0 ? `Nota guardada. ${n} campo${n > 1 ? "s" : ""} extraído${n > 1 ? "s" : ""}.` : "Nota guardada.");
      if (res.warning) toast.error(res.warning);
      onSaved?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al guardar");
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white border-slate-200 text-slate-900 max-w-2xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl flex items-center gap-2">
            <FileText className="w-5 h-5 text-blue-600" /> Nota de ingreso
          </DialogTitle>
        </DialogHeader>
        <p className="text-slate-600 text-sm">
          Pega la nota de ingreso completa desde MedSys. La IA extraerá automáticamente motivo de ingreso, padecimiento actual, dx, antecedentes, alergias, medicamentos, cirugías y estado oncológico. Nunca borra información previa.
        </p>
        <Textarea
          data-testid="input-admission-note"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={16}
          placeholder="Pega aquí la nota de ingreso completa desde MedSys…"
          className="bg-white border-slate-300 text-slate-900 font-mono text-sm focus-visible:ring-blue-500"
        />
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}
            className="flex-1 h-12 bg-white border-slate-300 text-slate-700 hover:bg-slate-50">Cancelar</Button>
          <Button
            data-testid="btn-save-admission-note"
            onClick={save} disabled={loading}
            className="flex-1 h-12 bg-blue-600 hover:bg-blue-700 text-white font-bold">
            {loading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Guardando…</> : "Guardar y analizar"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function AdditionalNoteDialog({ open, onOpenChange, patientId, onCreated }) {
  const [source, setSource] = useState("");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => { if (open) { setSource(""); setText(""); } }, [open]);

  const save = async () => {
    if (!source.trim()) { toast.error("Indica el servicio"); return; }
    if (text.trim().length < 20) { toast.error("La nota es demasiado corta"); return; }
    setLoading(true);
    try {
      const res = await api.addAdditionalNote(patientId, source.trim(), text);
      toast.success("Nota agregada y resumida");
      if (res.warning) toast.error(res.warning);
      onCreated?.(res.note);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al guardar");
    } finally { setLoading(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-white border-slate-200 text-slate-900 max-w-2xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-heading text-xl flex items-center gap-2">
            <ClipboardList className="w-5 h-5 text-blue-600" /> Nota de otro servicio
          </DialogTitle>
        </DialogHeader>
        <p className="text-slate-600 text-sm">
          Pega una nota de Medicina Interna, UTI, Oncología, Infectología, etc. La IA generará un resumen ejecutivo (dx, cambios, recomendaciones, pendientes). No modifica la información fija del paciente.
        </p>
        <div>
          <div className="text-xs font-semibold text-slate-700 mb-1.5">Servicio</div>
          <Input
            data-testid="input-note-source"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="Ej. Medicina Interna, UTI, Oncología, Nutrición, Infectología"
            className="bg-white border-slate-300 text-slate-900 focus-visible:ring-blue-500"
          />
        </div>
        <Textarea
          data-testid="input-additional-note"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={14}
          placeholder="Pega aquí la nota completa del servicio…"
          className="bg-white border-slate-300 text-slate-900 font-mono text-sm focus-visible:ring-blue-500"
        />
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}
            className="flex-1 h-12 bg-white border-slate-300 text-slate-700 hover:bg-slate-50">Cancelar</Button>
          <Button
            data-testid="btn-save-additional-note"
            onClick={save} disabled={loading}
            className="flex-1 h-12 bg-blue-600 hover:bg-blue-700 text-white font-bold">
            {loading ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Analizando…</> : "Guardar y resumir"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
