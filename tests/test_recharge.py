import pytest
import requests

from fastapi import HTTPException

import recharge


class FakeResponse:
    def __init__(
        self,
        status_code=200,
        payload=None,
        text="",
    ):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"HTTP {self.status_code}"
            )

    def json(self):
        return self._payload


# -------------------------------------------------
# _request()
# -------------------------------------------------

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
        return FakeResponse(
            status_code=404,
            text="Not found",
        )

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
    assert (
        "Recharge API request failed with status 404."
        in exc.value.detail
    )


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
    assert exc.value.detail == (
        "Recharge connection timed out."
    )


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
    assert exc.value.detail == (
        "Recharge response timed out."
    )


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
    assert exc.value.detail == (
        "Unable to connect to Recharge."
    )


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
    assert exc.value.detail == (
        "Recharge API request failed."
    )


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


# -------------------------------------------------
# One-time: create
# -------------------------------------------------

def test_create_onetime_sends_correct_payload(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))

        return FakeResponse(
            201,
            {
                "onetime": {
                    "id": 700001
                }
            },
        )

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    result = recharge.create_onetime(
        address_id=12345,
        variant_id=456789,
        quantity=2,
        next_charge_date="2026-09-28T00:00:00Z",
        price="7.50",
    )

    assert result["onetime"]["id"] == 700001
    assert len(calls) == 1

    method, url, kwargs = calls[0]

    assert method == "POST"
    assert url.endswith("/onetimes")

    assert kwargs["json"] == {
        "address_id": 12345,
        "next_charge_scheduled_at":
            "2026-09-28T00:00:00Z",
        "external_variant_id": {
            "ecommerce": "456789"
        },
        "quantity": 2,
        "price": "7.50",
        "properties": [
            {
                "name": "subscription_type",
                "value": "extra",
            },
            {
                "name": "subscriber_discount",
                "value": "25",
            },
        ],
    }


# -------------------------------------------------
# One-time: update
# -------------------------------------------------

def test_update_onetime_quantity(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))

        return FakeResponse(
            200,
            {
                "onetime": {
                    "id": 700001,
                    "quantity": 3,
                }
            },
        )

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    result = recharge.update_onetime_quantity(
        onetime_id=700001,
        quantity=3,
    )

    assert result["onetime"]["quantity"] == 3
    assert len(calls) == 1

    method, url, kwargs = calls[0]

    assert method == "PUT"
    assert url.endswith("/onetimes/700001")
    assert kwargs["json"] == {
        "quantity": 3
    }


# -------------------------------------------------
# One-time: delete
# -------------------------------------------------

def test_delete_onetime(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse(204)

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    result = recharge.delete_onetime(
        onetime_id=700001
    )

    assert result == {
        "success": True
    }

    assert len(calls) == 1

    method, url, kwargs = calls[0]

    assert method == "DELETE"
    assert url.endswith("/onetimes/700001")


# -------------------------------------------------
# One-time: get
# -------------------------------------------------

def test_get_onetimes(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))

        return FakeResponse(
            200,
            {
                "onetimes": [
                    {
                        "id": 700001
                    }
                ]
            },
        )

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    result = recharge.get_onetimes(
        customer_id=12345,
        address_id=67890,
    )

    assert result["onetimes"][0]["id"] == 700001
    assert len(calls) == 1

    method, url, kwargs = calls[0]

    assert method == "GET"
    assert url.endswith("/onetimes")

    assert kwargs["params"] == {
        "limit": 250,
        "customer_id": 12345,
        "address_id": 67890,
    }


# -------------------------------------------------
# One-time: filtering
# -------------------------------------------------

def test_get_extra_onetimes_returns_only_matching_extra():
    original_get_onetimes = recharge.get_onetimes

    try:
        recharge.get_onetimes = lambda **kwargs: {
            "onetimes": [
                {
                    "id": 700001,
                    "shopify_variant_id": 111,
                    "product_title": "Extra Soup",
                    "price": "7.50",
                    "quantity": 1,
                    "next_charge_scheduled_at":
                        "2026-09-28T00:00:00Z",
                    "properties": [
                        {
                            "name": "subscription_type",
                            "value": "extra",
                        }
                    ],
                },
                {
                    "id": 700002,
                    "shopify_variant_id": 222,
                    "product_title": "Another Item",
                    "price": "5.00",
                    "quantity": 1,
                    "next_charge_scheduled_at":
                        "2026-10-05T00:00:00Z",
                    "properties": [
                        {
                            "name": "subscription_type",
                            "value": "extra",
                        }
                    ],
                },
                {
                    "id": 700003,
                    "shopify_variant_id": 333,
                    "product_title": "Not Extra",
                    "price": "4.00",
                    "quantity": 1,
                    "next_charge_scheduled_at":
                        "2026-09-28T00:00:00Z",
                    "properties": [],
                },
            ]
        }

        result = recharge.get_extra_onetimes(
            customer_id=12345,
            address_id=67890,
            next_charge_date=
                "2026-09-28T00:00:00Z",
        )

        assert len(result) == 1
        assert result[0] == {
            "subscription_id": 700001,
            "variant_id": 111,
            "title": "Extra Soup",
            "price": "7.50",
            "quantity": 1,
        }

    finally:
        recharge.get_onetimes = (
            original_get_onetimes
        )


# -------------------------------------------------
# Existing subscription expiry
# -------------------------------------------------

def test_set_subscription_expire_after_charges(
    monkeypatch,
):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))

        return FakeResponse(
            200,
            {
                "subscription": {
                    "id": 884363081
                }
            },
        )

    monkeypatch.setattr(
        recharge.requests,
        "request",
        fake_request,
    )

    result = (
        recharge
        .set_subscription_expire_after_charges(
            subscription_id=884363081,
            number_of_charges=1,
        )
    )

    assert result["subscription"]["id"] == 884363081
    assert len(calls) == 1

    method, url, kwargs = calls[0]

    assert method == "PUT"
    assert url.endswith(
        "/subscriptions/884363081"
    )

    assert kwargs["json"] == {
        "expire_after_specific_number_of_charges": 1
    }