"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Play, AlertCircle, CheckCircle2, ChevronLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { Campaign, CampaignRunResponse } from "@/lib/types";

export default function CampaignDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const searchParams = useSearchParams();
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const clientId = searchParams.get("client_id") ?? "";

  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [runResult, setRunResult] = useState<CampaignRunResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Options for campaign run
  const [maxResults, setMaxResults] = useState(5);
  const [enrichLimit, setEnrichLimit] = useState(10);
  const [personalize, setPersonalize] = useState(true);

  useEffect(() => {
    params.then(({ id }) => setCampaignId(id));
  }, [params]);

  useEffect(() => {
    if (!campaignId || !clientId) return;
    api.campaigns.get(clientId, campaignId).then(setCampaign).catch((e) => {
      setError(e instanceof Error ? e.message : "Failed to load campaign");
    });
  }, [campaignId, clientId]);

  const canRun =
    !!campaign &&
    (campaign.status === "draft" || campaign.status === "paused") &&
    !running;

  async function runCampaign() {
    if (!campaignId || !clientId) return;
    setRunning(true);
    setError(null);
    setRunResult(null);
    try {
      const res = await api.campaigns.run(clientId, campaignId, {
        max_results: maxResults,
        enrich_limit: enrichLimit,
        personalize_limit: 3,
        run_discover: true,
        run_enrich: true,
        run_personalize: personalize,
      });
      setRunResult(res);
      const updated = await api.campaigns.get(clientId, campaignId);
      setCampaign(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <Link href="/campaigns" className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 mb-4 transition-colors">
        <ChevronLeft className="w-3 h-3" /> Campaigns
      </Link>

      {campaign ? (
        <>
          <PageHeader
            title={campaign.name}
            subtitle={`Campaign ID: ${campaign.id}`}
            action={<StatusBadge status={campaign.status} />}
          />

          {/* Stats */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            {[
              { label: "Leads", value: campaign.leads_discovered },
              { label: "Enriched", value: campaign.leads_enriched },
              { label: "Emails Sent", value: campaign.emails_sent },
            ].map(({ label, value }) => (
              <div key={label} className="rounded-lg border border-zinc-800/60 bg-zinc-900/40 px-4 py-3">
                <p className="text-xs text-zinc-500">{label}</p>
                <p className="text-xl font-semibold text-zinc-100 mt-0.5">{value}</p>
              </div>
            ))}
          </div>

          {/* Run panel */}
          <div className="rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-5 mb-6">
            <h2 className="text-sm font-medium text-zinc-200 mb-4">Run Campaign</h2>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <label className="block">
                <span className="text-xs text-zinc-500 block mb-1">Max leads to discover</span>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={maxResults}
                  onChange={(e) => setMaxResults(Number(e.target.value))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-violet-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-zinc-500 block mb-1">Enrich limit</span>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={enrichLimit}
                  onChange={(e) => setEnrichLimit(Number(e.target.value))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-violet-500"
                />
              </label>
            </div>

            <label className="flex items-center gap-2 mb-5 cursor-pointer">
              <input
                type="checkbox"
                checked={personalize}
                onChange={(e) => setPersonalize(e.target.checked)}
                className="rounded border-zinc-700 bg-zinc-800 text-violet-500 focus:ring-violet-500"
              />
              <span className="text-sm text-zinc-300">Generate outreach drafts (personalize)</span>
            </label>

            {!clientId && (
              <p className="text-xs text-amber-400 mb-4">
                Missing client_id in URL. Open this campaign from the Campaigns list.
              </p>
            )}

            {campaign.status === "active" && (
              <p className="text-xs text-amber-400 mb-4">Campaign is running…</p>
            )}

            {campaign.status === "completed" && (
              <p className="text-xs text-zinc-500 mb-4">This campaign is completed and cannot be re-run.</p>
            )}

            <button
              onClick={runCampaign}
              disabled={!canRun || !clientId}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
            >
              {running ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Running…</>
              ) : (
                <><Play className="w-4 h-4" /> Run Campaign</>
              )}
            </button>
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-rose-800/50 bg-rose-500/10 px-4 py-3 text-sm text-rose-400 mb-4">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          {runResult && (
            <div className="rounded-xl border border-emerald-800/50 bg-emerald-500/10 p-5">
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-medium text-emerald-400">Run complete</span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-sm">
                <div>
                  <p className="text-zinc-500 text-xs">Discovered</p>
                  <p className="text-zinc-200 font-semibold">{runResult.leads_discovered}</p>
                </div>
                <div>
                  <p className="text-zinc-500 text-xs">Enriched</p>
                  <p className="text-zinc-200 font-semibold">{runResult.leads_enriched}</p>
                </div>
                <div>
                  <p className="text-zinc-500 text-xs">Drafts Queued</p>
                  <p className="text-zinc-200 font-semibold">{runResult.drafts_queued}</p>
                </div>
              </div>
              {runResult.errors.length > 0 && (
                <ul className="mt-3 space-y-1">
                  {runResult.errors.map((e, i) => (
                    <li key={i} className="text-xs text-amber-400">⚠ {e}</li>
                  ))}
                </ul>
              )}
              {runResult.drafts_queued > 0 && (
                <Link href="/outreach" className="mt-3 inline-flex text-xs text-violet-400 hover:text-violet-300 underline transition-colors">
                  Review drafts in Outreach →
                </Link>
              )}
            </div>
          )}
        </>
      ) : (
        <div className="flex items-center gap-2 text-sm text-zinc-500">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading campaign…
        </div>
      )}
    </div>
  );
}
