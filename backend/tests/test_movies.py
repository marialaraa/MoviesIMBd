import pytest
from psycopg_pool import PoolTimeout

from app import create_app
from app.movies import MovieRepository

MATRIX = "tt0133093"
PULP_FICTION = "tt0110912"
KILL_BILL = "tt0266697"
AMELIE = "tt0211915"
GODFATHER = "tt0068646"
FIGHT_CLUB = "tt0137523"
MINIMAL = "tt9999999"

ALL_BY_VOTES = [FIGHT_CLUB, PULP_FICTION, MATRIX, GODFATHER, KILL_BILL, AMELIE, MINIMAL]


def ids(response):
    return [movie["imdb_title_id"] for movie in response.json["results"]]


def test_home_lists_the_endpoints(client):
    response = client.get("/")

    assert response.status_code == 200
    for endpoint in [b"/movies", b"/movies/&lt;imdb_title_id&gt;", b"/health"]:
        assert endpoint in response.data


def test_list_without_filters_returns_every_movie_most_voted_first(client):
    response = client.get("/movies")

    assert response.status_code == 200
    assert response.json["total"] == len(ALL_BY_VOTES)
    assert ids(response) == ALL_BY_VOTES


def test_list_returns_only_summary_fields(client):
    movie = client.get("/movies").json["results"][0]

    assert list(movie) == list(MovieRepository.LIST_FIELDS)


def test_pagination(client):
    response = client.get("/movies?page=2&limit=2")

    assert response.json["total"] == len(ALL_BY_VOTES)
    assert response.json["page"] == 2
    assert response.json["limit"] == 2
    assert ids(response) == [MATRIX, GODFATHER]


def test_page_past_the_end_is_empty(client):
    response = client.get("/movies?page=10")

    assert response.status_code == 200
    assert response.json["total"] == len(ALL_BY_VOTES)
    assert response.json["results"] == []


def test_limit_is_capped(client):
    assert client.get("/movies?limit=1000").json["limit"] == 100


@pytest.mark.parametrize("query", ["page=0", "page=abc", "limit=-1", "limit=2.5"])
def test_invalid_pagination_is_rejected(client, query):
    response = client.get(f"/movies?{query}")

    assert response.status_code == 400
    assert "must be a positive integer" in response.json["error"]


def test_title_filter_matches_substrings(client):
    assert ids(client.get("/movies?title=god")) == [GODFATHER]


def test_title_filter_searches_italian_and_original_titles(client):
    assert ids(client.get("/movies?title=padrino")) == [GODFATHER]
    assert ids(client.get("/movies?title=the godfather")) == [GODFATHER]


def test_title_filter_ignores_case(client):
    assert ids(client.get("/movies?title=MATRIX")) == [MATRIX]


def test_title_filter_tolerates_typos(client):
    assert ids(client.get("/movies?title=matrx")) == [MATRIX]


def test_title_filter_ignores_accents(client):
    assert ids(client.get("/movies?title=amelie")) == [AMELIE]


def test_every_word_must_match(client):
    assert ids(client.get("/movies?title=pulp fction")) == [PULP_FICTION]
    assert ids(client.get("/movies?title=pulp fiction z")) == []


def test_short_words_must_be_whole_words(client):
    assert ids(client.get("/movies?title=kill bill 1")) == [KILL_BILL]
    assert ids(client.get("/movies?title=pulp fiction p")) == []


def test_four_letter_words_do_not_tolerate_typos(client):
    assert ids(client.get("/movies?genre=dram")) == [FIGHT_CLUB, PULP_FICTION, GODFATHER, MINIMAL]
    assert ids(client.get("/movies?genre=drma")) == []


def test_filter_by_another_field_with_a_typo(client):
    assert ids(client.get("/movies?director=tarantno")) == [PULP_FICTION, KILL_BILL]


def test_filters_combine_with_and(client):
    assert ids(client.get("/movies?title=kill&director=tarantino")) == [KILL_BILL]

    response = client.get("/movies?title=matrix&director=tarantino")
    assert response.json["total"] == 0
    assert response.json["results"] == []


def test_year_filter_is_exact(client):
    assert ids(client.get("/movies?year=1999")) == [FIGHT_CLUB, MATRIX]


def test_year_filter_must_be_a_number(client):
    response = client.get("/movies?year=nineteen")

    assert response.status_code == 400
    assert response.json["error"] == "'year' must be a number"


def test_q_searches_every_field(client):
    assert ids(client.get("/movies?q=keanu")) == [MATRIX]
    assert ids(client.get("/movies?q=amelie")) == [AMELIE]
    assert ids(client.get("/movies?q=1972")) == [GODFATHER]


def test_q_words_can_match_different_fields(client):
    assert ids(client.get("/movies?q=tarantino pulp")) == [PULP_FICTION]
    assert ids(client.get("/movies?q=1999 fincher")) == [FIGHT_CLUB]


def test_get_movie_parses_numbers_and_empty_cells(client):
    matrix = client.get(f"/movies/{MATRIX}").json
    assert matrix["title"] == "Matrix"
    assert matrix["year"] == 1999
    assert matrix["avg_vote"] == 8.7
    assert matrix["metascore"] == 73

    minimal = client.get(f"/movies/{MINIMAL}").json
    assert minimal["original_title"] is None
    assert minimal["metascore"] is None


def test_get_unknown_movie_returns_404(client):
    response = client.get("/movies/tt0000000")

    assert response.status_code == 404
    assert response.json["error"] == "movie 'tt0000000' not found"


def test_health_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok", "database": "ok"}


def test_health_reports_unreachable_database(app, client, monkeypatch):
    def unreachable(timeout):
        raise PoolTimeout("no connection")

    monkeypatch.setattr(app.config["MOVIES"], "ping", unreachable)
    response = client.get("/health")

    assert response.status_code == 503
    assert response.json == {"status": "error", "database": "unreachable"}


def test_dirty_csv_stops_startup(database_url, tmp_path):
    dirty_csv = tmp_path / "dirty.csv"
    dirty_csv.write_text(
        "imdb_title_id,title,year\n"
        "tt8206668,Bad Education,TV Movie 2019\n",
        encoding="utf-8",
    )

    with pytest.raises(AssertionError, match="Invalid year='TV Movie 2019' in movie tt8206668"):
        create_app(database_url, dirty_csv)
