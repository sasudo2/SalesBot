import argparse
import csv
import logging
from decimal import Decimal
from pathlib import Path

FIELDS = [
    "id", "sku", "name", "description", "price",
    "currency", "stock_on_hand", "aliases", "tags",
]


def normalize(source: Path, destination: Path) -> None:
    products = []
    seen = set()

    with source.open(encoding="utf-8-sig", newline="") as file:
        for line, row in enumerate(csv.DictReader(file), start=2):
            product_id = row["product_id"].strip()
            name = row["product_name"].strip()
            currency = row["currency"].strip().upper()
            price = Decimal(row["final_price"])

            if not product_id or not name or len(currency) != 3:
                raise ValueError(f"CSV record {line}: missing/invalid ID, name, or currency")
            if not price.is_finite() or price < 0:
                raise ValueError(f"CSV record {line}: invalid price")
            if product_id in seen:
                raise ValueError(
                    f"CSV record {line}: duplicate product ID {product_id}; "
                    "resolve duplicate/variant rows first"
                )
            seen.add(product_id)

            tags = [
                row.get(key, "").strip()
                for key in ("root_category", "category", "brand", "color")
            ]
            tags = [tag for tag in tags if tag and tag.lower() != "null"]

            products.append({
                "id": product_id,
                "sku": product_id,
                "name": name[:200],
                "description": f"{name}\n{row['description'].strip()}",
                "price": str(price.quantize(Decimal("0.01"))),
                "currency": currency,
                "stock_on_hand": 0,
                "aliases": "",
                "tags": "|".join(dict.fromkeys(tags)),
            })

    # Exclusive creation prevents accidentally overwriting an existing dataset.
    with destination.open("x", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(products)

    logging.info("Normalized %d products into %s", len(products), destination)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    normalize(args.source, args.destination)