from pydantic_settings import BaseSettings, SettingsConfigDict

# this tells pydantic to read the .env file and load the environment variables
class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENVIRONMENT: str = "development"  # set to "production" in prod

    # Mailgun
    MAILGUN_API_KEY: str
    MAILGUN_DOMAIN: str
    MAILGUN_FROM_EMAIL: str
    MAILGUN_API_URL: str = "https://api.mailgun.net/v3"

    # Password reset
    APP_BASE_URL: str = "http://localhost:8000"
    PASSWORD_RESET_EXPIRE_MINUTES: int = 15
    EMAIL_VERIFICATION_EXPIRE_MINUTES: int = 1440

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Rate limits (requests per hour)
    RATE_LIMIT_LOGIN: int = 10
    RATE_LIMIT_LOGIN_GLOBAL: int = 30
    RATE_LIMIT_REGISTRATION: int = 5
    RATE_LIMIT_FORGOT_PASSWORD: int = 5
    RATE_LIMIT_RESET_PASSWORD: int = 10
    RATE_LIMIT_RESEND_VERIFICATION: int = 5
    RATE_LIMIT_REFRESH: int = 30
    RATE_LIMIT_VERIFY_EMAIL: int = 10
    RATE_LIMIT_VALIDATE_RESET_CODE: int = 10
    RATE_LIMIT_CHANGE_PASSWORD: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

#will create an instance that contains the configuration values, which can be accessed as attributes, e.g. settings.DATABASE_URL
settings = Settings() 