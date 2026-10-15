const FIELDS = [
  ["q", "All fields"],
  ["title", "Title"],
  ["director", "Director"],
  ["writer", "Writer"],
  ["actors", "Actors"],
  ["genre", "Genre"],
  ["year", "Year"],
];

export default function SearchBar({ field, text, onChange }) {
  return (
    <div className="search">
      <select value={field} onChange={(e) => onChange(e.target.value, text)} aria-label="Search in">
        {FIELDS.map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>

      <input
        type="search"
        inputMode={field === "year" ? "numeric" : "search"}
        value={text}
        onChange={(e) => onChange(field, e.target.value)}
        placeholder="Search movies…"
        aria-label="Search text"
        autoFocus
      />

      <span className="search-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.5">
          <circle cx="10.5" cy="10.5" r="6.5" />
          <line x1="15.5" y1="15.5" x2="21" y2="21" strokeLinecap="round" />
        </svg>
      </span>
    </div>
  );
}
