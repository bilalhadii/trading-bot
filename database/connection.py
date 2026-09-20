import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not configured in .env"
    )


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


def test_connection() -> None:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version();"))
        print(result.fetchone()[0])


if __name__ == "__main__":
    test_connection()