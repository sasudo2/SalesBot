from typing import Any

from app.domain.errors import NotFoundError
from app.domain.models import Product
from app.rag.product_search import search_products_hybrid
from app.repo.product import get_product_by_id
from app.tools.args import GetProductArgs, SearchProductsArgs
from app.tools.context import ToolContext
from app.tools.types import ToolResult


def _product_data(product: Product) -> dict[str, Any]:
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "price": str(product.price),
        "currency": product.currency,
        "available": product.available,
        "tags": product.tags,
    }


def tool_search_products(args: SearchProductsArgs, ctx: ToolContext) -> ToolResult:
    hits = search_products_hybrid(
        ctx.db, ctx.embedder, args.query, args.limit, ctx.settings.semantic_weight
    )
    return ToolResult(ok=True, data={"hits": [_product_data(hit.product) for hit in hits]})


def tool_get_product(args: GetProductArgs, ctx: ToolContext) -> ToolResult:
    product = get_product_by_id(ctx.db, args.product_id)
    if product is None:
        raise NotFoundError("Product not found")
    return ToolResult(ok=True, data={"product": _product_data(product)})
