import csv
from pathlib import Path

from psycopg import sql

from .utils import escape_like, is_valid

SQL_DIR = Path(__file__).parent / "sql"


def field_match(field, name, text):
    """
    SQL to match `text` against one movie field, as (condition, score, params); `name` prefixes the query params.

    `year` matches exactly. Text fields ignore case and accents, and match if they contain `text`
    (score 1) or if `text` is similar enough to some part of them, so typos still match: "matrx" -> "The Matrix"
    (score = pg_trgm word similarity, 0.6 to 1).
    """
    if field == "year":
        condition = sql.SQL("year = {}").format(sql.Placeholder(name))
        score = sql.SQL("CASE WHEN {} THEN 1.0 ELSE 0.0 END").format(condition)
        return condition, score, {name: int(text)}

    column = sql.SQL("immutable_unaccent({})").format(sql.Identifier(field))
    value = sql.SQL("immutable_unaccent({})").format(sql.Placeholder(name))
    pattern = sql.SQL("immutable_unaccent({})").format(sql.Placeholder(f"{name}_pattern"))

    contains = sql.SQL("{} ILIKE {}").format(column, pattern)
    condition = sql.SQL("({} OR {} <%% {})").format(contains, value, column)
    score = sql.SQL("CASE WHEN {} THEN 1.0 ELSE coalesce(word_similarity({}, {}), 0) END").format(
        contains, value, column
    )
    return condition, score, {name: text, f"{name}_pattern": f"%{escape_like(text)}%"}


class MovieRepository:
    INT_FIELDS = {"year", "duration", "votes", "metascore"}
    FLOAT_FIELDS = {"avg_vote", "reviews_from_users", "reviews_from_critics"}
    SEARCHABLE_FIELDS = ("title", "original_title", "director", "writer", "actors", "genre", "year")

    def __init__(self, pool):
        self._pool = pool

    def load_csv(self, path):
        """Replace the movies table with the contents of the CSV, in a single transaction."""
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
                movie[key] = cls._parse_number(value, int, key, movie_id)
            elif key in cls.FLOAT_FIELDS:
                movie[key] = cls._parse_number(value, float, key, movie_id)
            else:
                movie[key] = value or None
        return movie

    @classmethod
    def _parse_number(cls, value, cast, column, movie_id):
        if not value:
            return None
        assert is_valid(value, cast), f"Invalid {column}={value!r} in movie {movie_id}"
        return cast(value)

    def count(self):
        with self._pool.connection() as conn:
            return conn.execute("SELECT count(*) AS total FROM movies").fetchone()["total"]

    def get(self, movie_id):
        """The movie with this IMDb id, or None."""
        with self._pool.connection() as conn:
            return conn.execute("SELECT * FROM movies WHERE imdb_title_id = %s", [movie_id]).fetchone()

    def ping(self, timeout):
        """Check the database answers within `timeout` seconds; raises if it doesn't."""
        with self._pool.connection(timeout=timeout) as conn:
            conn.execute("SELECT 1")

    def find(self, filters, query, page, limit):
        """
        Movies matching every filter in `filters` ({field: text}) and, if given, `query` in any searchable field.

        See `field_match` for how a single field matches. Best matches come first, then the most voted;
        with no filters, that's simply the most voted movies.
        """
        params, conditions, scores = {}, [], []

        for field, text in filters.items():
            condition, score, field_params = field_match(field, field, text)
            conditions.append(condition)
            scores.append(score)
            params.update(field_params)

        if query:
            fields = [field for field in self.SEARCHABLE_FIELDS if field != "year" or query.isdigit()]
            matches = [field_match(field, f"q_{field}", query) for field in fields]
            conditions.append(sql.SQL("({})").format(sql.SQL(" OR ").join(m[0] for m in matches)))
            scores.append(sql.SQL("GREATEST({})").format(sql.SQL(", ").join(m[1] for m in matches)))
            for _, _, field_params in matches:
                params.update(field_params)

        where = sql.SQL("")
        order_by = sql.SQL("votes DESC, imdb_title_id")
        if conditions:
            where = sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(conditions))
            relevance = sql.SQL(" + ").join(scores)
            order_by = sql.SQL("{} DESC, {}").format(relevance, order_by)
        return self._paginate(where, order_by, params, page, limit)

    def _paginate(self, where, order_by, params, page, limit):
        count_query = sql.SQL("SELECT count(*) AS total FROM movies {}").format(where)
        page_query = sql.SQL("SELECT * FROM movies {} ORDER BY {} LIMIT %(limit)s OFFSET %(offset)s").format(
            where, order_by
        )
        with self._pool.connection() as conn:
            total = conn.execute(count_query, params).fetchone()["total"]
            results = conn.execute(
                page_query, {**params, "limit": limit, "offset": (page - 1) * limit}
            ).fetchall()
        return total, results
