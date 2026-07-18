import { useRef, useState } from "react";
import { Mic, Square, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";

export default function VoiceDictation({ onTranscribed, testid = "btn-voice-dictation" }) {
  const [state, setState] = useState("idle"); // idle | recording | processing
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);

  const start = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const mime = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
      const mr = new MediaRecorder(stream, { mimeType: mime });
      mr.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      mr.onstop = async () => {
        streamRef.current?.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: mime });
        setState("processing");
        try {
          const { text } = await api.transcribe(blob);
          onTranscribed?.(text || "");
          toast.success("Dictado transcrito");
        } catch (e) {
          toast.error(e?.response?.data?.detail || "Error al transcribir");
        } finally {
          setState("idle");
        }
      };
      mediaRecorderRef.current = mr;
      mr.start();
      setState("recording");
    } catch (e) {
      toast.error("No se pudo acceder al micrófono");
    }
  };

  const stop = () => {
    mediaRecorderRef.current?.stop();
  };

  const clickHandler = state === "idle" ? start : state === "recording" ? stop : null;

  return (
    <button
      type="button"
      data-testid={testid}
      onClick={clickHandler}
      disabled={state === "processing"}
      className={[
        "w-20 h-20 rounded-full flex items-center justify-center shadow-lg transition-colors active:scale-95",
        state === "recording"
          ? "bg-red-500 text-white animate-pulse-mic"
          : state === "processing"
          ? "bg-slate-200 text-slate-500"
          : "bg-blue-600 text-white hover:bg-blue-700",
      ].join(" ")}
      aria-label={state === "recording" ? "Detener dictado" : "Iniciar dictado"}
    >
      {state === "recording" ? (
        <Square className="w-8 h-8" fill="currentColor" />
      ) : state === "processing" ? (
        <Loader2 className="w-8 h-8 animate-spin" />
      ) : (
        <Mic className="w-9 h-9" fill="currentColor" strokeWidth={0} />
      )}
    </button>
  );
}
