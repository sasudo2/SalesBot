import re


def chunk_text(text: str, max_chars: int = 800, overlap: int = 100) -> list[str]:
    if max_chars < 1 or not 0 <= overlap < max_chars:
        raise ValueError("Require max_chars > 0 and 0 <= overlap < max_chars")
    chunks: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(paragraph):
                piece = paragraph[start : start + max_chars].strip()
                if piece:
                    chunks.append(piece)
                if start + max_chars >= len(paragraph):
                    break
                start += max_chars - overlap
        elif current and len(current) + 2 + len(paragraph) <= max_chars:
            current += "\n\n" + paragraph
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks
