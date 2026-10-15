import atexit

from flask import Flask
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .movies import MovieRepository
from .routes import bp


def create_app(database_url, csv_path):
    app = Flask(__name__)
    app.json.sort_keys = False

    pool = ConnectionPool(database_url, kwargs={"row_factory": dict_row}, open=True)
    atexit.register(pool.close)
    movies = MovieRepository(pool)
    try:
        pool.wait(timeout=10)
        movies.load_csv(csv_path)
    except Exception:
        pool.close()
        raise
    app.config["MOVIES"] = movies

    app.register_blueprint(bp)
    return app
