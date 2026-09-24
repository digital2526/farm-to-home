import time

import requests
from datetime import datetime
from fastapi import HTTPException

from config import BASE_URL, HEADERS


# -------------------------------------------------
# Recharge HTTP configuration
# -------------------------------------------------

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 20
REQUEST_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

MAX_GET_RETRIES = 2
RETRY_BACKOFF_SECONDS = 1


def _request(method, url, *, retry=False, **kwargs):
    """
    Make a Recharge API request with explicit timeouts
    and structured error handling.

    GET requests may be retried because they are idempotent.
    POST/PUT/DELETE requests are not automatically retried.
    """

    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", REQUEST_TIMEOUT)

    attempts = MAX_GET_RETRIES + 1 if retry else 1

    for attempt in range(attempts):
        try:
            response = requests.request(
                method,
                url,
                **kwargs,
            )

            response.raise_for_status()

            return response

        except requests.exceptions.ConnectTimeout as exc:
            if attempt < attempts - 1:
                time.sleep(
                    RETRY_BACKOFF_SECONDS * (attempt + 1)
                )
                continue

            raise HTTPException(
                status_code=504,
                detail="Recharge connection timed out.",
            ) from exc

        except requests.exceptions.ReadTimeout as exc:
            if attempt < attempts - 1:
                time.sleep(
                    RETRY_BACKOFF_SECONDS * (attempt + 1)
                )
                continue

            raise HTTPException(
                status_code=504,
                detail="Recharge response timed out.",
            ) from exc

        except requests.exceptions.ConnectionError as exc:
            if attempt < attempts - 1:
                time.sleep(
                    RETRY_BACKOFF_SECONDS * (attempt + 1)
                )
                continue

            raise HTTPException(
                status_code=503,
                detail="Unable to connect to Recharge.",
            ) from exc

        except requests.exceptions.HTTPError as exc:
            status_code = response.status_code
            response_text = getattr(response, "text", "")

            raise HTTPException(
                status_code=status_code,
                detail=(
                    f"Recharge API request failed with status "
                    f"{status_code}. {response_text}"
                ).strip(),
            ) from exc

        except requests.exceptions.RequestException as exc:
            raise HTTPException(
                status_code=502,
                detail="Recharge API request failed.",
            ) from exc


# -------------------------------------------------
# Subscriptions
# -------------------------------------------------

def get_subscriptions(customer_id):
    subscriptions = []
    cursor = None

    while True:
        params = {
            "customer_id": customer_id,
            "limit": 250,
        }

        if cursor:
            params["cursor"] = cursor

        response = _request(
            "GET",
            f"{BASE_URL}/subscriptions",
            params=params,
            retry=True,
        )

        data = response.json()

        subscriptions.extend(
            data.get("subscriptions", [])
        )

        cursor = data.get("next_cursor")

        if not cursor:
            break

    return {
        "subscriptions": subscriptions
    }



# -------------------------------------------------
# Addresses
# -------------------------------------------------

def get_addresses(customer_id):
    response = _request(
        "GET",
        f"{BASE_URL}/addresses",
        params={
            "customer_id": customer_id,
        },
        retry=True,
    )

    return response.json()


# -------------------------------------------------
# Create subscription
# -------------------------------------------------

def create_subscription(
    address_id,
    variant_id,
    quantity,
    next_charge_date,
    properties=None,
):
    if properties is None:
        properties = [
            {
                "name": "subscription_type",
                "value": "extra",
            },
            {
                "name": "subscriber_discount",
                "value": "25",
            },
        ]

    payload = {
        "address_id": int(address_id),
        "external_variant_id": {
            "ecommerce": str(variant_id)
        },
        "quantity": int(quantity),

        "order_interval_unit": "week",
        "order_interval_frequency": 1,
        "charge_interval_frequency": 1,

        "next_charge_scheduled_at": next_charge_date,

        "properties": properties,
    }

    response = _request(
        "POST",
        f"{BASE_URL}/subscriptions",
        json=payload,
    )

    return response.json()


