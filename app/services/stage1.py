from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from supabase import Client

from app.models.schemas import (
    CaseStudyCreate,
    CaseStudyResponse,
    CaseStudyUpdate,
    ClientCreate,
    ClientResponse,
    ClientStatus,
    ClientUpdate,
    DefinitionResponse,
    DefinitionUpsert,
    ICPProfileCreate,
    ICPProfileResponse,
    ICPProfileUpdate,
    Stage1BundleResponse,
    Stage1Checklist,
)


class NotFoundError(HTTPException):
    def __init__(self, resource: str, resource_id: UUID | str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} '{resource_id}' not found",
        )


def _row_to_model(model_cls: type, row: dict[str, Any]):
    return model_cls.model_validate(row)


class ClientService:
    def __init__(self, db: Client) -> None:
        self._db = db

    def create(self, payload: ClientCreate) -> ClientResponse:
        row = (
            self._db.table("clients")
            .insert(
                {
                    "name": payload.name,
                    "company_name": payload.company_name,
                    "contact_email": str(payload.contact_email) if payload.contact_email else None,
                    "status": ClientStatus.ONBOARDING.value,
                }
            )
            .execute()
        )
        return _row_to_model(ClientResponse, row.data[0])

    def list_clients(self) -> list[ClientResponse]:
        rows = self._db.table("clients").select("*").order("created_at", desc=True).execute()
        return [_row_to_model(ClientResponse, row) for row in rows.data]

    def get(self, client_id: UUID) -> ClientResponse:
        row = self._db.table("clients").select("*").eq("id", str(client_id)).maybe_single().execute()
        if not row or not row.data:
            raise NotFoundError("client", client_id)
        return _row_to_model(ClientResponse, row.data)

    def update(self, client_id: UUID, payload: ClientUpdate) -> ClientResponse:
        self.get(client_id)
        updates = payload.model_dump(exclude_unset=True)
        if "contact_email" in updates and updates["contact_email"] is not None:
            updates["contact_email"] = str(updates["contact_email"])
        if "status" in updates and updates["status"] is not None:
            updates["status"] = updates["status"].value

        row = self._db.table("clients").update(updates).eq("id", str(client_id)).execute()
        return _row_to_model(ClientResponse, row.data[0])


