from fastapi import APIRouter

router = APIRouter(prefix="/withdraw", tags=["withdraw"])


@router.post("")
def create_withdrawal():
    return {"status": "stub", "message": "Withdraw — этап 7"}


@router.get("/{withdrawal_id}")
def get_withdrawal(withdrawal_id: int):
    return {"status": "stub", "withdrawal_id": withdrawal_id}
