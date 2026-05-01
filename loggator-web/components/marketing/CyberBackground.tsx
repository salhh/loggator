export function CyberBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden>
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_120%_80%_at_50%_-20%,rgba(34,211,238,0.12),transparent_50%),radial-gradient(ellipse_80%_50%_at_100%_50%,rgba(139,92,246,0.08),transparent_45%),radial-gradient(ellipse_60%_40%_at_0%_80%,rgba(34,211,238,0.06),transparent_40%)]" />
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(34,211,238,0.4) 1px, transparent 1px),
            linear-gradient(90deg, rgba(34,211,238,0.4) 1px, transparent 1px)
          `,
          backgroundSize: "48px 48px",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.03] animate-pulse"
        style={{
          backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(34,211,238,0.15) 2px, rgba(34,211,238,0.15) 4px)",
        }}
      />
    </div>
  );
}
