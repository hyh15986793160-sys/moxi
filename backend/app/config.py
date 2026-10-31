from __future__ import annotations

import os
from dataclasses import dataclass, field


def _cors_origins() -> tuple[str, ...]:
    raw = os.getenv(
        "MOXI_CORS_ORIGINS",
        "http://127.0.0.1:6670,http://localhost:6670",
    )
    return tuple(origin.strip() for origin in raw.split(",") if origin.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    name: str = "MoXi API"
    version: str = field(default_factory=lambda: os.getenv("MOXI_VERSION", "0.1.0"))
    environment: str = field(default_factory=lambda: os.getenv("MOXI_ENV", "development"))
    cors_origins: tuple[str, ...] = field(default_factory=_cors_origins)


settings = Settings()
