import os
from pathlib import Path

import psycopg
import pytest
from flask import request
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app import create_app
from run import DEFAULT_DATABASE_URL

TEST_DATABASE = "movies_test"
SAMPLE_CSV = Path(__file__).parent / "movies_sample.csv"

ROUTES = {}
CALLED_ENDPOINTS = set()
UNTESTED_ROUTES = []


def pytest_addoption(parser):
    parser.addoption(
        "--check-routes",
        action="store_true",
        help="fail the run if any API route was never called by the tests",
    )


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption("--check-routes"):
        return
    UNTESTED_ROUTES.extend(
        f"{rule} ({endpoint})" for endpoint, rule in sorted(ROUTES.items()) if endpoint not in CALLED_ENDPOINTS
    )
    if UNTESTED_ROUTES:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter):
    if UNTESTED_ROUTES:
        terminalreporter.section("untested routes", red=True)
        for route in UNTESTED_ROUTES:
            terminalreporter.write_line(f"No test calls {route}", red=True)


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
    """The app under test; also records which routes the tests call, for --check-routes."""
    app = create_app(database_url, SAMPLE_CSV)
    ROUTES.update({rule.endpoint: rule.rule for rule in app.url_map.iter_rules() if rule.endpoint != "static"})
    app.before_request(lambda: CALLED_ENDPOINTS.add(request.endpoint))
    return app


@pytest.fixture
def client(app):
    return app.test_client()
