import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileText, Copy, MessageCircle, Sparkles } from "lucide-react";
import { api } from "@/lib/api";

export default function Notas() {
  const [patients, setPatients] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState("");
  const [wa, setWa] = useState("");

  useEffect(() => {
    api.listPatients().then((ps) => {
      setPatients(ps);
      if (ps[0]) setSelected(ps[0].id);
    }).catch(() => toast.error("Error"));
  }, []);

  const generate = async () => {
    if (!selected) return;
    setLoading(true);
    setNote(""); setWa("");
    try {
      const { note, whatsapp } = await api.generateNote(selected);
      setNote(note); setWa(whatsapp);
      toast.success("Nota generada");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al generar nota");
    } finally { setLoading(false); }
  };

  const copy = (t, label) => {
    navigator.clipboard?.writeText(t);
    toast.success(`${label} copiado`);
  };

  return (
    <div className="py-4">
      <div className="mb-6">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600 mb-1">Redacción con IA</div>
        <h1 className="font-heading font-extrabold text-3xl text-slate-900">Notas</h1>
        <p className="text-slate-500 text-sm mt-1">Genera nota de evolución y mensaje de WhatsApp para el médico tratante.</p>
      </div>

      {patients.length === 0 ? (
        <div className="border border-dashed border-slate-300 rounded-xl p-10 text-center bg-white">
          <p className="text-slate-500 text-sm">No hay pacientes activos. Agrega uno primero.</p>
        </div>
      ) : (
        <>
          <div className="mb-5">
            <div className="text-xs font-bold uppercase tracking-widest text-blue-600 mb-2">Paciente</div>
            <div className="grid gap-2" data-testid="notas-patient-list">
              {patients.map((p) => (
                <button
                  key={p.id}
                  data-testid={`notas-select-${p.id}`}
                  onClick={() => setSelected(p.id)}
                  className={[
                    "text-left rounded-xl border p-3 transition-colors",
                    selected === p.id
                      ? "bg-blue-50 border-blue-500 text-slate-900"
                      : "bg-white border-slate-200 text-slate-700 hover:border-slate-400",
                  ].join(" ")}
                >
                  <div className="font-heading font-bold text-sm">{p.name}</div>
                  <div className="text-xs text-slate-500 mt-0.5">
                    Cama {p.bed || "ND"} · Tratante {p.attending_physician || "ND"} · DPQX {p.days_postop ?? "ND"}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <button
            data-testid="btn-generate-note"
            onClick={generate}
            disabled={loading || !selected}
            className="w-full h-14 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold flex items-center justify-center gap-2 active:scale-[0.98] transition-colors disabled:opacity-60 mb-5"
          >
            {loading ? "Generando…" : <><Sparkles className="w-5 h-5" /> Generar Nota</>}
          </button>

          {note && (
            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-4 shadow-sm" data-testid="output-note">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-blue-600" />
                  <div className="text-xs font-bold uppercase tracking-widest text-blue-600">Nota de evolución</div>
                </div>
                <button data-testid="btn-copy-note" onClick={() => copy(note, "Nota")}
                  className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full border border-slate-200 bg-white text-slate-600 hover:border-blue-500 hover:text-blue-600 text-xs transition-colors">
                  <Copy className="w-3.5 h-3.5" /> Copiar
                </button>
              </div>
              <pre className="text-slate-800 text-sm leading-relaxed pre-wrap font-mono">{note}</pre>
            </div>
          )}

          {wa && (
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm" data-testid="output-whatsapp">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <MessageCircle className="w-4 h-4 text-emerald-600" />
                  <div className="text-xs font-bold uppercase tracking-widest text-emerald-600">Mensaje WhatsApp</div>
                </div>
                <button data-testid="btn-copy-whatsapp" onClick={() => copy(wa, "Mensaje")}
                  className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full border border-slate-200 bg-white text-slate-600 hover:border-emerald-500 hover:text-emerald-600 text-xs transition-colors">
                  <Copy className="w-3.5 h-3.5" /> Copiar
                </button>
              </div>
              <pre className="text-slate-800 text-sm leading-relaxed pre-wrap">{wa}</pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}
