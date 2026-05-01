import SidebarNav from "@/components/SidebarNav";
import SidebarStatus from "@/components/SidebarStatus";
import { AppHeader } from "@/components/shell/AppHeader";
import { ShellGate } from "@/components/shell/ShellGate";
import TenantBar from "@/components/TenantBar";

export default function ShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <ShellGate>
    <div className="flex min-h-screen w-full flex-1 flex-col">
      <AppHeader />
      <div className="flex min-h-0 flex-1">
        <aside className="flex w-[220px] shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground">
          <div className="px-3 py-3 border-b border-sidebar-border">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Workspace
            </p>
          </div>
          <TenantBar />
          <div className="flex-1 px-2 py-2 min-h-0 overflow-y-auto">
            <SidebarNav />
          </div>
          <SidebarStatus />
        </aside>
        <main className="flex-1 overflow-auto bg-muted/25 p-4 md:p-6">
          <div className="mx-auto w-full max-w-[1600px]">{children}</div>
        </main>
      </div>
    </div>
    </ShellGate>
  );
}
