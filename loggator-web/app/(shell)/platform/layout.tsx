import PlatformGuard from "@/components/platform/PlatformGuard";
import PlatformLayoutChrome from "@/components/platform/PlatformLayoutChrome";
import PlatformSidebarNav from "@/components/platform/PlatformSidebarNav";

export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  return (
    <PlatformGuard>
      <div className="flex h-full gap-0">
        <aside className="w-[200px] shrink-0 flex flex-col border-r border-border bg-card/50">
          <PlatformLayoutChrome />
          <div className="flex-1 px-2 py-3 min-h-0 overflow-y-auto">
            <PlatformSidebarNav />
          </div>
        </aside>
        <div className="flex-1 overflow-auto p-6">{children}</div>
      </div>
    </PlatformGuard>
  );
}
