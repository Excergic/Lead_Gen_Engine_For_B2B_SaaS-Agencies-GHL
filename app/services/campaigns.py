from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

from app.models.schemas import (
    CampaignCreate,
    CampaignMetricsUpdate,
    CampaignRates,
    CampaignResponse,
    CampaignStatus,
    CampaignSummary,
    CampaignUpdate,
    ClientDashboardResponse,
    ClientDashboardTotals,
    DailyMetricsResponse,
    DailyMetricsUpsert,
)


class NotFoundError(HTTPException):
    def __init__(self, resource: str, resource_id: UUID | str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} '{resource_id}' not found",
        )


def _row_to_model(model_cls: type, row: dict[str, Any]):
    return model_cls.model_validate(row)


def _compute_rates(
    emails_sent: int,
    emails_opened: int,
    emails_replied: int,
    positive_replies: int,
    meetings_booked: int,
) -> CampaignRates:
    def pct(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator * 100, 2)

    return CampaignRates(
        email_open_rate_pct=pct(emails_opened, emails_sent),
        email_reply_rate_pct=pct(emails_replied, emails_sent),
        meeting_conversion_rate_pct=pct(meetings_booked, emails_sent),
        positive_reply_rate_pct=pct(positive_replies, emails_replied),
    )


def _to_summary(row: dict[str, Any]) -> CampaignSummary:
    campaign = _row_to_model(CampaignResponse, row)
    rates = _compute_rates(
        campaign.emails_sent,
        campaign.emails_opened,
        campaign.emails_replied,
        campaign.positive_replies,
        campaign.meetings_booked,
    )
    return CampaignSummary(**campaign.model_dump(), rates=rates)


class CampaignService:
    def __init__(self, db: Client) -> None:
        self._db = db

    def _ensure_client(self, client_id: UUID) -> None:
        row = self._db.table("clients").select("id").eq("id", str(client_id)).maybe_single().execute()
        if not row or not row.data:
            raise NotFoundError("client", client_id)

    def create(self, client_id: UUID, payload: CampaignCreate) -> CampaignResponse:
        self._ensure_client(client_id)
        insert_data = {
            "client_id": str(client_id),
            "name": payload.name,
            "status": payload.status.value,
        }
        if payload.icp_profile_id:
            insert_data["icp_profile_id"] = str(payload.icp_profile_id)

        row = self._db.table("campaigns").insert(insert_data).execute()
        return _row_to_model(CampaignResponse, row.data[0])

    def list_for_client(self, client_id: UUID) -> list[CampaignSummary]:
        self._ensure_client(client_id)
        rows = (
            self._db.table("campaigns")
            .select("*")
            .eq("client_id", str(client_id))
            .order("created_at", desc=True)
            .execute()
        )
        return [_to_summary(row) for row in rows.data]

    def get(self, client_id: UUID, campaign_id: UUID) -> CampaignSummary:
        row = self._get_row(client_id, campaign_id)
        return _to_summary(row)

    def update(self, client_id: UUID, campaign_id: UUID, payload: CampaignUpdate) -> CampaignSummary:
        self._get_row(client_id, campaign_id)
        updates = payload.model_dump(exclude_unset=True)
        if "status" in updates and updates["status"] is not None:
            updates["status"] = updates["status"].value
        if "icp_profile_id" in updates and updates["icp_profile_id"] is not None:
            updates["icp_profile_id"] = str(updates["icp_profile_id"])
        if "started_at" in updates and updates["started_at"] is not None:
            updates["started_at"] = updates["started_at"].isoformat()
        if "ended_at" in updates and updates["ended_at"] is not None:
            updates["ended_at"] = updates["ended_at"].isoformat()

        row = (
            self._db.table("campaigns")
            .update(updates)
            .eq("id", str(campaign_id))
            .eq("client_id", str(client_id))
            .execute()
        )
        return _to_summary(row.data[0])

    def update_metrics(
        self, client_id: UUID, campaign_id: UUID, payload: CampaignMetricsUpdate
    ) -> CampaignSummary:
        self._get_row(client_id, campaign_id)
        updates = payload.model_dump(exclude_unset=True)
        row = (
            self._db.table("campaigns")
            .update(updates)
            .eq("id", str(campaign_id))
            .eq("client_id", str(client_id))
            .execute()
        )
        return _to_summary(row.data[0])

    def upsert_daily_metrics(
        self, client_id: UUID, campaign_id: UUID, payload: DailyMetricsUpsert
    ) -> DailyMetricsResponse:
        self._get_row(client_id, campaign_id)
        metric_date = payload.metric_date.isoformat()
        data = payload.model_dump(exclude={"metric_date"})
        data["campaign_id"] = str(campaign_id)
        data["metric_date"] = metric_date

        existing = (
            self._db.table("campaign_daily_metrics")
            .select("id")
            .eq("campaign_id", str(campaign_id))
            .eq("metric_date", metric_date)
            .maybe_single()
            .execute()
        )
        if existing.data:
            update_data = {k: v for k, v in data.items() if k != "campaign_id"}
            row = (
                self._db.table("campaign_daily_metrics")
                .update(update_data)
                .eq("id", existing.data["id"])
                .execute()
            )
        else:
            row = self._db.table("campaign_daily_metrics").insert(data).execute()
        return _row_to_model(DailyMetricsResponse, row.data[0])

    def list_daily_metrics(
        self, client_id: UUID, campaign_id: UUID, days: int = 30
    ) -> list[DailyMetricsResponse]:
        self._get_row(client_id, campaign_id)
        since = (date.today() - timedelta(days=days)).isoformat()
        rows = (
            self._db.table("campaign_daily_metrics")
            .select("*")
            .eq("campaign_id", str(campaign_id))
            .gte("metric_date", since)
            .order("metric_date")
            .execute()
        )
        return [_row_to_model(DailyMetricsResponse, row) for row in rows.data]

    def _get_row(self, client_id: UUID, campaign_id: UUID) -> dict[str, Any]:
        row = (
            self._db.table("campaigns")
            .select("*")
            .eq("id", str(campaign_id))
            .eq("client_id", str(client_id))
            .maybe_single()
            .execute()
        )
        if not row.data:
            raise NotFoundError("campaign", campaign_id)
        return row.data


