import json
import time

from sqlalchemy.orm import Session

from recharge import (
    create_subscription,
    get_customer_by_shopify_id,
    get_subscriptions,
)

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


PLAN_PARENT_PROPERTY = "_plan_parent"
PLAN_VARIANT_IDS_PROPERTY = "_plan_item_variant_ids"
PLAN_ORDER_ID_PROPERTY = "_plan_order_id"

PORTUGAL_TZ = ZoneInfo("Europe/Lisbon")



def calculate_delivery_details(created_at):
    """
    Calculate delivery information based on the order/charge
    creation time in Europe/Lisbon.

    Cut-off:
    Sunday 23:59 Lisbon time.

    Home delivery:
    Thursday following the cut-off.

    Pickup:
    Wednesday before that Thursday.
    """

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=PORTUGAL_TZ)

    local_dt = created_at.astimezone(PORTUGAL_TZ)

    # Monday = 0 ... Sunday = 6
    days_until_sunday = 6 - local_dt.weekday()

    cutoff_date = local_dt.date() + timedelta(
        days=days_until_sunday
    )

    cutoff = datetime(
        cutoff_date.year,
        cutoff_date.month,
        cutoff_date.day,
        23,
        59,
        59,
        tzinfo=PORTUGAL_TZ,
    )

    # If we're already past this Sunday's cut-off,
    # use the following Sunday.
    if local_dt > cutoff:
        cutoff_date += timedelta(days=7)

    # Thursday immediately after Sunday
    delivery_date = cutoff_date + timedelta(days=4)

    # Wednesday immediately before Thursday
    pickup_date = delivery_date - timedelta(days=1)

    return {
        "home": {
            "delivery_date": delivery_date,
            "delivery_day": "thursday",
            "delivery_time": "Durante o dia · DPD Fresh",
        },
        "pickup": {
            "delivery_date": pickup_date,
            "delivery_day": "wednesday",
            "delivery_time": "14:00-21:00",
        },
    }

def get_order_delivery_details(order):
    """
    Calculate delivery details for a Shopify order.

    Shipping address present:
        Thursday home delivery.

    No shipping address:
        Wednesday pickup.
    """

    if not order.created_at:
        raise RuntimeError(
            f"Shopify order {order.id} is missing created_at."
        )

    try:
        created_at = datetime.fromisoformat(
            order.created_at.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise RuntimeError(
            f"Invalid Shopify created_at for order {order.id}: "
            f"{order.created_at}"
        ) from exc

    delivery_options = calculate_delivery_details(
        created_at
    )

    if order.shipping_address:
        return delivery_options["home"]

    return delivery_options["pickup"]


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
    Verify the Weekly Meal Plan parent subscription in Recharge.
    Do not create individual meal subscriptions.

    Non-Weekly-Plan orders are ignored.
    """
    del db

    parent_line, properties = _find_weekly_plan_line(order)

    if not parent_line:
        return {
            "status": "ignored",
            "reason": "not_weekly_meal_plan",
            "order_id": order.id,
        }

    if not order.customer:
        raise RuntimeError(
            f"Weekly Meal Plan order {order.id} has no customer."
        )

    raw_variant_ids = properties.get(PLAN_VARIANT_IDS_PROPERTY)

    if not raw_variant_ids:
        raise RuntimeError(
            "Weekly Meal Plan is missing _plan_item_variant_ids."
        )

    try:
        variant_ids = json.loads(raw_variant_ids)
        if not isinstance(variant_ids, list):
            raise RuntimeError(
                "_plan_item_variant_ids must be an array."
            )
        variant_ids = [str(int(v)) for v in variant_ids]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise RuntimeError(
            "Invalid _plan_item_variant_ids."
        ) from exc

    if len(variant_ids) != 5:
        raise RuntimeError(
            f"Expected exactly 5 meal variants, received {len(variant_ids)}."
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
    parent_subscription = None

    for attempt in range(8):
        response = get_subscriptions(recharge_customer_id)
        subscriptions = response.get("subscriptions", [])

        parent_subscription = _find_parent_subscription(subscriptions)

        if parent_subscription:
            break

        if attempt < 7:
            time.sleep(2)

    if not parent_subscription:
        raise RuntimeError(
            "Recharge Weekly Meal Plan parent subscription was not found."
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
            "Parent Recharge subscription has no next_charge_scheduled_at."
        )

    print(
        "WEEKLY MEAL PLAN VERIFIED — child subscriptions disabled",
        {
            "order_id": order.id,
            "recharge_customer_id": recharge_customer_id,
            "parent_subscription_id": parent_subscription["id"],
            "child_subscriptions_created": 0,
        },
    )

    return {
        "status": "success",
        "order_id": order.id,
        "recharge_customer_id": recharge_customer_id,
        "parent_subscription_id": parent_subscription["id"],
        "message": "Parent verified; child subscriptions disabled.",
        "created": [],
        "skipped": [],
    }