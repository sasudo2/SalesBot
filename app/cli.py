import argparse
import csv
import logging
from decimal import Decimal
from pathlib import Path

from app.api.deps import get_embedder
from app.core.config import load_settings
from app.db.init import init_db
from app.db.session import get_sessionmaker
from app.domain.enums import KnowledgeSource
from app.domain.models import Product
from app.rag.ingest import ingest_knowledge, ingest_products

logger = logging.getLogger(__name__)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Sales agent administration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db")
    ingest = commands.add_parser("ingest")
    ingest.add_argument("--products", type=Path, required=True)
    ingest.add_argument("--knowledge", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.command == "init-db":
        init_db()
        logger.info("Database initialized")
        return
    settings = load_settings()
    embedder = get_embedder(settings)
    with args.products.open(encoding="utf-8", newline="") as file:
        products = [
            Product(
                id=row["id"],
                sku=row["sku"],
                name=row["name"],
                description=row["description"],
                price=Decimal(row["price"]),
                currency=row["currency"],
                stock_on_hand=int(row["stock_on_hand"]),
                aliases=list(filter(None, row["aliases"].split("|"))),
                tags=list(filter(None, row["tags"].split("|"))),
            )
            for row in csv.DictReader(file)
        ]
    docs = [
        (KnowledgeSource(path.parent.name), path.stem, path.read_text(encoding="utf-8"))
        for path in sorted(args.knowledge.glob("*/*.md"))
    ]
    with get_sessionmaker()() as db:
        model = (
            settings.local_embedding_model
            if settings.embedding_provider == "local"
            else settings.embedding_model
        )
        count = ingest_products(db, embedder, products, model)
        count += ingest_knowledge(db, embedder, docs)
        db.commit()
    logger.info("Wrote %d rows", count)


if __name__ == "__main__":
    _main()
