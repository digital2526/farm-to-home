import base64
import hashlib
import hmac


def verify_shopify_webhook(
    secret: str,
    body: bytes,
    hmac_header: str,
):
    digest = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()

    calculated_hmac = base64.b64encode(digest).decode()

    return hmac.compare_digest(
        calculated_hmac,
        hmac_header or "",
    )