# -------------------------------------------------
# One-times
# -------------------------------------------------

def get_onetimes(
    customer_id=None,
    address_id=None,
):
    onetimes = []
    cursor = None

    while True:
        params = {
            "limit": 250,
        }

        if customer_id is not None:
            params["customer_id"] = customer_id

        if address_id is not None:
            params["address_id"] = address_id

        if cursor:
            params["cursor"] = cursor

        response = _request(
            "GET",
            f"{BASE_URL}/onetimes",
            params=params,
            retry=True,
        )

        data = response.json()

        onetimes.extend(
            data.get("onetimes", [])
        )

        # Recharge may expose cursor as next_cursor
        # or next depending on response format.
        cursor = (
            data.get("next_cursor")
            or data.get("next")
        )

        if not cursor:
            break

    return {
        "onetimes": onetimes
    }


def get_onetime(onetime_id):
    response = _request(
        "GET",
        f"{BASE_URL}/onetimes/{onetime_id}",
        retry=True,
    )

    return response.json()


def create_onetime(
    address_id,
    variant_id,
    quantity,
    next_charge_date,
    price,
    properties=None,
):
    if properties is None:
        properties = [
            {
                "name": "subscription_type",
                "value": "extra",
            },
            {
                "name": "subscriber_discount",
                "value": "25",
            },
        ]

    payload = {
        "address_id": int(address_id),

        "next_charge_scheduled_at":
            next_charge_date,

        "external_variant_id": {
            "ecommerce": str(variant_id)
        },

        "quantity": int(quantity),

        "price": str(price),

        "properties": properties,
    }

    response = _request(
        "POST",
        f"{BASE_URL}/onetimes",
        json=payload,
    )

    return response.json()


def update_onetime_quantity(
    onetime_id,
    quantity,
):
    payload = {
        "quantity": int(quantity),
    }

    response = _request(
        "PUT",
        f"{BASE_URL}/onetimes/{onetime_id}",
        json=payload,
    )

    return response.json()


def delete_onetime(onetime_id):
    _request(
        "DELETE",
        f"{BASE_URL}/onetimes/{onetime_id}",
    )

    return {
        "success": True,
    }


def _is_extra_onetime(onetime):
    properties = onetime.get(
        "properties",
        [],
    )

    return any(
        str(prop.get("name", "")).lower()
        == "subscription_type"
        and str(prop.get("value", "")).lower()
        == "extra"
        for prop in properties
    )


def _get_onetime_variant_id(onetime):
    variant_id = onetime.get(
        "shopify_variant_id"
    )

    if variant_id:
        return str(variant_id)

    external_variant_id = onetime.get(
        "external_variant_id",
        {}
    )

    if isinstance(external_variant_id, dict):
        variant_id = external_variant_id.get(
            "ecommerce"
        )

    return (
        str(variant_id)
        if variant_id is not None
        else None
    )


def get_extra_onetime_by_variant(
    customer_id,
    variant_id,
    address_id=None,
    next_charge_date=None,
):
    onetimes = get_onetimes(
        customer_id=customer_id,
        address_id=address_id,
    )["onetimes"]

    target_variant_id = str(
        variant_id
    )

    for onetime in onetimes:

        if onetime.get("is_cancelled"):
            continue

        if not _is_extra_onetime(onetime):
            continue

        onetime_variant_id = (
            _get_onetime_variant_id(
                onetime
            )
        )

        if onetime_variant_id != target_variant_id:
            continue

        if (
            next_charge_date is not None
            and str(
                onetime.get(
                    "next_charge_scheduled_at",
                    ""
                )
            )
            != str(next_charge_date)
        ):
            continue

        return onetime

    return None


def get_valid_extra_onetime(
    recharge_customer_id,
    onetime_id,
):
    onetimes = get_onetimes(
        customer_id=recharge_customer_id,
    )["onetimes"]

    try:
        target_id = int(onetime_id)
    except (TypeError, ValueError):
        return None

    for onetime in onetimes:

        if onetime.get("id") != target_id:
            continue

        if onetime.get("is_cancelled"):
            return None

        if _is_extra_onetime(onetime):
            return onetime

        return None

    return None


