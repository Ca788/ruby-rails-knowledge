"""Tolerant HTML-to-Markdown converter and semantic section extractor."""
from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
from typing import List, Optional


@dataclass
class ExtractedSection:
    title: str
    source_section: str
    content: str
    level: int = 2
    subtopic: str = "general"
    related_concepts: List[str] = field(default_factory=list)
    anchor: str = ""


class _HTMLToMarkdownParser(HTMLParser):
    """Fault-tolerant HTML parser converting technical documentation into normalized Markdown."""

    SKIP_TAGS = {"script", "style", "nav", "footer", "noscript", "svg", "iframe", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.in_pre = False
        self.in_code = False
        self.in_table = False
        self.current_row: List[str] = []
        self.table_rows: List[List[str]] = []
        self.cell_buf: List[str] = []
        self.in_cell = False
        self.current_href: Optional[str] = None
        self.link_text_buf: List[str] = []
        self.out: List[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        t = tag.lower()
        if t in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth > 0:
            return

        attr_dict = dict(attrs)
        if t in ("h1", "h2", "h3", "h4"):
            level = int(t[1])
            self.out.append(f"\n\n{'#' * level} ")
        elif t == "p":
            self.out.append("\n\n")
        elif t == "br":
            self.out.append("\n")
        elif t == "li":
            self.out.append("\n- ")
        elif t == "pre":
            self.in_pre = True
            self.out.append("\n\n\x60\x60\x60ruby\n")
        elif t == "code":
            self.in_code = True
            if not self.in_pre:
                self._append("\x60")
        elif t == "a":
            href = attr_dict.get("href", "")
            if href and not href.startswith("javascript:"):
                self.current_href = href
                self.link_text_buf = []
        elif t == "table":
            self.in_table = True
            self.table_rows = []
        elif t == "tr" and self.in_table:
            self.current_row = []
        elif t in ("td", "th") and self.in_table:
            self.in_cell = True
            self.cell_buf = []
        elif t in ("blockquote", "div"):
            cls = (attr_dict.get("class") or "").lower()
            if any(k in cls for k in ("warning", "deprecated", "note", "info", "caution")):
                self.out.append("\n\n> **Note/Warning:** ")

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in self.SKIP_TAGS:
            if self.skip_depth > 0:
                self.skip_depth -= 1
            return
        if self.skip_depth > 0:
            return

        if t in ("h1", "h2", "h3", "h4"):
            self.out.append("\n\n")
        elif t == "pre":
            self.in_pre = False
            self.out.append("\n\x60\x60\x60\n\n")
        elif t == "code":
            if not self.in_pre:
                self._append("\x60")
            self.in_code = False
        elif t == "a" and self.current_href is not None:
            text = "".join(self.link_text_buf).strip()
            href = self.current_href
            self.current_href = None
            self.link_text_buf = []
            if text:
                self._append(f"[{text}]({href})")
        elif t in ("td", "th") and self.in_table:
            self.in_cell = False
            self.current_row.append(" ".join("".join(self.cell_buf).split()))
        elif t == "tr" and self.in_table:
            if self.current_row:
                self.table_rows.append(self.current_row)
        elif t == "table" and self.in_table:
            self.in_table = False
            if self.table_rows:
                self.out.append("\n\n" + self._format_table(self.table_rows) + "\n\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth > 0:
            return
        if self.current_href is not None:
            self.link_text_buf.append(data)
            return
        self._append(data)

    def _append(self, text: str) -> None:
        if self.in_cell:
            self.cell_buf.append(text)
        elif self.in_pre:
            self.out.append(text)
        else:
            cleaned = re.sub(r"[ \t]+", " ", text)
            self.out.append(cleaned)

    @staticmethod
    def _format_table(rows: List[List[str]]) -> str:
        col_count = max(len(r) for r in rows)
        norm_rows = [r + [""] * (col_count - len(r)) for r in rows]
        lines = [
            "| " + " | ".join(norm_rows[0]) + " |",
            "| " + " | ".join(["---"] * col_count) + " |",
        ]
        for r in norm_rows[1:]:
            lines.append("| " + " | ".join(r) + " |")
        return "\n".join(lines)

    def get_markdown(self) -> str:
        raw = "".join(self.out)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


HEADING_RE = re.compile(r"^(#{1,2})\s+(.+?)$", re.MULTILINE)


class SemanticDocumentParser:
    """Parses HTML or Markdown documents into coherent semantic sections."""

    def html_to_markdown(self, html_text: str) -> str:
        parser = _HTMLToMarkdownParser()
        parser.feed(html_text)
        parser.close()
        return parser.get_markdown()

    def parse_to_sections(
        self,
        raw_content: str,
        doc_title: str,
        default_subtopic: str = "overview",
        content_format: str = "markdown",
    ) -> List[ExtractedSection]:
        if content_format == "html" or ("<html" in raw_content.lower() or "<body" in raw_content.lower() or "<h1" in raw_content.lower() or "<h2" in raw_content.lower()):
            md_text = self.html_to_markdown(raw_content)
        else:
            md_text = raw_content.strip()

        if not md_text:
            return []

        matches = list(HEADING_RE.finditer(md_text))
        if not matches:
            return [
                ExtractedSection(
                    title=doc_title,
                    source_section=doc_title,
                    content=md_text,
                    level=1,
                    subtopic=default_subtopic,
                )
            ]

        sections: List[ExtractedSection] = []
        current_h1 = doc_title
        current_h2 = doc_title

        # Capture leading intro before first heading if substantial
        first_start = matches[0].start()
        if first_start > 40:
            intro = md_text[:first_start].strip()
            if intro:
                sections.append(
                    ExtractedSection(
                        title=f"{doc_title} — Overview",
                        source_section=doc_title,
                        content=intro,
                        level=1,
                        subtopic=default_subtopic,
                    )
                )

        for i, match in enumerate(matches):
            hashes = match.group(1)
            level = len(hashes)
            heading_text = match.group(2).strip()
            start_pos = match.start()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
            body = md_text[start_pos:end_pos].strip()

            if level == 1:
                current_h1 = heading_text
                current_h2 = heading_text
                source_sec = current_h1
            elif level == 2:
                current_h2 = heading_text
                source_sec = f"{current_h1} > {current_h2}" if current_h1 != current_h2 else current_h2
            else:
                source_sec = f"{current_h2} > {heading_text}" if current_h2 != heading_text else heading_text

            # Skip empty heading containers that immediately precede a child heading
            body_without_heading = md_text[match.end():end_pos].strip()
            if not body_without_heading:
                continue

            subtopic = self._infer_subtopic(heading_text, default_subtopic)
            sections.append(
                ExtractedSection(
                    title=heading_text,
                    source_section=source_sec,
                    content=body,
                    level=level,
                    subtopic=subtopic,
                )
            )

        return sections

    @staticmethod
    def _infer_subtopic(heading: str, fallback: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")
        if not slug:
            return fallback
        parts = slug.split("_")
        return "_".join(parts[:4])
