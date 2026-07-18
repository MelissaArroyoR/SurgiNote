import { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft, Pencil, BedDouble, Building2, Calendar, Activity,
  Save, ClipboardCheck, Sparkles, Copy, Trash2, ChevronDown, ChevronUp, Clock, Zap
} from "lucide-react";
import { api } from "@/lib/api";
import { Textarea } from "@/components/ui/textarea";
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
      <div className="text-[10px] font-bold uppercase tracking-widest text-amber-500 mb-0.5">{label}</div>
      <div className="text-slate-100 text-sm leading-snug whitespace-pre-wrap">{value}</div>
    </div>
  );
}

export default function PatientDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [patient, setPatient] = useState(null);
  const [entry, setEntry] = useState(null);
  const [entries, setEntries] = useState([]);
  const [expandedInfo, setExpandedInfo] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generatingPase, setGeneratingPase] = useState(false);
  const [generatingNoChanges, setGeneratingNoChanges] = useState(false);
  const [pase, setPase] = useState("");
  const debounceRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const [p, e, es] = await Promise.all([
        api.getPatient(id),
        api.getTodayEntry(id),
        api.listEntries(id),
      ]);
      setPatient(p);
      setEntry(e);
      setEntries(es);
      setPase(e.ai_pase_summary || "");
    } catch {
      toast.error("Error al cargar paciente");
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const patchEntry = (patch) => {
    setEntry((prev) => ({ ...prev, ...patch }));
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        await api.updateTodayEntry(id, patch);
      } catch {
        toast.error("Error al guardar");
      }
    }, 600);
  };

  const doGeneratePase = async () => {
    setGeneratingPase(true);
    setPase("");
    try {
      await api.updateTodayEntry(id, {
        dictation: entry.dictation || "",
        labs: entry.labs || "",
        studies: entry.studies || "",
        events: entry.events || "",
      });
      const { summary } = await api.generatePase(id);
      setPase(summary);
      setEntry((e) => ({ ...e, ai_pase_summary: summary, saved_to_pase: true }));
      toast.success("Resumen generado y guardado al pase");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al generar resumen");
    } finally {
      setGeneratingPase(false);
    }
  };

  const doGenerateNoChanges = async () => {
    if (!window.confirm("¿Confirmar que el paciente NO tuvo eventualidades en las últimas 24 horas? Se generarán automáticamente pase, nota y mensaje de WhatsApp.")) return;
    setGeneratingNoChanges(true);
    setPase("");
    try {
      // Ensure latest labs are saved before generating
      await api.updateTodayEntry(id, {
        dictation: entry.dictation || "",
        labs: entry.labs || "",
        studies: entry.studies || "",
        events: entry.events || "",
      });
      const { summary } = await api.generateNoChanges(id);
      setPase(summary);
      setEntry((e) => ({ ...e, ai_pase_summary: summary, saved_to_pase: true }));
      toast.success("Paciente sin cambios: pase, nota y WhatsApp generados");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al generar");
    } finally {
      setGeneratingNoChanges(false);
    }
  };

  const discharge = async () => {
    if (!window.confirm(`¿Dar de alta a ${patient.name}? Se quitará del censo activo.`)) return;
    try {
      await api.dischargePatient(id);
      toast.success("Paciente dado de alta");
      nav("/pacientes");
    } catch {
      toast.error("Error");
    }
  };

  if (!patient || !entry) {
    return <div className="text-slate-500 py-16 text-center text-sm">Cargando…</div>;
  }

  const fieldCls = "bg-slate-900 border-slate-700 text-slate-50 focus-visible:ring-amber-500 focus-visible:border-amber-500";

  return (
    <div className="py-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <button
          data-testid="btn-back"
          onClick={() => nav("/pacientes")}
          className="w-11 h-11 rounded-full border border-slate-700 flex items-center justify-center text-slate-300 hover:border-amber-500 hover:text-amber-500 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex gap-2">
          <button
            data-testid="btn-edit-patient"
            onClick={() => setEditing(true)}
            className="h-11 px-4 rounded-full border border-slate-700 flex items-center gap-2 text-slate-300 hover:border-amber-500 hover:text-amber-500 transition-colors text-sm"
          >
            <Pencil className="w-4 h-4" /> Editar
          </button>
          <button
            data-testid="btn-discharge"
            onClick={discharge}
            className="w-11 h-11 rounded-full border border-slate-700 flex items-center justify-center text-slate-400 hover:border-red-500 hover:text-red-500 transition-colors"
            aria-label="Dar de alta"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Sticky patient header info */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 mb-5" data-testid="patient-header">
        <h1 className="font-heading font-extrabold text-2xl text-slate-50 mb-1">{patient.name}</h1>
        <p className="text-slate-400 text-sm mb-4">
          {patient.age ? `${patient.age} años` : "Edad ND"}
          {patient.sex ? ` · ${patient.sex}` : ""}
        </p>
        <div className="grid grid-cols-2 gap-y-3 gap-x-4 text-sm">
          <div className="flex items-center gap-2 text-slate-300"><BedDouble className="w-4 h-4 text-amber-500" />Cama {patient.bed || "ND"}</div>
          <div className="flex items-center gap-2 text-slate-300"><Building2 className="w-4 h-4 text-amber-500" />Piso {patient.floor || "ND"}</div>
          <div className="flex items-center gap-2 text-slate-300"><Calendar className="w-4 h-4 text-amber-500" />DEIH {patient.days_admission ?? "ND"}</div>
          <div className="flex items-center gap-2 text-slate-300"><Activity className="w-4 h-4 text-amber-500" />DPQX {patient.days_postop ?? "ND"}</div>
        </div>

        <button
          data-testid="btn-toggle-info"
          onClick={() => setExpandedInfo((v) => !v)}
          className="mt-4 w-full h-11 rounded-lg border border-slate-700 flex items-center justify-center gap-2 text-slate-300 hover:border-amber-500 hover:text-amber-500 transition-colors text-sm"
        >
          {expandedInfo ? <>Ocultar información fija <ChevronUp className="w-4 h-4" /></> : <>Ver información fija completa <ChevronDown className="w-4 h-4" /></>}
        </button>

        {expandedInfo && (
          <div className="mt-4 pt-4 border-t border-slate-700 space-y-1" data-testid="patient-fixed-info">
            <Field label="Servicio" value={patient.service} />
            <Field label="Unidad" value={patient.unit_classification} />
            <Field label="Diagnóstico resumido" value={patient.dx_short} />
            <Field label="Diagnóstico completo" value={patient.dx_full} />
            <Field label="Cirugía" value={patient.surgery_date ? `${patient.surgery_date} — ${patient.surgery_procedure || ""}` : patient.surgery_procedure} />
            <Field label="Hallazgos quirúrgicos" value={patient.surgery_findings} />
            <Field label="Antecedentes personales" value={patient.medical_history} />
            <Field label="Alergias" value={patient.allergies} />
            <Field label="Medicamentos importantes" value={patient.important_medications} />
            <Field label="Interconsultantes" value={patient.consultants} />
            <Field label="Estado oncológico" value={patient.oncology_status} />
            <Field label="Tratamiento oncológico" value={patient.oncology_treatment} />
          </div>
        )}
      </div>

      {/* Daily entry zone */}
      <div className="mb-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-heading font-bold text-lg text-slate-50">Hoy — {entry.date}</h2>
          {entry.saved_to_pase && (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-400 font-semibold">
              <ClipboardCheck className="w-3.5 h-3.5" /> En pase
            </span>
          )}
        </div>

        {/* Voice dictation prominent */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 mb-4 flex flex-col items-center">
          <div className="text-xs font-bold uppercase tracking-widest text-amber-500 mb-3">Dictado del día</div>
          <VoiceDictation
            testid="btn-voice-dictation"
            onTranscribed={(t) => patchEntry({ dictation: (entry.dictation ? entry.dictation + "\n" : "") + t })}
          />
          <p className="text-slate-400 text-xs mt-3 text-center max-w-xs">Presiona para dictar. La transcripción se agregará abajo automáticamente.</p>
          <Textarea
            data-testid="input-dictation"
            value={entry.dictation}
            onChange={(e) => patchEntry({ dictation: e.target.value })}
            placeholder="O escribe aquí el dictado del día…"
            rows={4}
            className={`${fieldCls} mt-4 w-full`}
          />
        </div>

        {/* Labs */}
        <div className="mb-3">
          <div className="text-xs font-bold uppercase tracking-widest text-amber-500 mb-1.5">Laboratorios</div>
          <Textarea
            data-testid="input-labs"
            value={entry.labs}
            onChange={(e) => patchEntry({ labs: e.target.value })}
            placeholder="Pega aquí los laboratorios del día. Ej: Hb 11.2, Leu 12,500, Plt 220k, Cr 0.9…"
            rows={4}
            className={fieldCls}
          />
        </div>

        {/* Studies */}
        <div className="mb-3">
          <div className="text-xs font-bold uppercase tracking-widest text-amber-500 mb-1.5">Estudios / procedimientos</div>
          <Textarea
            data-testid="input-studies"
            value={entry.studies}
            onChange={(e) => patchEntry({ studies: e.target.value })}
            placeholder="Pega o describe estudios de imagen, endoscopias, procedimientos…"
            rows={3}
            className={fieldCls}
          />
        </div>

        {/* Events */}
        <div className="mb-5">
          <div className="text-xs font-bold uppercase tracking-widest text-amber-500 mb-1.5">Eventos del día</div>
          <Textarea
            data-testid="input-events"
            value={entry.events}
            onChange={(e) => patchEntry({ events: e.target.value })}
            placeholder="Fiebre, sangrado, cambios en el manejo, complicaciones…"
            rows={3}
            className={fieldCls}
          />
        </div>

        <button
          data-testid="btn-generate-pase"
          onClick={doGeneratePase}
          disabled={generatingPase}
          className="w-full h-14 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-base flex items-center justify-center gap-2 transition-colors active:scale-[0.98] disabled:opacity-60"
        >
          {generatingPase ? "Generando resumen…" : <><Sparkles className="w-5 h-5" /> Guardar al Pase</>}
        </button>

        {pase && (
          <div className="mt-4 bg-slate-800 border border-slate-700 rounded-xl p-5" data-testid="pase-summary">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-bold uppercase tracking-widest text-amber-500">Resumen del pase</div>
              <button
                data-testid="btn-copy-pase"
                onClick={() => copyText(pase)}
                className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full border border-slate-700 text-slate-300 hover:border-amber-500 hover:text-amber-500 text-xs transition-colors"
              >
                <Copy className="w-3.5 h-3.5" /> Copiar
              </button>
            </div>
            <div className="text-slate-100 text-sm leading-relaxed pre-wrap font-mono">{pase}</div>
          </div>
        )}
      </div>

      {/* Timeline */}
      {entries.length > 0 && (
        <div className="mt-8">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-amber-500" />
            <h3 className="font-heading font-bold text-base text-slate-50">Línea de tiempo</h3>
          </div>
          <div className="space-y-2">
            {entries.map((e) => (
              <div key={e.id} className="bg-slate-800/60 border border-slate-800 rounded-lg p-3" data-testid={`timeline-entry-${e.date}`}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="text-xs font-bold text-amber-500">{e.date}</div>
                  {e.saved_to_pase && <span className="text-[10px] uppercase tracking-widest text-emerald-400">En pase</span>}
                </div>
                {(e.dictation || e.events || e.labs) && (
                  <div className="text-slate-300 text-xs leading-snug line-clamp-3 pre-wrap">
                    {e.dictation || e.events || e.labs}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <PatientFormDialog
        open={editing}
        onOpenChange={setEditing}
        patient={patient}
        onSaved={() => { setEditing(false); load(); }}
      />
    </div>
  );
}
