import { cn } from "@/lib/utils";

export function TrafficLightIcon({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex h-5 w-5 items-center justify-center rounded-full bg-emerald-50", className)} aria-hidden="true">
      <span className="flex h-[82%] w-[58%] flex-col items-center justify-center gap-[8%] rounded-[999px] border border-zinc-700 bg-zinc-950 shadow-sm">
        <span className="h-[22%] w-[38%] rounded-full bg-red-500 shadow-[0_0_4px_rgba(239,68,68,0.8)]" />
        <span className="h-[22%] w-[38%] rounded-full bg-amber-400 shadow-[0_0_4px_rgba(251,191,36,0.75)]" />
        <span className="h-[22%] w-[38%] rounded-full bg-emerald-500 shadow-[0_0_4px_rgba(16,185,129,0.75)]" />
      </span>
    </span>
  );
}
