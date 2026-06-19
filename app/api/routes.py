from uuid import UUID

from fastapi import APIRouter, Depends
from supabase import Client

from app.api.deps import verify_api_key
from app.db.supabase import get_supabase_client
from app.models.schemas import (
    CampaignCreate,
    CampaignMetricsUpdate,
    CampaignResponse,
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
    ICPProfileCreate,
    ICPProfileResponse,
    ICPProfileUpdate,
    Stage1BundleResponse,
)
from app.services.campaigns import CampaignService, DashboardService
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
