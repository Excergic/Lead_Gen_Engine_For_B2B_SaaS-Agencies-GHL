const styles: Record<string, string> = {
  // campaign
  draft: "bg-zinc-800 text-zinc-400",
  active: "bg-emerald-500/15 text-emerald-400",
  paused: "bg-amber-500/15 text-amber-400",
  completed: "bg-sky-500/15 text-sky-400",
  archived: "bg-zinc-800 text-zinc-500",
  // draft status
  pending_review: "bg-amber-500/15 text-amber-400",
  approved: "bg-emerald-500/15 text-emerald-400",
  rejected: "bg-rose-500/15 text-rose-400",
  sent: "bg-sky-500/15 text-sky-400",
  bounced: "bg-rose-500/15 text-rose-500",
};

const labels: Record<string, string> = {
  pending_review: "Pending",
  approved: "Approved",
};

export default function StatusBadge({ status }: { status: string }) {
  const cls = styles[status] ?? "bg-zinc-800 text-zinc-400";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${cls}`}>
      {labels[status] ?? status}
    </span>
  );
}
