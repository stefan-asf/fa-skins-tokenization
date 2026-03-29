from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.inventory import router as inventory_router
from app.api.deposit import router as deposit_router
from app.api.withdraw import router as withdraw_router
from app.api.history import router as history_router

app = FastAPI(title="FA Skins Tokenization", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(inventory_router)
app.include_router(deposit_router)
app.include_router(withdraw_router)
app.include_router(history_router)
