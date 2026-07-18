import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Stethoscope, ArrowRight } from "lucide-react";

export default function Login() {
  const { login, register } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, name);
      toast.success("Bienvenido");
      nav("/pacientes");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#020617] flex flex-col items-center justify-center px-6 py-10">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-start mb-10">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-xl bg-amber-500 flex items-center justify-center">
              <Stethoscope className="w-6 h-6 text-slate-950" strokeWidth={2.5} />
            </div>
            <div>
              <div className="text-xs font-bold uppercase tracking-[0.2em] text-amber-500">Cirugía General</div>
              <h1 className="text-3xl font-heading font-extrabold text-slate-50 leading-tight">SurgiNote</h1>
            </div>
          </div>
          <p className="text-slate-400 text-sm leading-relaxed">
            Asistente personal para pase de visita, notas de evolución y mensajes a médicos tratantes.
          </p>
        </div>

        <form onSubmit={submit} className="space-y-5" data-testid="login-form">
          {mode === "register" && (
            <div>
              <Label htmlFor="name" className="text-slate-300 text-sm">Nombre</Label>
              <Input
                id="name"
                data-testid="input-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="mt-2 h-14 bg-slate-900 border-slate-700 text-slate-50 text-base focus-visible:ring-amber-500 focus-visible:border-amber-500"
                placeholder="Dr. Nombre Apellido"
              />
            </div>
          )}
          <div>
            <Label htmlFor="email" className="text-slate-300 text-sm">Email</Label>
            <Input
              id="email"
              type="email"
              data-testid="input-email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="mt-2 h-14 bg-slate-900 border-slate-700 text-slate-50 text-base focus-visible:ring-amber-500 focus-visible:border-amber-500"
            />
          </div>
          <div>
            <Label htmlFor="password" className="text-slate-300 text-sm">Contraseña</Label>
            <Input
              id="password"
              type="password"
              data-testid="input-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="mt-2 h-14 bg-slate-900 border-slate-700 text-slate-50 text-base focus-visible:ring-amber-500 focus-visible:border-amber-500"
            />
          </div>

          <Button
            type="submit"
            disabled={loading}
            data-testid="btn-submit-auth"
            className="w-full h-14 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold text-base rounded-xl transition-colors active:scale-[0.98]"
          >
            {loading ? "..." : mode === "login" ? "Entrar" : "Crear cuenta"}
            <ArrowRight className="w-5 h-5 ml-2" />
          </Button>

          <button
            type="button"
            data-testid="btn-toggle-mode"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            className="w-full text-center text-sm text-slate-400 hover:text-amber-500 py-2"
          >
            {mode === "login" ? "¿No tienes cuenta? Crear cuenta" : "¿Ya tienes cuenta? Entrar"}
          </button>
        </form>

        <div className="mt-10 pt-6 border-t border-slate-800">
          <p className="text-xs text-slate-500 leading-relaxed">
            <span className="text-amber-500 font-bold uppercase tracking-wider">Aviso:</span> Esta herramienta no es un expediente clínico oficial ni sustituye el juicio médico. Los datos se almacenan de forma privada para uso personal.
          </p>
        </div>
      </div>
    </div>
  );
}
