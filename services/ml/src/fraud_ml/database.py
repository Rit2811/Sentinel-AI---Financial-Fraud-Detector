"""Server-only PostgreSQL target and verified Supabase TLS settings."""

from __future__ import annotations

import os
import hashlib
import json
from urllib.parse import parse_qs, unquote, urlsplit


def database_target_sha256(url):
    parsed = urlsplit(url)
    identity = {
        "database": unquote(parsed.path.lstrip("/")),
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": unquote(parsed.username or ""),
    }
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def application_database_matches(connection, expected_target=None):
    info = connection.info
    if expected_target is None:
        return info.dbname == "sentinel"
    identity = {
        "database": info.dbname,
        "host": info.host,
        "port": info.port,
        "user": info.user,
    }
    actual = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return (
        len(expected_target) == 64
        and actual == expected_target
        and info.host.endswith(".pooler.supabase.com")
        and info.port == 5432
        and info.dbname == "postgres"
        and connection.pgconn.ssl_in_use
    )


def database_connection(environment=None):
    env = os.environ if environment is None else environment
    postgres, database = env.get("POSTGRES_URL"), env.get("DATABASE_URL")
    if postgres and database and postgres != database:
        raise ValueError("Conflicting server database targets")
    url = postgres or database
    if not url:
        raise ValueError("Server database connection is required")
    try:
        parsed = urlsplit(url)
        host, port = parsed.hostname or "", parsed.port
    except ValueError:
        raise ValueError("Invalid server database connection format") from None
    if parsed.scheme not in ("postgres", "postgresql") or not host:
        raise ValueError("Server database must use PostgreSQL")
    if host.endswith(".pooler.supabase.com") or host.endswith(".supabase.co"):
        if host.endswith(".pooler.supabase.com") and port != 5432:
            raise ValueError("Supabase requires the approved Session pooler")
        query = parse_qs(parsed.query, keep_blank_values=True)
        if set(query) - {"sslmode", "sslrootcert", "application_name"}:
            raise ValueError("Unsupported remote database URL option")
        mode = query.get("sslmode", [env.get("PGSSLMODE")])[0]
        if mode and mode != "verify-full":
            raise ValueError("Remote database requires verified TLS")
        root = (
            env.get("POSTGRES_SSL_ROOT_CERT")
            or env.get("PGSSLROOTCERT")
            or query.get("sslrootcert", [None])[0]
        )
        if not root:
            raise ValueError("Remote database root certificate is required")
        return url, {"sslmode": "verify-full", "sslrootcert": root}
    return url, {}
