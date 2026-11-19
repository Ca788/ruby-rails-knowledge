"""Bounded Knowledge Graph traversal in SQLite."""
from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set

from ..storage.database import DatabaseManager
from ..storage.fts import normalize_identifier


class KnowledgeGraphExpander:
    """Navigates grounded technical concept relationships with bounded depth and fan-out."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def traverse(
        self,
        concept_query: str,
        technology: Optional[str] = None,
        max_depth: int = 2,
        max_related: int = 8,
    ) -> Dict[str, Any]:
        norm_name = normalize_identifier(concept_query)
        max_depth = max(1, min(max_depth, 4))
        max_related = max(1, min(max_related, 25))

        with self.db.connect(readonly=True) as conn:
            # Find matching root concept(s)
            params: List[Any] = [norm_name, f"%{norm_name}%"]
            sql = "SELECT * FROM concepts WHERE (name = ? OR name LIKE ?)"
            if technology:
                sql += " AND technology = ?"
                params.append(technology)
            sql += " ORDER BY CASE WHEN name = ? THEN 0 ELSE 1 END, length(name) ASC LIMIT 3"
            params.append(norm_name)

            root_rows = conn.execute(sql, params).fetchall()
            if not root_rows:
                return {
                    "query_concept": concept_query,
                    "normalized_concept": norm_name,
                    "found": False,
                    "root_concepts": [],
                    "edges": [],
                    "related_concepts": [],
                    "metadata": {"max_depth": max_depth, "max_related": max_related, "total_edges": 0},
                }

            roots = [dict(r) for r in root_rows]
            visited_concepts: Set[str] = {r["id"] for r in roots}
            queue: deque[tuple[str, int]] = deque((r["id"], 0) for r in roots)

            edges: List[Dict[str, Any]] = []
            seen_edge_ids: Set[str] = set()
            related_nodes: Dict[str, Dict[str, Any]] = {}

            while queue and len(related_nodes) < max_related:
                curr_id, depth = queue.popleft()
                if depth >= max_depth:
                    continue

                rel_rows = conn.execute(
                    """
                    SELECT r.*,
                           cs.name AS source_name, cs.technology AS source_tech, cs.category AS source_category,
                           ct.name AS target_name, ct.technology AS target_tech, ct.category AS target_category,
                           ct.description AS target_description, cs.description AS source_description
                    FROM relationships r
                    JOIN concepts cs ON cs.id = r.source_concept_id
                    JOIN concepts ct ON ct.id = r.target_concept_id
                    WHERE r.source_concept_id = ? OR r.target_concept_id = ?
                    ORDER BY CASE WHEN r.source_concept_id = ? THEN 0 ELSE 1 END, r.relation_type
                    """,
                    (curr_id, curr_id, curr_id),
                ).fetchall()

                for row in rel_rows:
                    edge_id = row["id"]
                    if edge_id in seen_edge_ids:
                        continue
                    seen_edge_ids.add(edge_id)

                    is_outgoing = row["source_concept_id"] == curr_id
                    neighbor_id = row["target_concept_id"] if is_outgoing else row["source_concept_id"]
                    neighbor_name = row["target_name"] if is_outgoing else row["source_name"]
                    neighbor_tech = row["target_tech"] if is_outgoing else row["source_tech"]
                    neighbor_cat = row["target_category"] if is_outgoing else row["source_category"]
                    neighbor_desc = row["target_description"] if is_outgoing else row["source_description"]

                    edges.append({
                        "source": row["source_name"],
                        "target": row["target_name"],
                        "relation_type": row["relation_type"],
                        "direction": "outgoing" if is_outgoing else "incoming",
                        "technology": row["technology"],
                        "version_scope": row["version_scope"],
                        "source_url": row["source_url"],
                        "notes": row["notes"],
                        "depth": depth + 1,
                    })

                    if neighbor_id not in visited_concepts and len(related_nodes) < max_related:
                        visited_concepts.add(neighbor_id)
                        related_nodes[neighbor_id] = {
                            "id": neighbor_id,
                            "name": neighbor_name,
                            "technology": neighbor_tech,
                            "category": neighbor_cat,
                            "description": neighbor_desc,
                            "distance": depth + 1,
                        }
                        queue.append((neighbor_id, depth + 1))

        return {
            "query_concept": concept_query,
            "normalized_concept": norm_name,
            "found": True,
            "root_concepts": roots,
            "edges": edges[: max_related * 2],
            "related_concepts": list(related_nodes.values()),
            "metadata": {
                "max_depth": max_depth,
                "max_related": max_related,
                "total_edges": len(edges[: max_related * 2]),
                "total_related_concepts": len(related_nodes),
            },
        }

    def expand_for_concepts(
        self,
        concept_names: List[str],
        technology: Optional[str] = None,
        max_depth: int = 1,
        max_related: int = 6,
    ) -> List[Dict[str, Any]]:
        """Return compact grounded edges for a list of concept names attached to a search result."""
        collected: List[Dict[str, Any]] = []
        seen_keys: Set[tuple[str, str, str]] = set()
        for cname in concept_names[:4]:
            res = self.traverse(cname, technology=technology, max_depth=max_depth, max_related=max_related)
            for edge in res.get("edges", []):
                key = (edge["source"], edge["relation_type"], edge["target"])
                if key not in seen_keys:
                    seen_keys.add(key)
                    collected.append({
                        "source": edge["source"],
                        "relation_type": edge["relation_type"],
                        "target": edge["target"],
                        "version_scope": edge["version_scope"],
                        "source_url": edge["source_url"],
                    })
                    if len(collected) >= max_related:
                        return collected
        return collected
