from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Данные из енв файла
    """
    
    VK_TOKEN: str
    DATABASE: str
    ENTER_DUNGEON: int
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
settings = Settings()