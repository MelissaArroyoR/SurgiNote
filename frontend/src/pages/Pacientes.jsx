import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, BedDouble, Building2, Calendar, Activity, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import PatientFormDialog from "@/components/PatientFormDialog";

export default function Pacientes() {
  const nav = useNavigate();
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.listPatients();
      setPatients(data);
    } catch {
      toast.error("Error al cargar pacientes");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="py-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-amber-500 mb-1">Censo</div>
          <h1 className="font-heading font-extrabold text-3xl text-slate-50">Pacientes</h1>
          <p className="text-slate-400 text-sm mt-1">{patients.length} paciente{patients.length !== 1 ? "s" : ""} activo{patients.length !== 1 ? "s" : ""}</p>
        </div>
        <button
          data-testid="btn-add-patient"
          onClick={() => setOpen(true)}
          className="w-14 h-14 rounded-full bg-amber-500 hover:bg-amber-600 text-slate-950 flex items-center justify-center transition-all active:scale-95 shadow-lg shadow-amber-500/20"
          aria-label="Agregar paciente"
        >
          <Plus className="w-6 h-6" strokeWidth={2.8} />
        </button>
      </div>

      {loading ? (
        <div className="text-slate-500 text-center py-16 text-sm">Cargando…</div>
      ) : patients.length === 0 ? (
        <div className="border border-dashed border-slate-700 rounded-xl p-10 text-center">
          <p className="text-slate-400 mb-4">Aún no hay pacientes registrados.</p>
          <button
            data-testid="btn-add-first"
            onClick={() => setOpen(true)}
            className="inline-flex items-center gap-2 h-12 px-6 rounded-full bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold"
          >
            <Plus className="w-4 h-4" strokeWidth={3} /> Agregar primer paciente
          </button>
        </div>
      ) : (
        <div className="space-y-3" data-testid="patient-list">
          {patients.map((p) => (
            <button
              key={p.id}
              data-testid={`patient-card-${p.id}`}
              onClick={() => nav(`/pacientes/${p.id}`)}
              className="w-full text-left bg-slate-800 hover:bg-slate-800/70 border border-slate-700 hover:border-amber-500/60 rounded-xl p-4 transition-colors active:scale-[0.99]"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-heading font-bold text-slate-50 text-lg truncate">{p.name}</h3>
                    {p.age && <span className="text-slate-400 text-sm">· {p.age}{p.sex ? p.sex : ""}</span>}
                  </div>
                  {p.dx_short && (
                    <p className="text-slate-300 text-sm leading-snug mb-3 line-clamp-2">{p.dx_short}</p>
                  )}
                  <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs">
                    <span className="inline-flex items-center gap-1 text-slate-400">
                      <BedDouble className="w-3.5 h-3.5" /> Cama {p.bed || "ND"}
                    </span>
                    <span className="inline-flex items-center gap-1 text-slate-400">
                      <Building2 className="w-3.5 h-3.5" /> Piso {p.floor || "ND"}
                    </span>
                    {p.days_admission != null && (
                      <span className="inline-flex items-center gap-1 text-slate-400">
                        <Calendar className="w-3.5 h-3.5" /> DEA {p.days_admission}
                      </span>
                    )}
                    {p.days_postop != null && (
                      <span className="inline-flex items-center gap-1 text-amber-500 font-semibold">
                        <Activity className="w-3.5 h-3.5" /> DPQ {p.days_postop}
                      </span>
                    )}
                  </div>
                </div>
                <ChevronRight className="w-5 h-5 text-slate-500 flex-shrink-0 mt-1" />
              </div>
            </button>
          ))}
        </div>
      )}

      <PatientFormDialog
        open={open}
        onOpenChange={setOpen}
        onSaved={() => { setOpen(false); load(); }}
      />
    </div>
  );
}
