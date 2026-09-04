import { BarChart3, BriefcaseBusiness, CirclePlay, LayoutDashboard, Settings, Users } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

const navigation = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/runs/new", label: "Запуск поиска", icon: CirclePlay },
  { to: "/runs", label: "Runs", icon: BriefcaseBusiness }
];

const futureNavigation = [
  { label: "Vacancies", icon: BriefcaseBusiness },
  { label: "Applications", icon: Users },
  { label: "Statistics", icon: BarChart3 },
  { label: "Settings", icon: Settings }
];

export function AppShell() {
  return (
    <div className="min-h-screen bg-canvas text-ink">
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <aside className="hidden w-60 shrink-0 border-r border-line bg-white p-5 lg:block">
          <div className="mb-9 flex items-center gap-3 px-2">
            <div className="grid size-9 place-items-center rounded-md bg-ink text-sm font-bold text-white">AJ</div>
            <div><p className="font-semibold">AI Job Automation</p><p className="text-xs text-zinc-500">Рабочая панель</p></div>
          </div>
          <nav aria-label="Основная навигация" className="space-y-1">
            {navigation.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition ${isActive ? "bg-zinc-900 text-white" : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950"}`}>
                <Icon size={18} aria-hidden="true" />{label}
              </NavLink>
            ))}
          </nav>
          <div className="mt-8 border-t border-line pt-5">
            <p className="px-3 text-xs font-medium uppercase text-zinc-400">Следующие экраны</p>
            <div className="mt-2 space-y-1">{futureNavigation.map(({ label, icon: Icon }) => <div key={label} className="flex items-center gap-3 px-3 py-2 text-sm text-zinc-400"><Icon size={18} aria-hidden="true" />{label}</div>)}</div>
          </div>
        </aside>
        <main className="min-w-0 flex-1"><div className="border-b border-line bg-white px-5 py-4 lg:hidden"><p className="font-semibold">AI Job Automation</p></div><div className="mx-auto max-w-7xl p-5 md:p-8"><Outlet /></div></main>
      </div>
    </div>
  );
}
