# Movies API (backend)

Read-only REST API built with Flask that serves the IMDb movies dataset from Postgres, with fuzzy search.
On startup, the server loads the CSV into Postgres, replacing any previous data.

## Requirements

- Python 3.14
- Docker (to run Postgres), or a local Postgres 13+ with the `pg_trgm` and `unaccent` extensions available
- Python packages in `requirements.txt`: Flask, psycopg, pytest

## Setup

Start Postgres (from the project root):

```bash
docker compose up -d
```

This starts Postgres 16 on `localhost:5432` with user, password and database `movies`.If port 5432 is already in use by a local Postgres, change the host port in `docker-compose.yml` and pass `--database-url` accordingly.

Install the Python dependencies:

```bash
conda activate <your-env>
cd backend
pip install -r requirements.txt
```

## Data preparation

The dataset is not included in the repository: copy the provided `IMDb movies.csv` to the project root as `IMDb_movies.csv` (no spaces).

The raw `IMDb_movies.csv` has dirty values (e.g. `year = "TV Movie 2019"`).
The API does **not** fix data: it only validates it, and refuses to start if a numeric column has a non-numeric value:

```
AssertionError: Invalid year='TV Movie 2019' in movie tt8206668
```

Run `notebooks/DataExploration.ipynb` first. Its "Cases to clean" section fixes these values and writes `IMDb_movies_clean.csv`, which is the file the API should load.

## Running

```bash
python run.py --csv ../IMDb_movies_clean.csv
```

Or with an environment variable:

```bash
MOVIES_CSV=../IMDb_movies_clean.csv python run.py
```

Options:

| Flag             | Default                                                             | Description              |
|------------------|---------------------------------------------------------------------|--------------------------|
| `--csv`          | `$MOVIES_CSV`                                                       | Path to the movies CSV   |
| `--database-url` | `$DATABASE_URL`, else `postgresql://movies:movies@localhost:5432/movies` | Postgres connection URL  |
| `--port`         | `5000`                                                              | Port to listen on        |
| `--debug`        | off                                                                 | Enable Flask debug mode  |

## API

### `GET /`

HTML page describing the API: number of movies loaded, the available endpoints with their query parameters, and clickable example URLs.
Open `http://localhost:5000/` in a browser to see it.

### `GET /movies`

Returns a paginated list of movies, optionally filtered.

| Query param | Default | Description                                                         |
|-------------|---------|---------------------------------------------------------------------|
| `title`, `original_title`, `director`, `writer`, `actors`, `genre` | — | Filter by that field (see matching rules below) |
| `year`      | —       | Exact year (must be a number)                                       |
| `q`         | —       | Search in all the fields above at once (matches if any field does)  |
| `page`      | `1`     | Page number (positive integer)                                      |
| `limit`     | `20`    | Movies per page (positive integer, capped at `100`)                 |

Matching rules:

- Text filters ignore case and accents, and match if the field **contains** the text (`?title=god` finds *The Godfather*)
  or if the text is **similar** to part of it, so typos still match (`?title=matrx` finds *The Matrix*).
- Several filters combine with AND: `?title=pulp&director=tarantino` must match both.
- Order: best matches first (exact containment beats a fuzzy match), then the most voted. With no filters, the most voted movies come first.

Response:

```json
{
  "total": 85855,
  "page": 1,
  "limit": 20,
  "results": [
    {
      "imdb_title_id": "tt0000009",
      "title": "Miss Jerry",
      "year": 1894,
      "avg_vote": 5.9,
      "...": "..."
    }
  ]
}
```

`total` is the number of movies matching the filter, not the number in `results`.
Numeric columns are returned as numbers, and empty cells as `null`.

Errors (`400`): invalid `page` or `limit`, or non-numeric `year`:

```json
{"error": "'page' must be a positive integer"}
```

Examples:

```bash
# First page (most voted first)
curl "localhost:5000/movies"

# Filter by title (substring)
curl "localhost:5000/movies?title=godfather"

# Typo and accent tolerant
curl "localhost:5000/movies?title=matrx"
curl "localhost:5000/movies?director=tarantno"

# Combined filters + pagination
curl "localhost:5000/movies?title=pulp&director=tarantino"
curl "localhost:5000/movies?year=1999&page=2&limit=50"

# Search every field
curl "localhost:5000/movies?q=amelie"

# Invalid parameter -> 400
curl "localhost:5000/movies?page=abc"
```

