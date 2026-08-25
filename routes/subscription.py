from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel

from shopify_auth import verify_shopify_proxy

from services.add_extra import create_extra_subscription
from services.remove_extra import remove_extra
from services.get_extras import get_extras
from services.update_extra import update_extra


router = APIRouter()

limiter = Limiter(key_func=get_remote_address)

class AddExtraRequest(BaseModel):
    variant_id: int
    quantity: int = 1


@router.post("/add-extra")
@limiter.limit("10/minute")
async def add_extra(
    data: AddExtraRequest,
    request: Request,
):
    shopify_customer_id = await verify_shopify_proxy(request)

    return create_extra_subscription(
        shopify_customer_id=shopify_customer_id,
        variant_id=data.variant_id,
        quantity=data.quantity,
    )


class RemoveExtraRequest(BaseModel):
    subscription_id: int


@router.delete("/remove-extra")
@limiter.limit("10/minute")
async def delete_extra(
    data: RemoveExtraRequest,
    request: Request,
):
    shopify_customer_id = await verify_shopify_proxy(request)

    return remove_extra(
        shopify_customer_id=shopify_customer_id,
        subscription_id=data.subscription_id,
    )


class UpdateExtraRequest(BaseModel):
    subscription_id: int
    quantity: int


@router.patch("/update-extra")
@limiter.limit("20/minute")
async def patch_extra(
    data: UpdateExtraRequest,
    request: Request,
):
    shopify_customer_id = await verify_shopify_proxy(request)

    return update_extra(
        shopify_customer_id=shopify_customer_id,
        subscription_id=data.subscription_id,
        quantity=data.quantity,
    )


@router.get("/extras")
@limiter.limit("60/minute")
async def extras(
    request: Request,
):
    shopify_customer_id = await verify_shopify_proxy(request)

    return get_extras(shopify_customer_id)