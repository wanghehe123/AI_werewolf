from fastapi import APIRouter, Depends
from sqlmodel import Session

from ai_werewolf.api.admin.dependencies import get_admin_session, require_admin_session
from ai_werewolf.api.admin.serializers import role_metadata_to_dict
from ai_werewolf.api.responses import success_response
from ai_werewolf.seeds.admin_roles import default_role_metadata
from ai_werewolf.storage.admin_repository import RoleMetadataRepository

router = APIRouter(prefix="/admin/roles", tags=["admin-roles"])


@router.get("", dependencies=[Depends(require_admin_session)])
def list_roles(session: Session = Depends(get_admin_session)) -> dict:
    roles = RoleMetadataRepository(session).list_all()
    return success_response(data=[role_metadata_to_dict(role) for role in roles])


@router.post("/seed", dependencies=[Depends(require_admin_session)])
def seed_roles(session: Session = Depends(get_admin_session)) -> dict:
    for role in default_role_metadata():
        session.merge(role)
    session.commit()
    roles = RoleMetadataRepository(session).list_all()
    return success_response(data=[role_metadata_to_dict(role) for role in roles])