def _same_datetime(value_a, value_b):
    if not value_a or not value_b:
        return False

    try:
        dt_a = datetime.fromisoformat(
            str(value_a).replace("Z", "+00:00")
        )
        dt_b = datetime.fromisoformat(
            str(value_b).replace("Z", "+00:00")
        )

        if dt_a.tzinfo and dt_b.tzinfo:
            return dt_a.astimezone().timestamp() == dt_b.astimezone().timestamp()

        return dt_a.replace(tzinfo=None) == dt_b.replace(tzinfo=None)

    except (ValueError, TypeError):
        return str(value_a) == str(value_b)
    
    
def get_extra_onetimes(
    customer_id,
    address_id,
    next_charge_date,
):
    onetimes = get_onetimes(
        customer_id=customer_id,
        address_id=address_id,
    )["onetimes"]

    extras = []

    for onetime in onetimes:

        if onetime.get("is_cancelled"):
            continue

        if not _is_extra_onetime(onetime):
            continue

        onetime_date = onetime.get(
            "next_charge_scheduled_at"
        )

        if not _same_datetime(
            onetime_date,
            next_charge_date,
        ):
            continue

        variant_id = _get_onetime_variant_id(
            onetime
        )

        if not variant_id:
            continue

        extras.append(
            {
                "subscription_id":
                    onetime["id"],

                "variant_id":
                    int(variant_id),

                "title":
                    onetime.get(
                        "product_title",
                        onetime.get(
                            "title",
                            ""
                        )
                    ),

                "price":
                    onetime.get(
                        "price",
                        0
                    ),

                "quantity":
                    onetime.get(
                        "quantity",
                        1
                    ),
            }
        )

    return extras


# -------------------------------------------------
# Delete subscription
# -------------------------------------------------

def delete_subscription(subscription_id):
    _request(
        "DELETE",
        f"{BASE_URL}/subscriptions/{subscription_id}",
    )

    return {
        "success": True,
    }


# -------------------------------------------------
# Extra subscriptions
# -------------------------------------------------

def get_extra_subscriptions(customer_id):
    
    print("🔵 get_extra_subscriptions START")
    print("customer_id:", customer_id)

    subscriptions = get_subscriptions(
        customer_id
    )["subscriptions"]

    print("🟡 TOTAL RECHARGE SUBSCRIPTIONS:", len(subscriptions))
    print("🟡 SUBSCRIPTIONS:")
    print(subscriptions)
    
    extras = []

    for subscription in subscriptions:
        print("🔎 CHECKING SUBSCRIPTION:", subscription.get("id"))
        print("   properties:", subscription.get("properties"))
        print("   product_title:", subscription.get("product_title"))
        print("   shopify_variant_id:", subscription.get("shopify_variant_id"))
        print("   external_variant_id:", subscription.get("external_variant_id"))
        
        properties = subscription.get(
            "properties",
            [],
        )

        is_extra = any(
            str(prop.get("name", "")).lower() == "subscription_type"
            and str(prop.get("value", "")).lower() == "extra"
            for prop in properties
        )

        if not is_extra:
            continue

        variant_id = subscription.get("shopify_variant_id")

        if not variant_id:
            external_variant_id = subscription.get(
                "external_variant_id",
                {}
            )

            variant_id = external_variant_id.get(
                "ecommerce"
            )

        if not variant_id:
            print("   ❌ NO VARIANT ID - SKIPPING")
            
            continue

        extras.append(
            {
                "subscription_id": subscription["id"],
                "variant_id": int(variant_id),
                "title": subscription.get(
                    "product_title",
                    ""
                ),
                "price": subscription.get(
                    "price",
                    0
                ),
                "quantity": subscription.get(
                    "quantity",
                    1
                ),
            }
        )
    print("🟢 FINAL EXTRAS:", extras)
    
    return extras

