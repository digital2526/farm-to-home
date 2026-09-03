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
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue

            raise HTTPException(
                status_code=504,
                detail="Recharge connection timed out.",
            ) from exc

        except requests.exceptions.ReadTimeout as exc:
            if attempt < attempts - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue

            raise HTTPException(
                status_code=504,
                detail="Recharge response timed out.",
            ) from exc

        except requests.exceptions.ConnectionError as exc:
            if attempt < attempts - 1:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue

            raise HTTPException(
                status_code=503,
                detail="Unable to connect to Recharge.",
            ) from exc

        except requests.exceptions.HTTPError as exc:
            status_code = response.status_code

            raise HTTPException(
                status_code=status_code,
                detail=f"Recharge API request failed with status {status_code}.",
            ) from exc

        except requests.exceptions.RequestException as exc:
            raise HTTPException(
                status_code=502,
                detail="Recharge API request failed.",
            ) from exc


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


def create_subscription(
    address_id,
    variant_id,
    quantity,
    next_charge_date,
):

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
                "value": "extra",
            },
            {
                "name": "subscriber_discount",
                "value": "25",
            },
        ],
    }

    response = _request(
        "POST",
        f"{BASE_URL}/subscriptions",
        json=payload,
    )

    return response.json()


def delete_subscription(subscription_id):

    _request(
        "DELETE",
        f"{BASE_URL}/subscriptions/{subscription_id}",
    )

    return {
        "success": True,
    }


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

        is_extra = False

        for prop in properties:

            if (
                prop["name"] == "subscription_type"
                and prop["value"] == "extra"
            ):
                is_extra = True
                break

        if is_extra:

            extras.append(
                {
                    "subscription_id": subscription["id"],
                    "variant_id": subscription[
                        "shopify_variant_id"
                    ],
                    "title": subscription[
                        "product_title"
                    ],
                    "price": subscription["price"],
                    "quantity": subscription.get(
                        "quantity",
                        1,
                    ),
                }
            )

    return extras


def get_customer_by_shopify_id(
    shopify_customer_id,
):

    response = _request(
        "GET",
        f"{BASE_URL}/customers",
        params={
            "shopify_customer_id": shopify_customer_id,
        },
        retry=True,
    )

    customers = response.json()["customers"]

    if not customers:

        raise HTTPException(
            status_code=404,
            detail="Recharge customer not found.",
        )

    return customers[0]


def get_valid_extra_subscription(
    recharge_customer_id,
    subscription_id,
):
    subscriptions = get_subscriptions(
        recharge_customer_id
    )["subscriptions"]

    for subscription in subscriptions:
        if subscription["id"] != int(subscription_id):
            continue

        is_extra = any(
            prop["name"] == "subscription_type"
            and prop["value"] == "extra"
            for prop in subscription.get("properties", [])
        )

        if is_extra:
            return subscription

        return None

    return None




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
                p["name"] == "subscription_type"
                and p["value"] == "extra"
                for p in subscription.get(
                    "properties",
                    [],
                )
            )
        ):
            return subscription

    return None


def get_charges(
    status="SUCCESS",
    limit=250,
):
    charges = []
    cursor = None

    while True:
        params = {
            "status": status,
            "limit": limit,
        }

        if cursor:
            params["cursor"] = cursor

        response = _request(
            "GET",
            f"{BASE_URL}/charges",
            params=params,
            retry=True,
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
        retry=True,
    )

    return response.json()