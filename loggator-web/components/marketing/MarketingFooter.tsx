import Link from "next/link";

export function MarketingFooter() {
  return (
    <footer className="border-t border-border/80 px-4 py-12 mt-8">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-2 text-sm font-bold tracking-widest text-primary">
          <span className="h-2 w-2 rounded-full bg-primary inline-block" />
          LOGGATOR
        </div>
        <nav className="flex flex-wrap justify-center gap-6 text-xs text-muted-foreground">
          <Link href="/login" className="hover:text-primary transition-colors">
            Sign in
          </Link>
          <span className="text-border">|</span>
          <span className="cursor-default">Privacy (placeholder)</span>
          <span className="text-border">|</span>
          <span className="cursor-default">Terms (placeholder)</span>
        </nav>
        <p className="text-[10px] font-mono text-muted-foreground">© {new Date().getFullYear()} Loggator</p>
      </div>
    </footer>
  );
}
