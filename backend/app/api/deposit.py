from fastapi import APIRouter

router = APIRouter(prefix="/deposit", tags=["deposit"])


@router.post("")
def create_deposit():
    return {"status": "stub", "message": "Deposit — этап 6"}


@router.get("/{deposit_id}")
def get_deposit(deposit_id: int):
    return {"status": "stub", "deposit_id": deposit_id}
