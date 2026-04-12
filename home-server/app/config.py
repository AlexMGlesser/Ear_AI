from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8765

    lm_studio_base_url: str = "http://127.0.0.1:1234"
    lm_studio_model: str = "local-model"
    request_timeout_seconds: int = 45
    session_history_messages: int = 12
    web_lookup_enabled: bool = False
    web_lookup_timeout_seconds: int = 10
    web_lookup_max_results: int = 4

    auth_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
