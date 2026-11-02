import math
import re

from app.domain.models import Product


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        raise ValueError("Vector dimensions differ")
    norm_a, norm_b = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    if not norm_a or not norm_b:
        return 0.0
    return sum(x * y for x, y in zip(a, b, strict=True)) / (norm_a * norm_b)


def lexical_score(query: str, product: Product) -> float:
    def _tokens(text: str) -> set[str]:
        return set(filter(None, re.split(r"[\s,.;:!?()\[\]\"'/\\-]+", text.lower())))

    q = _tokens(query)
    if not q:
        return 0.0
    haystack = _tokens(" ".join([product.name, *product.aliases, *product.tags]))
    score = len(q & haystack) / len(q)
    if any(query.lower() in text.lower() for text in [product.name, *product.aliases]):
        score += 0.2
    return min(score, 1.0)
