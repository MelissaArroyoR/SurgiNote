import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

const EMPTY = {
  name: "", age: "", sex: "", bed: "", floor: "", service: "", attending_physician: "",
  dx_short: "", dx_full: "",
  admission_date: "", surgery_date: "", surgery_procedure: "", surgery_findings: "",
  medical_history: "", allergies: "", important_medications: "",
  oncology_treatment: "", oncology_status: "", unit_classification: "",
  is_surgical: true, is_pending_discharge: false,
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
        service: patient.service || "",
        attending_physician: patient.attending_physician || "",
        dx_short: patient.dx_short || "",
        dx_full: patient.dx_full || "",
        admission_date: patient.admission_date || "",
        surgery_date: patient.surgery_date || "",
        surgery_procedure: patient.surgery_procedure || "",
        surgery_findings: patient.surgery_findings || "",
        medical_history: patient.medical_history || "",
        allergies: patient.allergies || "",
        important_medications: patient.important_medications || "",
        oncology_treatment: patient.oncology_treatment || "",
        oncology_status: patient.oncology_status || "",
        unit_classification: patient.unit_classification || "",
        is_surgical: patient.is_surgical ?? true,
        is_pending_discharge: patient.is_pending_discharge ?? false,
      });
    } else { setForm(EMPTY); }
  }, [patient, open]);

  const upd = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const toggle = (k) => () => setForm({ ...form, [k]: !form[k] });

  const save = async () => {
    if (!form.name.trim()) { toast.error("El nombre es requerido"); return; }
    setSaving(true);
    try {
      const payload = { ...form };
      payload.age = payload.age ? parseInt(payload.age, 10) : null;
      Object.keys(payload).forEach((k) => {
        if (payload[k] === "") payload[k] = null;
      });
      if (isEdit) await api.updatePatient(patient.id, payload);
      else await api.createPatient(payload);
      toast.success(isEdit ? "Paciente actualizado" : "Paciente agregado");
      onSaved?.();
    } catch { toast.error("Error al guardar"); } finally { setSaving(false); }
  };

  const fieldCls = "mt-1.5 bg-white border-slate-300 text-slate-900 focus-visible:ring-blue-500 focus-visible:border-blue-500";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="bg-white border-slate-200 text-slate-900 max-w-lg max-h-[92vh] overflow-y-auto"
        data-testid="dialog-patient-form"
      >
        <DialogHeader>
          <DialogTitle className="font-heading text-xl text-slate-900">
            {isEdit ? "Editar paciente" : "Nuevo paciente"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div>
            <Label className="text-slate-700 text-sm">Nombre completo *</Label>
            <Input data-testid="input-patient-name" value={form.name} onChange={upd("name")} className={fieldCls} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label className="text-slate-700 text-sm">Edad</Label>
              <Input type="number" data-testid="input-patient-age" value={form.age} onChange={upd("age")} className={fieldCls} />
            </div>
            <div>
              <Label className="text-slate-700 text-sm">Sexo</Label>
              <Input placeholder="M/F" data-testid="input-patient-sex" value={form.sex} onChange={upd("sex")} className={fieldCls} />
            </div>
            <div>
              <Label className="text-slate-700 text-sm">Cama</Label>
              <Input data-testid="input-patient-bed" value={form.bed} onChange={upd("bed")} className={fieldCls} />
            </div>
          </div>
          <div>
            <Label className="text-slate-700 text-sm">Tratante</Label>
            <Input placeholder="Dr. Apellido" data-testid="input-attending" value={form.attending_physician} onChange={upd("attending_physician")} className={fieldCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-slate-700 text-sm">Servicio</Label>
              <Input placeholder="Cirugía General" data-testid="input-patient-service" value={form.service} onChange={upd("service")} className={fieldCls} />
            </div>
            <div>
              <Label className="text-slate-700 text-sm">Unidad</Label>
              <Input placeholder="Piso / UTI / UTIM" data-testid="input-unit" value={form.unit_classification} onChange={upd("unit_classification")} className={fieldCls} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <button type="button" data-testid="toggle-surgical" onClick={toggle("is_surgical")}
              className={`h-11 rounded-lg text-sm font-semibold border transition-colors ${form.is_surgical ? "bg-white border-slate-300 text-slate-800" : "bg-pink-50 border-pink-300 text-pink-700"}`}>
              {form.is_surgical ? "Quirúrgico" : "No quirúrgico"}
            </button>
            <button type="button" data-testid="toggle-pending-discharge" onClick={toggle("is_pending_discharge")}
              className={`h-11 rounded-lg text-sm font-semibold border transition-colors ${form.is_pending_discharge ? "bg-orange-50 border-orange-300 text-orange-700" : "bg-white border-slate-300 text-slate-500"}`}>
              {form.is_pending_discharge ? "Alta pendiente" : "Sin alta pendiente"}
            </button>
          </div>
          <div>
            <Label className="text-slate-700 text-sm">Diagnóstico resumido</Label>
            <Input placeholder="Ej. Apendicitis aguda perforada" data-testid="input-dx-short" value={form.dx_short} onChange={upd("dx_short")} className={fieldCls} />
          </div>
          <div>
            <Label className="text-slate-700 text-sm">Diagnóstico completo</Label>
            <Textarea data-testid="input-dx-full" value={form.dx_full} onChange={upd("dx_full")} rows={2} className={fieldCls} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-slate-700 text-sm">Fecha ingreso</Label>
              <Input type="date" data-testid="input-admission-date" value={form.admission_date} onChange={upd("admission_date")} className={fieldCls} />
            </div>
            <div>
              <Label className="text-slate-700 text-sm">Fecha cirugía</Label>
              <Input type="date" data-testid="input-surgery-date" value={form.surgery_date} onChange={upd("surgery_date")} className={fieldCls} />
            </div>
          </div>
          <div>
            <Label className="text-slate-700 text-sm">Procedimiento quirúrgico</Label>
            <Textarea data-testid="input-surgery-procedure" value={form.surgery_procedure} onChange={upd("surgery_procedure")} rows={2} className={fieldCls} />
          </div>
          <div>
            <Label className="text-slate-700 text-sm">Hallazgos quirúrgicos</Label>
            <Textarea data-testid="input-surgery-findings" value={form.surgery_findings} onChange={upd("surgery_findings")} rows={2} className={fieldCls} />
          </div>
          <div>
            <Label className="text-slate-700 text-sm">Antecedentes personales patológicos</Label>
            <Textarea data-testid="input-medical-history" value={form.medical_history} onChange={upd("medical_history")} rows={2} className={fieldCls} />
          </div>
          <div>
            <Label className="text-slate-700 text-sm">Alergias</Label>
            <Input placeholder="Ninguna referida" data-testid="input-allergies" value={form.allergies} onChange={upd("allergies")} className={fieldCls} />
          </div>
          <div>
            <Label className="text-slate-700 text-sm">Medicamentos importantes / crónicos</Label>
            <Textarea data-testid="input-important-meds" value={form.important_medications} onChange={upd("important_medications")} rows={2} className={fieldCls} />
          </div>
          <div className="grid grid-cols-1 gap-3">
            <div>
              <Label className="text-slate-700 text-sm">Estado oncológico</Label>
              <Input placeholder="Ej. Estadio IIIA, en QT adyuvante" data-testid="input-oncology-status" value={form.oncology_status} onChange={upd("oncology_status")} className={fieldCls} />
            </div>
            <div>
              <Label className="text-slate-700 text-sm">Tratamiento oncológico</Label>
              <Textarea data-testid="input-oncology" value={form.oncology_treatment} onChange={upd("oncology_treatment")} rows={2} className={fieldCls} />
            </div>
          </div>

          <div className="flex gap-3 pt-2 sticky bottom-0 bg-white pb-1">
            <Button variant="outline" data-testid="btn-cancel-patient" onClick={() => onOpenChange(false)}
              className="flex-1 h-12 bg-white border-slate-300 text-slate-700 hover:bg-slate-50">
              Cancelar
            </Button>
            <Button data-testid="btn-save-patient" onClick={save} disabled={saving}
              className="flex-1 h-12 bg-blue-600 hover:bg-blue-700 text-white font-bold">
              {saving ? "Guardando…" : "Guardar"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
