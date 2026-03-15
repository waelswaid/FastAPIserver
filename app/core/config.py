from pydantic_settings import BaseSettings, SettingsConfigDict

# this tells pydantic to read the .env file and load the environment variables
class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENVIRONMENT: str = "development"  # set to "production" in prod

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

#will create an instance that contains the configuration values, which can be accessed as attributes, e.g. settings.DATABASE_URL
settings = Settings() 