from pydantic_settings import BaseSettings

class DatabaseSettings(BaseSettings):
    host: str = "localhost"
    port: int = 5432
    user: str = "developer"
    password: str = "devpassword"
    database: str = "githubxplainer"

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

db_settings = DatabaseSettings()
