from pydantic_settings import SettingsConfigDict,BaseSettings


class Settings(BaseSettings):
    DATABASE_URL:str
    MAIL_USERNAME:str
    MAIL_PASSWORD:str
    SECRET_KEY:str

    model_config=SettingsConfigDict(
        env_file=".env"
    )

settings=Settings()
