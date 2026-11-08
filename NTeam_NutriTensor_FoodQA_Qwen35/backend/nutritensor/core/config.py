"""Validated deployment settings with conservative defaults for a 12 GB GPU."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    pass


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered not in {"true", "false", "1", "0", "yes", "no"}:
        raise ConfigurationError(f"{name} must be true or false")
    return lowered in {"true", "1", "yes"}


def env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return value


def env_list(name: str, default: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in os.getenv(name, default).split(",") if part.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    mode: str = "demo"
    environment: str = "development"
    model_backend: str = "demo"
    model_path: str = ""
    local_files_only: bool = True
    quantization: str = "nf4"
    dtype: str = "float16"
    attention: str = "sdpa"
    context_tokens: int = 4096
    max_new_tokens: int = 384
    gpu_memory_gib: int = 9
    thinking: bool = False
    fast_scan: bool = True
    queue_capacity: int = 4
    inference_timeout: int = 120
    database_path: Path = Path("data/nutritensor.sqlite3")
    catalog_path: Path = Path("data/foods.json")
    uploads_path: Path = Path("data/uploads")
    users_path: Path = Path("data/users.json")
    session_secret: str = field(default_factory=lambda: secrets.token_urlsafe(48))
    admin_password: str = ""
    admin_password_hash: str = ""
    cookie_secure: bool = False
    allowed_origins: tuple[str, ...] = ("http://localhost:4173", "http://127.0.0.1:4173", "http://localhost:8000", "http://127.0.0.1:8000")
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "testserver")
    session_ttl_hours: int = 12
    upload_limit_mb: int = 10
    image_max_pixels: int = 20_000_000
    image_max_edge: int = 1280
    image_retention_hours: int = 24
    request_limit: int = 120
    login_limit: int = 8
    enable_ocr: bool = False
    fdc_api_key: str = ""
    remote_llm_url: str = "http://127.0.0.1:8080/v1"
    remote_llm_model: str = "local-ntemma"
    remote_llm_key: str = ""
    allow_remote_inference: bool = False
    remote_supports_vision: bool = False
    audit_retention_days: int = 30
    allow_demo_catalog: bool = False

    @property
    def is_demo(self) -> bool:
        return self.mode == "demo"

    @property
    def upload_limit_bytes(self) -> int:
        return self.upload_limit_mb * 1024 * 1024

    def validate(self) -> Settings:
        if self.mode not in {"live", "demo"}:
            raise ConfigurationError("NTEAM_MODE must be live or demo")
        if self.model_backend not in {"demo", "transformers", "openai-compatible"}:
            raise ConfigurationError("Unsupported model backend")
        if not self.is_demo:
            if self.model_backend == "demo":
                raise ConfigurationError("Live mode cannot use the demo model")
            if len(self.session_secret) < 32 or self.session_secret.startswith("replace-"):
                raise ConfigurationError("Set a random session secret of at least 32 characters")
            if not self.users_path.exists() and not self.admin_password_hash and (
                len(self.admin_password) < 12 or self.admin_password.startswith("replace-")
            ):
                raise ConfigurationError("Set an admin password of at least 12 characters")
            if self.model_backend == "transformers" and not self.model_path:
                raise ConfigurationError("Set NTEAM_MODEL_PATH to your model directory or explicit Hub ID")
        if self.environment == "production":
            if not self.cookie_secure:
                raise ConfigurationError("Production requires HTTPS and NTEAM_COOKIE_SECURE=true")
            if "*" in self.allowed_hosts or "*" in self.allowed_origins:
                raise ConfigurationError("Production requires explicit origins and hosts")
        if self.quantization not in {"nf4", "int8", "none"}:
            raise ConfigurationError("NTEAM_QUANTIZATION must be nf4, int8, or none")
        if self.dtype not in {"float16", "bfloat16", "float32"}:
            raise ConfigurationError("Unsupported inference dtype")
        if self.attention not in {"sdpa", "eager", "flash_attention_2"}:
            raise ConfigurationError("Unsupported attention implementation")
        if not 128 <= self.context_tokens <= 32768:
            raise ConfigurationError("Context must be within 128 and 32768 tokens")
        if not 16 <= self.max_new_tokens < self.context_tokens:
            raise ConfigurationError("Generation budget must be positive and smaller than context")
        if not 1 <= self.queue_capacity <= 64:
            raise ConfigurationError("Queue capacity must be 1 to 64")
        parsed = urlparse(self.remote_llm_url)
        if self.model_backend == "openai-compatible":
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ConfigurationError("The inference endpoint must be an HTTP URL")
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ConfigurationError("Credentials and query strings are not permitted in endpoint URLs")
            if not self.allow_remote_inference and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
                raise ConfigurationError("Remote inference requires explicit NTEAM_ALLOW_REMOTE_INFERENCE=true")
        return self

    @classmethod
    def from_env(cls, dotenv: bool = True) -> Settings:
        if dotenv:
            load_dotenv(override=False)
        mode = os.getenv("NTEAM_MODE", "demo")
        secret = os.getenv("NTEAM_SESSION_SECRET", "")
        if mode == "demo" and not secret:
            secret = secrets.token_urlsafe(48)
        return cls(
            mode=mode,
            environment=os.getenv("NTEAM_ENVIRONMENT", "development"),
            model_backend=os.getenv("NTEAM_MODEL_BACKEND", "demo" if mode == "demo" else "transformers"),
            model_path=os.getenv("NTEAM_MODEL_PATH", ""),
            local_files_only=env_bool("NTEAM_LOCAL_FILES_ONLY", True),
            quantization=os.getenv("NTEAM_QUANTIZATION", "nf4"),
            dtype=os.getenv("NTEAM_DTYPE", "float16"),
            attention=os.getenv("NTEAM_ATTENTION", "sdpa"),
            context_tokens=env_int("NTEAM_CONTEXT_TOKENS", 4096, 128, 32768),
            max_new_tokens=env_int("NTEAM_MAX_NEW_TOKENS", 384, 16, 4096),
            gpu_memory_gib=env_int("NTEAM_GPU_MEMORY_GIB", 9, 1, 80),
            thinking=env_bool("NTEAM_THINKING", False),
            fast_scan=env_bool("NTEAM_FAST_SCAN", True),
            queue_capacity=env_int("NTEAM_QUEUE_CAPACITY", 4, 1, 64),
            inference_timeout=env_int("NTEAM_INFERENCE_TIMEOUT", 120, 5, 600),
            database_path=Path(os.getenv("NTEAM_DATABASE_PATH", "data/nutritensor.sqlite3")),
            catalog_path=Path(os.getenv("NTEAM_CATALOG_PATH", "data/foods.json")),
            uploads_path=Path(os.getenv("NTEAM_UPLOADS_PATH", "data/uploads")),
            users_path=Path(os.getenv("NTEAM_USERS_PATH", "data/users.json")),
            session_secret=secret,
            admin_password=os.getenv("NTEAM_ADMIN_PASSWORD", ""),
            admin_password_hash=os.getenv("NTEAM_ADMIN_PASSWORD_HASH", ""),
            cookie_secure=env_bool("NTEAM_COOKIE_SECURE", False),
            allowed_origins=env_list("NTEAM_ALLOWED_ORIGINS", "http://localhost:4173,http://127.0.0.1:4173,http://localhost:8000,http://127.0.0.1:8000"),
            allowed_hosts=env_list("NTEAM_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"),
            session_ttl_hours=env_int("NTEAM_SESSION_TTL_HOURS", 12, 1, 168),
            upload_limit_mb=env_int("NTEAM_UPLOAD_LIMIT_MB", 10, 1, 30),
            image_max_pixels=env_int("NTEAM_IMAGE_MAX_PIXELS", 20_000_000, 100_000, 40_000_000),
            image_max_edge=env_int("NTEAM_IMAGE_MAX_EDGE", 1280, 224, 2048),
            image_retention_hours=env_int("NTEAM_IMAGE_RETENTION_HOURS", 24, 1, 168),
            request_limit=env_int("NTEAM_REQUEST_LIMIT", 120, 10, 1000),
            login_limit=env_int("NTEAM_LOGIN_LIMIT", 8, 1, 50),
            enable_ocr=env_bool("NTEAM_ENABLE_OCR", False),
            fdc_api_key=os.getenv("NTEAM_FDC_API_KEY", ""),
            remote_llm_url=os.getenv("NTEAM_REMOTE_LLM_URL", "http://127.0.0.1:8080/v1"),
            remote_llm_model=os.getenv("NTEAM_REMOTE_LLM_MODEL", "local-ntemma"),
            remote_llm_key=os.getenv("NTEAM_REMOTE_LLM_KEY", ""),
            allow_remote_inference=env_bool("NTEAM_ALLOW_REMOTE_INFERENCE", False),
            remote_supports_vision=env_bool("NTEAM_REMOTE_SUPPORTS_VISION", False),
            audit_retention_days=env_int("NTEAM_AUDIT_RETENTION_DAYS", 30, 1, 365),
            allow_demo_catalog=env_bool("NTEAM_ALLOW_DEMO_CATALOG", False),
        ).validate()