### `GET /movies/<imdb_title_id>`

A single movie, with every column. `404` if it doesn't exist.

```bash
curl "localhost:5000/movies/tt0133093"
```

```json
{"error": "movie 'tt0000000' not found"}
```

### `GET /health`

Whether the API can reach the database (2 second timeout). Useful for docker health checks.

```bash
curl "localhost:5000/health"
```

- `200` `{"status": "ok", "database": "ok"}`
- `503` `{"status": "error", "database": "unreachable"}`

## Tests

Endpoint tests use Flask's test client (no server needed) and `pytest`. They need the docker Postgres running:

```bash
docker compose up -d                      # from the project root
cd backend
pip install -r requirements.txt
pytest
```

- Tests run against a separate `movies_test` database on the same server, created automatically on the first run,
  so they never touch the development data. Override the server with `DATABASE_URL`.
- Data comes from `tests/movies_sample.csv`: 7 movies picked to cover each case
  (typo: *Matrix*, accent: *Amélie*, two Tarantino films, two from 1999, one with empty optional fields).
- Covered: listing and ordering, pagination and its `400`s, substring / case / typo / accent matching,
  combined filters, exact `year`, `q`, `/movies/<id>` (`200` and `404`), `/health` (`200` and `503`), and that a dirty CSV stops startup.

## Design notes

- **Postgres + `pg_trgm`.** Each text filter is `field ILIKE '%text%' OR text <% field`:
  the `ILIKE` keeps the plain "contains" behavior the challenge asks for, and `<%` (trigram word similarity) adds typo tolerance:
  `matrx` and `matrix` share most of their 3-letter chunks, so they match even with the typo.
  A GIN trigram index per searchable field serves both operators without scanning every row.
  The similarity threshold is Postgres' default `pg_trgm.word_similarity_threshold` (0.6).
  Relevance = 1 for a "contains" match, else the similarity; with several filters, their relevances are added.
- **Accent-insensitive.** Both the query and the fields go through `unaccent`, so `amelie` finds *Amélie*.
  `unaccent()` can't be used in an index directly (it's `STABLE`), so `schema.sql` defines an `IMMUTABLE` wrapper, `immutable_unaccent()`,
  and the trigram indexes are built on `immutable_unaccent(column)`, the same expression the queries use.
- **Read-only.** The challenge only requires reading. Routes only depend on `MovieRepository`, so editing could be added there later.
- **CSV as the source of truth.** On every startup the `movies` table is dropped, recreated and filled from the CSV (with `COPY`) in a single transaction.
  Indexes are created after loading, which is faster than filling an already indexed table.
- **Pagination.** Returning all 85k movies at once would be tens of MB, so results are paginated, in SQL (`LIMIT` / `OFFSET`).
- **Validation, not cleaning.** Data cleaning lives in the notebook; the API fails fast on dirty data instead of guessing.

## Scope: local development only

This project is set up to run locally. A production deployment would need, at least:

- **CORS.** Locally, the React dev server proxies API calls, so the browser sees a single origin.
  In production, if the frontend and the API are served from different origins, the browser will block the requests
  unless the API sends the right CORS headers for the frontend's origin (e.g. with `flask-cors`), or both are served behind the same domain through a reverse proxy.
- **A production WSGI server.** `app.run()` starts Flask's development server, which is not meant for production. Use e.g. `gunicorn` instead.
- **Debug mode off.** `--debug` exposes an interactive console that can run arbitrary code.
- **Data validation that can't be disabled.** The CSV checks use `assert`, which Python skips when run with `-O`.
- **Loading as a separate step.** Every process reloads the CSV on startup; with several workers they would each replace the table.
  In production, loading (or migrations) should run once, separately from starting the API.
- **Database credentials** from a secret store, not the `movies:movies` defaults in `docker-compose.yml`.
- **HTTPS.** The API is served over plain HTTP. Production needs a TLS certificate (e.g. from Let's Encrypt),
  usually configured in a reverse proxy (e.g. nginx) in front of the WSGI server.
- **Logging and configuration** through environment variables instead of CLI flags.
