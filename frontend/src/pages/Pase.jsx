import { useState } from "react";
import { toast } from "sonner";
import { ClipboardList, Copy, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";

export default function Pase() {
  const [pase, setPase] = useState("");
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    try {
      const { pase, patient_count } = await api.fullPase();
      setPase(pase);
      setCount(patient_count);
    } catch {
      toast.error("Error al generar pase");
    } finally { setLoading(false); }
  };

  const copy = () => {
    navigator.clipboard?.writeText(pase);
    toast.success("Pase copiado");
  };

  return (
    <div className="py-4">
      <div className="mb-6">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600 mb-1">Documento único</div>
        <h1 className="font-heading font-extrabold text-3xl text-slate-900">Pase de visita</h1>
        <p className="text-slate-500 text-sm mt-1">
          Compila todos los pacientes con resumen guardado hoy en un solo documento listo para leer.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <button
          data-testid="btn-generate-full-pase"
          onClick={generate}
          disabled={loading}
          className="flex-1 h-14 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold flex items-center justify-center gap-2 active:scale-[0.98] transition-colors disabled:opacity-60"
        >
          {loading ? <><RefreshCw className="w-4 h-4 animate-spin" /> Compilando…</> : <><ClipboardList className="w-5 h-5" /> Generar pase completo</>}
        </button>
        {pase && (
          <button
            data-testid="btn-copy-full-pase"
            onClick={copy}
            className="h-14 px-6 rounded-xl border border-slate-200 bg-white text-slate-700 hover:border-blue-500 hover:text-blue-600 font-semibold flex items-center justify-center gap-2 transition-colors"
          >
            <Copy className="w-4 h-4" /> Copiar
          </button>
        )}
      </div>

      {pase && (
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm" data-testid="full-pase-doc">
          <div className="flex items-center justify-between mb-3">
            <div className="text-xs font-bold uppercase tracking-widest text-blue-600">
              {count} paciente{count !== 1 ? "s" : ""}
            </div>
          </div>
          <pre className="text-slate-800 text-sm leading-relaxed pre-wrap font-mono">{pase}</pre>
        </div>
      )}

      {!pase && !loading && (
        <div className="border border-dashed border-slate-300 rounded-xl p-10 text-center bg-white">
          <ClipboardList className="w-8 h-8 text-slate-400 mx-auto mb-3" />
          <p className="text-slate-500 text-sm">
            Genera el resumen del pase de cada paciente desde su ficha, luego regresa aquí y presiona "Generar pase completo".
          </p>
        </div>
      )}
    </div>
  );
}
