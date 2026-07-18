import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  FileText, Copy, Sparkles, LogIn, ClipboardList, MessageSquarePlus,
  X, Loader2, Save,
} from "lucide-react";
import { api } from "@/lib/api";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

function copyText(t, label = "Nota") {
  navigator.clipboard?.writeText(t);
  toast.success(`${label} copiada`);
}

export default function Ingresos() {
  const [patients, setPatients] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [patient, setPatient] = useState(null);
  const [notes, setNotes] = useState([]);
  const [aiNote, setAiNote] = useState("");
  const [loadingAi, setLoadingAi] = useState(false);

  // "Nota de ingreso" state
  const [admText, setAdmText] = useState("");
  const [savingAdm, setSavingAdm] = useState(false);

  // "Notas adicionales" state
  const [newSource, setNewSource] = useState("");
  const [newText, setNewText] = useState("");
  const [savingAdd, setSavingAdd] = useState(false);

  useEffect(() => {
    api.listPatients().then((ps) => {
      setPatients(ps);
      if (ps[0]) setSelectedId(ps[0].id);
    }).catch(() => toast.error("Error"));
  }, []);

  useEffect(() => {
    if (!selectedId) { setPatient(null); return; }
    Promise.all([
      api.getPatient(selectedId),
      api.listAdditionalNotes(selectedId).catch(() => []),
    ]).then(([p, ns]) => {
      setPatient(p);
      setNotes(ns);
      setAdmText(p.admission_note_text || "");
      setAiNote("");
    }).catch(() => toast.error("Error al cargar"));
  }, [selectedId]);

  const generateAi = async () => {
    if (!selectedId) return;
    setLoadingAi(true);
    setAiNote("");
    try {
      const { note } = await api.generateAdmission(selectedId);
      setAiNote(note);
      toast.success("Nota IA generada");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al generar");
    } finally { setLoadingAi(false); }
  };

  const saveAdmission = async () => {
    if (admText.trim().length < 20) { toast.error("La nota es demasiado corta"); return; }
    setSavingAdm(true);
    try {
      const res = await api.pasteAdmissionNote(selectedId, admText);
      const n = (res.merged_fields || []).length;
      toast.success(n > 0 ? `Nota guardada. ${n} campo${n > 1 ? "s" : ""} extraído${n > 1 ? "s" : ""}.` : "Nota guardada.");
      if (res.warning) toast.error(res.warning);
      // refresh patient
      const p = await api.getPatient(selectedId);
      setPatient(p);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al guardar");
    } finally { setSavingAdm(false); }
  };

  const addAdditional = async () => {
    if (!newSource.trim()) { toast.error("Indica el servicio"); return; }
    if (newText.trim().length < 20) { toast.error("La nota es demasiado corta"); return; }
    setSavingAdd(true);
    try {
      const res = await api.addAdditionalNote(selectedId, newSource.trim(), newText);
      setNotes((ns) => [res.note, ...ns]);
      setNewSource(""); setNewText("");
      toast.success("Nota agregada y resumida");
      if (res.warning) toast.error(res.warning);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al guardar");
    } finally { setSavingAdd(false); }
  };

  const deleteNote = async (noteId) => {
    if (!window.confirm("¿Eliminar esta nota?")) return;
    try {
      await api.deleteAdditionalNote(selectedId, noteId);
      setNotes((ns) => ns.filter((x) => x.id !== noteId));
      toast.success("Nota eliminada");
    } catch { toast.error("Error"); }
  };

  const fieldCls = "bg-white border-slate-300 text-slate-900 focus-visible:ring-blue-500 focus-visible:border-blue-500";

  return (
    <div className="py-4">
      <div className="mb-6">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600 mb-1">Módulo de ingresos</div>
        <h1 className="font-heading font-extrabold text-3xl text-slate-900">Ingresos</h1>
        <p className="text-slate-500 text-sm mt-1">Nota de ingreso · Notas adicionales · Generar nota con IA.</p>
      </div>

      {patients.length === 0 ? (
        <div className="border border-dashed border-slate-300 rounded-xl p-10 text-center bg-white">
          <LogIn className="w-8 h-8 text-slate-400 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">No hay pacientes activos. Agrega uno o importa el censo primero.</p>
        </div>
      ) : (
        <>
          {/* Patient selector */}
          <div className="mb-5">
            <div className="text-xs font-bold uppercase tracking-widest text-blue-600 mb-2">Paciente</div>
            <div className="grid gap-2" data-testid="ingresos-patient-list">
              {patients.map((p) => (
                <button
                  key={p.id}
                  data-testid={`ingresos-select-${p.id}`}
                  onClick={() => setSelectedId(p.id)}
                  className={[
                    "text-left rounded-xl border p-3 transition-colors",
                    selectedId === p.id
                      ? "bg-blue-50 border-blue-500 text-slate-900"
                      : "bg-white border-slate-200 text-slate-700 hover:border-slate-400",
                  ].join(" ")}
                >
                  <div className="font-heading font-bold text-sm">{p.name}</div>
                  <div className="text-xs text-slate-500 mt-0.5 line-clamp-1">
                    {p.dx_short || "Sin dx registrado"} · Cama {p.bed || "ND"}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* SECTION 1: Nota de ingreso (pegar desde MedSys) */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 mb-5 shadow-sm" data-testid="section-admission-note">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="w-4 h-4 text-blue-600" />
              <h2 className="font-heading font-bold text-base text-slate-900">Nota de ingreso</h2>
            </div>
            <p className="text-slate-500 text-xs mb-3">
              Pega la nota completa desde MedSys. La IA extraerá motivo, padecimiento, dx, antecedentes, alergias, medicamentos, procedimiento, hallazgos y estado oncológico. No borra información previa.
            </p>
            <Textarea
              data-testid="input-admission-note"
              value={admText}
              onChange={(e) => setAdmText(e.target.value)}
              rows={10}
              placeholder="Pega aquí la nota de ingreso completa…"
              className={`${fieldCls} font-mono text-sm`}
            />
            <Button
              data-testid="btn-save-admission-note"
              onClick={saveAdmission}
              disabled={savingAdm || !selectedId}
              className="w-full h-12 mt-3 bg-blue-600 hover:bg-blue-700 text-white font-bold"
            >
              {savingAdm ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Analizando…</> : <><Save className="w-4 h-4 mr-2" />Guardar y analizar</>}
            </Button>
          </div>

          {/* SECTION 2: Notas adicionales */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 mb-5 shadow-sm" data-testid="section-additional-notes">
            <div className="flex items-center gap-2 mb-3">
              <ClipboardList className="w-4 h-4 text-blue-600" />
              <h2 className="font-heading font-bold text-base text-slate-900">Notas adicionales</h2>
            </div>
            <p className="text-slate-500 text-xs mb-3">
              Notas de Medicina Interna, UTI, Oncología, Nutrición, Infectología, Radiología. La IA generará un resumen ejecutivo. No modifica la información fija del paciente.
            </p>
            <Input
              data-testid="input-note-source"
              value={newSource}
              onChange={(e) => setNewSource(e.target.value)}
              placeholder="Servicio (ej. Medicina Interna, UTI, Oncología…)"
              className={fieldCls}
            />
            <Textarea
              data-testid="input-additional-note"
              value={newText}
              onChange={(e) => setNewText(e.target.value)}
              rows={6}
              placeholder="Pega aquí la nota del otro servicio…"
              className={`${fieldCls} mt-2 font-mono text-sm`}
            />
            <Button
              data-testid="btn-save-additional-note"
              onClick={addAdditional}
              disabled={savingAdd || !selectedId}
              className="w-full h-12 mt-3 bg-blue-600 hover:bg-blue-700 text-white font-bold"
            >
              {savingAdd ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Resumiendo…</> : <><MessageSquarePlus className="w-4 h-4 mr-2" />Agregar y resumir</>}
            </Button>

            {notes.length > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-200 space-y-2">
                {notes.map((n) => (
                  <div key={n.id} className="bg-slate-50 border border-slate-200 rounded-lg p-3" data-testid={`additional-note-${n.id}`}>
                    <div className="flex items-center justify-between mb-2">
                      <div>
                        <div className="text-xs font-bold text-blue-600 uppercase tracking-widest">{n.source}</div>
                        <div className="text-[10px] text-slate-500">{n.created_at?.split("T")[0]}</div>
                      </div>
                      <div className="flex gap-1">
                        <button onClick={() => copyText(n.ai_summary || n.text, "Resumen")}
                          className="w-8 h-8 rounded-full border border-slate-200 bg-white flex items-center justify-center text-slate-500 hover:text-blue-600 hover:border-blue-500">
                          <Copy className="w-3 h-3" />
                        </button>
                        <button onClick={() => deleteNote(n.id)}
                          className="w-8 h-8 rounded-full border border-slate-200 bg-white flex items-center justify-center text-slate-500 hover:text-red-600 hover:border-red-500">
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                    {n.ai_summary && (
                      <div className="text-slate-800 text-sm leading-relaxed pre-wrap font-mono">{n.ai_summary}</div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* SECTION 3: Generar nota IA */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm" data-testid="section-generate-admission">
            <div className="flex items-center gap-2 mb-3">
              <Sparkles className="w-4 h-4 text-blue-600" />
              <h2 className="font-heading font-bold text-base text-slate-900">Generar nota de ingreso con IA</h2>
            </div>
            <p className="text-slate-500 text-xs mb-3">
              Utiliza la información fija almacenada del paciente para redactar una nota de ingreso completa en formato MedSys.
            </p>
            <Button
              data-testid="btn-generate-admission"
              onClick={generateAi}
              disabled={loadingAi || !selectedId}
              className="w-full h-12 bg-blue-600 hover:bg-blue-700 text-white font-bold"
            >
              {loadingAi ? "Generando…" : <><Sparkles className="w-4 h-4 mr-2" />Generar</>}
            </Button>

            {aiNote && (
              <div className="mt-4 pt-4 border-t border-slate-200" data-testid="output-admission">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-xs font-bold uppercase tracking-widest text-blue-600">Nota generada</div>
                  <button data-testid="btn-copy-admission" onClick={() => copyText(aiNote, "Nota")}
                    className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full border border-slate-200 bg-white text-slate-600 hover:border-blue-500 hover:text-blue-600 text-xs transition-colors">
                    <Copy className="w-3.5 h-3.5" /> Copiar
                  </button>
                </div>
                <pre className="text-slate-800 text-sm leading-relaxed pre-wrap font-mono">{aiNote}</pre>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
