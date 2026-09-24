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
        "get_subscriptions",
        lambda customer_id: {
            "subscriptions": [
                {
                    "id": 884363081,
                    "status": "active",
                    "address_id": 12345,
                    "next_charge_scheduled_at": (
                        "2026-09-28T00:00:00Z"
                    ),
                    "properties": [
                        {
                            "name": "_plan_parent",
                            "value": "true",
                        }
                    ],
                }
            ]
        },
    )

    monkeypatch.setattr(
        add_extra,
        "get_charges",
        lambda **kwargs: {
            "charges": [
                {
                    "id": 900001,
                    "scheduled_at": (
                        "2026-09-28T00:00:00Z"
                    ),
                }
            ]
        },
    )

    monkeypatch.setattr(
        add_extra,
        "get_extra_onetime_by_variant",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        add_extra,
        "get_shopify_variant_price",
        lambda variant_id: 10,
    )

    monkeypatch.setattr(
        add_extra,
        "create_onetime",
        lambda **kwargs: {
            "onetime": {
                "id": 700001,
                "address_id": 12345,
                "external_variant_id": {
                    "ecommerce": "123456"
                },
                "quantity": 1,
                "price": "7.50",
                "next_charge_scheduled_at": (
                    "2026-09-28T00:00:00Z"
                ),
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
        },
    )

    result = add_extra.create_extra_subscription(
        shopify_customer_id=123456,
        variant_id=123456,
        quantity=1,
    )

    assert result["success"] is True
    assert result["delivery_date"] == (
        "2026-09-28T00:00:00Z"
    )
    assert result["address_id"] == 12345
    assert result["subscription"]["id"] == 700001

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