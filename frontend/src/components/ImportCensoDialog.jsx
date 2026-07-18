import { useRef, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Upload, FileText, CheckCircle2, AlertTriangle, UserPlus, RefreshCw, LogOut, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

export default function ImportCensoDialog({ open, onOpenChange, onFinished }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const pick = () => inputRef.current?.click();

  const onFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".docx")) {
      toast.error("El archivo debe ser un .docx");
      return;
    }
    setFile(f);
    setResult(null);
  };

  const runImport = async () => {
    if (!file) return;
    setLoading(true);
    setResult(null);
    try {
      const { job_id } = await api.importCenso(file);
      // Poll status every 3s until done or failed (max ~4 min)
      let attempts = 0;
      const maxAttempts = 80;
      const poll = async () => {
        attempts += 1;
        try {
          const st = await api.importCensoStatus(job_id);
          if (st.status === "done") {
            setResult(st.result);
            toast.success("Censo actualizado");
            onFinished?.();
            setLoading(false);
            return;
          }
          if (st.status === "failed") {
            toast.error(st.error || "Error al procesar el censo");
            setLoading(false);
            return;
          }
          if (attempts >= maxAttempts) {
            toast.error("El procesamiento tardó demasiado. Intenta con un censo más pequeño.");
            setLoading(false);
            return;
          }
          setTimeout(poll, 3000);
        } catch (e) {
          toast.error(e?.response?.data?.detail || "Error consultando estado");
          setLoading(false);
        }
      };
      setTimeout(poll, 2500);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Error al importar el censo");
      setLoading(false);
    }
  };

  const close = () => {
    setFile(null);
    setResult(null);
    setLoading(false);
    onOpenChange(false);
  };

  const Section = ({ icon: Icon, color, title, items }) => (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-3">
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${color}`} />
        <div className={`text-xs font-bold uppercase tracking-widest ${color}`}>
          {title} ({items.length})
        </div>
      </div>
      {items.length === 0 ? (
        <div className="text-slate-500 text-xs">Ninguno</div>
      ) : (
        <ul className="space-y-1">
          {items.map((it, i) => (
            <li key={i} className="text-slate-200 text-sm">{it.name || it}</li>
          ))}
        </ul>
      )}
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent
        className="bg-slate-900 border-slate-700 text-slate-50 max-w-lg max-h-[92vh] overflow-y-auto"
        data-testid="dialog-import-censo"
      >
        <DialogHeader>
          <DialogTitle className="font-heading text-xl flex items-center gap-2">
            <Upload className="w-5 h-5 text-amber-500" /> Actualizar censo del día
          </DialogTitle>
        </DialogHeader>

        {!result && (
          <div className="mt-2 space-y-4">
            <p className="text-slate-400 text-sm leading-relaxed">
              Sube el archivo <span className="text-amber-500 font-semibold">.docx</span> descargado desde Google Docs.
              La IA identificará automáticamente a los pacientes, actualizará los existentes y creará los nuevos.
              Los pacientes ausentes se moverán a <span className="text-amber-500 font-semibold">Egresados</span> sin borrar su historial.
            </p>

            <input
              ref={inputRef}
              type="file"
              accept=".docx"
              className="hidden"
              onChange={onFile}
              data-testid="input-file-censo"
            />

            <button
              onClick={pick}
              disabled={loading}
              data-testid="btn-pick-file"
              className="w-full h-24 border-2 border-dashed border-slate-700 hover:border-amber-500 rounded-xl flex flex-col items-center justify-center gap-2 text-slate-300 hover:text-amber-500 transition-colors"
            >
              <FileText className="w-6 h-6" />
              <span className="text-sm font-semibold">
                {file ? file.name : "Elegir archivo .docx"}
              </span>
            </button>

            <div className="flex gap-3">
              <Button
                variant="outline"
                data-testid="btn-cancel-import"
                onClick={close}
                disabled={loading}
                className="flex-1 h-12 bg-transparent border-slate-700 text-slate-300 hover:bg-slate-800"
              >
                Cancelar
              </Button>
              <Button
                data-testid="btn-run-import"
                onClick={runImport}
                disabled={!file || loading}
                className="flex-1 h-12 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold"
              >
                {loading ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Procesando…</>
                ) : (
                  <><Upload className="w-4 h-4 mr-2" /> Importar</>
                )}
              </Button>
            </div>

            {loading && (
              <p className="text-center text-xs text-slate-500 mt-2">
                Analizando el censo con IA. Puede tardar 20-60 segundos según el número de pacientes.
              </p>
            )}
          </div>
        )}

        {result && (
          <div className="mt-2 space-y-3" data-testid="import-result">
            <div className="text-slate-300 text-sm">
              Se procesaron <span className="text-amber-500 font-bold">{result.parsed_count}</span> pacientes del censo.
            </div>
            <Section icon={UserPlus} color="text-emerald-400" title="Nuevos ingresos" items={result.new || []} />
            <Section icon={RefreshCw} color="text-amber-500" title="Actualizados" items={result.updated || []} />
            <Section icon={LogOut} color="text-slate-400" title="Movidos a egresados" items={result.discharged || []} />
            {result.errors?.length > 0 && (
              <Section icon={AlertTriangle} color="text-red-400" title="Errores" items={result.errors} />
            )}
            <div className="pt-2 flex items-center gap-2 text-emerald-400 text-sm">
              <CheckCircle2 className="w-4 h-4" /> Historial de pases, notas y evolución conservado.
            </div>
            <Button
              onClick={close}
              data-testid="btn-close-import"
              className="w-full h-12 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold mt-2"
            >
              Listo
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
