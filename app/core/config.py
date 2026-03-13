from pydantic_settings import BaseSettings, SettingsConfigDict

# this tells pydantic to read the .env file and load the environment variables from there
class Settings(BaseSettings):
    DATABASE_URL: str 

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

#will create an instance that contains the configuration values, which can be accessed as attributes, e.g. settings.DATABASE_URL
settings = Settings() 