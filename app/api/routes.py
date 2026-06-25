from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from supabase import Client

from app.api.deps import verify_api_key
from app.config import Settings, get_settings
from app.db.supabase import get_supabase_client
from app.models.schemas import (
    CampaignCreate,
    CampaignLeadResponse,
    CampaignMetricsUpdate,
    CampaignResponse,
    CampaignRunAcceptedResponse,
    CampaignRunRequest,
    CampaignRunResponse,
    CampaignSummary,
    CampaignUpdate,
    CaseStudyCreate,
    CaseStudyResponse,
    CaseStudyUpdate,
    ClientCreate,
    ClientDashboardResponse,
    ClientResponse,
    ClientUpdate,
    DailyMetricsResponse,
    DailyMetricsUpsert,
    DefinitionResponse,
    DefinitionUpsert,
    DiscoverRunRequest,
    DiscoverRunResponse,
    EnrichRunRequest,
    EnrichRunResponse,
    OutreachApproveRequest,
    OutreachDraftResponse,
    OutreachRejectRequest,
    OutreachSendResponse,
    OutreachUpdateRequest,
    PersonalizeRunRequest,
    PersonalizeRunResponse,
    ICPProfileCreate,
    ICPProfileResponse,
    ICPProfileUpdate,
    Stage1BundleResponse,
)
from app.services.campaign_runner import (
    CampaignNotFound,
    CampaignNotRunnable,
    CampaignRunNotFound,
    CampaignRunnerService,
)
from app.services.campaigns import CampaignService, DashboardService
from app.services.discover import build_discover_service
from app.services.enrich import EnrichService
from app.services.personalize import PersonalizeService
from app.services.outreach_hitl import OutreachHitlService
from app.services.stage1 import (
    CaseStudyService,
    ClientService,
    DefinitionService,
    ICPProfileService,
    Stage1Service,
)

public_router = APIRouter(prefix="/api/v1")
router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_api_key)])


def _clients(db: Client = Depends(get_supabase_client)) -> ClientService:
    return ClientService(db)


def _definitions(db: Client = Depends(get_supabase_client)) -> DefinitionService:
    return DefinitionService(db)


def _icp(db: Client = Depends(get_supabase_client)) -> ICPProfileService:
    return ICPProfileService(db)


def _case_studies(db: Client = Depends(get_supabase_client)) -> CaseStudyService:
    return CaseStudyService(db)


def _stage1(db: Client = Depends(get_supabase_client)) -> Stage1Service:
    return Stage1Service(db)


def _campaigns(db: Client = Depends(get_supabase_client)) -> CampaignService:
    return CampaignService(db)


def _dashboard(db: Client = Depends(get_supabase_client)) -> DashboardService:
    return DashboardService(db)


@public_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "stage": "define"}


@router.post("/clients", response_model=ClientResponse, status_code=201)
def create_client(payload: ClientCreate, service: ClientService = Depends(_clients)) -> ClientResponse:
    return service.create(payload)


@router.get("/clients", response_model=list[ClientResponse])
def list_clients(service: ClientService = Depends(_clients)) -> list[ClientResponse]:
    return service.list_clients()


@router.get("/clients/{client_id}", response_model=ClientResponse)
def get_client(client_id: UUID, service: ClientService = Depends(_clients)) -> ClientResponse:
    return service.get(client_id)


@router.patch("/clients/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    service: ClientService = Depends(_clients),
) -> ClientResponse:
    return service.update(client_id, payload)


@router.put("/clients/{client_id}/definition", response_model=DefinitionResponse)
def upsert_definition(
    client_id: UUID,
    payload: DefinitionUpsert,
    service: DefinitionService = Depends(_definitions),
) -> DefinitionResponse:
    return service.upsert(client_id, payload)


@router.get("/clients/{client_id}/definition", response_model=DefinitionResponse | None)
def get_definition(
    client_id: UUID,
    service: DefinitionService = Depends(_definitions),
) -> DefinitionResponse | None:
    return service.get_active(client_id)


@router.post("/clients/{client_id}/icp-profiles", response_model=ICPProfileResponse, status_code=201)
def create_icp_profile(
    client_id: UUID,
    payload: ICPProfileCreate,
    service: ICPProfileService = Depends(_icp),
) -> ICPProfileResponse:
    return service.create(client_id, payload)


@router.get("/clients/{client_id}/icp-profiles", response_model=list[ICPProfileResponse])
def list_icp_profiles(
    client_id: UUID,
    service: ICPProfileService = Depends(_icp),
) -> list[ICPProfileResponse]:
    return service.list_for_client(client_id)


