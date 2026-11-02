from app.rag.knowledge_search import search_knowledge_chunks
from app.tools.args import SearchKnowledgeArgs
from app.tools.context import ToolContext
from app.tools.types import ToolResult


def tool_search_knowledge(args: SearchKnowledgeArgs, ctx: ToolContext) -> ToolResult:
    hits = search_knowledge_chunks(
        ctx.db, ctx.embedder, args.query, args.source, args.limit, ctx.settings.min_knowledge_score
    )
    return ToolResult(
        ok=True,
        data={
            "hits": [
                {
                    "title": h.chunk.title,
                    "source": h.chunk.source.value,
                    "text": h.chunk.text,
                    "score": h.score,
                }
                for h in hits
            ]
        },
    )
