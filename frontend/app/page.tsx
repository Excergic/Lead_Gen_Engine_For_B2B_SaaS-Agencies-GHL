"use client";

import { useEffect, useState } from "react";
import { Users, Megaphone, Mail, SendHorizonal, AlertCircle } from "lucide-react";
import MetricCard from "@/components/MetricCard";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { Campaign, Client } from "@/lib/types";

interface Summary {
  totalClients: number;
  totalCampaigns: number;
  activeCampaigns: number;
  totalLeads: number;
  pendingReview: number;
}

export default function DashboardPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
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
            <div key={i} className="h-28 rounded-xl bg-zinc-900/60 border border-zinc-800/60 animate-pulse" />
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
            <MetricCard label="Leads Discovered" value={summary.totalLeads} icon={Users} accent="emerald" />
            <MetricCard
              label="Pending Review"
              value={summary.pendingReview}
              sub="awaiting your approval"
              icon={SendHorizonal}
              accent={summary.pendingReview > 0 ? "amber" : "violet"}
            />
            <MetricCard label="Outreach Queue" value={summary.totalCampaigns} icon={Mail} accent="amber" />
          </div>

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
                        <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                        <td className="px-4 py-3 text-zinc-400">{c.icp_template.replace(/_/g, " ")}</td>
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
