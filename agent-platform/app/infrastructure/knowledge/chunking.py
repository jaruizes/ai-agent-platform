from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ChunkingStrategyName(StrEnum):
    FIXED = "FIXED"
    PARAGRAPH = "PARAGRAPH"
    HEADING = "HEADING"
    PAGE = "PAGE"
    HIERARCHICAL = "HIERARCHICAL"


@dataclass(frozen=True)
class ChunkCandidate:
    content: str
    start: int
    end: int
    metadata: dict[str, object] = field(default_factory=dict)
    embed: bool = True


class ChunkingStrategy(Protocol):
    name: ChunkingStrategyName

    def split(self, text: str) -> list[ChunkCandidate]: ...


def _validate_size(size: int, overlap: int) -> None:
    if size <= 0:
        raise ValueError("chunk size must be greater than zero")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk size")


class FixedChunker:
    name = ChunkingStrategyName.FIXED

    def __init__(self, *, chunk_size: int = 1600, overlap: int = 200):
        _validate_size(chunk_size, overlap)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[ChunkCandidate]:
        if not text:
            return []
        chunks: list[ChunkCandidate] = []
        start = 0
        while start < len(text):
            hard_end = min(start + self.chunk_size, len(text))
            end = hard_end
            if hard_end < len(text):
                search_start = start + self.chunk_size // 2
                candidates = [
                    text.rfind("\n\n", search_start, hard_end),
                    text.rfind("\n", search_start, hard_end),
                    text.rfind(". ", search_start, hard_end),
                    text.rfind(" ", search_start, hard_end),
                ]
                boundary = max(candidates)
                if boundary > start:
                    end = boundary + 1
            content = text[start:end].strip()
            if content:
                chunks.append(
                    ChunkCandidate(
                        content=content,
                        start=start,
                        end=end,
                        metadata={"chunkingStrategy": "FIXED"},
                    )
                )
            if end >= len(text):
                break
            start = max(start + 1, end - self.overlap)
        return chunks


class ParagraphChunker:
    name = ChunkingStrategyName.PARAGRAPH

    def __init__(self, *, chunk_size: int = 1600, overlap: int = 200):
        _validate_size(chunk_size, overlap)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[ChunkCandidate]:
        if not text:
            return []
        paragraphs = [
            (match.group(0).strip(), match.start(), match.end())
            for match in re.finditer(r"[^\n].*?(?=\n\s*\n|\Z)", text, re.S)
            if match.group(0).strip()
        ]
        chunks: list[ChunkCandidate] = []
        current: list[tuple[str, int, int]] = []
        current_len = 0

        def flush() -> None:
            nonlocal current, current_len
            if not current:
                return
            chunks.append(
                ChunkCandidate(
                    content="\n\n".join(item[0] for item in current),
                    start=current[0][1],
                    end=current[-1][2],
                    metadata={"chunkingStrategy": "PARAGRAPH"},
                )
            )
            current = []
            current_len = 0

        for content, start, end in paragraphs:
            if len(content) > self.chunk_size:
                flush()
                for item in FixedChunker(
                    chunk_size=self.chunk_size,
                    overlap=self.overlap,
                ).split(content):
                    chunks.append(
                        ChunkCandidate(
                            content=item.content,
                            start=start + item.start,
                            end=start + item.end,
                            metadata={
                                "chunkingStrategy": "PARAGRAPH",
                                "oversizedParagraph": True,
                            },
                        )
                    )
                continue

            projected = current_len + (2 if current else 0) + len(content)
            if current and projected > self.chunk_size:
                flush()
            current.append((content, start, end))
            current_len += (2 if current_len else 0) + len(content)

        flush()
        return chunks


class HeadingAwareChunker:
    name = ChunkingStrategyName.HEADING

    def __init__(self, *, chunk_size: int = 1600, overlap: int = 200):
        _validate_size(chunk_size, overlap)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[ChunkCandidate]:
        headings = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text))
        if not headings:
            return [
                ChunkCandidate(
                    item.content,
                    item.start,
                    item.end,
                    {**item.metadata, "chunkingStrategy": "HEADING", "heading": None},
                )
                for item in ParagraphChunker(
                    chunk_size=self.chunk_size,
                    overlap=self.overlap,
                ).split(text)
            ]

        chunks: list[ChunkCandidate] = []
        for index, heading in enumerate(headings):
            section_start = heading.start()
            section_end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            section = text[section_start:section_end].strip()
            for item in FixedChunker(
                chunk_size=self.chunk_size,
                overlap=self.overlap,
            ).split(section):
                chunks.append(
                    ChunkCandidate(
                        content=item.content,
                        start=section_start + item.start,
                        end=section_start + item.end,
                        metadata={
                            "chunkingStrategy": "HEADING",
                            "heading": heading.group(2).strip(),
                            "headingLevel": len(heading.group(1)),
                        },
                    )
                )
        return chunks


