import type { Campaign, Client, ICPTemplate } from "./types";

/** Raw shapes returned by the FastAPI backend (snake_case, different field names). */

export interface BackendClient {
  id: string;
  name: string;
  company_name: string | null;
  contact_email: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface BackendCampaign {
  id: string;
  client_id: string;
  icp_profile_id: string | null;
  name: string;
  status: string;
  prospects_discovered: number;
  prospects_enriched: number;
  prospects_contacted: number;
  emails_sent: number;
  emails_replied: number;
  created_at: string;
  updated_at: string;
  icp_template?: ICPTemplate;
}

export function mapClient(row: BackendClient): Client {
  return {
    id: row.id,
    name: row.name,
    industry: row.company_name,
    website: null,
    created_at: row.created_at,
  };
}

export function mapCampaign(row: BackendCampaign): Campaign {
  return {
    id: row.id,
    client_id: row.client_id,
    name: row.name,
    status: row.status as Campaign["status"],
    icp_template: row.icp_template ?? "custom",
    target_region: null,
    leads_target: 0,
    leads_discovered: row.prospects_discovered ?? 0,
    leads_enriched: row.prospects_enriched ?? 0,
    emails_sent: row.emails_sent ?? 0,
    emails_replied: row.emails_replied ?? 0,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}
