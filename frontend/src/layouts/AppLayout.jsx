import { NavLink, Outlet } from "react-router-dom";
import { LayoutDashboard, Users, Building2, Menu, X, LogOut, ScrollText } from "lucide-react";
import { useAuth } from "../hooks/AuthContext";
import { useState } from "react";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/users", label: "User Management", icon: Users, roles: ["ADMIN"] },
  { to: "/clients", label: "Client Management", icon: Building2, roles: ["ADMIN"] },
  { to: "/audit", label: "Audit Log", icon: ScrollText, roles: ["ADMIN"] },
];

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  const { user, logout } = useAuth();
  const items = NAV.filter((i) => !i.roles || i.roles.includes(user.role));
  return (
    <div className="min-h-screen md:flex">
      <aside
        className={`${open ? "block" : "hidden"} md:block md:w-64 shrink-0 bg-navy-900 text-slate-200`}
        aria-label="Primary"
      >
        <div className="px-5 py-5 text-lg font-semibold text-white">Manpower Portal</div>
        <nav className="px-3 space-y-1">
          {items.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
                  isActive ? "bg-blue-600 text-white" : "hover:bg-navy-800"
                }`
              }
            >
              <Icon size={18} aria-hidden /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-8 border-t border-white/10 px-5 py-4 text-sm">
          <p className="font-medium text-white">{user.full_name}</p>
          <p className="text-slate-400">{user.employee_id} · {user.role}</p>
          <button onClick={logout} className="mt-3 flex items-center gap-2 text-slate-300 hover:text-white">
            <LogOut size={16} aria-hidden /> Sign out
          </button>
        </div>
      </aside>
      <div className="flex-1 min-w-0">
        <header className="md:hidden flex items-center justify-between bg-navy-900 text-white px-4 py-3">
          <span className="font-semibold">Manpower Portal</span>
          <button onClick={() => setOpen(!open)} aria-label="Toggle navigation">
            {open ? <X /> : <Menu />}
          </button>
        </header>
        <main className="p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
