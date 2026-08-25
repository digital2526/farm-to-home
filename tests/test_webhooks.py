import base64
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app


TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)

    yield

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


SECRET = "test-shopify-webhook-secret"

ORDER_BODY = b"""
{
    "id": 12345,
    "email": "customer@example.com",
    "total_price": "49.90",
    "subtotal_price": "45.00",
    "financial_status": "paid",
    "customer": {
        "id": 98765,
        "email": "customer@example.com"
    }
}
"""


def create_hmac(secret, body):
    digest = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()

    return base64.b64encode(digest).decode()


def signed_headers(body, event_id="test-event-001"):
    return {
        "X-Shopify-Hmac-Sha256": create_hmac(SECRET, body),
        "X-Shopify-Event-Id": event_id,
        "Content-Type": "application/json",
    }


def test_missing_hmac_is_rejected(client, monkeypatch):
    monkeypatch.setattr(
        "routes.webhooks.SHOPIFY_WEBHOOK_SECRET",
        SECRET,
    )

    response = client.post(
        "/webhooks/orders-paid",
        content=ORDER_BODY,
        headers={
            "X-Shopify-Event-Id": "event-missing-hmac",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing Shopify webhook signature."


def test_invalid_hmac_is_rejected(client, monkeypatch):
    monkeypatch.setattr(
        "routes.webhooks.SHOPIFY_WEBHOOK_SECRET",
        SECRET,
    )

    response = client.post(
        "/webhooks/orders-paid",
        content=ORDER_BODY,
        headers={
            "X-Shopify-Hmac-Sha256": "invalid-signature",
            "X-Shopify-Event-Id": "event-invalid-hmac",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid Shopify webhook signature."


def test_missing_event_id_is_rejected(client, monkeypatch):
    monkeypatch.setattr(
        "routes.webhooks.SHOPIFY_WEBHOOK_SECRET",
        SECRET,
    )

    response = client.post(
        "/webhooks/orders-paid",
        content=ORDER_BODY,
        headers={
            "X-Shopify-Hmac-Sha256": create_hmac(
                SECRET,
                ORDER_BODY,
            ),
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Shopify webhook event ID."


def test_valid_webhook_is_processed(client, monkeypatch):
    monkeypatch.setattr(
        "routes.webhooks.SHOPIFY_WEBHOOK_SECRET",
        SECRET,
    )

    response = client.post(
        "/webhooks/orders-paid",
        content=ORDER_BODY,
        headers=signed_headers(
            ORDER_BODY,
            "event-valid-001",
        ),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "duplicate"


def test_duplicate_webhook_delivery_is_rejected_as_duplicate(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        "routes.webhooks.SHOPIFY_WEBHOOK_SECRET",
        SECRET,
    )

    headers = signed_headers(
        ORDER_BODY,
        "event-duplicate-001",
    )

    first_response = client.post(
        "/webhooks/orders-paid",
        content=ORDER_BODY,
        headers=headers,
    )

    second_response = client.post(
        "/webhooks/orders-paid",
        content=ORDER_BODY,
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert second_response.json() == {
        "status": "duplicate",
        "message": "Shopify webhook delivery already processed.",
    }


def test_oversized_request_body_is_rejected(client):
    oversized_body = b"x" * (1024 * 1024 + 1)

    response = client.post(
        "/webhooks/orders-paid",
        content=oversized_body,
        headers={
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Request body too large."
