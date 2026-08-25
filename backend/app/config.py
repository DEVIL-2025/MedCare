from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "MedCare Pharma SCM Control Tower"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database Configuration
    DATABASE_URL: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: int = 5432
    DB_NAME: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_SCHEMA: str = "public"

    @property
    def sync_database_url(self) -> str:
        if self.DB_HOST and self.DB_USER and self.DB_NAME:
            pwd = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
            return f"postgresql://{self.DB_USER}{pwd}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        if self.DATABASE_URL:
            return self.DATABASE_URL.replace("+asyncpg", "").replace("+aiosqlite", "")
        return "sqlite:///./medcare_scm.db"

    @property
    def async_database_url(self) -> str:
        if self.DB_HOST and self.DB_USER and self.DB_NAME:
            pwd = f":{self.DB_PASSWORD}" if self.DB_PASSWORD else ""
            return f"postgresql+asyncpg://{self.DB_USER}{pwd}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return "sqlite+aiosqlite:///./medcare_scm.db"
    
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
    ADMIN_EMAIL: str = "admin@medcarepharma.com"
    ADMIN_USER_ID: str = "admin"
    ADMIN_FULL_NAME: str = "System Administrator"
    ADMIN_INITIAL_PASSWORD: str = "Admin@12345"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
