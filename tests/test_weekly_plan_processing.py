
import json
from types import SimpleNamespace

from services import shopify_webhooks as service


def test_weekly_plan_does_not_create_child_subscriptions(monkeypatch):
    variant_ids = ["101", "102", "103", "104", "105"]
    create_calls = []

    order = SimpleNamespace(
        id=12345,
        customer=SimpleNamespace(id=9876),
        line_items=[
            SimpleNamespace(
                properties=[
                    SimpleNamespace(name="_plan_parent", value="true"),
                    SimpleNamespace(
                        name="_plan_item_variant_ids",
                        value=json.dumps(variant_ids),
                    ),
                    SimpleNamespace(
                        name="Preference",
                        value="vegetarian",
                    ),
                ],
            )
        ],
    )

    # Mock the existing Recharge customer.
    monkeypatch.setattr(
        service,
        "get_customer_by_shopify_id",
        lambda shopify_id: {"id": 555},
    )

    # Mock the existing Weekly Meal Plan parent subscription.
    monkeypatch.setattr(
        service,
        "get_subscriptions",
        lambda customer_id: {
            "subscriptions": [
                {
                    "id": 777,
                    "address_id": 888,
                    "next_charge_scheduled_at": "2026-11-01",
                    "properties": [
                        {"name": "_plan_parent", "value": "true"}
                    ],
                }
            ]
        },
    )

    # Fail the test if the code attempts to create child subscriptions.
    def unexpected_create_subscription(**kwargs):
        create_calls.append(kwargs)
        raise AssertionError(
            "Individual meal subscriptions must not be created"
        )

    monkeypatch.setattr(
        service,
        "create_subscription",
        unexpected_create_subscription,
    )

    result = service.process_paid_order(db=None, order=order)

    assert result["status"] == "success"
    assert result["order_id"] == 12345
    assert result["parent_subscription_id"] == 777
    assert result["created"] == []
    assert create_calls == []


def test_non_weekly_order_is_ignored():
    order = SimpleNamespace(
        id=12346,
        line_items=[
            SimpleNamespace(properties=[])
        ],
    )

    result = service.process_paid_order(db=None, order=order)

    assert result["status"] == "ignored"
    assert result["reason"] == "not_weekly_meal_plan"
    assert result["order_id"] == 12346