@router.patch("/clients/{client_id}/icp-profiles/{icp_id}", response_model=ICPProfileResponse)
def update_icp_profile(
    client_id: UUID,
    icp_id: UUID,
    payload: ICPProfileUpdate,
    service: ICPProfileService = Depends(_icp),
) -> ICPProfileResponse:
    return service.update(client_id, icp_id, payload)


@router.post("/clients/{client_id}/case-studies", response_model=CaseStudyResponse, status_code=201)
def create_case_study(
    client_id: UUID,
    payload: CaseStudyCreate,
    service: CaseStudyService = Depends(_case_studies),
) -> CaseStudyResponse:
    return service.create(client_id, payload)


@router.get("/clients/{client_id}/case-studies", response_model=list[CaseStudyResponse])
def list_case_studies(
    client_id: UUID,
    service: CaseStudyService = Depends(_case_studies),
) -> list[CaseStudyResponse]:
    return service.list_for_client(client_id)


@router.patch("/clients/{client_id}/case-studies/{case_study_id}", response_model=CaseStudyResponse)
def update_case_study(
    client_id: UUID,
    case_study_id: UUID,
    payload: CaseStudyUpdate,
    service: CaseStudyService = Depends(_case_studies),
) -> CaseStudyResponse:
    return service.update(client_id, case_study_id, payload)


@router.get("/clients/{client_id}/stage1", response_model=Stage1BundleResponse)
def get_stage1_bundle(
    client_id: UUID,
    service: Stage1Service = Depends(_stage1),
) -> Stage1BundleResponse:
    return service.get_bundle(client_id)


@router.post("/clients/{client_id}/stage1/complete", response_model=Stage1BundleResponse)
def complete_stage1(
    client_id: UUID,
    service: Stage1Service = Depends(_stage1),
) -> Stage1BundleResponse:
    return service.complete(client_id)


@router.get("/clients/{client_id}/dashboard", response_model=ClientDashboardResponse)
def get_client_dashboard(
    client_id: UUID,
    trend_days: int = 30,
    service: DashboardService = Depends(_dashboard),
) -> ClientDashboardResponse:
    return service.get_client_dashboard(client_id, trend_days=trend_days)


@router.post("/clients/{client_id}/campaigns", response_model=CampaignResponse, status_code=201)
def create_campaign(
    client_id: UUID,
    payload: CampaignCreate,
    service: CampaignService = Depends(_campaigns),
) -> CampaignResponse:
    return service.create(client_id, payload)


@router.get("/clients/{client_id}/campaigns", response_model=list[CampaignSummary])
def list_campaigns(
    client_id: UUID,
    service: CampaignService = Depends(_campaigns),
) -> list[CampaignSummary]:
    return service.list_for_client(client_id)


@router.get("/clients/{client_id}/campaigns/{campaign_id}", response_model=CampaignSummary)
def get_campaign(
    client_id: UUID,
    campaign_id: UUID,
    service: CampaignService = Depends(_campaigns),
) -> CampaignSummary:
    return service.get(client_id, campaign_id)


@router.patch("/clients/{client_id}/campaigns/{campaign_id}", response_model=CampaignSummary)
def update_campaign(
    client_id: UUID,
    campaign_id: UUID,
    payload: CampaignUpdate,
    service: CampaignService = Depends(_campaigns),
) -> CampaignSummary:
    return service.update(client_id, campaign_id, payload)


@router.patch("/clients/{client_id}/campaigns/{campaign_id}/metrics", response_model=CampaignSummary)
def update_campaign_metrics(
    client_id: UUID,
    campaign_id: UUID,
    payload: CampaignMetricsUpdate,
    service: CampaignService = Depends(_campaigns),
) -> CampaignSummary:
    return service.update_metrics(client_id, campaign_id, payload)


@router.put(
    "/clients/{client_id}/campaigns/{campaign_id}/daily-metrics",
    response_model=DailyMetricsResponse,
)
def upsert_daily_metrics(
    client_id: UUID,
    campaign_id: UUID,
    payload: DailyMetricsUpsert,
    service: CampaignService = Depends(_campaigns),
) -> DailyMetricsResponse:
    return service.upsert_daily_metrics(client_id, campaign_id, payload)


@router.get(
    "/clients/{client_id}/campaigns/{campaign_id}/daily-metrics",
    response_model=list[DailyMetricsResponse],
)
def list_daily_metrics(
    client_id: UUID,
    campaign_id: UUID,
    days: int = 30,
    service: CampaignService = Depends(_campaigns),
) -> list[DailyMetricsResponse]:
    return service.list_daily_metrics(client_id, campaign_id, days=days)


