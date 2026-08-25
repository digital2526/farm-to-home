import base64
import hashlib
import hmac

from services.webhook_security import verify_shopify_webhook


SECRET = "test-shopify-secret"
BODY = b'{"id":12345,"financial_status":"paid"}'


def create_hmac(secret, body):
    digest = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()

    return base64.b64encode(digest).decode()


def test_valid_shopify_hmac_is_accepted():
    signature = create_hmac(SECRET, BODY)

    assert verify_shopify_webhook(
        secret=SECRET,
        body=BODY,
        hmac_header=signature,
    ) is True


def test_invalid_shopify_hmac_is_rejected():
    signature = create_hmac(
        "wrong-secret",
        BODY,
    )

    assert verify_shopify_webhook(
        secret=SECRET,
        body=BODY,
        hmac_header=signature,
    ) is False


def test_modified_body_is_rejected():
    signature = create_hmac(
        SECRET,
        BODY,
    )

    modified_body = b'{"id":99999,"financial_status":"paid"}'

    assert verify_shopify_webhook(
        secret=SECRET,
        body=modified_body,
        hmac_header=signature,
    ) is False


def test_empty_hmac_is_rejected():
    assert verify_shopify_webhook(
        secret=SECRET,
        body=BODY,
        hmac_header="",
    ) is False
