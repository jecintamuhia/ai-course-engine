"""Compute and persist ContentLevel for topics."""

from __future__ import annotations

import re
import uuid
from collections import deque

from app.models.dependency import Dependency
from app.models.topic import ContentLevel, Topic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

TERM_PATTERNS = [
    r"DNS",
    r"SMTP",
    r"DKIM",
    r"DMARC",
    r"SPF",
    r"SSL",
    r"TLS",
    r"API",
    r"JSON",
    r"PHP",
    r"Redis",
    r"Nginx",
    r"Exim",
    r"Postfix",
    r"SSH",
    r"WHM",
    r"cPanel",
    r"Plesk",
    r"DirectAdmin",
    r"Firewall",
    r"ModSecurity",
    r"AutoSSL",
]


def _count_technical_terms(title: str, description: str = "") -> int:
    text = f"{title} {description}".lower()
    count = 0
    for pat in TERM_PATTERNS:
        count += len(re.findall(pat, text, re.IGNORECASE))
    return count


def compute_content_level(
    *,
    depth: int,
    prereq_count: int,
    technical_terms: int,
    workload_minutes: int,
) -> ContentLevel:
    """Compute content level using deterministic rules."""
    if (
        depth >= 4
        or prereq_count >= 3
        or technical_terms >= 5
        or workload_minutes >= 90
    ):
        return ContentLevel.ADVANCED
    if (
        depth >= 2
        or prereq_count >= 1
        or technical_terms >= 2
        or workload_minutes >= 40
    ):
        return ContentLevel.INTERMEDIATE
    return ContentLevel.BASIC


class ContentLevelService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def compute_for_document(self, document_id: uuid.UUID) -> int:
        # Load topics and dependencies
        topics_res = await self._session.execute(
            select(Topic).where(Topic.document_id == document_id)
        )
        topics = list(topics_res.scalars().all())
        if not topics:
            return 0

        deps_res = await self._session.execute(
            select(Dependency)
            .join(Topic, Dependency.topic_id == Topic.id)
            .where(Topic.document_id == document_id)
        )
        deps = list(deps_res.scalars().all())

        # Build adjacency
        graph: dict[uuid.UUID, set[uuid.UUID]] = {t.id: set() for t in topics}
        reverse: dict[uuid.UUID, set[uuid.UUID]] = {t.id: set() for t in topics}
        for d in deps:
            if d.topic_id in graph and d.depends_on_topic_id in graph:
                graph[d.topic_id].add(d.depends_on_topic_id)
                reverse[d.depends_on_topic_id].add(d.topic_id)

        # Compute depth (longest path from sources) - simple approach
        # Depth = max distance from roots
        indeg = {t.id: len(graph[t.id]) for t in topics}
        dist = {t.id: 0 for t in topics}
        q = deque([tid for tid, d in indeg.items() if d == 0])
        order = []
        while q:
            cur = q.popleft()
            order.append(cur)
            for child in reverse[cur]:
                dist[child] = max(dist[child], dist[cur] + 1)
                indeg[child] -= 1
                if indeg[child] == 0:
                    q.append(child)

        updated = 0
        for t in topics:
            depth = dist.get(t.id, 0)
            prereq_count = len(graph.get(t.id, set()))
            technical_terms = _count_technical_terms(t.title)
            workload = t.estimated_workload_minutes or 0
            level = compute_content_level(
                depth=depth,
                prereq_count=prereq_count,
                technical_terms=technical_terms,
                workload_minutes=workload,
            )
            if t.content_level != level:
                t.content_level = level
                updated += 1

        await self._session.commit()
        return updated
