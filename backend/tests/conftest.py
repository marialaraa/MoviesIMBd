import os
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app import create_app
from run import DEFAULT_DATABASE_URL

TEST_DATABASE = "movies_test"
SAMPLE_CSV = Path(__file__).parent / "movies_sample.csv"


@pytest.fixture(scope="session")
def database_url():
    """URL of a separate test database on the same server, created if missing, so tests never touch dev data."""
    server_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    with psycopg.connect(server_url, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", [TEST_DATABASE]).fetchone()
        if not exists:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DATABASE)))
    return make_conninfo(server_url, dbname=TEST_DATABASE)


@pytest.fixture(scope="session")
def app(database_url):
    return create_app(database_url, SAMPLE_CSV)


@pytest.fixture
def client(app):
    return app.test_client()
