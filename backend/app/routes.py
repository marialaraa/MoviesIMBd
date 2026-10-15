from flask import Blueprint, current_app, jsonify, render_template, request, url_for
from psycopg import Error as DatabaseError
from psycopg_pool import PoolTimeout

from .movies import MovieRepository
from .utils import BadRequest, positive_int

bp = Blueprint("movies", __name__)

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
HEALTH_TIMEOUT_SECONDS = 2


def pagination():
    page = positive_int("page", 1)
    limit = min(positive_int("limit", DEFAULT_LIMIT), MAX_LIMIT)
    return page, limit


def page_response(total, page, limit, results):
    return jsonify(total=total, page=page, limit=limit, results=results)


@bp.errorhandler(BadRequest)
def bad_request(error):
    return jsonify(error=str(error)), 400


@bp.get("/")
def home():
    movies_url = url_for("movies.list_movies")
    return render_template(
        "home.html",
        movies_loaded=current_app.config["MOVIES"].count(),
        default_limit=DEFAULT_LIMIT,
        max_limit=MAX_LIMIT,
        searchable_fields=MovieRepository.SEARCHABLE_FIELDS,
        examples=[
            movies_url,
            f"{movies_url}?title=godfather",
            f"{movies_url}?title=matrx",
            f"{movies_url}?director=tarantno",
            f"{movies_url}?title=pulp&director=tarantino",
            f"{movies_url}?year=1999&page=2&limit=50",
            f"{movies_url}?q=amelie",
        ],
    )


@bp.get("/movies")
def list_movies():
    page, limit = pagination()

    filters = {}
    for field in MovieRepository.SEARCHABLE_FIELDS:
        text = request.args.get(field, "").strip()
        if text:
            filters[field] = text
    if "year" in filters and not filters["year"].isdigit():
        raise BadRequest("'year' must be a number")

    query = request.args.get("q", "").strip()
    total, results = current_app.config["MOVIES"].find(filters, query, page, limit)
    return page_response(total, page, limit, results)


@bp.get("/movies/<movie_id>")
def get_movie(movie_id):
    movie = current_app.config["MOVIES"].get(movie_id)
    if movie is None:
        return jsonify(error=f"movie '{movie_id}' not found"), 404
    return jsonify(movie)


@bp.get("/health")
def health():
    try:
        current_app.config["MOVIES"].ping(timeout=HEALTH_TIMEOUT_SECONDS)
    except (DatabaseError, PoolTimeout):
        return jsonify(status="error", database="unreachable"), 503
    return jsonify(status="ok", database="ok")
