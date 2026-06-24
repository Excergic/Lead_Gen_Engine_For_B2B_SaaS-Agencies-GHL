"use client";

import { useEffect, useState } from "react";
import { Users, ExternalLink, Mail, AlertCircle, Loader2 } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import { api } from "@/lib/api";
import type { Lead, LeadChannel } from "@/lib/types";

const CHANNEL_COLORS: Record<LeadChannel, string> = {
  linkedin: "text-sky-400 bg-sky-400/10",
  x: "text-zinc-300 bg-zinc-700/40",
  reddit: "text-orange-400 bg-orange-400/10",
};

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? "text-emerald-400 bg-emerald-400/10 border-emerald-800/50"
      : score >= 60
      ? "text-sky-400 bg-sky-400/10 border-sky-800/50"
      : score >= 40
      ? "text-amber-400 bg-amber-400/10 border-amber-800/50"
      : "text-zinc-500 bg-zinc-800/40 border-zinc-700/50";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${color}`}>
      {score}
    </span>
  );
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [channelFilter, setChannelFilter] = useState<string>("");
  const [minScore, setMinScore] = useState(0);

  useEffect(() => {
    setLoading(true);
    api.leads
      .listAll({ channel: channelFilter || undefined, min_score: minScore || undefined })
      .then(setLeads)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load leads"))
      .finally(() => setLoading(false));
  }, [channelFilter, minScore]);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <PageHeader
        title="Leads"
        subtitle="All discovered and enriched leads across campaigns"
        action={
          <span className="text-sm text-zinc-500">
            {leads.length} lead{leads.length !== 1 ? "s" : ""}
          </span>
        }
      />

      {/* Filters */}
      <div className="flex items-center gap-3 mb-6">
        <select
          value={channelFilter}
          onChange={(e) => setChannelFilter(e.target.value)}
          className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-violet-500"
        >
          <option value="">All channels</option>
          <option value="linkedin">LinkedIn</option>
          <option value="x">X / Twitter</option>
          <option value="reddit">Reddit</option>
        </select>

        <select
          value={minScore}
          onChange={(e) => setMinScore(Number(e.target.value))}
          className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-violet-500"
        >
          <option value={0}>All scores</option>
          <option value={40}>Score ≥ 40</option>
          <option value={60}>Score ≥ 60</option>
          <option value={80}>Score ≥ 80</option>
        </select>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-lg border border-rose-800/50 bg-rose-500/10 px-4 py-3 text-sm text-rose-400">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-zinc-500 py-12 justify-center">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading leads…
        </div>
      ) : leads.length === 0 ? (
        <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/40 px-6 py-12 text-center">
          <Users className="w-8 h-8 text-zinc-700 mx-auto mb-3" />
          <p className="text-sm text-zinc-500">No leads found. Run a campaign to discover leads.</p>
        </div>
      ) : (
        <div className="rounded-xl border border-zinc-800/60 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800/60 bg-zinc-900/40">
                {["Score", "Contact", "Company", "Channel", "Email", "Status", "Profile"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wide"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/40">
              {leads.map((lead) => (
                <tr key={lead.id} className="hover:bg-zinc-800/20 transition-colors">
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-0.5">
                      <ScoreBadge score={lead.lead_score} />
                      {lead.lead_score_reason && (
                        <span
                          className="text-[10px] text-zinc-600 leading-tight max-w-[140px] truncate"
                          title={lead.lead_score_reason}
                        >
                          {lead.lead_score_reason}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-zinc-200">{lead.contact_name ?? "—"}</p>
                    {lead.job_title && (
                      <p className="text-xs text-zinc-500 truncate max-w-[160px]">{lead.job_title}</p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-zinc-300">{lead.company_name ?? "—"}</p>
                    {lead.industry && (
                      <p className="text-xs text-zinc-600 truncate max-w-[140px]">{lead.industry}</p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${CHANNEL_COLORS[lead.channel]}`}
                    >
                      {lead.channel}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {lead.email ? (
                      <span className="flex items-center gap-1 text-emerald-400 text-xs">
                        <Mail className="w-3 h-3" />
                        {lead.email}
                        {lead.email_verified && (
                          <span className="text-[10px] text-emerald-600">✓</span>
                        )}
                      </span>
                    ) : (
                      <span className="text-xs text-zinc-600">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs text-zinc-400 capitalize">{lead.status}</span>
                    {lead.needs_human_review && (
                      <span className="ml-1 text-[10px] text-amber-500">⚑ review</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {lead.profile_link ? (
                      <a
                        href={lead.profile_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300 transition-colors"
                      >
                        <ExternalLink className="w-3 h-3" />
                        View
                      </a>
                    ) : (
                      <span className="text-xs text-zinc-700">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
