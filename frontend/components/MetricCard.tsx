import type { LucideIcon } from "lucide-react";

interface Props {
  label: string;
  value: string | number;
  sub?: string;
  icon: LucideIcon;
  accent?: "violet" | "emerald" | "amber" | "sky" | "rose";
}

const accents = {
  violet: "text-violet-400 bg-violet-400/10",
  emerald: "text-emerald-400 bg-emerald-400/10",
  amber: "text-amber-400 bg-amber-400/10",
  sky: "text-sky-400 bg-sky-400/10",
  rose: "text-rose-400 bg-rose-400/10",
};

export default function MetricCard({ label, value, sub, icon: Icon, accent = "violet" }: Props) {
  const color = accents[accent];
  return (
    <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/60 p-5 flex items-start gap-4">
      <span className={`p-2 rounded-lg ${color}`}>
        <Icon className="w-5 h-5" />
      </span>
      <div className="min-w-0">
        <p className="text-xs text-zinc-500 font-medium uppercase tracking-wide">{label}</p>
        <p className="text-2xl font-bold text-zinc-100 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-zinc-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}
