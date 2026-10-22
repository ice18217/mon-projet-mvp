import os
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi import HTTPException, status


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str


def get_settings() -> Settings:
    load_dotenv()

    required = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_ANON_KEY": os.getenv("SUPABASE_ANON_KEY"),
        "SUPABASE_SERVICE_ROLE_KEY": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The access-management API is not configured. Missing: "
                + ", ".join(missing)
            ),
        )

    return Settings(
        supabase_url=required["SUPABASE_URL"].rstrip("/"),
        supabase_anon_key=required["SUPABASE_ANON_KEY"],
        supabase_service_role_key=required["SUPABASE_SERVICE_ROLE_KEY"],
    )
