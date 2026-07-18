import { Lock, LogIn } from "lucide-react";

export default function Ingresos() {
  return (
    <div className="py-4">
      <div className="mb-6">
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-amber-500 mb-1">Próximamente</div>
        <h1 className="font-heading font-extrabold text-3xl text-slate-50">Ingresos</h1>
        <p className="text-slate-400 text-sm mt-1">Notas de ingreso hospitalario con la información ya almacenada del paciente.</p>
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-xl p-10 text-center" data-testid="ingresos-placeholder">
        <div className="w-16 h-16 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center mx-auto mb-4">
          <Lock className="w-6 h-6 text-amber-500" />
        </div>
        <h2 className="font-heading font-bold text-lg text-slate-50 mb-2">Módulo en desarrollo</h2>
        <p className="text-slate-400 text-sm max-w-sm mx-auto leading-relaxed">
          En la próxima versión podrás generar notas de ingreso completas usando automáticamente los antecedentes, diagnóstico y datos del paciente.
        </p>
        <div className="mt-5 inline-flex items-center gap-2 text-xs text-slate-500">
          <LogIn className="w-3.5 h-3.5" />
          Próximamente
        </div>
      </div>
    </div>
  );
}
