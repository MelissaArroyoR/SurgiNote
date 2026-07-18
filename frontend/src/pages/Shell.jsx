import { Outlet, NavLink, useLocation } from "react-router-dom";
import { Users, FileText, ClipboardList, LogIn, LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";

const tabs = [
  { to: "/pacientes", label: "Pacientes", Icon: Users, testid: "tab-pacientes" },
  { to: "/pase", label: "Pase", Icon: ClipboardList, testid: "tab-pase" },
  { to: "/notas", label: "Notas", Icon: FileText, testid: "tab-notas" },
  { to: "/ingresos", label: "Ingresos", Icon: LogIn, testid: "tab-ingresos" },
];

export default function Shell() {
  const { logout, user } = useAuth();
  const loc = useLocation();
  const isDetail = loc.pathname.startsWith("/pacientes/") && loc.pathname !== "/pacientes";

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <div className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-slate-200 pt-safe">
        <div className="max-w-3xl mx-auto flex items-center justify-between px-5 py-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <span className="text-white font-heading font-extrabold text-sm">S</span>
            </div>
            <div>
              <div className="font-heading font-bold text-slate-900 text-base leading-tight">SurgiNote</div>
              <div className="text-[10px] uppercase tracking-widest text-blue-600 font-bold leading-none">
                {user?.name || "Cirugía"}
              </div>
            </div>
          </div>
          <button
            data-testid="btn-logout"
            onClick={logout}
            className="w-11 h-11 rounded-full border border-slate-200 flex items-center justify-center text-slate-500 hover:text-blue-600 hover:border-blue-600 transition-colors bg-white"
            aria-label="Cerrar sesión"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>

      <main className="flex-1 max-w-3xl w-full mx-auto pb-32 pt-2 px-5">
        <Outlet />
      </main>

      <nav
        className="fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-slate-200 pb-safe"
        data-testid="bottom-nav"
      >
        <div className="max-w-3xl mx-auto grid grid-cols-4 h-20">
          {tabs.map(({ to, label, Icon, testid }) => (
            <NavLink
              key={to}
              to={to}
              data-testid={testid}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center gap-1 transition-colors ${
                  (isActive || (to === "/pacientes" && isDetail))
                    ? "text-blue-600"
                    : "text-slate-500 hover:text-slate-800"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className="w-6 h-6"
                    strokeWidth={(isActive || (to === "/pacientes" && isDetail)) ? 2.5 : 1.75}
                  />
                  <span className="text-[11px] font-heading font-semibold tracking-wide">{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
