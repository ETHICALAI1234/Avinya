"""FLOW-06 Part A: Grounded context retrieval and chunking."""

def chunk_context(context: str | list[str], size: int = 900, overlap: int = 150) -> list[str]:
    """Naive char chunking with overlap for grounded context exceeding single-window threshold."""
    if not context:
        return []
    
    if isinstance(context, list):
        text = "\n\n".join(c for c in context if c)
    else:
        text = str(context)

    if len(text) <= size:
        return [text]

    chunks = []
    i = 0
    while i < len(text):
        chunk = text[i:i + size]
        if chunk.strip():
            chunks.append(chunk)
        i += size - overlap
    return chunks