def _engine_deps(settings: Settings = Depends(get_settings), db: Client = Depends(get_supabase_client)):
    if not settings.perplexity_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PERPLEXITY_API_KEY not configured",
        )
    from app.engine.factory import build_lead_gen_engine
    from app.tools.email.smtp_sender import smtp_sender_from_settings

    return build_lead_gen_engine(
        perplexity_api_key=settings.perplexity_api_key.get_secret_value(),
        hunter_api_key=settings.hunter_api_key.get_secret_value() if settings.hunter_api_key else None,
        apollo_api_key=settings.apollo_api_key.get_secret_value() if settings.apollo_api_key else None,
        audit_jsonl_path=Path(settings.discover_audit_jsonl),
        outreach_queue_jsonl=Path(settings.outreach_queue_jsonl),
        db=db,
        email_dry_run=settings.email_dry_run,
        smtp=smtp_sender_from_settings(settings),
    )


def _discover_service(
    settings: Settings = Depends(get_settings),
    db: Client = Depends(get_supabase_client),
):
    if not settings.perplexity_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PERPLEXITY_API_KEY not configured",
        )
    return build_discover_service(
        perplexity_api_key=settings.perplexity_api_key.get_secret_value(),
        audit_jsonl_path=Path(settings.discover_audit_jsonl),
        leads_jsonl_path=Path(settings.discover_leads_jsonl),
        db=db,
    )


def _enrich_service(
    settings: Settings = Depends(get_settings),
    db: Client = Depends(get_supabase_client),
    engine=Depends(_engine_deps),
):
    return EnrichService(
        engine,
        leads_jsonl_path=Path(settings.discover_leads_jsonl),
        db=db,
    )


def _hitl_service(
    settings: Settings = Depends(get_settings),
    db: Client = Depends(get_supabase_client),
    engine=Depends(_engine_deps),
) -> OutreachHitlService:
    return OutreachHitlService(engine, engine.queue, db=db)


def _personalize_service(
    settings: Settings = Depends(get_settings),
    db: Client = Depends(get_supabase_client),
    engine=Depends(_engine_deps),
    hitl: OutreachHitlService = Depends(_hitl_service),
) -> PersonalizeService:
    return PersonalizeService(
        engine,
        hitl,
        leads_jsonl_path=Path(settings.discover_leads_jsonl),
        db=db,
    )


@router.get("/tools")
def list_tools(service=Depends(_discover_service)) -> dict[str, Any]:
    registry = service._engine.tooling.registry
    policy = service._engine.tooling.policy
    from app.tools.policy import AgentRole

    return {
        "tools": registry.list_tools(),
        "openai_schemas": registry.openai_tools(),
        "discover_agent_allowed": policy.allowed_tools(AgentRole.DISCOVER_AGENT),
        "enrich_agent_allowed": policy.allowed_tools(AgentRole.ENRICH_AGENT),
        "outreach_agent_allowed": policy.allowed_tools(AgentRole.OUTREACH_AGENT),
    }


@router.post("/discover/run", response_model=DiscoverRunResponse)
def run_discover(
    payload: DiscoverRunRequest,
    service=Depends(_discover_service),
) -> DiscoverRunResponse:
    from app.tools.models import ICPId

    icp_ids = [ICPId(i) for i in payload.icp_ids] if payload.icp_ids else None
    result = service.run(
        max_results=payload.max_results,
        icp_ids=icp_ids,
        persist=payload.persist,
    )
    return DiscoverRunResponse(**result)


@router.post("/enrich/run", response_model=EnrichRunResponse)
def run_enrich(
    payload: EnrichRunRequest,
    service: EnrichService = Depends(_enrich_service),
) -> EnrichRunResponse:
    result = service.run(limit=payload.limit, persist=payload.persist)
    return EnrichRunResponse(**result)


@router.post("/personalize/run", response_model=PersonalizeRunResponse)
def run_personalize(
    payload: PersonalizeRunRequest,
    service: PersonalizeService = Depends(_personalize_service),
) -> PersonalizeRunResponse:
    result = service.run(
        limit=payload.limit,
        client_id=payload.client_id,
        lead_ids=payload.lead_ids,
    )
    return PersonalizeRunResponse(**result)


@router.get("/outreach/pending", response_model=list[OutreachDraftResponse])
def list_pending_outreach(
    limit: int = 50,
    hitl: OutreachHitlService = Depends(_hitl_service),
) -> list[OutreachDraftResponse]:
    return [OutreachDraftResponse(**d) for d in hitl.list_pending(limit=limit)]


