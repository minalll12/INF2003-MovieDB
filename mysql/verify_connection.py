"""Read-only connection check: run `python -m mysql.verify_connection` from the repo root."""
import sys

import pymysql

from .db import connect


def main():
    try:
        with connect() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("START TRANSACTION READ ONLY")
                    cursor.execute("SELECT DATABASE() AS database_name")
                    database = cursor.fetchone()["database_name"]
                    cursor.execute("SELECT COUNT(*) AS movie_count FROM movies")
                    movie_count = cursor.fetchone()["movie_count"]
            finally:
                connection.rollback()
    except (pymysql.MySQLError, OSError, ValueError):
        # Driver exceptions can contain connection details; never print them.
        print(
            "MySQL connection verification failed. Check DB_HOST, DB_PORT, DB_USER, "
            "DB_PASSWORD, DB_NAME and network access.",
            file=sys.stderr,
        )
        return 1

    print(f"Database: {database}")
    print(f"Movies: {movie_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
