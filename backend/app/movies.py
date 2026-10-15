import csv
import re
from pathlib import Path

from psycopg import sql

from .utils import escape_like, is_valid

SQL_DIR = Path(__file__).parent / "sql"

WHOLE_WORD_MAX_LENGTH = 2
MIN_FUZZY_WORD_LENGTH = 5


def word_match(field, name, word):
    """Returns (condition, score, params) to match one word against one field."""
    if field == "year":
        condition = sql.SQL("year = {}").format(sql.Placeholder(name))
        score = sql.SQL("CASE WHEN {} THEN 1.0 ELSE 0.0 END").format(condition)
        return condition, score, {name: int(word)}

    column = sql.SQL("immutable_unaccent({})").format(sql.Identifier(field))

    if len(word) <= WHOLE_WORD_MAX_LENGTH:
        whole_word = sql.SQL("immutable_unaccent({})").format(sql.Placeholder(f"{name}_regex"))
        condition = sql.SQL("{} ~* {}").format(column, whole_word)
        score = sql.SQL("CASE WHEN {} THEN 1.0 ELSE 0.0 END").format(condition)
        return condition, score, {f"{name}_regex": rf"\m{re.escape(word)}\M"}

    pattern = sql.SQL("immutable_unaccent({})").format(sql.Placeholder(f"{name}_pattern"))
    contains = sql.SQL("{} ILIKE {}").format(column, pattern)
    params = {f"{name}_pattern": f"%{escape_like(word)}%"}

    if len(word) < MIN_FUZZY_WORD_LENGTH:
        return contains, sql.SQL("CASE WHEN {} THEN 1.0 ELSE 0.0 END").format(contains), params

    value = sql.SQL("immutable_unaccent({})").format(sql.Placeholder(name))
    condition = sql.SQL("({} OR {} <%% {})").format(contains, value, column)
    score = sql.SQL("CASE WHEN {} THEN 1.0 ELSE coalesce(word_similarity({}, {}), 0) END").format(
        contains, value, column
    )
    return condition, score, {**params, name: word}


def text_match(fields, name, text):
    """Returns (condition, score, params) requiring every word of `text` to match one of `fields`."""
    conditions, scores, params = [], [], {}
    for i, word in enumerate(text.split()):
        matches = [
            word_match(field, f"{name}_{i}_{field}", word) for field in fields if field != "year" or word.isdecimal()
        ]
        conditions.append(sql.SQL("({})").format(sql.SQL(" OR ").join(m[0] for m in matches)))
        scores.append(sql.SQL("GREATEST({})").format(sql.SQL(", ").join(m[1] for m in matches)))
        for _, _, match_params in matches:
            params.update(match_params)

    condition = sql.SQL("({})").format(sql.SQL(" AND ").join(conditions))
    score = sql.SQL("(({}) / {})").format(sql.SQL(" + ").join(scores), sql.Literal(len(scores)))
    return condition, score, params


def parse_number(value, cast, column, movie_id):
    if not value:
        return None
    assert is_valid(value, cast), f"Invalid {column}={value!r} in movie {movie_id}"
    return cast(value)


class MovieRepository:
    INT_FIELDS = {"year", "duration", "votes", "metascore"}
    FLOAT_FIELDS = {"avg_vote", "reviews_from_users", "reviews_from_critics"}
    SEARCHABLE_FIELDS = ("title", "original_title", "director", "writer", "actors", "genre", "year")
    FILTER_FIELDS = {"title": ("title", "original_title")}
    LIST_FIELDS = ("imdb_title_id", "title", "original_title", "year", "genre", "director", "avg_vote", "votes")

    def __init__(self, pool):
        self._pool = pool

    def load_csv(self, path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Movies CSV not found: {path}")
        with path.open(encoding="utf-8", newline="") as f, self._pool.connection() as conn:
            reader = csv.DictReader(f)
            columns = reader.fieldnames
            conn.execute((SQL_DIR / "schema.sql").read_text())

            copy_query = sql.SQL("COPY movies ({}) FROM STDIN").format(
                sql.SQL(", ").join(map(sql.Identifier, columns))
            )
            with conn.cursor() as cur, cur.copy(copy_query) as copy:
                for row in reader:
                    movie = self._parse_row(row)
                    copy.write_row([movie[column] for column in columns])

            conn.execute((SQL_DIR / "indexes.sql").read_text())

    @classmethod
    def _parse_row(cls, row):
        movie_id = row["imdb_title_id"]
        movie = {}
        for key, value in row.items():
            if key in cls.INT_FIELDS:
                movie[key] = parse_number(value, int, key, movie_id)
            elif key in cls.FLOAT_FIELDS:
                movie[key] = parse_number(value, float, key, movie_id)
            else:
                movie[key] = value or None
        return movie

    def count(self):
        with self._pool.connection() as conn:
            return conn.execute("SELECT count(*) AS total FROM movies").fetchone()["total"]

    def get(self, movie_id):
        with self._pool.connection() as conn:
            return conn.execute("SELECT * FROM movies WHERE imdb_title_id = %s", [movie_id]).fetchone()

    def ping(self, timeout):
        with self._pool.connection(timeout=timeout) as conn:
            conn.execute("SELECT 1")

    def find(self, filters, query, page, limit):
        params, conditions, scores = {}, [], []

        matches = [
            text_match(self.FILTER_FIELDS.get(field, (field,)), field, text) for field, text in filters.items()
        ]
        if query:
            matches.append(text_match(self.SEARCHABLE_FIELDS, "q", query))

        for condition, score, match_params in matches:
            conditions.append(condition)
            scores.append(score)
            params.update(match_params)

        where = sql.SQL("")
        order_by = sql.SQL("votes DESC, imdb_title_id")
        if conditions:
            where = sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(conditions))
            relevance = sql.SQL(" + ").join(scores)
            order_by = sql.SQL("{} DESC, {}").format(relevance, order_by)
        return self._paginate(where, order_by, params, page, limit)

    def _paginate(self, where, order_by, params, page, limit):
        count_query = sql.SQL("SELECT count(*) AS total FROM movies {}").format(where)
        page_query = sql.SQL("SELECT {} FROM movies {} ORDER BY {} LIMIT %(limit)s OFFSET %(offset)s").format(
            sql.SQL(", ").join(map(sql.Identifier, self.LIST_FIELDS)), where, order_by
        )
        with self._pool.connection() as conn:
            total = conn.execute(count_query, params).fetchone()["total"]
            results = conn.execute(
                page_query, {**params, "limit": limit, "offset": (page - 1) * limit}
            ).fetchall()
        return total, results
