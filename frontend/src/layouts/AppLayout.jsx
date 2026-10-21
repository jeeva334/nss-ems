import { NavLink, Outlet } from "react-router-dom";
import { LayoutDashboard, Users, Building2, Menu, X } from "lucide-react";
import { useState } from "react";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/users", label: "User Management", icon: Users },
  { to: "/clients", label: "Client Management", icon: Building2 },
];

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen md:flex">
      <aside
        className={`${open ? "block" : "hidden"} md:block md:w-64 shrink-0 bg-navy-900 text-slate-200`}
        aria-label="Primary"
      >
        <div className="px-5 py-5 text-lg font-semibold text-white">Manpower Portal</div>
        <nav className="px-3 space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
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
