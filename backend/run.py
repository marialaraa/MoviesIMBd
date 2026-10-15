import argparse
import os

from app import create_app

DEFAULT_DATABASE_URL = "postgresql://movies:movies@localhost:5432/movies"


def main():
    parser = argparse.ArgumentParser(description="IMDb movies API")
    parser.add_argument(
        "--csv",
        default=os.environ.get("MOVIES_CSV"),
        help="Path to the movies CSV (or set the MOVIES_CSV environment variable)",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="Postgres connection URL (or set the DATABASE_URL environment variable)",
    )
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if not args.csv:
        parser.error("provide the CSV with --csv or the MOVIES_CSV environment variable")

    app = create_app(args.database_url, args.csv)
    print(f"Loaded {app.config['MOVIES'].count()} movies from {args.csv}")
    app.run(port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
