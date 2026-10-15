import { Fragment, useEffect, useState } from "react";

import { fetchMovie } from "./api";
import { Rating, Title } from "./MovieCard";

function currencySymbol(code) {
  try {
    const parts = new Intl.NumberFormat("en-US", { style: "currency", currency: code }).formatToParts(0);
    return parts.find((part) => part.type === "currency").value;
  } catch {
    return code;
  }
}

function formatMoney(value) {
  const [code, amount] = value.split(" ");
  if (!amount || Number.isNaN(Number(amount))) return value;
  const symbol = code === "$" ? "$" : currencySymbol(code);
  return `${symbol} ${Number(amount).toLocaleString("es-AR")}`;
}

const DETAILS = [
  ["director", "Director"],
  ["writer", "Writer"],
  ["actors", "Cast"],
  ["duration", "Duration", (minutes) => `${minutes} min`],
  ["date_published", "Published"],
  ["country", "Country"],
  ["language", "Language"],
  ["production_company", "Production"],
  ["metascore", "Metascore"],
  ["budget", "Budget", formatMoney],
  ["worlwide_gross_income", "Worldwide gross", formatMoney],
];

export default function MovieDetails({ id, onClose }) {
  const [movie, setMovie] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    fetchMovie(id, controller.signal)
      .then(setMovie)
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      });
    return () => controller.abort();
  }, [id]);

  useEffect(() => {
    const closeOnEscape = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div className="overlay" onClick={onClose}>
      <article className="details" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <button className="close" onClick={onClose} aria-label="Close">
          ×
        </button>

        {error && <p className="error">{error}</p>}
        {!movie && !error && <p className="muted">Loading…</p>}

        {movie && (
          <>
            <Title movie={movie} />
            <p className="muted">
              {movie.year} · {movie.genre}
            </p>
            <p>
              <Rating vote={movie.avg_vote} /> <span className="muted">· {movie.votes.toLocaleString()} votes</span>
            </p>
            {movie.description && <p className="description">{movie.description}</p>}

            <dl>
              {DETAILS.filter(([key]) => movie[key] != null).map(([key, label, format]) => (
                <Fragment key={key}>
                  <dt>{label}</dt>
                  <dd>{format ? format(movie[key]) : movie[key]}</dd>
                </Fragment>
              ))}
            </dl>
          </>
        )}
      </article>
    </div>
  );
}
