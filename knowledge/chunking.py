"""Heading-aware Unicode character windows with exact, reproducible citations."""

import re


def chunk_document(text, title, metadata, size=1600, overlap=200):
    if size < 1 or not 0 <= overlap < size:
        raise ValueError("Overlap must be smaller than the chunk size.")
    sections = []
    path = []
    section_start = 0
    offset = 0
    fence = ""
    for line in text.splitlines(keepends=True):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = ""
        heading = None if fence or marker else re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            sections.append((section_start, offset, " / ".join(label for _, label in path) or title))
            level = len(heading[1])
            path = [(depth, label) for depth, label in path if depth < level]
            path.append((level, heading[2]))
            section_start = offset + len(line)
        offset += len(line)
    sections.append((section_start, len(text), " / ".join(label for _, label in path) or title))

    chunks = []
    for left, right, section in sections:
        cursor = left
        while cursor < right:
            end = min(cursor + size, right)
            if end < right:
                # Prefer paragraphs, then a word boundary, without making tiny windows.
                lower = cursor + size // 2
                boundary = text.rfind("\n\n", lower, end)
                if boundary < 0:
                    whitespace = list(re.finditer(r"\s+", text[lower:end]))
                    boundary = lower + whitespace[-1].end() if whitespace else end
                else:
                    boundary += 2
                end = boundary
            raw = text[cursor:end]
            start_trim = len(raw) - len(raw.lstrip())
            end_trim = len(raw.rstrip())
            start, stop = cursor + start_trim, cursor + end_trim
            if stop > start:
                pages = [span["page"] for span in metadata.get("page_spans", [])
                         if span["start"] < stop and span["end"] > start]
                chunks.append({"text": text[start:stop], "start": start, "end": stop,
                               "section": section, "page_start": min(pages) if pages else None,
                               "page_end": max(pages) if pages else None})
            if end >= right:
                break
            cursor = max(cursor + 1, end - overlap)
    return chunks
