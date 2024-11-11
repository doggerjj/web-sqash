from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    binance_api_key: str = ""
    binance_api_secret: str = ""
    default_symbol: str = "BTCUSDT"
    default_interval: str = "1m"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()