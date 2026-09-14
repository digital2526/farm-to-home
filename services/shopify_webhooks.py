import json
import time

from sqlalchemy.orm import Session

from recharge import (
    create_subscription,
    get_customer_by_shopify_id,
    get_subscriptions,
)

PLAN_PARENT_PROPERTY = "_plan_parent"
PLAN_VARIANT_IDS_PROPERTY = "_plan_item_variant_ids"
PLAN_ORDER_ID_PROPERTY = "_plan_order_id"
PLAN_ITEM_PROPERTY = "_plan_item"
PLAN_SUBSCRIPTION_TYPE = "plan_item"


def _properties_dict(properties):
    return {
        str(prop.name): prop.value
        for prop in properties
        if prop.name
    }


def _find_weekly_plan_line(order):
    for line in order.line_items:
        props = _properties_dict(line.properties)

        if props.get(PLAN_PARENT_PROPERTY) == "true":
            return line, props

    return None, None


def _find_parent_subscription(subscriptions):
    for subscription in subscriptions:
        properties = subscription.get("properties", [])

        for prop in properties:
            if (
                str(prop.get("name", "")) == PLAN_PARENT_PROPERTY
                and str(prop.get("value", "")).lower() == "true"
            ):
                return subscription

    return None


def _existing_plan_item_variants(subscriptions, order_id):
    result = set()

    for subscription in subscriptions:
        properties = {
            str(prop.get("name", "")): prop.get("value")
            for prop in subscription.get("properties", [])
        }

        if (
            properties.get(PLAN_ITEM_PROPERTY) == "true"
            and str(properties.get(PLAN_ORDER_ID_PROPERTY, "")) == str(order_id)
        ):
            variant_id = subscription.get("shopify_variant_id")

            if not variant_id:
                external_variant_id = subscription.get(
                    "external_variant_id",
                    {},
                )
                variant_id = external_variant_id.get("ecommerce")

            if variant_id:
                result.add(str(variant_id))

    return result


def process_paid_order(
    db: Session,
    order,
):
    """
    Create the five Weekly Meal Plan component subscriptions
    in Recharge after the Shopify order is paid.

    Shopify checkout contains only the paid parent Weekly Meal Plan
    line. The selected meal subscription variant IDs are carried in
    private line-item properties.
    """

    del db  # no database write required here

    if not order.customer:
        print("⚠️ Weekly plan order has no Shopify customer.")
        return {
            "status": "ignored",
            "reason": "missing_customer",
            "order_id": order.id,
        }

    plan_line, properties = _find_weekly_plan_line(order)

    if not plan_line:
        print(
            f"ℹ️ Order {order.id} is not a Weekly Meal Plan order."
        )
        return {
            "status": "ignored",
            "reason": "not_weekly_plan",
            "order_id": order.id,
        }

    raw_variant_ids = properties.get(
        PLAN_VARIANT_IDS_PROPERTY
    )

    if not raw_variant_ids:
        raise RuntimeError(
            "Weekly Meal Plan order is missing "
            "_plan_item_variant_ids."
        )

    try:
        meal_variant_ids = json.loads(raw_variant_ids)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Invalid _plan_item_variant_ids JSON."
        ) from exc

    if not isinstance(meal_variant_ids, list):
        raise RuntimeError(
            "_plan_item_variant_ids must be a list."
        )

    meal_variant_ids = [
        str(int(variant_id))
        for variant_id in meal_variant_ids
    ]

    if len(meal_variant_ids) != 5:
        raise RuntimeError(
            f"Weekly Meal Plan must contain exactly 5 meals, "
            f"received {len(meal_variant_ids)}."
        )

    recharge_customer = get_customer_by_shopify_id(
        order.customer.id
    )

    if not recharge_customer:
        raise RuntimeError(
            f"Recharge customer not found for Shopify customer "
            f"{order.customer.id}."
        )

    recharge_customer_id = recharge_customer["id"]

    # Recharge may finish creating the parent subscription
    # slightly after Shopify sends orders/paid.
    parent_subscription = None
    subscriptions = []

    for attempt in range(6):
        subscriptions = get_subscriptions(
            recharge_customer_id
        )["subscriptions"]

        parent_subscription = _find_parent_subscription(
            subscriptions
        )

        if parent_subscription:
            break

        if attempt < 5:
            time.sleep(2)

    if not parent_subscription:
        raise RuntimeError(
            "Weekly Meal Plan parent Recharge subscription "
            "was not found yet."
        )

    address_id = parent_subscription.get("address_id")
    next_charge_date = parent_subscription.get(
        "next_charge_scheduled_at"
    )

    if not address_id:
        raise RuntimeError(
            "Parent Weekly Meal Plan has no Recharge address_id."
        )

    if not next_charge_date:
        raise RuntimeError(
            "Parent Weekly Meal Plan has no next charge date."
        )

    existing_variant_ids = _existing_plan_item_variants(
        subscriptions,
        order.id,
    )

    created = []
    skipped = []

    preference = properties.get("Preference", "")

    for variant_id in meal_variant_ids:

        if variant_id in existing_variant_ids:
            skipped.append(int(variant_id))
            continue

        result = create_subscription(
            address_id=address_id,
            variant_id=variant_id,
            quantity=1,
            next_charge_date=next_charge_date,
            properties=[
                {
                    "name": "subscription_type",
                    "value": PLAN_SUBSCRIPTION_TYPE,
                },
                {
                    "name": PLAN_ITEM_PROPERTY,
                    "value": "true",
                },
                {
                    "name": PLAN_ORDER_ID_PROPERTY,
                    "value": str(order.id),
                },
                {
                    "name": "_plan_parent_subscription_id",
                    "value": str(parent_subscription["id"]),
                },
                {
                    "name": "_plan_preference",
                    "value": preference,
                },
            ],
        )

        created.append(
            {
                "variant_id": int(variant_id),
                "subscription_id": result.get(
                    "subscription",
                    {}
                ).get("id"),
            }
        )

    print(
        "✅ Weekly Meal Plan processed",
        {
            "order_id": order.id,
            "recharge_customer_id": recharge_customer_id,
            "parent_subscription_id": parent_subscription["id"],
            "address_id": address_id,
            "next_charge_date": next_charge_date,
            "created": created,
            "skipped": skipped,
        },
    )

    return {
        "status": "success",
        "order_id": order.id,
        "customer_id": order.customer.id,
        "parent_subscription_id": parent_subscription["id"],
        "created": created,
        "skipped": skipped,
    }