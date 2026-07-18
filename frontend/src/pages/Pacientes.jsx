import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, BedDouble, UserRound, Calendar, Activity, ChevronRight, Upload, LogOut, RotateCcw, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import PatientFormDialog from "@/components/PatientFormDialog";
import ImportCensoDialog from "@/components/ImportCensoDialog";

function getCardStyle(p) {
  // Priority: pending discharge > new admission > non-surgical > default
  if (p.is_pending_discharge) return "bg-orange-50 border-orange-200";
  if (p.is_new_admission) return "bg-sky-50 border-sky-200";
  if (p.is_surgical === false) return "bg-pink-50 border-pink-200";
  return "bg-white border-slate-200";
}

function getBadge(p) {
  if (p.is_pending_discharge) return { text: "Alta pendiente", cls: "bg-orange-100 text-orange-700 border-orange-200" };
  if (p.is_new_admission) return { text: "Nuevo ingreso", cls: "bg-sky-100 text-sky-700 border-sky-200" };
  if (p.is_surgical === false) return { text: "No quirúrgico", cls: "bg-pink-100 text-pink-700 border-pink-200" };
  return null;
}

export default function Pacientes() {
  const nav = useNavigate();
  const [patients, setPatients] = useState([]);
  const [discharged, setDischarged] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [tab, setTab] = useState("active");

  const load = async () => {
    setLoading(true);
    try {
      const [act, dis] = await Promise.all([api.listPatients(), api.listDischarged()]);
      setPatients(act);
      setDischarged(dis);
    } catch {
      toast.error("Error al cargar pacientes");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const readmit = async (id, e) => {
    e.stopPropagation();
    try {
      await api.readmitPatient(id);
      toast.success("Paciente reingresado");
      load();
    } catch {
      toast.error("Error");
    }
  };

  const list = tab === "active" ? patients : discharged;

  return (
    <div className="py-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-xs font-bold uppercase tracking-[0.2em] text-blue-600 mb-1">Censo</div>
          <h1 className="font-heading font-extrabold text-3xl text-slate-900">Pacientes</h1>
          <p className="text-slate-500 text-sm mt-1">
            {patients.length} activo{patients.length !== 1 ? "s" : ""} · {discharged.length} egresado{discharged.length !== 1 ? "s" : ""}
          </p>
        </div>
        <button
          data-testid="btn-add-patient"
          onClick={() => setOpen(true)}
          className="w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center transition-all active:scale-95 shadow-sm"
          aria-label="Agregar paciente"
        >
          <Plus className="w-6 h-6" strokeWidth={2.8} />
        </button>
      </div>

      <button
        data-testid="btn-open-import-censo"
        onClick={() => setImportOpen(true)}
        className="w-full h-14 rounded-xl border border-blue-200 bg-blue-50 hover:bg-blue-100 text-blue-700 font-heading font-bold text-sm flex items-center justify-center gap-2 transition-colors active:scale-[0.99] mb-5"
      >
        <Upload className="w-4 h-4" /> Actualizar censo del día
      </button>

      <div className="flex gap-2 mb-5" data-testid="patient-tabs">
        <button
          data-testid="tab-active-patients"
          onClick={() => setTab("active")}
          className={[
            "flex-1 h-11 rounded-full text-sm font-heading font-semibold transition-colors",
            tab === "active"
              ? "bg-blue-600 text-white"
              : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200",
          ].join(" ")}
        >
          Activos ({patients.length})
        </button>
        <button
          data-testid="tab-discharged-patients"
          onClick={() => setTab("discharged")}
          className={[
            "flex-1 h-11 rounded-full text-sm font-heading font-semibold transition-colors",
            tab === "discharged"
              ? "bg-slate-800 text-white"
              : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200",
          ].join(" ")}
        >
          Egresados ({discharged.length})
        </button>
      </div>

      {loading ? (
        <div className="text-slate-500 text-center py-16 text-sm">Cargando…</div>
      ) : list.length === 0 ? (
        <div className="border border-dashed border-slate-300 rounded-xl p-10 text-center bg-white">
          <p className="text-slate-500 mb-4">
            {tab === "active" ? "Aún no hay pacientes activos." : "Aún no hay pacientes egresados."}
          </p>
          {tab === "active" && (
            <button
              data-testid="btn-add-first"
              onClick={() => setOpen(true)}
              className="inline-flex items-center gap-2 h-12 px-6 rounded-full bg-blue-600 hover:bg-blue-700 text-white font-bold"
            >
              <Plus className="w-4 h-4" strokeWidth={3} /> Agregar primer paciente
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-3" data-testid="patient-list">
          {list.map((p) => {
            const badge = getBadge(p);
            return (
              <button
                key={p.id}
                data-testid={`patient-card-${p.id}`}
                onClick={() => nav(`/pacientes/${p.id}`)}
                className={`w-full text-left ${getCardStyle(p)} border rounded-xl p-4 transition-colors active:scale-[0.99] hover:shadow-sm`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h3 className="font-heading font-bold text-slate-900 text-lg truncate">{p.name}</h3>
                      {p.age && <span className="text-slate-500 text-sm">· {p.age}{p.sex ? p.sex : ""}</span>}
                    </div>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {badge && (
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-widest ${badge.cls}`}>
                          {badge.text}
                        </span>
                      )}
                      {p.unit_classification && p.unit_classification !== "Piso" && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-red-100 border border-red-200 text-red-700 text-[10px] font-bold uppercase tracking-widest">
                          {p.unit_classification}
                        </span>
                      )}
                    </div>
                    {p.dx_short && (
                      <p className="text-slate-700 text-sm leading-snug mb-3 line-clamp-2">{p.dx_short}</p>
                    )}
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                      <span className="inline-flex items-center gap-1 text-slate-600">
                        <BedDouble className="w-3.5 h-3.5" /> Cama {p.bed || "ND"}
                      </span>
                      <span className="inline-flex items-center gap-1 text-slate-600 truncate">
                        <UserRound className="w-3.5 h-3.5 flex-shrink-0" /> {p.attending_physician || "Tratante ND"}
                      </span>
                      {p.days_admission != null && (
                        <span className="inline-flex items-center gap-1 text-slate-600">
                          <Calendar className="w-3.5 h-3.5" /> DEIH {p.days_admission}
                        </span>
                      )}
                      {p.days_postop != null && (
                        <span className="inline-flex items-center gap-1 text-blue-700 font-semibold">
                          <Activity className="w-3.5 h-3.5" /> DPQX {p.days_postop}
                        </span>
                      )}
                      {tab === "discharged" && p.discharged_at && (
                        <span className="col-span-2 inline-flex items-center gap-1 text-slate-500 mt-1">
                          <LogOut className="w-3.5 h-3.5" /> Egresó {p.discharged_at}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col items-center gap-2">
                    {tab === "discharged" && (
                      <button
                        data-testid={`btn-readmit-${p.id}`}
                        onClick={(e) => readmit(p.id, e)}
                        className="w-9 h-9 rounded-full border border-slate-200 bg-white flex items-center justify-center text-slate-500 hover:border-blue-500 hover:text-blue-600 transition-colors"
                        aria-label="Reingresar"
                      >
                        <RotateCcw className="w-4 h-4" />
                      </button>
                    )}
                    <ChevronRight className="w-5 h-5 text-slate-400 flex-shrink-0 mt-1" />
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}

      <PatientFormDialog
        open={open}
        onOpenChange={setOpen}
        onSaved={() => { setOpen(false); load(); }}
      />

      <ImportCensoDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        onFinished={load}
      />
    </div>
  );
}
