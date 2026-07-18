import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const EMPTY = {
  name: "", age: "", sex: "", bed: "", floor: "",
  dx_short: "", dx_full: "",
  admission_date: "", surgery_date: "", surgery_procedure: "", surgery_findings: "",
  medical_history: "", consultants: "", oncology_treatment: "",
};

export default function PatientFormDialog({ open, onOpenChange, patient, onSaved }) {
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const isEdit = !!patient;

  useEffect(() => {
    if (patient) {
      setForm({
        name: patient.name || "",
        age: patient.age ?? "",
        sex: patient.sex || "",
        bed: patient.bed || "",
        floor: patient.floor || "",
        dx_short: patient.dx_short || "",
        dx_full: patient.dx_full || "",
        admission_date: patient.admission_date || "",
        surgery_date: patient.surgery_date || "",
        surgery_procedure: patient.surgery_procedure || "",
        surgery_findings: patient.surgery_findings || "",
        medical_history: patient.medical_history || "",
        consultants: patient.consultants || "",
        oncology_treatment: patient.oncology_treatment || "",
      });
    } else {
      setForm(EMPTY);
    }
  }, [patient, open]);

  const upd = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = async () => {
    if (!form.name.trim()) { toast.error("El nombre es requerido"); return; }
    setSaving(true);
    try {
      const payload = { ...form };
      payload.age = payload.age ? parseInt(payload.age, 10) : null;
      Object.keys(payload).forEach((k) => { if (payload[k] === "") payload[k] = null; });
      if (isEdit) await api.updatePatient(patient.id, payload);
      else await api.createPatient(payload);
      toast.success(isEdit ? "Paciente actualizado" : "Paciente agregado");
      onSaved?.();
    } catch (e) {
      toast.error("Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  const fieldCls = "mt-1.5 bg-slate-900 border-slate-700 text-slate-50 focus-visible:ring-amber-500 focus-visible:border-amber-500";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="bg-slate-900 border-slate-700 text-slate-50 max-w-lg max-h-[92vh] overflow-y-auto"
        data-testid="dialog-patient-form"
      >
        <DialogHeader>
          <DialogTitle className="font-heading text-xl">
            {isEdit ? "Editar paciente" : "Nuevo paciente"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div>
            <Label className="text-slate-300 text-sm">Nombre completo *</Label>
            <Input data-testid="input-patient-name" value={form.name} onChange={upd("name")} className={fieldCls} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label className="text-slate-300 text-sm">Edad</Label>
              <Input type="number" data-testid="input-patient-age" value={form.age} onChange={upd("age")} className={fieldCls} />
            </div>
            <div>
              <Label className="text-slate-300 text-sm">Sexo</Label>
              <Input placeholder="M/F" data-testid="input-patient-sex" value={form.sex} onChange={upd("sex")} className={fieldCls} />
            </div>
            <div>
              <Label className="text-slate-300 text-sm">Cama</Label>
              <Input data-testid="input-patient-bed" value={form.bed} onChange={upd("bed")} className={fieldCls} />
            </div>
          </div>
          <div>
            <Label className="text-slate-300 text-sm">Piso / Servicio</Label>
            <Input data-testid="input-patient-floor" value={form.floor} onChange={upd("floor")} className={fieldCls} />
          </div>
          <div>
            <Label className="text-slate-300 text-sm">Diagnóstico resumido</Label>
            <Input placeholder="Ej. Apendicitis aguda perforada" data-testid="input-dx-short" value={form.dx_short} onChange={upd("dx_short")} className={fieldCls} />
          </div>
          <div>
            <Label className="text-slate-300 text-sm">Diagnóstico completo</Label>
            <Textarea data-testid="input-dx-full" value={form.dx_full} onChange={upd("dx_full")} rows={2} className={fieldCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-slate-300 text-sm">Fecha ingreso</Label>
              <Input type="date" data-testid="input-admission-date" value={form.admission_date} onChange={upd("admission_date")} className={fieldCls} />
            </div>
            <div>
              <Label className="text-slate-300 text-sm">Fecha cirugía</Label>
              <Input type="date" data-testid="input-surgery-date" value={form.surgery_date} onChange={upd("surgery_date")} className={fieldCls} />
            </div>
          </div>
          <div>
            <Label className="text-slate-300 text-sm">Procedimiento quirúrgico</Label>
            <Textarea data-testid="input-surgery-procedure" value={form.surgery_procedure} onChange={upd("surgery_procedure")} rows={2} className={fieldCls} />
          </div>
          <div>
            <Label className="text-slate-300 text-sm">Hallazgos quirúrgicos</Label>
            <Textarea data-testid="input-surgery-findings" value={form.surgery_findings} onChange={upd("surgery_findings")} rows={2} className={fieldCls} />
          </div>
          <div>
            <Label className="text-slate-300 text-sm">Antecedentes personales patológicos</Label>
            <Textarea data-testid="input-medical-history" value={form.medical_history} onChange={upd("medical_history")} rows={2} className={fieldCls} />
          </div>
          <div>
            <Label className="text-slate-300 text-sm">Interconsultantes activos</Label>
            <Textarea placeholder="Ej. Cardiología, Infectología..." data-testid="input-consultants" value={form.consultants} onChange={upd("consultants")} rows={2} className={fieldCls} />
          </div>
          <div>
            <Label className="text-slate-300 text-sm">Tratamiento oncológico</Label>
            <Textarea data-testid="input-oncology" value={form.oncology_treatment} onChange={upd("oncology_treatment")} rows={2} className={fieldCls} />
          </div>

          <div className="flex gap-3 pt-2 sticky bottom-0 bg-slate-900 pb-1">
            <Button
              variant="outline"
              data-testid="btn-cancel-patient"
              onClick={() => onOpenChange(false)}
              className="flex-1 h-12 bg-transparent border-slate-700 text-slate-300 hover:bg-slate-800"
            >
              Cancelar
            </Button>
            <Button
              data-testid="btn-save-patient"
              onClick={save}
              disabled={saving}
              className="flex-1 h-12 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold"
            >
              {saving ? "Guardando…" : "Guardar"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