def set_subscription_next_charge_date(
    subscription_id,
    date,
):
    response = _request(
        "POST",
        f"{BASE_URL}/subscriptions/{subscription_id}/set_next_charge_date",
        json={
            "date": date,
        },
    )

    return response.json()


def set_subscription_expire_after_charges(
    subscription_id,
    number_of_charges=1,
):
    response = _request(
        "PUT",
        f"{BASE_URL}/subscriptions/{subscription_id}",
        json={
            "expire_after_specific_number_of_charges":
                int(number_of_charges)
        },
    )

    return response.json()

# -------------------------------------------------
# Customer lookup
# -------------------------------------------------

def get_customer_by_shopify_id(shopify_customer_id):
    response = _request(
        "GET",
        f"{BASE_URL}/customers",
        params={
            "external_customer_id": str(shopify_customer_id),
            "limit": 250,
        },
    )

    data = response.json()

    customers = data.get("customers", [])

    if not customers:
        return None

    return customers[0]


# -------------------------------------------------
# Validate extra subscription
# -------------------------------------------------

def get_valid_extra_subscription(
    recharge_customer_id,
    subscription_id,
):
    subscriptions = get_subscriptions(
        recharge_customer_id
    )["subscriptions"]
    
    
    for subscription in subscriptions:
        if subscription.get("id") != int(subscription_id):
            continue

        is_extra = any(
            prop.get("name") == "subscription_type"
            and prop.get("value") == "extra"
            for prop in subscription.get(
                "properties",
                [],
            )
        )

        if is_extra:
            return subscription

        return None

    return None


# -------------------------------------------------
# Update subscription quantity
# -------------------------------------------------

def update_subscription_quantity(
    subscription_id,
    quantity,
):
    payload = {
        "quantity": int(quantity),
    }

    response = _request(
        "PUT",
        f"{BASE_URL}/subscriptions/{subscription_id}",
        json=payload,
    )

    return response.json()


# -------------------------------------------------
# Find existing extra by variant
# -------------------------------------------------

def get_extra_subscription_by_variant(
    customer_id,
    variant_id,
):
    subscriptions = get_subscriptions(
        customer_id
    )["subscriptions"]

    target_variant_id = str(variant_id)

    for subscription in subscriptions:

        properties = subscription.get(
            "properties",
            [],
        )

        is_extra = any(
            str(p.get("name", "")).lower()
            == "subscription_type"
            and str(p.get("value", "")).lower()
            == "extra"
            for p in properties
        )

        if not is_extra:
            continue

        subscription_variant_id = (
            subscription.get("shopify_variant_id")
        )

        if not subscription_variant_id:
            external_variant_id = subscription.get(
                "external_variant_id",
                {},
            )

            subscription_variant_id = (
                external_variant_id.get("ecommerce")
            )

        if (
            subscription_variant_id
            and str(subscription_variant_id)
            == target_variant_id
        ):
            return subscription

    return None


# -------------------------------------------------
# Charges
# -------------------------------------------------

def get_charges(
    status="SUCCESS",
    limit=250,
    customer_id=None,
    address_id=None,
):
    charges = []
    cursor = None

    while True:
        params = {
            "status": status,
            "limit": limit,
        }

        if customer_id is not None:
            params["customer_id"] = customer_id

        if address_id is not None:
            params["address_id"] = address_id

        if cursor:
            params["cursor"] = cursor

        response = _request(
            "GET",
            f"{BASE_URL}/charges",
            params=params,
        )

        data = response.json()

        charges.extend(
            data.get("charges", [])
        )

        cursor = data.get("next_cursor")

        if not cursor:
            break

    return {
        "charges": charges
    }


# -------------------------------------------------
# Get customer
# -------------------------------------------------

def get_customer(customer_id):
    response = _request(
        "GET",
        f"{BASE_URL}/customers/{customer_id}",
        retry=True,
    )

    return response.json()


def get_delivery_schedule(customer_id):
    response = _request(
        "GET",
        f"{BASE_URL}/customers/{customer_id}/delivery_schedule",
        params={
            "delivery_count_future": 1,
        },
    )

    return response.json()