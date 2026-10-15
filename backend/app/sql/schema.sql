CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- unaccent() is STABLE, so it can't be used in an index; this wrapper pins the dictionary and is IMMUTABLE.
CREATE OR REPLACE FUNCTION immutable_unaccent(text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
    AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$;

DROP TABLE IF EXISTS movies;

CREATE TABLE movies (
    imdb_title_id         text PRIMARY KEY,
    title                 text NOT NULL,
    original_title        text,
    year                  integer,
    date_published        text,
    genre                 text,
    duration              integer,
    country               text,
    language              text,
    director              text,
    writer                text,
    production_company    text,
    actors                text,
    description           text,
    avg_vote              double precision,
    votes                 integer,
    budget                text,
    usa_gross_income      text,
    worlwide_gross_income text,
    metascore             integer,
    reviews_from_users    double precision,
    reviews_from_critics  double precision
);
