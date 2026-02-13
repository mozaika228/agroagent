import pytest

pytest.importorskip("jwt")

from app.auth import create_access_token


def test_create_access_token_returns_string():
    token = create_access_token("u1", "farmer")
    assert isinstance(token, str)
    assert len(token) > 20
