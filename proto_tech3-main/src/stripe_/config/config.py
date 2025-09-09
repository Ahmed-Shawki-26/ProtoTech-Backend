from pydantic import  Extra
from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    # Stripe config
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    # SMTP config
    MAIL_USERNAME : str 
    MAIL_PASSWORD : str
    MAIL_FROM : str
    MAIL_PORT : int
    MAIL_SERVER : str
    SSL_PORT : int 
    # App config
    API_VERSION: str = "0.1.0"
    SUCCESS_URL: str = "https://chatgpt.com/"
    CANCEL_URL: str = "https://www.perplexity.ai/"
    CURRENCY: str = "egp"

    class Config:
        extra = Extra.allow
        env_file =  ".env"
        # env_file_encoding = "utf-8"

# Singleton instance for importing across modules
settings = Settings()
