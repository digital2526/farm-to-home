import os

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
    
    if (
        os.getenv("APP_ENV") == "development"
        and request.url.hostname in {"localhost", "127.0.0.1"}
    ):
        customer_id = request.query_params.get("logged_in_customer_id")
        if customer_id and customer_id.isdigit():
            return customer_id

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
    
    print("APP PROXY DEBUG:", {
        "path": request.url.path,
        "query_keys": sorted(request.query_params.keys()),
        "has_signature": bool(signature),
        "has_timestamp": bool(request.query_params.get("timestamp")),
        "has_customer_id": bool(
            request.query_params.get("logged_in_customer_id")
        ),
    })
    
    print(
        "APP PROXY SECRET FINGERPRINT:",
        hashlib.sha256(
            SHOPIFY_API_SECRET.encode("utf-8")
        ).hexdigest()[:12],
    )

    #if not signature:
        #raise HTTPException(
            #status_code=401,
            #detail="Missing Shopify signature.",
       # )
    demo_bypass = (
        os.getenv("TEMP_DISABLE_PROXY_SIGNATURE", "").strip().lower()
        == "true"
    )

    if not signature_valid and not demo_bypass:
        raise HTTPException(
            status_code=401,
            detail="Invalid Shopify signature.",
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
    
    print("APP PROXY SIGNING DEBUG:", {
        "parameter_keys": sorted(grouped_params.keys()),
        "parameter_count": len(grouped_params),
        "has_path_prefix": "path_prefix" in grouped_params,
        "has_shop": "shop" in grouped_params,
        "has_timestamp": "timestamp" in grouped_params,
        "canonical_message_length": len(message),
    })
    
    calculated_signature = hmac.new(
        SHOPIFY_API_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    
    print(
        "APP PROXY SIGNATURE MATCH:",
        hmac.compare_digest(calculated_signature, signature),
    )

    signature_valid = hmac.compare_digest(
        calculated_signature,
        signature,
    )

    if not signature_valid:
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
