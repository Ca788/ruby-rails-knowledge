"""Evidence selector enforcing character, token, and related concept budgets."""
from __future__ import annotations

from typing import Any, Dict, List
from ..config import RetrievalLimits
from ..models.entities import SearchResultItem


class EvidenceSelector:
    def __init__(self, limits: RetrievalLimits):
        self.limits = limits

    def truncate_content(self, content: str) -> str:
        max_chars = self.limits.max_content_chars
        if len(content) <= max_chars:
            return content
        # Truncate cleanly at paragraph or line boundary
        cut = content[:max_chars]
        last_nl = cut.rfind("\n")
        if last_nl > max_chars // 2:
            cut = cut[:last_nl]
        return cut.rstrip() + "\n\n...[truncated for context efficiency]..."

    def select_evidence(
        self,
        ranked_items: List[SearchResultItem],
        max_results_override: int = 0,
    ) -> List[SearchResultItem]:
        limit_k = max_results_override if max_results_override > 0 else self.limits.max_results
        selected: List[SearchResultItem] = []
        running_tokens = 0

        for item in ranked_items:
            if len(selected) >= limit_k:
                break
            item.content = self.truncate_content(item.content)
            item.related_concepts = item.related_concepts[: self.limits.max_related_concepts]
            item_tokens = max(1, (len(item.content) + 3) // 4)

            if selected and (running_tokens + item_tokens) > self.limits.max_estimated_tokens:
                # If adding this item exceeds total token budget, stop or trim
                remaining_chars = (self.limits.max_estimated_tokens - running_tokens) * 4
                if remaining_chars < 280:
                    break
                item.content = item.content[:remaining_chars].rstrip() + "\n...[truncated]..."
                item_tokens = max(1, (len(item.content) + 3) // 4)

            running_tokens += item_tokens
            selected.append(item)

        return selected
