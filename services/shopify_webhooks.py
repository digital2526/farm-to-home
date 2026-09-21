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


def _properties_dict(properties):
    return {
        str(prop.name): prop.value
        for prop in properties
        if prop.name
    }


def _find_weekly_plan_line(order):
    for line in order.line_items:
        properties = _properties_dict(line.properties)

        if properties.get(PLAN_PARENT_PROPERTY) == "true":
            return line, properties

    return None, None


def _find_parent_subscription(subscriptions):
    for subscription in subscriptions:
        for prop in subscription.get("properties", []):
            if (
                str(prop.get("name", "")) == PLAN_PARENT_PROPERTY
                and str(prop.get("value", "")).lower() == "true"
            ):
                return subscription

    return None


def _get_variant_id(subscription):
    variant_id = subscription.get("shopify_variant_id")

    if variant_id:
        return str(variant_id)

    external_variant_id = subscription.get(
        "external_variant_id",
        {}
    )

    variant_id = external_variant_id.get("ecommerce")

    return str(variant_id) if variant_id else None


def _get_existing_plan_items(subscriptions, order_id):
    existing = set()

    for subscription in subscriptions:
        properties = {
            str(prop.get("name", "")): prop.get("value")
            for prop in subscription.get("properties", [])
        }

        if (
            properties.get("subscription_type") == "plan_item"
            and str(properties.get(PLAN_ORDER_ID_PROPERTY, ""))
            == str(order_id)
        ):
            variant_id = _get_variant_id(subscription)

            if variant_id:
                existing.add(variant_id)

    return existing


def process_paid_order(
    db: Session,
    order,
):
    """
    Process a paid Weekly Meal Plan order.

    Shopify contains one paid parent line.
    The selected five subscription variant IDs are stored
    on that line in private properties.

    This function creates five recurring Recharge child
    subscriptions using the parent's address and charge date.

    Non-Weekly-Plan orders are ignored.
    """

    del db

    # ---------------------------------------------------------
    # Find Weekly Meal Plan parent line
    # ---------------------------------------------------------

    parent_line, properties = _find_weekly_plan_line(order)

    if not parent_line:
        return {
            "status": "ignored",
            "reason": "not_weekly_meal_plan",
            "order_id": order.id,
        }

    # ---------------------------------------------------------
    # Validate customer
    # ---------------------------------------------------------

    if not order.customer:
        raise RuntimeError(
            f"Weekly Meal Plan order {order.id} has no customer."
        )

    # ---------------------------------------------------------
    # Read selected five subscription variant IDs
    # ---------------------------------------------------------

    raw_variant_ids = properties.get(
        PLAN_VARIANT_IDS_PROPERTY
    )

    if not raw_variant_ids:
        raise RuntimeError(
            "Weekly Meal Plan is missing "
            "_plan_item_variant_ids."
        )

    try:
        variant_ids = json.loads(raw_variant_ids)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Invalid _plan_item_variant_ids JSON."
        ) from exc

    if not isinstance(variant_ids, list):
        raise RuntimeError(
            "_plan_item_variant_ids must be an array."
        )

    variant_ids = [
        str(int(variant_id))
        for variant_id in variant_ids
    ]

    if len(variant_ids) != 5:
        raise RuntimeError(
            f"Expected exactly 5 meal variants, "
            f"received {len(variant_ids)}."
        )

    # ---------------------------------------------------------
    # Find Recharge customer
    # ---------------------------------------------------------

    recharge_customer = get_customer_by_shopify_id(
        order.customer.id
    )

    if not recharge_customer:
        raise RuntimeError(
            f"Recharge customer not found for Shopify "
            f"customer {order.customer.id}."
        )

    recharge_customer_id = recharge_customer["id"]

    # ---------------------------------------------------------
    # Wait for Recharge parent subscription
    #
    # The Shopify order can arrive slightly before Recharge
    # finishes creating the parent subscription.
    # ---------------------------------------------------------

    parent_subscription = None
    subscriptions = []

    for attempt in range(8):

        subscriptions = get_subscriptions(
            recharge_customer_id
        )["subscriptions"]

        parent_subscription = _find_parent_subscription(
            subscriptions
        )

        if parent_subscription:
            break

        if attempt < 7:
            time.sleep(2)

    if not parent_subscription:
        raise RuntimeError(
            "Recharge Weekly Meal Plan parent subscription "
            "was not found."
        )

    address_id = parent_subscription.get("address_id")

    next_charge_date = parent_subscription.get(
        "next_charge_scheduled_at"
    )

    if not address_id:
        raise RuntimeError(
            "Parent Recharge subscription has no address_id."
        )

    if not next_charge_date:
        raise RuntimeError(
            "Parent Recharge subscription has no "
            "next_charge_scheduled_at."
        )

    # ---------------------------------------------------------
    # Prevent duplicate child subscriptions
    # ---------------------------------------------------------

    existing_variant_ids = _get_existing_plan_items(
        subscriptions,
        order.id,
    )

    preference = properties.get(
        "Preference",
        "",
    )

    created = []
    skipped = []

    # ---------------------------------------------------------
    # Create five Recharge child subscriptions
    # ---------------------------------------------------------

    for variant_id in variant_ids:

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
                    "value": "plan_item",
                },
                {
                    "name": "_plan_item",
                    "value": "true",
                },
                {
                    "name": "_plan_order_id",
                    "value": str(order.id),
                },
                {
                    "name": "_plan_parent_subscription_id",
                    "value": str(
                        parent_subscription["id"]
                    ),
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
                "subscription_id": (
                    result
                    .get("subscription", {})
                    .get("id")
                ),
            }
        )

    print(
        "✅ WEEKLY MEAL PLAN PROCESSED",
        {
            "order_id": order.id,
            "shopify_customer_id": order.customer.id,
            "recharge_customer_id": recharge_customer_id,
            "parent_subscription_id": parent_subscription["id"],
            "address_id": address_id,
            "next_charge_date": next_charge_date,
            "preference": preference,
            "created": created,
            "skipped": skipped,
        },
    )

    return {
        "status": "success",
        "order_id": order.id,
        "recharge_customer_id": recharge_customer_id,
        "parent_subscription_id": parent_subscription["id"],
        "created": created,
        "skipped": skipped,
    }