import pytest
from fastapi import HTTPException

from services.add_extra import create_extra_subscription
from services.update_extra import update_extra


def test_invalid_variant_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "services.add_extra.EXTRA_VARIANT_IDS",
        {111, 222},
    )

    with pytest.raises(HTTPException) as exc:
        create_extra_subscription(
            shopify_customer_id="123",
            variant_id=999,
            quantity=1,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "This product is not available as an extra."


def test_zero_quantity_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "services.add_extra.EXTRA_VARIANT_IDS",
        {111},
    )

    with pytest.raises(HTTPException) as exc:
        create_extra_subscription(
            shopify_customer_id="123",
            variant_id=111,
            quantity=0,
        )

    # If your current implementation reaches Recharge before
    # validating quantity, this test will expose that gap.
    assert exc.value.status_code == 400


def test_negative_quantity_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "services.add_extra.EXTRA_VARIANT_IDS",
        {111},
    )

    with pytest.raises(HTTPException) as exc:
        create_extra_subscription(
            shopify_customer_id="123",
            variant_id=111,
            quantity=-1,
        )

    assert exc.value.status_code == 400
