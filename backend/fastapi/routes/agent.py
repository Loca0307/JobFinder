from fastapi import APIRouter
from services.agent_service import *


router = APIRouter(prefix="/agent")


@router.get("/health")
def agent_health() -> dict[str, str]:
    return check_agent_health()
