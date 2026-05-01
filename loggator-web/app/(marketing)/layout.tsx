import { CyberBackground } from "@/components/marketing/CyberBackground";

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div data-marketing className="min-h-full flex flex-col w-full relative">
      <CyberBackground />
      {children}
    </div>
  );
}
