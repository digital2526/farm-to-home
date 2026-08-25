import hashlib
import hmac
import time
from collections import defaultdict

from fastapi import HTTPException, Request

from config import SHOPIFY_API_SECRET


APP_PROXY_TIMESTAMP_TOLERANCE = 300  # 5 minutes


async def verify_shopify_proxy(request: Request) -> str:
    """
    Authenticate a Shopify App Proxy request.

    Returns the authenticated Shopify customer ID from
    Shopify's signed `logged_in_customer_id` parameter.

    Shopify App Proxy signature algorithm:
    1. Read all query parameters.
    2. Remove `signature`.
    3. Preserve repeated parameters.
    4. Join repeated values with commas.
    5. Sort key=value pairs.
    6. Concatenate without separators.
    7. Calculate HMAC-SHA256 using SHOPIFY_API_SECRET.
    8. Compare using constant-time comparison.
    9. Validate timestamp freshness.
    10. Return the signed logged-in customer ID.
    """

    if not SHOPIFY_API_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Shopify API secret is not configured.",
        )

    # Preserve repeated query parameters.
    grouped_params = defaultdict(list)

    for key, value in request.query_params.multi_items():
        if key == "signature":
            continue

        grouped_params[key].append(value)

    signature = request.query_params.get("signature")

    if not signature:
        raise HTTPException(
            status_code=401,
            detail="Missing Shopify signature.",
        )

    # Shopify canonicalization:
    # repeated values are joined with commas,
    # key=value pairs are sorted,
    # then concatenated without separators.
    sorted_params = sorted(
        f"{key}={','.join(values)}"
        for key, values in grouped_params.items()
    )

    message = "".join(sorted_params)

    calculated_signature = hmac.new(
        SHOPIFY_API_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        calculated_signature,
        signature,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid Shopify signature.",
        )

    # Validate timestamp freshness.
    timestamp = request.query_params.get("timestamp")

    if not timestamp:
        raise HTTPException(
            status_code=401,
            detail="Missing Shopify timestamp.",
        )

    try:
        timestamp_value = int(timestamp)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Shopify timestamp.",
        )

    current_time = int(time.time())

    if abs(current_time - timestamp_value) > APP_PROXY_TIMESTAMP_TOLERANCE:
        raise HTTPException(
            status_code=401,
            detail="Expired Shopify proxy request.",
        )

    # The customer ID comes ONLY from Shopify's signed parameter.
    customer_id = request.query_params.get(
        "logged_in_customer_id"
    )

    if not customer_id:
        raise HTTPException(
            status_code=401,
            detail="Customer is not logged in.",
        )

    return customer_id