@router.get("/outreach/{draft_id}", response_model=OutreachDraftResponse)
def get_outreach_draft(
    draft_id: str,
    hitl: OutreachHitlService = Depends(_hitl_service),
) -> OutreachDraftResponse:
    try:
        return OutreachDraftResponse(**hitl.get_draft(draft_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/outreach/{draft_id}", response_model=OutreachDraftResponse)
def update_outreach_draft(
    draft_id: str,
    payload: OutreachUpdateRequest,
    hitl: OutreachHitlService = Depends(_hitl_service),
) -> OutreachDraftResponse:
    """Edit subject, body, hook, or email. Approved drafts return to pending_review."""
    try:
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(status_code=400, detail="No fields to update")
        return OutreachDraftResponse(**hitl.update(draft_id, **data))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/outreach/{draft_id}/approve", response_model=OutreachDraftResponse)
def approve_outreach(
    draft_id: str,
    payload: OutreachApproveRequest,
    hitl: OutreachHitlService = Depends(_hitl_service),
) -> OutreachDraftResponse:
    try:
        return OutreachDraftResponse(**hitl.approve(draft_id, reviewed_by=payload.reviewed_by))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/outreach/{draft_id}/reject", response_model=OutreachDraftResponse)
def reject_outreach(
    draft_id: str,
    payload: OutreachRejectRequest,
    hitl: OutreachHitlService = Depends(_hitl_service),
) -> OutreachDraftResponse:
    try:
        return OutreachDraftResponse(
            **hitl.reject(draft_id, reason=payload.reason, reviewed_by=payload.reviewed_by)
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/outreach/{draft_id}/send", response_model=OutreachSendResponse)
def send_outreach(
    draft_id: str,
    hitl: OutreachHitlService = Depends(_hitl_service),
) -> OutreachSendResponse:
    """Explicit human-triggered send. Draft must be approved first."""
    try:
        result = hitl.send(draft_id)
        return OutreachSendResponse(**result)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Email connection
# ---------------------------------------------------------------------------

@router.get("/email/config")
def get_email_config(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """Return current email configuration (no secrets exposed)."""
    from app.tools.email.smtp_sender import smtp_sender_from_settings

    smtp = smtp_sender_from_settings(settings)
    return {
        "email_dry_run": settings.email_dry_run,
        "smtp_configured": smtp is not None,
        "smtp_host": settings.smtp_host,
        "smtp_port": settings.smtp_port,
        "smtp_use_tls": settings.smtp_use_tls,
        "smtp_use_ssl": settings.smtp_use_ssl,
        "from_email": settings.email_from_address,
        "from_name": settings.email_from_name,
        "reply_to": settings.email_reply_to,
        "ready_to_send": not settings.email_dry_run and smtp is not None,
        "hint": (
            "Set EMAIL_DRY_RUN=false and configure SMTP_* + EMAIL_FROM_ADDRESS to enable live sending."
            if settings.email_dry_run or smtp is None
            else "Live email sending is enabled."
        ),
    }


@router.post("/email/test")
def test_email_connection(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    """
    Verify SMTP credentials without sending anything.
    Returns {"ok": true} on success or 503 with error detail.
    """
    from app.tools.email.smtp_sender import SmtpConnectionError, smtp_sender_from_settings

    smtp = smtp_sender_from_settings(settings)
    if not smtp:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "SMTP not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, "
                "EMAIL_FROM_ADDRESS in your .env file."
            ),
        )
    try:
        return smtp.test_connection()
    except SmtpConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Campaign running
# ---------------------------------------------------------------------------

def _campaign_runner(
    db: Client = Depends(get_supabase_client),
    engine=Depends(_engine_deps),
) -> CampaignRunnerService:
    return CampaignRunnerService(engine=engine, db=db)


@router.post(
    "/clients/{client_id}/campaigns/{campaign_id}/run",
    response_model=CampaignRunAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_campaign(
    client_id: UUID,
    campaign_id: UUID,
    payload: CampaignRunRequest,
    background_tasks: BackgroundTasks,
    runner: CampaignRunnerService = Depends(_campaign_runner),
) -> CampaignRunAcceptedResponse:
    """
    Queue the full pipeline (discover → enrich → personalize) for one campaign.

    Returns immediately (202). Poll GET .../runs/{run_id} or campaign status until
    the run completes — large batches can take several minutes.
    """
    try:
        accepted = runner.accept_run(client_id, campaign_id, request=payload)
        background_tasks.add_task(
            runner.execute_run,
            client_id,
            campaign_id,
            request=payload,
            run_id=accepted.run_id,
        )
        return accepted
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CampaignNotRunnable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/clients/{client_id}/campaigns/{campaign_id}/runs/{run_id}",
    response_model=CampaignRunResponse,
)
def get_campaign_run(
    client_id: UUID,
    campaign_id: UUID,
    run_id: str,
    runner: CampaignRunnerService = Depends(_campaign_runner),
) -> CampaignRunResponse:
    """Poll run progress and final metrics after POST .../run (202)."""
    try:
        return runner.get_run(client_id, campaign_id, run_id)
    except CampaignNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CampaignRunNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Leads — cross-channel read endpoints
# ---------------------------------------------------------------------------

_LEAD_TABLES = {
    "linkedin": "linkedin_leads",
    "x": "x_leads",
    "reddit": "reddit_leads",
}


def _row_to_lead_response(row: dict[str, Any], channel: str) -> CampaignLeadResponse:
    return CampaignLeadResponse(
        id=str(row["id"]),
        campaign_id=str(row["campaign_id"]) if row.get("campaign_id") else None,
        channel=channel,
        icp_id=row.get("icp_id", ""),
        contact_name=row.get("contact_name"),
        job_title=row.get("job_title") or row.get("title"),
        company_name=row.get("company_name"),
        company_domain=row.get("company_domain"),
        industry=row.get("industry"),
        email=row.get("email"),
        email_verified=bool(row.get("email_verified")),
        phone=row.get("phone"),
        profile_link=row.get("profile_link"),
        source_url=row.get("source_url", ""),
        status=row.get("status", "discovered"),
        lead_score=int(row.get("lead_score") or 0),
        lead_score_reason=row.get("lead_score_reason"),
        needs_human_review=bool(row.get("needs_human_review")),
        enrichment_confidence=float(row.get("enrichment_confidence") or 0.0),
        discovered_at=row.get("discovered_at"),
        enriched_at=row.get("enriched_at"),
        signal_category=row.get("signal_category") or "other",
        signal_freshness_hours=row.get("signal_freshness_hours"),
    )


@router.get(
    "/campaigns/{campaign_id}/leads",
    response_model=list[CampaignLeadResponse],
)
def list_campaign_leads(
    campaign_id: UUID,
    channel: str | None = Query(default=None, description="Filter by channel: linkedin, x, reddit"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Client = Depends(get_supabase_client),
) -> list[CampaignLeadResponse]:
    """All leads (discovered + enriched) for a campaign, sorted by lead_score desc."""
    tables = {channel: _LEAD_TABLES[channel]} if channel and channel in _LEAD_TABLES else _LEAD_TABLES
    results: list[CampaignLeadResponse] = []
    for ch, table in tables.items():
        try:
            rows = (
                db.table(table)
                .select("*")
                .eq("campaign_id", str(campaign_id))
                .order("lead_score", desc=True)
                .limit(limit)
                .execute()
            )
            results.extend(_row_to_lead_response(r, ch) for r in rows.data)
        except Exception:
            pass
    results.sort(key=lambda l: l.lead_score, reverse=True)
    return results[:limit]


@router.get("/leads", response_model=list[CampaignLeadResponse])
def list_all_leads(
    client_id: UUID | None = Query(default=None),
    campaign_id: UUID | None = Query(default=None),
    channel: str | None = Query(default=None),
    min_score: int = Query(default=0, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=500),
    db: Client = Depends(get_supabase_client),
) -> list[CampaignLeadResponse]:
    """All leads across channels with optional filters."""
    tables = {channel: _LEAD_TABLES[channel]} if channel and channel in _LEAD_TABLES else _LEAD_TABLES
    results: list[CampaignLeadResponse] = []

    # Resolve campaign_ids for client filter
    campaign_ids: list[str] | None = None
    if client_id and not campaign_id:
        try:
            rows = db.table("campaigns").select("id").eq("client_id", str(client_id)).execute()
            campaign_ids = [str(r["id"]) for r in rows.data]
        except Exception:
            campaign_ids = []

    for ch, table in tables.items():
        try:
            q = db.table(table).select("*").gte("lead_score", min_score).order("lead_score", desc=True)
            if campaign_id:
                q = q.eq("campaign_id", str(campaign_id))
            elif campaign_ids is not None:
                if not campaign_ids:
                    continue
                q = q.in_("campaign_id", campaign_ids)
            rows = q.limit(limit).execute()
            results.extend(_row_to_lead_response(r, ch) for r in rows.data)
        except Exception:
            pass

    results.sort(key=lambda l: l.lead_score, reverse=True)
    return results[:limit]
