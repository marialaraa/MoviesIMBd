CREATE INDEX movies_title_trgm ON movies USING gin (immutable_unaccent(title) gin_trgm_ops);
CREATE INDEX movies_original_title_trgm ON movies USING gin (immutable_unaccent(original_title) gin_trgm_ops);
CREATE INDEX movies_director_trgm ON movies USING gin (immutable_unaccent(director) gin_trgm_ops);
CREATE INDEX movies_writer_trgm ON movies USING gin (immutable_unaccent(writer) gin_trgm_ops);
CREATE INDEX movies_actors_trgm ON movies USING gin (immutable_unaccent(actors) gin_trgm_ops);
CREATE INDEX movies_genre_trgm ON movies USING gin (immutable_unaccent(genre) gin_trgm_ops);
CREATE INDEX movies_year ON movies (year);

ANALYZE movies;
