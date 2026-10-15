const API_URL = "/api";

async function request(path, signal) {
  const response = await fetch(`${API_URL}${path}`, { signal });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error ?? `Request failed (${response.status})`);
  }
  return body;
}

export function fetchMovies({ field, text, page, limit }, signal) {
  const params = new URLSearchParams({ page, limit });
  if (text) {
    params.set(field, text);
  }
  return request(`/movies?${params}`, signal);
}

export function fetchMovie(id, signal) {
  return request(`/movies/${encodeURIComponent(id)}`, signal);
}
