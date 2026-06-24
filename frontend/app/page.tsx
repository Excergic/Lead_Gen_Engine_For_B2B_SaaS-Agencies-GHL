"use client";

import { useEffect, useState } from "react";
import { Users, Megaphone, Mail, SendHorizonal, AlertCircle, ExternalLink } from "lucide-react";
import Link from "next/link";
import MetricCard from "@/components/MetricCard";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { Campaign, Client, Lead } from "@/lib/types";

interface Summary {
  totalClients: number;
  totalCampaigns: number;
  activeCampaigns: number;
  totalLeads: number;
  pendingReview: number;
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? "text-emerald-400 bg-emerald-400/10"
      : score >= 60
      ? "text-sky-400 bg-sky-400/10"
      : score >= 40
      ? "text-amber-400 bg-amber-400/10"
      : "text-zinc-500 bg-zinc-800/40";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${color}`}>
      {score}
    </span>
  );
}

export default function DashboardPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [topLeads, setTopLeads] = useState<Lead[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [cl, drafts] = await Promise.all([
          api.clients.list(),
          api.outreach.listPending(100),
        ]);
        setClients(cl.items);

        const allCampaigns: Campaign[] = [];
        await Promise.all(
          cl.items.map(async (c) => {
            try {
              const pg = await api.campaigns.list(c.id);
              allCampaigns.push(...pg.items);
            } catch {
              /* client may have no campaigns */
            }
          })
        );
        setCampaigns(allCampaigns);

        setSummary({
          totalClients: cl.total,
          totalCampaigns: allCampaigns.length,
          activeCampaigns: allCampaigns.filter((c) => c.status === "active").length,
          totalLeads: allCampaigns.reduce((s, c) => s + c.leads_discovered, 0),
          pendingReview: drafts.filter((d) => d.status === "pending_review").length,
        });

        // Load top scoring leads (best fit)
        try {
          const leads = await api.leads.listAll({ min_score: 60 });
          setTopLeads(leads.slice(0, 8));
        } catch {
          // leads endpoint optional — don't fail dashboard
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <PageHeader title="Dashboard" subtitle="Overview of your lead generation workflow" />

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-lg border border-rose-800/50 bg-rose-500/10 px-4 py-3 text-sm text-rose-400">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error} — is the backend running?
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-28 rounded-xl bg-zinc-900/60 border border-zinc-800/60 animate-pulse"
            />
          ))}
        </div>
      ) : summary ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            <MetricCard label="Clients" value={summary.totalClients} icon={Users} accent="violet" />
            <MetricCard
              label="Campaigns"
              value={summary.totalCampaigns}
              sub={`${summary.activeCampaigns} active`}
              icon={Megaphone}
              accent="sky"
            />
            <MetricCard
              label="Leads Discovered"
              value={summary.totalLeads}
              icon={Users}
              accent="emerald"
            />
            <MetricCard
              label="Pending Review"
              value={summary.pendingReview}
              sub="awaiting your approval"
              icon={SendHorizonal}
              accent={summary.pendingReview > 0 ? "amber" : "violet"}
            />
            <MetricCard label="Outreach Queue" value={summary.totalCampaigns} icon={Mail} accent="amber" />
          </div>

          {/* Highest Fit Leads */}
          {topLeads.length > 0 && (
            <section className="mb-8">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wide">
                  Highest Fit Leads
                </h2>
                <Link
                  href="/leads"
                  className="text-xs text-violet-400 hover:text-violet-300 transition-colors"
                >
                  View all →
                </Link>
              </div>
              <div className="rounded-xl border border-zinc-800/60 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-800/60 bg-zinc-900/40">
                      {["Score", "Contact", "Company", "Email", "Profile"].map((h) => (
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
                    {topLeads.map((lead) => (
                      <tr key={lead.id} className="hover:bg-zinc-800/20 transition-colors">
                        <td className="px-4 py-3">
                          <ScoreBadge score={lead.lead_score} />
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-medium text-zinc-200">{lead.contact_name ?? "—"}</p>
                          {lead.job_title && (
                            <p className="text-xs text-zinc-500 truncate max-w-[140px]">
                              {lead.job_title}
                            </p>
                          )}
                        </td>
                        <td className="px-4 py-3 text-zinc-300">{lead.company_name ?? "—"}</td>
                        <td className="px-4 py-3 text-xs">
                          {lead.email ? (
                            <span className="text-emerald-400">{lead.email}</span>
                          ) : (
                            <span className="text-zinc-600">—</span>
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
            </section>
          )}

          {/* Recent Campaigns */}
          <section>
            <h2 className="text-xs font-medium text-zinc-500 uppercase tracking-wide mb-3">
              Recent Campaigns
            </h2>
            {campaigns.length === 0 ? (
              <p className="text-sm text-zinc-600">No campaigns yet. Create one in Campaigns.</p>
            ) : (
              <div className="rounded-xl border border-zinc-800/60 overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-800/60 bg-zinc-900/40">
                      {["Name", "Status", "ICP", "Leads", "Enriched"].map((h) => (
                        <th
                          key={h}
                          className="px-4 py-3 text-left text-xs font-medium text-zinc-500 uppercase tracking-wide last:text-right"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/40">
                    {campaigns.slice(0, 8).map((c) => (
                      <tr key={c.id} className="hover:bg-zinc-800/20 transition-colors">
                        <td className="px-4 py-3 font-medium text-zinc-200">{c.name}</td>
                        <td className="px-4 py-3">
                          <StatusBadge status={c.status} />
                        </td>
                        <td className="px-4 py-3 text-zinc-400">
                          {c.icp_template.replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-3 text-zinc-300">{c.leads_discovered}</td>
                        <td className="px-4 py-3 text-right text-zinc-300">{c.leads_enriched}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
