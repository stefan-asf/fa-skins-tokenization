import os
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_FILE = os.path.join(_ROOT, ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql://fr1endlyyy@localhost:5432/faskins"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change_me"
    api_port: int = 8000

    steam_login: str = ""
    steam_password: str = ""
    steam_steam_id: str = ""
    steam_trade_link: str = ""
    steam_shared_secret: str = ""
    steam_identity_secret: str = ""

    sepolia_rpc_url: str = ""
    deployer_private_key: str = ""
    skin_vault_address: str = ""

    steam_api_key: str = ""

    base_url: str = "https://fa.stfnasf.tech"
    jwt_expire_hours: int = 168


settings = Settings()
