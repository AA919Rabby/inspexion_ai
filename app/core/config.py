from pydantic_settings import BaseSettings,SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "InspeXion AI"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY:str
    ALGORITHM:str="HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:int=1440
    DATABASE_URL:str
    GOOGLE_CLIENT_ID:str
    OPENROUTER_API_KEY:str
    OPENROUTER_MODEL:str="anthropic/claude-3.5-sonnet"
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    model_config=SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

settings = Settings()