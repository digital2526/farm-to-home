import time
import requests
from decimal import Decimal, InvalidOperation

from config import (
    SHOPIFY_ADMIN_API_VERSION,
    SHOPIFY_API_SECRET,
    SHOPIFY_CLIENT_ID,
    SHOPIFY_STORE,
)

EXTRA_PRODUCT_TAG = "add-extra"

_access_token = None
_token_expires_at = 0


def _shop_domain():
    store = SHOPIFY_STORE.strip()

    if store.startswith("https://"):
        store = store[len("https://"):]

    if store.startswith("http://"):
        store = store[len("http://"):]

    store = store.rstrip("/")

    if store.endswith(".myshopify.com"):
        return store

    return f"{store}.myshopify.com"


def _get_access_token():
    global _access_token
    global _token_expires_at

    now = time.time()

    if _access_token and now < _token_expires_at:
        return _access_token

    response = requests.post(
        f"https://{_shop_domain()}/admin/oauth/access_token",
        data={
            "client_id": SHOPIFY_CLIENT_ID,
            "client_secret": SHOPIFY_API_SECRET,
            "grant_type": "client_credentials",
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        timeout=15,
    )

    if not response.ok:
        raise RuntimeError(
            f"Shopify token request failed: "
            f"HTTP {response.status_code} - {response.text}"
        )

    data = response.json()

    token = data.get("access_token")

    if not token:
        raise RuntimeError(
            "Shopify did not return an Admin API access token."
        )

    expires_in = int(data.get("expires_in", 86400))

    _access_token = token
    _token_expires_at = time.time() + max(expires_in - 300, 60)

    return _access_token


def is_extra_variant(variant_id):
    try:
        variant_id = int(variant_id)
    except (TypeError, ValueError):
        return False

    query = """
    query GetVariantProduct($id: ID!) {
      productVariant(id: $id) {
        product {
          id
          title
          tags
        }
      }
    }
    """

    response = requests.post(
        f"https://{_shop_domain()}/admin/api/"
        f"{SHOPIFY_ADMIN_API_VERSION}/graphql.json",
        json={
            "query": query,
            "variables": {
                "id": f"gid://shopify/ProductVariant/{variant_id}"
            },
        },
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": _get_access_token(),
        },
        timeout=15,
    )

    if not response.ok:
        raise RuntimeError(
            f"Shopify token request failed: "
            f"HTTP {response.status_code} - {response.text}"
        )

    data = response.json()

    if data.get("errors"):
        raise RuntimeError(
            f"Shopify GraphQL error: {data['errors']}"
        )

    product_variant = (
        data.get("data", {})
        .get("productVariant")
    )

    if not product_variant:
        return False

    product = product_variant.get("product")

    if not product:
        return False

    tags = product.get("tags", [])

    return any(
        str(tag).strip().lower() == EXTRA_PRODUCT_TAG
        for tag in tags
    )
    

# -------------------------------------------------
# Get Shopify variant price
# -------------------------------------------------

def get_shopify_variant_price(variant_id):
    try:
        variant_id = int(variant_id)
    except (TypeError, ValueError):
        raise RuntimeError(
            "Invalid Shopify variant ID."
        )

    query = """
    query GetVariantPrice($id: ID!) {
      productVariant(id: $id) {
        id
        price
      }
    }
    """

    response = requests.post(
        f"https://{_shop_domain()}/admin/api/"
        f"{SHOPIFY_ADMIN_API_VERSION}/graphql.json",
        json={
            "query": query,
            "variables": {
                "id": f"gid://shopify/ProductVariant/{variant_id}"
            },
        },
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": _get_access_token(),
        },
        timeout=15,
    )

    if not response.ok:
        raise RuntimeError(
            f"Shopify price request failed: "
            f"HTTP {response.status_code} - {response.text}"
        )

    data = response.json()

    if data.get("errors"):
        raise RuntimeError(
            f"Shopify GraphQL error: {data['errors']}"
        )

    product_variant = (
        data.get("data", {})
        .get("productVariant")
    )

    if not product_variant:
        raise RuntimeError(
            "Shopify variant not found."
        )

    raw_price = product_variant.get("price")

    if raw_price is None:
        raise RuntimeError(
            "Shopify variant price is missing."
        )

    try:
        return Decimal(str(raw_price))
    except (InvalidOperation, ValueError) as exc:
        raise RuntimeError(
            f"Invalid Shopify variant price: {raw_price}"
        ) from exc
        
# -------------------------------------------------
# Set Shopify order delivery date
# -------------------------------------------------

# -------------------------------------------------
# Set Shopify order delivery details
# -------------------------------------------------

def set_order_delivery_details(
    order_id,
    delivery_date,
    delivery_day,
    delivery_time,
):
    """
    Save delivery information to the Shopify order:

    custom.delivery_date
    custom.delivery_day
    custom.delivery_time
    """

    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        raise RuntimeError("Invalid Shopify order ID.")

    mutation = """
    mutation SetOrderDeliveryDetails(
        $metafields: [MetafieldsSetInput!]!
    ) {
        metafieldsSet(metafields: $metafields) {
            metafields {
                id
                namespace
                key
                value
            }
            userErrors {
                field
                message
            }
        }
    }
    """

    variables = {
        "metafields": [
            {
                "ownerId": f"gid://shopify/Order/{order_id}",
                "namespace": "custom",
                "key": "delivery_date",
                "type": "date",
                "value": str(delivery_date),
            },
            {
                "ownerId": f"gid://shopify/Order/{order_id}",
                "namespace": "custom",
                "key": "delivery_day",
                "type": "single_line_text_field",
                "value": str(delivery_day),
            },
            {
                "ownerId": f"gid://shopify/Order/{order_id}",
                "namespace": "custom",
                "key": "delivery_time",
                "type": "single_line_text_field",
                "value": str(delivery_time),
            },
        ]
    }

    response = requests.post(
        f"https://{_shop_domain()}/admin/api/"
        f"{SHOPIFY_ADMIN_API_VERSION}/graphql.json",
        json={
            "query": mutation,
            "variables": variables,
        },
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": _get_access_token(),
        },
        timeout=15,
    )

    if not response.ok:
        raise RuntimeError(
            f"Shopify delivery details request failed: "
            f"HTTP {response.status_code} - {response.text}"
        )

    data = response.json()

    if data.get("errors"):
        raise RuntimeError(
            f"Shopify GraphQL error: {data['errors']}"
        )

    result = (
        data.get("data", {})
        .get("metafieldsSet", {})
    )

    user_errors = result.get("userErrors", [])

    if user_errors:
        raise RuntimeError(
            f"Shopify delivery metafield error: {user_errors}"
        )

    return result.get("metafields", [])