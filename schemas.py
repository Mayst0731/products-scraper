from typing import List, Optional
from pydantic import BaseModel


class Product(BaseModel):
    product_id: str
    url: str
    title: Optional[str] = None
    price: Optional[str] = None
    image: Optional[str] = None


class Shop(BaseModel):
    shop_id: Optional[str] = None
    brand_name: Optional[str] = None
    shop_url: str
    total_products: Optional[int] = None  # total count reported by Taobao API
    products: List[Product] = []
