from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def prepare_documents(product_category: Path = Path("../data/shein-products.csv")):
    pass