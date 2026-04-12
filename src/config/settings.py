from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _str_to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _load_env_file(env_path: Path) -> None:
    """
    외부 패키지 없이 .env를 간단히 로드한다.
    이미 시스템 환경변수에 있는 값은 덮어쓰지 않는다.
    """
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        os.environ.setdefault(key, value)


def _resolve_project_root() -> Path:
    env_base = _get_env("CAPSTONE_BASE_DIR")
    if env_base:
        return Path(env_base).resolve()
    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    # base
    project_root: Path
    src_dir: Path
    docs_dir: Path
    data_dir: Path
    raw_data_dir: Path
    raw_google_flights_dir: Path
    interim_data_dir: Path
    processed_data_dir: Path
    outputs_dir: Path
    logs_dir: Path
    backups_dir: Path
    requirements_dir: Path
    docker_dir: Path

    # runtime
    app_env: str
    debug: bool
    log_level: str
    request_timeout: int
    max_retries: int
    timezone: str

    # db
    mysql_database: str
    mysql_user: str | None
    mysql_password: str | None
    mysql_root_password: str | None
    mysql_host: str
    mysql_port: int

    # external keys
    airkorea_api_key: str | None
    kma_api_key: str | None
    public_data_api_key: str | None
    flight_api_key: str | None

    kaggle_dataset_path: Path


def build_settings() -> Settings:
    default_project_root = Path(__file__).resolve().parents[2]
    env_path = default_project_root / ".env"
    _load_env_file(env_path)

    project_root = _resolve_project_root()

    data_dir = project_root / (_get_env("DATA_DIR", "data") or "data")
    raw_data_dir = project_root / (_get_env("RAW_DATA_DIR", "data/raw") or "data/raw")
    interim_data_dir = project_root / (_get_env("INTERIM_DATA_DIR", "data/interim") or "data/interim")
    processed_data_dir = project_root / (_get_env("PROCESSED_DATA_DIR", "data/processed") or "data/processed")
    outputs_dir = project_root / (_get_env("OUTPUT_DIR", "outputs") or "outputs")
    logs_dir = project_root / (_get_env("LOG_DIR", "logs") or "logs")
    backups_dir = project_root / (_get_env("BACKUP_DIR", "backups") or "backups")
    requirements_dir = project_root / (_get_env("REQUIREMENTS_DIR", "requirements") or "requirements")
    docker_dir = project_root / (_get_env("DOCKER_DIR", "docker") or "docker")
    raw_google_flights_dir = raw_data_dir / "google_flights"

    for path in (
        data_dir,
        raw_data_dir,
        raw_google_flights_dir,
        interim_data_dir,
        processed_data_dir,
        outputs_dir,
        logs_dir,
        backups_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)

    return Settings(
        project_root=project_root,
        src_dir=project_root / "src",
        docs_dir=project_root / "docs",
        data_dir=data_dir,
        raw_data_dir=raw_data_dir,
        raw_google_flights_dir=raw_google_flights_dir,
        interim_data_dir=interim_data_dir,
        processed_data_dir=processed_data_dir,
        outputs_dir=outputs_dir,
        logs_dir=logs_dir,
        backups_dir=backups_dir,
        requirements_dir=requirements_dir,
        docker_dir=docker_dir,
        app_env=_get_env("APP_ENV", "local") or "local",
        debug=_str_to_bool(_get_env("DEBUG", "false"), default=False),
        log_level=_get_env("LOG_LEVEL", "INFO") or "INFO",
        request_timeout=int(_get_env("REQUEST_TIMEOUT", "30") or "30"),
        max_retries=int(_get_env("MAX_RETRIES", "3") or "3"),
        timezone=_get_env("TZ", "Asia/Seoul") or "Asia/Seoul",
        mysql_database=_get_env("MYSQL_DATABASE", "capstone_db") or "capstone_db",
        mysql_user=_get_env("MYSQL_USER"),
        mysql_password=_get_env("MYSQL_PASSWORD"),
        mysql_root_password=_get_env("MYSQL_ROOT_PASSWORD"),
        mysql_host=_get_env("MYSQL_HOST", "127.0.0.1") or "127.0.0.1",
        mysql_port=int(_get_env("MYSQL_PORT", "3306") or "3306"),
        airkorea_api_key=_get_env("AIRKOREA_API_KEY"),
        kma_api_key=_get_env("KMA_API_KEY"),
        public_data_api_key=_get_env("PUBLIC_DATA_API_KEY"),
        flight_api_key=_get_env("FLIGHT_API_KEY"),
        kaggle_dataset_path=project_root / (
            _get_env("KAGGLE_DATASET_PATH", "data/raw/kaggle/itineraries.csv")
            or "data/raw/kaggle/itineraries.csv"
        ),
    )


settings = build_settings()