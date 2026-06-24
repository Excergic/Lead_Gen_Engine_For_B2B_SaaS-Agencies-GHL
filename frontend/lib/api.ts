import type {
  Campaign,
  CampaignRunRequest,
  CampaignRunResponse,
  Client,
  ClientDefinition,
  EmailConfigResponse,
  EnrichedLead,
  ICPTemplate,
  Lead,
  OutreachDraft,
  OutreachSendResponse,
  Page,
} from "./types";
import {
  mapCampaign,
  mapClient,
  type BackendCampaign,
  type BackendClient,
} from "./mappers";

const BASE = "/api/proxy";

function asPage<T>(data: T[] | Page<T>): Page<T> {
  if (Array.isArray(data)) {
    return { items: data, total: data.length, limit: data.length, offset: 0 };
  }
  return data;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export interface CreateClientBody {
  name: string;
  company_name?: string | null;
  contact_email?: string | null;
}

export interface CreateCampaignBody {
  name: string;
  icp_profile_id?: string | null;
  status?: "draft" | "active" | "paused" | "completed";
}

export interface CreateIcpBody {
  name: string;
  icp_template: ICPTemplate;
  is_primary?: boolean;
}

export interface IcpProfile {
  id: string;
  client_id: string;
  name: string;
  icp_template: ICPTemplate;
  is_primary: boolean;
}

export const api = {
  clients: {
    list: async () => {
      const rows = await req<BackendClient[]>("/clients");
      return asPage(rows.map(mapClient));
    },
    get: async (id: string) => mapClient(await req<BackendClient>(`/clients/${id}`)),
    create: async (body: CreateClientBody) =>
      mapClient(await req<BackendClient>("/clients", { method: "POST", body: JSON.stringify(body) })),
  },

  icp: {
    create: (clientId: string, body: CreateIcpBody) =>
      req<IcpProfile>(`/clients/${clientId}/icp-profiles`, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    list: (clientId: string) =>
      req<IcpProfile[]>(`/clients/${clientId}/icp-profiles`),
  },

  definition: {
    get: (clientId: string) =>
      req<ClientDefinition | null>(`/clients/${clientId}/definition`),
    upsert: (clientId: string, body: Partial<ClientDefinition>) =>
      req<ClientDefinition>(`/clients/${clientId}/definition`, {
        method: "PUT",
        body: JSON.stringify(body),
      }),
  },

  campaigns: {
    list: async (clientId: string) => {
      const rows = await req<BackendCampaign[]>(`/clients/${clientId}/campaigns`);
      const icps = await req<IcpProfile[]>(`/clients/${clientId}/icp-profiles`).catch(() => []);
      const icpById = Object.fromEntries(icps.map((i) => [i.id, i.icp_template]));
      return asPage(
        rows.map((r) =>
          mapCampaign({
            ...r,
            icp_template: r.icp_profile_id ? icpById[r.icp_profile_id] : undefined,
          })
        )
      );
    },
    get: async (clientId: string, campaignId: string) => {
      const row = await req<BackendCampaign>(`/clients/${clientId}/campaigns/${campaignId}`);
      let icp_template: ICPTemplate | undefined;
      if (row.icp_profile_id) {
        const icps = await req<IcpProfile[]>(`/clients/${clientId}/icp-profiles`).catch(() => []);
        icp_template = icps.find((i) => i.id === row.icp_profile_id)?.icp_template;
      }
      return mapCampaign({ ...row, icp_template });
    },
    create: async (clientId: string, body: CreateCampaignBody) =>
      mapCampaign(await req<BackendCampaign>(`/clients/${clientId}/campaigns`, {
        method: "POST",
        body: JSON.stringify(body),
      })),
    update: async (clientId: string, campaignId: string, body: Partial<CreateCampaignBody>) =>
      mapCampaign(
        await req<BackendCampaign>(`/clients/${clientId}/campaigns/${campaignId}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        })
      ),
    run: (clientId: string, campaignId: string, body: CampaignRunRequest) =>
      req<CampaignRunResponse>(
        `/clients/${clientId}/campaigns/${campaignId}/run`,
        { method: "POST", body: JSON.stringify(body) }
      ),
  },

  leads: {
    list: (campaignId: string) =>
      req<Lead[]>(`/campaigns/${campaignId}/leads`),
    listAll: (params?: { client_id?: string; campaign_id?: string; channel?: string; min_score?: number }) => {
      const qs = new URLSearchParams();
      if (params?.client_id) qs.set("client_id", params.client_id);
      if (params?.campaign_id) qs.set("campaign_id", params.campaign_id);
      if (params?.channel) qs.set("channel", params.channel);
      if (params?.min_score !== undefined) qs.set("min_score", String(params.min_score));
      const query = qs.toString();
      return req<Lead[]>(`/leads${query ? `?${query}` : ""}`);
    },
  },

  enriched: {
    list: (campaignId: string) =>
      req<Page<EnrichedLead>>(`/campaigns/${campaignId}/enriched`),
  },

  outreach: {
    listPending: (limit = 50) =>
      req<OutreachDraft[]>(`/outreach/pending?limit=${limit}`),
    get: (id: string) => req<OutreachDraft>(`/outreach/${id}`),
    update: (
      id: string,
      body: { subject?: string; body?: string; hook?: string; email?: string | null }
    ) =>
      req<OutreachDraft>(`/outreach/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    approve: (id: string) =>
      req<OutreachDraft>(`/outreach/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ reviewed_by: "operator" }),
      }),
    reject: (id: string, reason = "") =>
      req<OutreachDraft>(`/outreach/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason, reviewed_by: "operator" }),
      }),
    send: (id: string) =>
      req<OutreachSendResponse>(`/outreach/${id}/send`, { method: "POST" }),
  },

  email: {
    config: () => req<EmailConfigResponse>("/email/config"),
    test: () =>
      req<{ ok: boolean; message: string }>("/email/test", { method: "POST" }),
  },
};
