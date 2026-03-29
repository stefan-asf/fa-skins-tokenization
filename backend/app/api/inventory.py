from fastapi import APIRouter

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("")
def get_inventory():
    return {"status": "stub", "message": "Inventory — этап 2"}
