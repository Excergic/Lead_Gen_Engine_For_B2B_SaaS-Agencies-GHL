"use client";

import { useEffect, useState } from "react";
import { Loader2, X } from "lucide-react";
import { api } from "@/lib/api";
import type { Client, ICPTemplate } from "@/lib/types";

const ICP_OPTIONS: { value: ICPTemplate; label: string; hint: string }[] = [
  {
    value: "outbound_agencies",
    label: "Marketing / outbound agencies",
    hint: "5–10 person agencies, $25K+ MRR",
  },
  {
    value: "saas_founders",
    label: "B2B SaaS founders",
    hint: "Revenue pressure or scaling GTM",
  },
  {
    value: "ghl_saaspreneurs",
    label: "GHL / SaaS entrepreneurs",
    hint: "High-ticket SaaS operators",
  },
  {
    value: "custom",
    label: "All ICPs",
    hint: "Run discover across every segment",
  },
];

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (clientId: string, campaignId: string) => void;
}

export default function CreateCampaignModal({ open, onClose, onCreated }: Props) {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState<string>("");
  const [newClientName, setNewClientName] = useState("");
  const [campaignName, setCampaignName] = useState("");
  const [icpTemplate, setIcpTemplate] = useState<ICPTemplate>("outbound_agencies");
  const [loadingClients, setLoadingClients] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const useNewClient = clients.length === 0 || clientId === "__new__";

  useEffect(() => {
    if (!open) return;
    setError(null);
    setCampaignName("");
    setNewClientName("");
    setLoadingClients(true);
    api.clients
      .list()
      .then((page) => {
        setClients(page.items);
        setClientId(page.items.length ? page.items[0].id : "__new__");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load clients"))
      .finally(() => setLoadingClients(false));
  }, [open]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const name = campaignName.trim();
    if (!name) {
      setError("Campaign name is required");
      return;
    }

    setSubmitting(true);
    try {
      let resolvedClientId = clientId;
      if (useNewClient) {
        const clientName = newClientName.trim();
        if (!clientName) {
          setError("Client name is required");
          setSubmitting(false);
          return;
        }
        const client = await api.clients.create({ name: clientName });
        resolvedClientId = client.id;
      }

      const icp = await api.icp.create(resolvedClientId, {
        name: `${name} ICP`,
        icp_template: icpTemplate,
        is_primary: true,
      });

      const campaign = await api.campaigns.create(resolvedClientId, {
        name,
        icp_profile_id: icp.id,
        status: "draft",
      });

      onCreated(resolvedClientId, campaign.id);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create campaign");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
      <div className="w-full max-w-md rounded-xl border border-zinc-800 bg-zinc-950 shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
          <h2 className="text-sm font-semibold text-zinc-100">New Campaign</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {loadingClients ? (
            <div className="flex items-center gap-2 text-sm text-zinc-500 py-4">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading…
            </div>
          ) : (
            <>
              {clients.length > 0 && (
                <label className="block">
                  <span className="text-xs text-zinc-500 block mb-1">Client</span>
                  <select
                    value={clientId}
                    onChange={(e) => setClientId(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-violet-500"
                  >
                    {clients.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name}
                      </option>
                    ))}
                    <option value="__new__">+ New client</option>
                  </select>
                </label>
              )}

              {useNewClient && (
                <label className="block">
                  <span className="text-xs text-zinc-500 block mb-1">Client name</span>
                  <input
                    type="text"
                    value={newClientName}
                    onChange={(e) => setNewClientName(e.target.value)}
                    placeholder="Acme Outbound"
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-violet-500"
                  />
                </label>
              )}

              <label className="block">
                <span className="text-xs text-zinc-500 block mb-1">Campaign name</span>
                <input
                  type="text"
                  value={campaignName}
                  onChange={(e) => setCampaignName(e.target.value)}
                  placeholder="Agency outreach — March"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:outline-none focus:border-violet-500"
                  autoFocus={!useNewClient}
                />
              </label>

              <label className="block">
                <span className="text-xs text-zinc-500 block mb-1">Target ICP</span>
                <select
                  value={icpTemplate}
                  onChange={(e) => setIcpTemplate(e.target.value as ICPTemplate)}
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-violet-500"
                >
                  {ICP_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-zinc-600 mt-1">
                  {ICP_OPTIONS.find((o) => o.value === icpTemplate)?.hint}
                </p>
              </label>
            </>
          )}

          {error && (
            <p className="text-xs text-rose-400 bg-rose-500/10 border border-rose-800/50 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-2 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || loadingClients}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Creating…
                </>
              ) : (
                "Create & run setup"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
