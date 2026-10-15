export function Rating({ vote }) {
  const stars = Math.round(vote / 2);
  return (
    <span className="rating" title={`${vote} / 10`}>
      {"★".repeat(stars)}
      {"☆".repeat(5 - stars)} <small>{vote.toFixed(1)}</small>
    </span>
  );
}

export function Title({ movie }) {
  const original = movie.original_title ?? movie.title;
  return (
    <>
      <h2>{original}</h2>
      {movie.title !== original && <p className="translated">{movie.title}</p>}
    </>
  );
}

export default function MovieCard({ movie, onSelect }) {
  return (
    <button className="card" onClick={onSelect}>
      <Title movie={movie} />
      <p className="muted">
        {movie.year} · {movie.director ?? "Unknown director"}
      </p>
      <p className="genre">{movie.genre}</p>
      <Rating vote={movie.avg_vote} />
    </button>
  );
}
