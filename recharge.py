import time

import requests
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

            raise HTTPException(
                status_code=status_code,
                detail=(
                    f"Recharge API request failed with status "
                    f"{status_code}: {response.text}"
                ),
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

def create_subscription(address_id, variant_id, quantity, next_charge_date):

    payload = {
        "address_id": address_id,
        "shopify_variant_id": int(variant_id),
        "quantity": int(quantity),

        "order_interval_unit": "week",
        "order_interval_frequency": "1",
        "charge_interval_frequency": "1",

        "next_charge_scheduled_at": next_charge_date,

        "properties": [
            {
                "name": "subscription_type",
                "value": "extra"
            },
            {
                "name": "subscriber_discount",
                "value": "25"
            }
        ]
    }

    response = requests.post(
        f"{BASE_URL}/subscriptions",
        headers=HEADERS,
        json=payload
    )

    response.raise_for_status()

    return response.json()
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
    subscriptions = get_subscriptions(
        customer_id
    )["subscriptions"]

    extras = []

    for subscription in subscriptions:
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

    for subscription in subscriptions:
        if (
            subscription.get("shopify_variant_id")
            == int(variant_id)
            and any(
                p.get("name") == "subscription_type"
                and p.get("value") == "extra"
                for p in subscription.get(
                    "properties",
                    [],
                )
            )
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