class PageAwareChunker:
    name = ChunkingStrategyName.PAGE

    def __init__(self, *, chunk_size: int = 1600, overlap: int = 200):
        _validate_size(chunk_size, overlap)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[ChunkCandidate]:
        return [
            ChunkCandidate(
                item.content,
                item.start,
                item.end,
                {**item.metadata, "chunkingStrategy": "PAGE"},
            )
            for item in FixedChunker(
                chunk_size=self.chunk_size,
                overlap=self.overlap,
            ).split(text)
        ]


class HierarchicalChunker:
    name = ChunkingStrategyName.HIERARCHICAL

    def __init__(
        self,
        *,
        parent_size: int = 6000,
        child_size: int = 1600,
        child_overlap: int = 200,
    ):
        _validate_size(parent_size, 0)
        _validate_size(child_size, child_overlap)
        if child_size >= parent_size:
            raise ValueError("child size must be smaller than parent size")
        self.parent_size = parent_size
        self.child_size = child_size
        self.child_overlap = child_overlap

    def split(self, text: str) -> list[ChunkCandidate]:
        parents = FixedChunker(chunk_size=self.parent_size, overlap=0).split(text)
        chunks: list[ChunkCandidate] = []
        for parent_index, parent in enumerate(parents):
            chunks.append(
                ChunkCandidate(
                    parent.content,
                    parent.start,
                    parent.end,
                    {
                        "chunkingStrategy": "HIERARCHICAL",
                        "hierarchyLevel": "parent",
                        "parentIndex": parent_index,
                    },
                    embed=False,
                )
            )
            children = FixedChunker(
                chunk_size=self.child_size,
                overlap=self.child_overlap,
            ).split(parent.content)
            for child_index, child in enumerate(children):
                chunks.append(
                    ChunkCandidate(
                        child.content,
                        parent.start + child.start,
                        parent.start + child.end,
                        {
                            "chunkingStrategy": "HIERARCHICAL",
                            "hierarchyLevel": "child",
                            "parentIndex": parent_index,
                            "childIndex": child_index,
                        },
                        embed=True,
                    )
                )
        return chunks


def build_chunker(policy: dict) -> ChunkingStrategy:
    strategy = ChunkingStrategyName(str(policy.get("strategy", "PARAGRAPH")).upper())
    chunk_size = int(policy.get("chunkSize", 1600))
    overlap = int(policy.get("overlap", 200))

    if strategy is ChunkingStrategyName.FIXED:
        return FixedChunker(chunk_size=chunk_size, overlap=overlap)
    if strategy is ChunkingStrategyName.PARAGRAPH:
        return ParagraphChunker(chunk_size=chunk_size, overlap=overlap)
    if strategy is ChunkingStrategyName.HEADING:
        return HeadingAwareChunker(chunk_size=chunk_size, overlap=overlap)
    if strategy is ChunkingStrategyName.PAGE:
        return PageAwareChunker(chunk_size=chunk_size, overlap=overlap)

    return HierarchicalChunker(
        parent_size=int(policy.get("parentSize", 6000)),
        child_size=int(policy.get("childSize", chunk_size)),
        child_overlap=int(policy.get("childOverlap", overlap)),
    )


def normalize_chunking_policy(policy: dict | None) -> dict:
    value = dict(policy or {})
    strategy = ChunkingStrategyName(str(value.get("strategy", "PARAGRAPH")).upper())
    normalized = {
        "strategy": strategy.value,
        "chunkSize": int(value.get("chunkSize", 1600)),
        "overlap": int(value.get("overlap", 200)),
        "parentSize": int(value.get("parentSize", 6000)),
        "childSize": int(value.get("childSize", value.get("chunkSize", 1600))),
        "childOverlap": int(value.get("childOverlap", value.get("overlap", 200))),
    }
    build_chunker(normalized)
    return normalized
