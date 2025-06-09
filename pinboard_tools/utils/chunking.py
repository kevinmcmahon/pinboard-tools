# ABOUTME: JSON chunking utilities for processing large datasets
# ABOUTME: Splits large JSON arrays into manageable chunks for LLM processing

import json
from pathlib import Path
from typing import Any


def calculate_token_estimate(obj: Any) -> int:
    """Estimate token count for a JSON object

    Uses rough heuristic: ~4 characters per token
    """
    json_str = json.dumps(obj, ensure_ascii=False)
    return len(json_str) // 4


def chunk_json_array(
    data: list[dict[str, Any]],
    max_tokens_per_chunk: int = 100000,
    max_items_per_chunk: int | None = None,
) -> list[list[dict[str, Any]]]:
    """Split JSON array into chunks based on token limits

    Args:
        data: List of JSON objects to chunk
        max_tokens_per_chunk: Maximum tokens per chunk
        max_items_per_chunk: Maximum items per chunk (optional)

    Returns:
        List of chunks, where each chunk is a list of objects
    """
    chunks = []
    current_chunk: list[dict[str, Any]] = []
    current_tokens = 0

    for item in data:
        item_tokens = calculate_token_estimate(item)

        # Check if adding this item would exceed limits
        would_exceed_tokens = current_tokens + item_tokens > max_tokens_per_chunk
        would_exceed_items = (
            max_items_per_chunk and len(current_chunk) >= max_items_per_chunk
        )

        if current_chunk and (would_exceed_tokens or would_exceed_items):
            # Start new chunk
            chunks.append(current_chunk)
            current_chunk = []
            current_tokens = 0

        current_chunk.append(item)
        current_tokens += item_tokens

    # Add final chunk if not empty
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def save_chunks(
    chunks: list[list[dict[str, Any]]], output_dir: Path, base_name: str = "chunk"
) -> list[Path]:
    """Save chunks to individual JSON files

    Returns:
        List of paths to saved chunk files
    """
    output_dir.mkdir(exist_ok=True)
    saved_files = []

    for i, chunk in enumerate(chunks):
        output_file = output_dir / f"{base_name}_{i + 1:03d}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chunk, f, ensure_ascii=False, indent=2)
        saved_files.append(output_file)

    return saved_files


def analyze_chunks(chunks: list[list[dict[str, Any]]]) -> dict[str, Any]:
    """Generate statistics about chunks"""
    if not chunks:
        return {
            "total_chunks": 0,
            "total_items": 0,
            "avg_items_per_chunk": 0,
            "avg_tokens_per_chunk": 0,
        }

    total_items = sum(len(chunk) for chunk in chunks)
    token_counts = [
        sum(calculate_token_estimate(item) for item in chunk) for chunk in chunks
    ]

    return {
        "total_chunks": len(chunks),
        "total_items": total_items,
        "avg_items_per_chunk": total_items / len(chunks),
        "min_items_per_chunk": min(len(chunk) for chunk in chunks),
        "max_items_per_chunk": max(len(chunk) for chunk in chunks),
        "avg_tokens_per_chunk": sum(token_counts) / len(chunks),
        "min_tokens_per_chunk": min(token_counts),
        "max_tokens_per_chunk": max(token_counts),
    }


def chunk_bookmarks_for_llm(
    bookmarks: list[dict[str, Any]], max_tokens: int = 100000
) -> list[list[dict[str, Any]]]:
    """Chunk bookmarks for LLM processing"""
    return chunk_json_array(bookmarks, max_tokens_per_chunk=max_tokens)
