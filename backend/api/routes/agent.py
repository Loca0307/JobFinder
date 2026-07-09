from fastapi import APIRouter
from api.services.agent_service import check_agent_health


router = APIRouter(prefix="/agent")


@router.get("/health")
def agent_health() -> dict[str, str]:
    return check_agent_health()
