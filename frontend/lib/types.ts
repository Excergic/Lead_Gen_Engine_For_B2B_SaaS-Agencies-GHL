// ── Clients & Campaigns ──────────────────────────────────────────────────────

export type CampaignStatus = "draft" | "active" | "paused" | "completed" | "archived";
export type ICPTemplate = "saas_founders" | "outbound_agencies" | "ghl_saaspreneurs" | "custom";
export type LeadChannel = "linkedin" | "x" | "reddit";

export interface Client {
  id: string;
  name: string;
  industry: string | null;
  website: string | null;
  created_at: string;
}

export interface Campaign {
  id: string;
  client_id: string;
  name: string;
  status: CampaignStatus;
  icp_template: ICPTemplate;
  target_region: string | null;
  leads_target: number;
  leads_discovered: number;
  leads_enriched: number;
  emails_sent: number;
  emails_replied: number;
  created_at: string;
  updated_at: string;
}

export interface ClientDefinition {
  id: string;
  client_id: string;
  product_description: string;
  value_proposition: string;
  pain_points: string[];
  calendar_url: string | null;
  created_at: string;
  updated_at: string;
}

// ── Leads ────────────────────────────────────────────────────────────────────

export interface Lead {
  id: string;
  campaign_id: string | null;
  channel: LeadChannel;
  icp_id: string;
  contact_name: string | null;
  job_title: string | null;
  company_name: string | null;
  company_domain: string | null;
  industry: string | null;
  email: string | null;
  email_verified: boolean;
  phone: string | null;
  profile_link: string | null;
  source_url: string;
  status: string;
  lead_score: number;
  lead_score_reason: string | null;
  needs_human_review: boolean;
  enrichment_confidence: number;
  discovered_at: string | null;
  enriched_at: string | null;
}

export interface EnrichedLead {
  id: string;
  lead_id: string;
  company_name: string;
  website: string | null;
  contact_name: string | null;
  contact_title: string | null;
  email: string | null;
  linkedin_url: string | null;
  enriched_at: string;
}

// ── Outreach Drafts (HITL) ───────────────────────────────────────────────────

export type DraftStatus = "pending_review" | "approved" | "rejected" | "sent" | "bounced";

export interface OutreachDraft {
  id: string;
  lead_id: string;
  campaign_id: string | null;
  contact_name: string;
  company_name: string;
  email: string | null;
  subject: string;
  body: string;
  hook: string | null;
  signal_used: string | null;
  status: DraftStatus;
  created_at: string;
  updated_at: string;
}

// ── Campaign Run ─────────────────────────────────────────────────────────────

export interface CampaignRunRequest {
  max_results?: number;
  enrich_limit?: number;
  personalize_limit?: number;
  run_discover?: boolean;
  run_enrich?: boolean;
  run_personalize?: boolean;
}

export interface CampaignRunResponse {
  run_id: string;
  campaign_id: string;
  campaign_status: CampaignStatus;
  leads_discovered: number;
  leads_enriched: number;
  drafts_queued: number;
  errors: string[];
  message: string;
}

// ── Outreach Send ────────────────────────────────────────────────────────────

export interface OutreachSendResponse {
  draft: Record<string, unknown>;
  send_result: Record<string, unknown>;
}

// ── Email / SMTP ─────────────────────────────────────────────────────────────

export interface EmailConfigResponse {
  dry_run: boolean;
  smtp_configured: boolean;
  from_address: string | null;
  from_name: string | null;
}

// ── Paginated lists ──────────────────────────────────────────────────────────

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
