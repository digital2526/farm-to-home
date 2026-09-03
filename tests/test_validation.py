import pytest
from fastapi import HTTPException

from services import add_extra


def test_invalid_variant_is_rejected(monkeypatch):
    monkeypatch.setattr(
        add_extra,
        "is_extra_variant",
        lambda variant_id: False,
    )

    with pytest.raises(HTTPException) as exc:
        add_extra.create_extra_subscription(
            shopify_customer_id="123",
            variant_id=999,
            quantity=1,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "This product is not available as an extra."


def test_valid_variant_is_allowed(monkeypatch):
    monkeypatch.setattr(
        add_extra,
        "is_extra_variant",
        lambda variant_id: True,
    )

    monkeypatch.setattr(
        add_extra,
        "get_customer_by_shopify_id",
        lambda customer_id: {
            "id": "recharge-customer-123"
        },
    )

    monkeypatch.setattr(
        add_extra,
        "get_extra_subscription_by_variant",
        lambda customer_id, variant_id: None,
    )

    monkeypatch.setattr(
        add_extra,
        "get_addresses",
        lambda customer_id: {
            "addresses": [
                {"id": "address-123"}
            ]
        },
    )

    monkeypatch.setattr(
        add_extra,
        "get_subscriptions",
        lambda customer_id: {
            "subscriptions": [
                {
                    "id": "subscription-123",
                    "status": "ACTIVE",
                    "next_charge_scheduled_at": "2026-09-10T10:00:00Z",
                    "address_id": "address-123",
                }
            ]
        },
    )

    monkeypatch.setattr(
        add_extra,
        "create_subscription",
        lambda **kwargs: {
            "subscription": {
                "id": "new-subscription"
            }
        },
    )

    result = add_extra.create_extra_subscription(
        shopify_customer_id="123",
        variant_id=58829308559744,
        quantity=1,
    )

    assert result["success"] is True


def test_zero_quantity_is_rejected(monkeypatch):
    monkeypatch.setattr(
        add_extra,
        "is_extra_variant",
        lambda variant_id: True,
    )

    with pytest.raises(HTTPException) as exc:
        add_extra.create_extra_subscription(
            shopify_customer_id="123",
            variant_id=111,
            quantity=0,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Quantity must be at least 1."


def test_negative_quantity_is_rejected(monkeypatch):
    monkeypatch.setattr(
        add_extra,
        "is_extra_variant",
        lambda variant_id: True,
    )

    with pytest.raises(HTTPException) as exc:
        add_extra.create_extra_subscription(
            shopify_customer_id="123",
            variant_id=111,
            quantity=-1,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Quantity must be at least 1."