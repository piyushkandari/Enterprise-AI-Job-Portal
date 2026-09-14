from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    cors_origins: str = "http://localhost:3000"
    jwt_secret: str = "dev-secret"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

settings = Settings()