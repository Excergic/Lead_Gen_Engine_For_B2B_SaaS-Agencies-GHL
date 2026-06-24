"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, AlertCircle, ChevronRight } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import CreateCampaignModal from "@/components/CreateCampaignModal";
import { api } from "@/lib/api";
import type { Campaign, CampaignChannel, Client } from "@/lib/types";

const CHANNEL_STYLES: Record<CampaignChannel, string> = {
  linkedin: "text-sky-400 bg-sky-400/10",
  x: "text-zinc-300 bg-zinc-700/50",
  reddit: "text-orange-400 bg-orange-400/10",
  all: "text-violet-400 bg-violet-400/10",
};
const CHANNEL_LABELS: Record<CampaignChannel, string> = {
  linkedin: "LinkedIn",
  x: "X",
  reddit: "Reddit",
  all: "All",
};

function ChannelBadge({ channel }: { channel: CampaignChannel }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${CHANNEL_STYLES[channel]}`}>
      {CHANNEL_LABELS[channel]}
    </span>
  );
}

interface ClientWithCampaigns {
  client: Client;
  campaigns: Campaign[];
}

export default function CampaignsPage() {
  const router = useRouter();
  const [data, setData] = useState<ClientWithCampaigns[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const cl = await api.clients.list();
      const pairs = await Promise.all(
        cl.items.map(async (client) => {
          try {
            const pg = await api.campaigns.list(client.id);
            return { client, campaigns: pg.items };
          } catch {
            return { client, campaigns: [] };
          }
        })
      );
      setData(pairs);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function handleCreated(clientId: string, campaignId: string) {
    load();
    router.push(`/campaigns/${campaignId}?client_id=${clientId}`);
  }

  const allCampaigns = data.flatMap(({ client, campaigns }) =>
    campaigns.map((c) => ({ campaign: c, client }))
  );

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <PageHeader
        title="Campaigns"
        subtitle="Create a campaign, then run discover → enrich → personalize"
        action={
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors"
          >
            <Plus className="w-4 h-4" /> New Campaign
          </button>
        }
      />

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-lg border border-rose-800/50 bg-rose-500/10 px-4 py-3 text-sm text-rose-400">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-zinc-900/60 border border-zinc-800/60 animate-pulse" />
          ))}
        </div>
      ) : allCampaigns.length === 0 ? (
        <div className="text-center py-24 rounded-xl border border-dashed border-zinc-800">
          <p className="text-sm text-zinc-400">No campaigns yet</p>
          <p className="text-xs text-zinc-600 mt-1 mb-4">
            Creates a client, ICP profile, and draft campaign in one step.
          </p>
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium"
          >
            <Plus className="w-4 h-4" /> Create first campaign
          </button>
        </div>
      ) : (
        <div className="rounded-xl border border-zinc-800/60 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800/60 bg-zinc-900/40">
                {["Campaign", "Client", "Status", "Channel", "ICP", "Leads", "Enriched", "Emails", ""].map((h) => (
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
              {allCampaigns.map(({ campaign: c, client }) => (
                <tr key={c.id} className="hover:bg-zinc-800/20 transition-colors">
                  <td className="px-4 py-3 font-medium text-zinc-200">{c.name}</td>
                  <td className="px-4 py-3 text-zinc-400">{client.name}</td>
                  <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                  <td className="px-4 py-3">
                    <ChannelBadge channel={c.channel ?? "all"} />
                  </td>
                  <td className="px-4 py-3 text-zinc-400 capitalize">
                    {c.icp_template.replace(/_/g, " ")}
                  </td>
                  <td className="px-4 py-3 text-zinc-300">{c.leads_discovered}</td>
                  <td className="px-4 py-3 text-zinc-300">{c.leads_enriched}</td>
                  <td className="px-4 py-3 text-zinc-300">{c.emails_sent}</td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/campaigns/${c.id}?client_id=${client.id}`}
                      className="flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300 transition-colors"
                    >
                      Run <ChevronRight className="w-3 h-3" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <CreateCampaignModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={handleCreated}
      />
    </div>
  );
}
