from pydantic import BaseModel, Field


class ShopifyCustomer(BaseModel):
    id: int
    email: str | None = None


class ShopifyLineItemProperty(BaseModel):
    name: str
    value: str | None = None


class ShopifyOrderLineItem(BaseModel):
    id: int | None = None
    variant_id: int | None = None
    product_id: int | None = None
    title: str | None = None
    quantity: int = 1
    properties: list[ShopifyLineItemProperty] = Field(
        default_factory=list
    )


class ShopifyOrderPaid(BaseModel):
    id: int
    email: str | None = None
    total_price: str | None = None
    subtotal_price: str | None = None
    financial_status: str
    customer: ShopifyCustomer | None = None

    line_items: list[ShopifyOrderLineItem] = Field(
        default_factory=list
    )