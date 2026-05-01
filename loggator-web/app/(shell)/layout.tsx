import SidebarNav from "@/components/SidebarNav";
import SidebarStatus from "@/components/SidebarStatus";
import TenantBar from "@/components/TenantBar";

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <aside className="w-[220px] shrink-0 flex flex-col border-r border-border bg-card">
        <div className="px-4 py-5">
          <div className="text-sm font-bold tracking-widest text-cyan-400 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-cyan-400 inline-block" />
            LOGGATOR
          </div>
        </div>
        <TenantBar />
        <div className="flex-1 px-2 min-h-0 overflow-y-auto">
          <SidebarNav />
        </div>
        <SidebarStatus />
      </aside>
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </>
  );
}