class DashboardService:
    def __init__(self, db: Client) -> None:
        self._db = db
        self._campaigns = CampaignService(db)

    def get_client_dashboard(self, client_id: UUID, trend_days: int = 30) -> ClientDashboardResponse:
        campaigns = self._campaigns.list_for_client(client_id)
        active_campaigns = sum(1 for c in campaigns if c.status == CampaignStatus.ACTIVE)

        total_emails_sent = sum(c.emails_sent for c in campaigns)
        total_emails_replied = sum(c.emails_replied for c in campaigns)
        total_positive = sum(c.positive_replies for c in campaigns)
        total_meetings_booked = sum(c.meetings_booked for c in campaigns)
        total_meetings_held = sum(c.meetings_held for c in campaigns)

        totals = ClientDashboardTotals(
            active_campaigns=active_campaigns,
            total_emails_sent=total_emails_sent,
            total_emails_replied=total_emails_replied,
            total_positive_replies=total_positive,
            total_meetings_booked=total_meetings_booked,
            total_meetings_held=total_meetings_held,
            email_reply_rate_pct=_compute_rates(
                total_emails_sent, 0, total_emails_replied, total_positive, total_meetings_booked
            ).email_reply_rate_pct,
            meeting_conversion_rate_pct=_compute_rates(
                total_emails_sent, 0, total_emails_replied, total_positive, total_meetings_booked
            ).meeting_conversion_rate_pct,
        )

        since = (date.today() - timedelta(days=trend_days)).isoformat()
        campaign_ids = [str(c.id) for c in campaigns]
        daily_trend: list[DailyMetricsResponse] = []
        if campaign_ids:
            rows = (
                self._db.table("campaign_daily_metrics")
                .select("*")
                .in_("campaign_id", campaign_ids)
                .gte("metric_date", since)
                .order("metric_date")
                .execute()
            )
            daily_trend = [_row_to_model(DailyMetricsResponse, row) for row in rows.data]

        return ClientDashboardResponse(
            client_id=client_id,
            totals=totals,
            campaigns=campaigns,
            daily_trend=daily_trend,
        )
