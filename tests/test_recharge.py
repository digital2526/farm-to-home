import pytest
import requests

from fastapi import HTTPException

import recharge


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"HTTP {self.status_code}"
            )


def test_successful_recharge_request(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse(200)

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    response = recharge._request(
        "GET",
        "https://recharge.test/customers",
    )

    assert response.status_code == 200
    assert len(calls) == 1


def test_recharge_http_error_is_exposed(monkeypatch):
    def fake_request(method, url, **kwargs):
        return FakeResponse(404)

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    with pytest.raises(HTTPException) as exc:
        recharge._request(
            "GET",
            "https://recharge.test/customers",
        )

    assert exc.value.status_code == 404
    assert "Recharge API request failed with status 404." in exc.value.detail


def test_connection_timeout_returns_504(monkeypatch):
    def fake_request(method, url, **kwargs):
        raise requests.exceptions.ConnectTimeout()

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    with pytest.raises(HTTPException) as exc:
        recharge._request(
            "GET",
            "https://recharge.test/customers",
        )

    assert exc.value.status_code == 504
    assert exc.value.detail == "Recharge connection timed out."


def test_read_timeout_returns_504(monkeypatch):
    def fake_request(method, url, **kwargs):
        raise requests.exceptions.ReadTimeout()

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    with pytest.raises(HTTPException) as exc:
        recharge._request(
            "GET",
            "https://recharge.test/customers",
        )

    assert exc.value.status_code == 504
    assert exc.value.detail == "Recharge response timed out."


def test_connection_error_returns_503(monkeypatch):
    def fake_request(method, url, **kwargs):
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    with pytest.raises(HTTPException) as exc:
        recharge._request(
            "GET",
            "https://recharge.test/customers",
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "Unable to connect to Recharge."


def test_other_request_error_returns_502(monkeypatch):
    def fake_request(method, url, **kwargs):
        raise requests.exceptions.RequestException()

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    with pytest.raises(HTTPException) as exc:
        recharge._request(
            "GET",
            "https://recharge.test/customers",
        )

    assert exc.value.status_code == 502
    assert exc.value.detail == "Recharge API request failed."


def test_get_request_retries(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(1)

        if len(calls) < 3:
            raise requests.exceptions.ConnectionError()

        return FakeResponse(200)

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    monkeypatch.setattr(
        recharge.time,
        "sleep",
        lambda _: None,
    )

    response = recharge._request(
        "GET",
        "https://recharge.test/customers",
        retry=True,
    )

    assert response.status_code == 200
    assert len(calls) == 3


def test_post_is_not_retried(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(1)
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    with pytest.raises(HTTPException) as exc:
        recharge._request(
            "POST",
            "https://recharge.test/subscriptions",
        )

    assert exc.value.status_code == 503
    assert len(calls) == 1