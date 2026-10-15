import { useEffect, useState } from "react";

import { fetchMovies } from "./api";
import MovieCard from "./MovieCard";
import MovieDetails from "./MovieDetails";
import SearchBar from "./SearchBar";

const PAGE_SIZE = 24;
const SEARCH_DELAY_MS = 300;

export default function App() {
  const [field, setField] = useState("q");
  const [text, setText] = useState("");
  const [page, setPage] = useState(1);
  const [movies, setMovies] = useState({ total: 0, results: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      fetchMovies({ field, text: text.trim(), page, limit: PAGE_SIZE }, controller.signal)
        .then((data) => {
          setMovies(data);
          setError(null);
        })
        .catch((err) => {
          if (err.name !== "AbortError") setError(err.message);
        })
        .finally(() => setLoading(false));
    }, SEARCH_DELAY_MS);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [field, text, page]);

  function search(newField, newText) {
    setField(newField);
    setText(newText);
    setPage(1);
  }

  const totalPages = Math.max(1, Math.ceil(movies.total / PAGE_SIZE));
  const status = error ?? (loading ? "Searching…" : `${movies.total.toLocaleString()} movies`);

  return (
    <div className="page">
      <header>
        <h1>Movie Finder</h1>
        <SearchBar field={field} text={text} onChange={search} />
      </header>

      <main>
        <p className={error ? "status error" : "status"}>{status}</p>

        <section className="grid">
          {movies.results.map((movie) => (
            <MovieCard key={movie.imdb_title_id} movie={movie} onSelect={() => setSelectedId(movie.imdb_title_id)} />
          ))}
        </section>

        {totalPages > 1 && (
          <nav className="pagination">
            <button disabled={page === 1} onClick={() => setPage(page - 1)}>
              ← Previous
            </button>
            <span>
              Page {page} of {totalPages.toLocaleString()}
            </span>
            <button disabled={page === totalPages} onClick={() => setPage(page + 1)}>
              Next →
            </button>
          </nav>
        )}
      </main>

      {selectedId && <MovieDetails id={selectedId} onClose={() => setSelectedId(null)} />}
    </div>
  );
}
