import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Save, GraduationCap } from "lucide-react";
import { api } from "@/lib/api";

export default function Configuracion() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hospital, setHospital] = useState("");
  const [uti, setUti] = useState("");
  const [whatsapp, setWhatsapp] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const data = await api.getTrainingExamples();
        setHospital(data.hospital_notes_examples || "");
        setUti(data.uti_notes_examples || "");
        setWhatsapp(data.whatsapp_examples || "");
      } catch (e) {
        toast.error("No se pudieron cargar los ejemplos");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.saveTrainingExamples({
        hospital_notes_examples: hospital,
        uti_notes_examples: uti,
        whatsapp_examples: whatsapp,
      });
      toast.success("Ejemplos guardados. La IA los usará como referencia de estilo.");
    } catch (e) {
      toast.error("Error al guardar");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6 pt-4" data-testid="configuracion-page">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-blue-600/10 flex items-center justify-center">
          <GraduationCap className="w-5 h-5 text-blue-600" />
        </div>
        <div>
          <h1 className="text-2xl font-heading font-extrabold text-slate-900 leading-tight">
            Configuración
          </h1>
          <p className="text-xs text-slate-500 leading-tight">
            Ajustes y entrenamiento de la IA
          </p>
        </div>
      </div>

      <section
        className="bg-white rounded-2xl border border-slate-200 p-5 space-y-5"
        data-testid="entrenamiento-ia-section"
      >
        <div>
          <h2 className="text-lg font-heading font-bold text-slate-900">
            Entrenamiento de IA
          </h2>
          <p className="text-xs text-slate-500 mt-1 leading-relaxed">
            Pega aquí notas reales tuyas. La IA aprenderá tu estructura, vocabulario y forma de
            redactar como residente R3. Nunca copiará nombres, diagnósticos ni fechas — solo el
            estilo.
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-heading font-semibold text-slate-700 uppercase tracking-wide">
            Ejemplos de Notas de Hospitalización
          </label>
          <textarea
            data-testid="hospital-notes-textarea"
            value={hospital}
            onChange={(e) => setHospital(e.target.value)}
            placeholder="Pega aquí una o varias notas reales de tus pacientes de piso..."
            className="w-full min-h-[220px] rounded-lg border border-slate-300 p-3 text-sm font-mono leading-relaxed focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y"
          />
          <div className="text-[11px] text-slate-400 text-right">
            {hospital.length.toLocaleString()} caracteres
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-heading font-semibold text-slate-700 uppercase tracking-wide">
            Ejemplos de Notas de UTI / UTIM
          </label>
          <textarea
            data-testid="uti-notes-textarea"
            value={uti}
            onChange={(e) => setUti(e.target.value)}
            placeholder="Pega aquí notas reales de terapia intensiva..."
            className="w-full min-h-[220px] rounded-lg border border-slate-300 p-3 text-sm font-mono leading-relaxed focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y"
          />
          <div className="text-[11px] text-slate-400 text-right">
            {uti.length.toLocaleString()} caracteres
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-heading font-semibold text-slate-700 uppercase tracking-wide">
            Ejemplos de Mensajes para el Tratante
          </label>
          <textarea
            data-testid="whatsapp-examples-textarea"
            value={whatsapp}
            onChange={(e) => setWhatsapp(e.target.value)}
            placeholder="Pega aquí mensajes reales que hayas enviado por WhatsApp al tratante..."
            className="w-full min-h-[180px] rounded-lg border border-slate-300 p-3 text-sm font-mono leading-relaxed focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y"
          />
          <div className="text-[11px] text-slate-400 text-right">
            {whatsapp.length.toLocaleString()} caracteres
          </div>
        </div>

        <button
          data-testid="save-training-btn"
          onClick={handleSave}
          disabled={saving}
          className="w-full h-12 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-heading font-semibold flex items-center justify-center gap-2 disabled:opacity-60"
        >
          {saving ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Guardando…
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              Guardar ejemplos
            </>
          )}
        </button>
      </section>
    </div>
  );
}
