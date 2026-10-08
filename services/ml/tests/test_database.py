import pytest
from types import SimpleNamespace

from fraud_ml.database import (
    application_database_matches,
    database_connection,
    database_target_sha256,
)


URL = "postgresql://postgres.example:placeholder@aws-0-example.pooler.supabase.com:5432/postgres"


def test_session_pooler_uses_verified_tls():
    assert database_connection(
        {"DATABASE_URL": URL, "PGSSLROOTCERT": "/trusted/root.crt"}
    ) == (URL, {"sslmode": "verify-full", "sslrootcert": "/trusted/root.crt"})


def test_local_target_is_unchanged():
    assert database_connection(
        {"POSTGRES_URL": "postgresql://sentinel:placeholder@postgres/sentinel"}
    ) == ("postgresql://sentinel:placeholder@postgres/sentinel", {})


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"POSTGRES_URL": URL, "DATABASE_URL": "postgresql://other/target"},
        {"DATABASE_URL": URL},
        {"DATABASE_URL": URL.replace(":5432/", ":6543/"), "PGSSLROOTCERT": "/root.crt"},
        {"DATABASE_URL": URL + "?sslmode=require", "PGSSLROOTCERT": "/root.crt"},
        {"DATABASE_URL": URL + "?host=other", "PGSSLROOTCERT": "/root.crt"},
    ],
)
def test_invalid_target_is_rejected_without_secret_details(env):
    with pytest.raises(ValueError) as error:
        database_connection(env)
    assert "placeholder" not in str(error.value)


def cloud_connection(**changes):
    values = dict(
        dbname="postgres",
        host="aws-0-example.pooler.supabase.com",
        port=5432,
        user="postgres.example",
    )
    values.update(changes)
    return SimpleNamespace(
        info=SimpleNamespace(**values), pgconn=SimpleNamespace(ssl_in_use=True)
    )


def test_application_cloud_guard_requires_exact_identity_and_tls():
    connection = cloud_connection()
    pin = database_target_sha256(URL)
    assert application_database_matches(connection, pin)
    assert not application_database_matches(connection)
    assert not application_database_matches(
        cloud_connection(user="postgres.other"), pin
    )
    assert not application_database_matches(cloud_connection(port=6543), pin)
    assert not application_database_matches(cloud_connection(dbname="sentinel"), pin)
    connection.pgconn.ssl_in_use = False
    assert not application_database_matches(connection, pin)


def test_local_application_guard_is_unchanged():
    assert application_database_matches(
        SimpleNamespace(info=SimpleNamespace(dbname="sentinel"))
    )


def test_pinned_local_application_requires_exact_private_identity():
    url = "postgresql://sentinel:placeholder@postgres:5432/sentinel"
    connection = cloud_connection(host="postgres", user="sentinel", dbname="sentinel")
    connection.pgconn.ssl_in_use = False
    pin = database_target_sha256(url)
    assert application_database_matches(connection, pin)
    assert not application_database_matches(
        cloud_connection(host="postgres", user="other", dbname="sentinel"), pin
    )
    assert not application_database_matches(
        cloud_connection(host="public.example", user="sentinel", dbname="sentinel"), pin
    )
    assert not application_database_matches(connection, "a" * 64)
