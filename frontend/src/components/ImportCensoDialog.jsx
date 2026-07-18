import { useRef, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Upload, FileText, CheckCircle2, AlertTriangle, UserPlus, RefreshCw, LogOut, Loader2, Eye } from "lucide-react";
import { api } from "@/lib/api";

export default function ImportCensoDialog({ open, onOpenChange, onFinished }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [step, setStep] = useState("choose"); // choose | previewing | preview | confirming | done
  const [preview, setPreview] = useState(null);
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
    setPreview(null);
    setResult(null);
    setStep("choose");
  };

  const pollJob = (jobId, isConfirm) =>
    new Promise((resolve, reject) => {
      let attempts = 0;
      const max = 80;
      const tick = async () => {
        attempts += 1;
        try {
          const st = await api.importCensoStatus(jobId);
          if (st.status === "done") return resolve(st.result);
          if (st.status === "failed") return reject(new Error(st.error || "Error"));
          if (attempts >= max) return reject(new Error("Tiempo excedido"));
          setTimeout(tick, 3000);
        } catch (e) {
          reject(e);
        }
      };
      setTimeout(tick, 2500);
    });

  const runPreview = async () => {
    if (!file) return;
    setStep("previewing");
    try {
      const { job_id } = await api.importCenso(file, false);
      const res = await pollJob(job_id, false);
      setPreview(res);
      setStep("preview");
    } catch (e) {
      toast.error(e?.message || e?.response?.data?.detail || "Error al analizar el censo");
      setStep("choose");
    }
  };

  const runConfirm = async () => {
    if (!file) return;
    setStep("confirming");
    try {
      const { job_id } = await api.importCenso(file, true);
      const res = await pollJob(job_id, true);
      setResult(res);
      setStep("done");
      onFinished?.();
      toast.success("Censo actualizado");
    } catch (e) {
      toast.error(e?.message || e?.response?.data?.detail || "Error al importar");
      setStep("preview");
    }
  };

  const close = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setStep("choose");
    onOpenChange(false);
  };

  const Section = ({ icon: Icon, color, title, items }) => (
    <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
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
            <li key={i} className="text-slate-800 text-sm">{it.name || it}</li>
          ))}
        </ul>
      )}
    </div>
  );

  const showing = result || preview;

  return (
    <Dialog open={open} onOpenChange={(v) => (!v ? close() : onOpenChange(true))}>
      <DialogContent
        className="bg-white border-slate-200 text-slate-900 max-w-lg max-h-[92vh] overflow-y-auto"
        data-testid="dialog-import-censo"
      >
        <DialogHeader>
          <DialogTitle className="font-heading text-xl flex items-center gap-2 text-slate-900">
            <Upload className="w-5 h-5 text-blue-600" /> Actualizar censo del día
          </DialogTitle>
        </DialogHeader>

        {step === "choose" && (
          <div className="mt-2 space-y-4">
            <p className="text-slate-600 text-sm leading-relaxed">
              Sube el archivo <span className="text-blue-600 font-semibold">.docx</span> descargado desde Google Docs.
              Primero verás una <span className="font-semibold">vista previa</span> con los cambios propuestos y decides si aplicarlos.
              El historial de pases, notas y evolución NUNCA se borra.
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
              data-testid="btn-pick-file"
              className="w-full h-24 border-2 border-dashed border-slate-300 hover:border-blue-500 rounded-xl flex flex-col items-center justify-center gap-2 text-slate-600 hover:text-blue-600 transition-colors bg-slate-50"
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
                className="flex-1 h-12 bg-white border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Cancelar
              </Button>
              <Button
                data-testid="btn-preview-import"
                onClick={runPreview}
                disabled={!file}
                className="flex-1 h-12 bg-blue-600 hover:bg-blue-700 text-white font-bold"
              >
                <Eye className="w-4 h-4 mr-2" /> Ver vista previa
              </Button>
            </div>
          </div>
        )}

        {(step === "previewing" || step === "confirming") && (
          <div className="mt-2 py-10 flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
            <p className="text-slate-700 text-sm font-semibold">
              {step === "previewing" ? "Analizando el censo con IA…" : "Aplicando cambios…"}
            </p>
            <p className="text-slate-500 text-xs text-center max-w-xs">
              Puede tardar 20-60 segundos según el número de pacientes.
            </p>
          </div>
        )}

        {step === "preview" && showing && (
          <div className="mt-2 space-y-3" data-testid="preview-result">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
              <div className="text-sm text-blue-900 font-semibold mb-1">Vista previa · {showing.parsed_count} pacientes en el censo</div>
              <div className="text-xs text-blue-700">Aún no se han aplicado cambios. Revisa lo siguiente:</div>
            </div>
            <Section icon={UserPlus} color="text-emerald-600" title="Se crearán como nuevos" items={showing.new || []} />
            <Section icon={RefreshCw} color="text-blue-600" title="Se actualizarán" items={showing.updated || []} />
            <Section icon={LogOut} color="text-orange-600" title="Pasarán a Egresados" items={showing.discharged || []} />
            {showing.errors?.length > 0 && (
              <Section icon={AlertTriangle} color="text-red-600" title="Errores" items={showing.errors} />
            )}
            <div className="pt-2 text-slate-600 text-sm font-semibold">
              ¿Desea importar este censo?
            </div>
            <div className="flex gap-3">
              <Button
                variant="outline"
                data-testid="btn-cancel-preview"
                onClick={close}
                className="flex-1 h-12 bg-white border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Cancelar
              </Button>
              <Button
                data-testid="btn-confirm-import"
                onClick={runConfirm}
                className="flex-1 h-12 bg-blue-600 hover:bg-blue-700 text-white font-bold"
              >
                <CheckCircle2 className="w-4 h-4 mr-2" /> Confirmar
              </Button>
            </div>
          </div>
        )}

        {step === "done" && result && (
          <div className="mt-2 space-y-3" data-testid="import-result">
            <div className="text-slate-700 text-sm">
              Se procesaron <span className="text-blue-600 font-bold">{result.parsed_count}</span> pacientes del censo.
            </div>
            <Section icon={UserPlus} color="text-emerald-600" title="Nuevos ingresos" items={result.new || []} />
            <Section icon={RefreshCw} color="text-blue-600" title="Actualizados" items={result.updated || []} />
            <Section icon={LogOut} color="text-orange-600" title="Movidos a egresados" items={result.discharged || []} />
            {result.errors?.length > 0 && (
              <Section icon={AlertTriangle} color="text-red-600" title="Errores" items={result.errors} />
            )}
            <div className="pt-2 flex items-center gap-2 text-emerald-600 text-sm">
              <CheckCircle2 className="w-4 h-4" /> Historial preservado. Orden del censo actualizado.
            </div>
            <Button
              onClick={close}
              data-testid="btn-close-import"
              className="w-full h-12 bg-blue-600 hover:bg-blue-700 text-white font-bold mt-2"
            >
              Listo
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
