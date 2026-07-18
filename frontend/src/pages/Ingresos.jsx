import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileText, Copy, Sparkles, LogIn } from "lucide-react";
import { api } from "@/lib/api";

export default function Ingresos() {
  const [patients, setPatients] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => {
    api.listPatients().then((ps) => {
      setPatients(ps);
      if (ps[0]) setSelected(ps[0].id);
    }).catch(() => toast.error("Error al cargar pacientes"));
  }, []);

  const generate = async () => {
    if (!selected) return;
    setLoading(true);
    setNote("");
    try {
      const { note } = await api.generateAdmission(selected);
      setNote(note);
      toast.success("Nota de ingreso generada");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al generar nota de ingreso");
    } finally {
      setLoading(false);
    }
  };

  const copy = () => {
    navigator.clipboard?.writeText(note);
    toast.success("Nota copiada");
  };

  return (
    <div className="py-4">
      <div className="mb-6">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-amber-500 mb-1">Nota de ingreso</div>
        <h1 className="font-heading font-extrabold text-3xl text-slate-50">Ingresos</h1>
        <p className="text-slate-400 text-sm mt-1">
          Genera una nota de ingreso hospitalario utilizando la información fija ya almacenada del paciente.
        </p>
      </div>

      {patients.length === 0 ? (
        <div className="border border-dashed border-slate-700 rounded-xl p-10 text-center">
          <LogIn className="w-8 h-8 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">No hay pacientes activos. Agrega uno o importa el censo primero.</p>
        </div>
      ) : (
        <>
          <div className="mb-5">
            <div className="text-xs font-bold uppercase tracking-widest text-amber-500 mb-2">Paciente</div>
            <div className="grid gap-2" data-testid="ingresos-patient-list">
              {patients.map((p) => (
                <button
                  key={p.id}
                  data-testid={`ingresos-select-${p.id}`}
                  onClick={() => setSelected(p.id)}
                  className={[
                    "text-left rounded-xl border p-3 transition-colors",
                    selected === p.id
                      ? "bg-amber-500/10 border-amber-500 text-slate-50"
                      : "bg-slate-800 border-slate-700 text-slate-200 hover:border-slate-500",
                  ].join(" ")}
                >
                  <div className="font-heading font-bold text-sm">{p.name}</div>
                  <div className="text-xs text-slate-400 mt-0.5 line-clamp-1">
                    {p.dx_short || "Sin dx registrado"} · Cama {p.bed || "ND"}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <button
            data-testid="btn-generate-admission"
            onClick={generate}
            disabled={loading || !selected}
            className="w-full h-14 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold flex items-center justify-center gap-2 active:scale-[0.98] transition-colors disabled:opacity-60 mb-5"
          >
            {loading ? "Generando…" : <><Sparkles className="w-5 h-5" /> Generar nota de ingreso</>}
          </button>

          {note && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-5" data-testid="output-admission">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-amber-500" />
                  <div className="text-xs font-bold uppercase tracking-widest text-amber-500">Nota de ingreso</div>
                </div>
                <button
                  data-testid="btn-copy-admission"
                  onClick={copy}
                  className="inline-flex items-center gap-1.5 h-9 px-3 rounded-full border border-slate-700 text-slate-300 hover:border-amber-500 hover:text-amber-500 text-xs transition-colors"
                >
                  <Copy className="w-3.5 h-3.5" /> Copiar
                </button>
              </div>
              <pre className="text-slate-100 text-sm leading-relaxed pre-wrap font-mono">{note}</pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}
