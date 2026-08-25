import hashlib
import hmac
import time

import pytest
from fastapi import HTTPException
from fastapi import Request
from starlette.requests import Request as StarletteRequest

from shopify_auth import verify_shopify_proxy


SECRET = "test-shopify-api-secret"


def make_signature(params):
    message = "".join(
        f"{key}={value}"
        for key, value in sorted(params.items())
        if key != "signature"
    )

    return hmac.new(
        SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()


def make_request(params):
    query_string = "&".join(
        f"{key}={value}"
        for key, value in params.items()
    )

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/seeds/dashboard",
        "query_string": query_string.encode(),
        "headers": [],
        "server": ("testserver", 80),
        "client": ("testclient", 12345),
        "scheme": "http",
    }

    return StarletteRequest(scope)


@pytest.fixture
def shopify_secret(monkeypatch):
    monkeypatch.setattr(
        "shopify_auth.SHOPIFY_API_SECRET",
        SECRET,
    )


@pytest.mark.asyncio
async def test_missing_shopify_signature_is_rejected(shopify_secret):
    timestamp = str(int(time.time()))

    params = {
        "logged_in_customer_id": "1001",
        "timestamp": timestamp,
    }

    request = make_request(params)

    with pytest.raises(HTTPException) as exc:
        await verify_shopify_proxy(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Missing Shopify signature."


@pytest.mark.asyncio
async def test_invalid_shopify_signature_is_rejected(shopify_secret):
    timestamp = str(int(time.time()))

    params = {
        "logged_in_customer_id": "1001",
        "timestamp": timestamp,
        "signature": "invalid-signature",
    }

    request = make_request(params)

    with pytest.raises(HTTPException) as exc:
        await verify_shopify_proxy(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid Shopify signature."


@pytest.mark.asyncio
async def test_expired_shopify_request_is_rejected(shopify_secret):
    timestamp = str(int(time.time()) - 600)

    params = {
        "logged_in_customer_id": "1001",
        "timestamp": timestamp,
    }

    params["signature"] = make_signature(params)

    request = make_request(params)

    with pytest.raises(HTTPException) as exc:
        await verify_shopify_proxy(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Expired Shopify proxy request."


@pytest.mark.asyncio
async def test_missing_timestamp_is_rejected(shopify_secret):
    params = {
        "logged_in_customer_id": "1001",
    }

    params["signature"] = make_signature(params)

    request = make_request(params)

    with pytest.raises(HTTPException) as exc:
        await verify_shopify_proxy(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Missing Shopify timestamp."


@pytest.mark.asyncio
async def test_missing_customer_is_rejected(shopify_secret):
    timestamp = str(int(time.time()))

    params = {
        "timestamp": timestamp,
    }

    params["signature"] = make_signature(params)

    request = make_request(params)

    with pytest.raises(HTTPException) as exc:
        await verify_shopify_proxy(request)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Customer is not logged in."


@pytest.mark.asyncio
async def test_valid_shopify_proxy_returns_signed_customer_id(
    shopify_secret,
):
    timestamp = str(int(time.time()))

    params = {
        "logged_in_customer_id": "1001",
        "timestamp": timestamp,
    }

    params["signature"] = make_signature(params)

    request = make_request(params)

    customer_id = await verify_shopify_proxy(request)

    assert customer_id == "1001"