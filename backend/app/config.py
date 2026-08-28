from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "MedCare Pharma SCM Control Tower"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # CORS Configuration (comma-separated or wildcard '*')
    CORS_ORIGINS: str = "*"

    # Database Configuration
    DATABASE_URL: Optional[str] = None
    DATABASE_URL_UNPOOLED: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: int = 5432
    DB_NAME: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_SCHEMA: str = "public"

    # Neon Cloud Backend Primitives
    NEON_PROJECT_ID: Optional[str] = "wispy-poetry-14541559"
    NEON_ORG_ID: Optional[str] = "org-morning-sound-68167997"
    NEON_AUTH_BASE_URL: Optional[str] = None
    NEON_AI_GATEWAY_URL: Optional[str] = None
    NEON_AI_GATEWAY_API_KEY: Optional[str] = None
    AWS_ENDPOINT_URL_S3: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = "us-east-2"
    AWS_S3_BUCKET: Optional[str] = None

    @property
    def sync_database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL.replace("+asyncpg", "")
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return url
        if self.DB_HOST and self.DB_USER and self.DB_NAME:
            pwd = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
            return f"postgresql://{self.DB_USER}{pwd}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return "postgresql://postgres:postgres@localhost:5432/medcare_scm"

    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            if "sslmode=" in url:
                url = url.replace("sslmode=", "ssl=")
            return url
        if self.DB_HOST and self.DB_USER and self.DB_NAME:
            pwd = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
            return f"postgresql+asyncpg://{self.DB_USER}{pwd}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return "postgresql+asyncpg://postgres:postgres@localhost:5432/medcare_scm"
    
    @property
    def allowed_cors_origins(self) -> List[str]:
        if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    # SCM Engine Parameters
    SERVICE_LEVEL: float = 0.95  # 95% service level
    LEAD_TIME_BUFFER_DAYS: int = 2
    FORECAST_HORIZON_DAYS: int = 30
    SURGE_THRESHOLD_PCT: float = 25.0  # +25% triggers surge detection
    FLU_SEASON_UPLIFT_PCT: float = 60.0  # +60% flu season spike
    
    # Expiry Risk Thresholds (in days)
    EXPIRY_CRITICAL_DAYS: int = 30
    EXPIRY_AT_RISK_DAYS: int = 90
    EXPIRY_WATCH_DAYS: int = 180
    
    # Financial Approval Thresholds (INR)
    AUTO_APPROVE_THRESHOLD_INR: float = 100000.0  # ₹1.0 Lakh
    MANAGER_APPROVAL_THRESHOLD_INR: float = 500000.0  # ₹5.0 Lakh
    
    # Shortage Escalation SLA (in hours)
    ESCALATION_CRITICAL_HOURS: int = 4
    ESCALATION_HIGH_HOURS: int = 24
    ESCALATION_MEDIUM_HOURS: int = 72
    
    # Transfer-First Network Policy
    TRANSFER_FIRST_ENABLED: bool = True
    
    # JWT Authentication & Security Configuration
    JWT_SECRET_KEY: str = "medcare_scm_control_tower_super_secure_jwt_secret_key_2026_npn"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Initial Admin Seed Configuration
    ADMIN_INITIAL_PASSWORD: str = "Admin@12345"
    
    # Gemini AI Configuration
    GEMINI_API_KEY: str = ""

    # Email & Alert Dispatch Configuration (Resend / SMTP)
    RESEND_API_KEY: str = ""
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = ""
    EMAIL_TO: Optional[str] = None
    APP_FRONTEND_URL: str = "http://localhost:5173"


settings = Settings()