class DefinitionService:
    def __init__(self, db: Client) -> None:
        self._db = db
        self._clients = ClientService(db)

    def get_active(self, client_id: UUID) -> DefinitionResponse | None:
        self._clients.get(client_id)
        row = (
            self._db.table("client_definitions")
            .select("*")
            .eq("client_id", str(client_id))
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        if not row or not row.data:
            return None
        return _row_to_model(DefinitionResponse, row.data)

    def upsert(self, client_id: UUID, payload: DefinitionUpsert) -> DefinitionResponse:
        self._clients.get(client_id)
        data = payload.model_dump(exclude_unset=True)
        if "calendar_url" in data and data["calendar_url"] is not None:
            data["calendar_url"] = str(data["calendar_url"])

        existing = self.get_active(client_id)
        if existing:
            row = (
                self._db.table("client_definitions")
                .update(data)
                .eq("id", str(existing.id))
                .execute()
            )
            definition = _row_to_model(DefinitionResponse, row.data[0])
        else:
            insert_data = {"client_id": str(client_id), **data}
            row = self._db.table("client_definitions").insert(insert_data).execute()
            definition = _row_to_model(DefinitionResponse, row.data[0])

        self._sync_definition_links(client_id, definition.id)
        return definition

    def _sync_definition_links(self, client_id: UUID, definition_id: UUID) -> None:
        self._db.table("icp_profiles").update({"definition_id": str(definition_id)}).eq(
            "client_id", str(client_id)
        ).is_("definition_id", "null").execute()
        self._db.table("case_studies").update({"definition_id": str(definition_id)}).eq(
            "client_id", str(client_id)
        ).is_("definition_id", "null").execute()


class ICPProfileService:
    def __init__(self, db: Client) -> None:
        self._db = db
        self._clients = ClientService(db)
        self._definitions = DefinitionService(db)

    def list_for_client(self, client_id: UUID) -> list[ICPProfileResponse]:
        self._clients.get(client_id)
        rows = (
            self._db.table("icp_profiles")
            .select("*")
            .eq("client_id", str(client_id))
            .order("is_primary", desc=True)
            .order("created_at")
            .execute()
        )
        return [_row_to_model(ICPProfileResponse, row) for row in rows.data]

    def create(self, client_id: UUID, payload: ICPProfileCreate) -> ICPProfileResponse:
        self._clients.get(client_id)
        definition = self._definitions.get_active(client_id)
        insert_data = payload.model_dump()
        insert_data["client_id"] = str(client_id)
        insert_data["icp_template"] = payload.icp_template.value
        if definition:
            insert_data["definition_id"] = str(definition.id)

        if payload.is_primary:
            self._clear_primary(client_id)

        row = self._db.table("icp_profiles").insert(insert_data).execute()
        return _row_to_model(ICPProfileResponse, row.data[0])

    def update(self, client_id: UUID, icp_id: UUID, payload: ICPProfileUpdate) -> ICPProfileResponse:
        self._get(client_id, icp_id)
        updates = payload.model_dump(exclude_unset=True)
        if "icp_template" in updates and updates["icp_template"] is not None:
            updates["icp_template"] = updates["icp_template"].value
        if payload.is_primary:
            self._clear_primary(client_id)

        row = (
            self._db.table("icp_profiles")
            .update(updates)
            .eq("id", str(icp_id))
            .eq("client_id", str(client_id))
            .execute()
        )
        return _row_to_model(ICPProfileResponse, row.data[0])

    def _get(self, client_id: UUID, icp_id: UUID) -> ICPProfileResponse:
        row = (
            self._db.table("icp_profiles")
            .select("*")
            .eq("id", str(icp_id))
            .eq("client_id", str(client_id))
            .maybe_single()
            .execute()
        )
        if not row or not row.data:
            raise NotFoundError("icp_profile", icp_id)
        return _row_to_model(ICPProfileResponse, row.data)

    def _clear_primary(self, client_id: UUID) -> None:
        self._db.table("icp_profiles").update({"is_primary": False}).eq(
            "client_id", str(client_id)
        ).execute()


class CaseStudyService:
    def __init__(self, db: Client) -> None:
        self._db = db
        self._clients = ClientService(db)
        self._definitions = DefinitionService(db)

    def list_for_client(self, client_id: UUID) -> list[CaseStudyResponse]:
        self._clients.get(client_id)
        rows = (
            self._db.table("case_studies")
            .select("*")
            .eq("client_id", str(client_id))
            .order("sort_order")
            .order("created_at")
            .execute()
        )
        return [_row_to_model(CaseStudyResponse, row) for row in rows.data]

    def create(self, client_id: UUID, payload: CaseStudyCreate) -> CaseStudyResponse:
        self._clients.get(client_id)
        definition = self._definitions.get_active(client_id)
        insert_data = payload.model_dump()
        insert_data["client_id"] = str(client_id)
        if definition:
            insert_data["definition_id"] = str(definition.id)

        row = self._db.table("case_studies").insert(insert_data).execute()
        return _row_to_model(CaseStudyResponse, row.data[0])

    def update(
        self, client_id: UUID, case_study_id: UUID, payload: CaseStudyUpdate
    ) -> CaseStudyResponse:
        self._get(client_id, case_study_id)
        updates = payload.model_dump(exclude_unset=True)
        row = (
            self._db.table("case_studies")
            .update(updates)
            .eq("id", str(case_study_id))
            .eq("client_id", str(client_id))
            .execute()
        )
        return _row_to_model(CaseStudyResponse, row.data[0])

    def _get(self, client_id: UUID, case_study_id: UUID) -> CaseStudyResponse:
        row = (
            self._db.table("case_studies")
            .select("*")
            .eq("id", str(case_study_id))
            .eq("client_id", str(client_id))
            .maybe_single()
            .execute()
        )
        if not row or not row.data:
            raise NotFoundError("case_study", case_study_id)
        return _row_to_model(CaseStudyResponse, row.data)


class Stage1Service:
    def __init__(self, db: Client) -> None:
        self._clients = ClientService(db)
        self._definitions = DefinitionService(db)
        self._icp = ICPProfileService(db)
        self._case_studies = CaseStudyService(db)
        self._db = db

    def get_bundle(self, client_id: UUID) -> Stage1BundleResponse:
        client = self._clients.get(client_id)
        definition = self._definitions.get_active(client_id)
        icp_profiles = self._icp.list_for_client(client_id)
        case_studies = self._case_studies.list_for_client(client_id)
        checklist = self._build_checklist(definition, icp_profiles, case_studies)
        return Stage1BundleResponse(
            client=client,
            definition=definition,
            icp_profiles=icp_profiles,
            case_studies=case_studies,
            checklist=checklist,
        )

    def complete(self, client_id: UUID) -> Stage1BundleResponse:
        bundle = self.get_bundle(client_id)
        if not bundle.checklist.ready:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Stage 1 DEFINE is incomplete",
                    "missing": bundle.checklist.missing,
                },
            )

        now = datetime.now(UTC).isoformat()
        self._db.table("client_definitions").update(
            {"stage1_complete": True, "completed_at": now}
        ).eq("id", str(bundle.definition.id)).execute()

        self._clients.update(client_id, ClientUpdate(status=ClientStatus.ACTIVE))
        return self.get_bundle(client_id)

    def _build_checklist(
        self,
        definition: DefinitionResponse | None,
        icp_profiles: list[ICPProfileResponse],
        case_studies: list[CaseStudyResponse],
    ) -> Stage1Checklist:
        missing: list[str] = []
        has_definition = definition is not None

        has_calendar_url = bool(definition and definition.calendar_url)
        has_offer = bool(definition and definition.offer_headline and definition.offer_description)
        has_pain_points = bool(definition and definition.pain_points)
        has_primary_icp = any(p.is_primary for p in icp_profiles)
        has_case_study = len(case_studies) >= 1

        if not has_definition:
            missing.append("definition")
        if not has_calendar_url:
            missing.append("calendar_url")
        if not has_offer:
            missing.append("offer")
        if not has_pain_points:
            missing.append("pain_points")
        if not has_primary_icp:
            missing.append("primary_icp")
        if not has_case_study:
            missing.append("case_study")

        ready = len(missing) == 0
        return Stage1Checklist(
            has_definition=has_definition,
            has_calendar_url=has_calendar_url,
            has_offer=has_offer,
            has_pain_points=has_pain_points,
            has_primary_icp=has_primary_icp,
            has_case_study=has_case_study,
            ready=ready,
            missing=missing,
        )
