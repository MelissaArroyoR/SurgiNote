import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
import Login from "@/pages/Login";
import Shell from "@/pages/Shell";
import Pacientes from "@/pages/Pacientes";
import PatientDetail from "@/pages/PatientDetail";
import Pase from "@/pages/Pase";
import Notas from "@/pages/Notas";
import Ingresos from "@/pages/Ingresos";

function Protected({ children }) {
  const { user, ready } = useAuth();
  if (!ready) return null;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="top-center"
          theme="light"
          toastOptions={{
            style: {
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#0F172A",
              fontFamily: "IBM Plex Sans",
            },
          }}
        />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Protected><Shell /></Protected>}>
            <Route index element={<Navigate to="/pacientes" replace />} />
            <Route path="pacientes" element={<Pacientes />} />
            <Route path="pacientes/:id" element={<PatientDetail />} />
            <Route path="pase" element={<Pase />} />
            <Route path="notas" element={<Notas />} />
            <Route path="ingresos" element={<Ingresos />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
