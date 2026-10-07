"""Document-wide prerequisite linking service.

Runs after every chapter has been analyzed, when the full set of real topic
titles finally exists. One LLM call is shown the whole catalogue so it can
name cross-chapter prerequisites by their actual titles; the proposals are
then validated deterministically by ``dependency.linker``.
"""

from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.core.exceptions import DocumentNotFound
from app.core.logging import get_logger
from app.db.repositories.documents import DocumentRepository
from app.db.repositories.topics import TopicRepository
from app.schemas.ai_extraction import PrerequisiteLinkResult
from app.services.ai.base import LLMProvider
from app.services.ai.prompts import (
    PREREQUISITE_LINKING_SYSTEM_PROMPT,
    build_prerequisite_linking_user_prompt,
)
from app.services.dependency.linker import (
    LinkResolution,
    build_catalogue,
    flatten_topics_in_reading_order,
    render_catalogue,
    resolve_links,
)

logger = get_logger(__name__)


class PrerequisiteLinkingService:
    """Asks the LLM which real topics each topic genuinely requires."""

    def __init__(
        self,
        document_repository: DocumentRepository,
        topic_repository: TopicRepository,
        llm_provider: LLMProvider,
    ) -> None:
        self._document_repository = document_repository
        self._topic_repository = topic_repository
        self._llm_provider = llm_provider

    async def link_document(self, document_id: uuid.UUID) -> LinkResolution:
        """
        Produce validated cross-topic prerequisite edges for a document.

        Returns edges keyed by topic id plus the proposals that were
        refused. Every refusal carries a reason so a thin graph can be
        diagnosed rather than guessed at.
        """
        document = await self._document_repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFound(f"Document {document_id} was not found.")

        top_level, chapter_labels = await self._topic_repository.list_in_reading_order(
            document_id
        )
        topics = flatten_topics_in_reading_order(top_level)

        if len(topics) < 2:
            logger.info(
                "Skipping prerequisite linking document_id=%s topics=%s",
                document_id,
                len(topics),
            )
            return LinkResolution()

        entries = build_catalogue(topics, chapter_labels)

        # Close the read transaction before the LLM call so a connection
        # is not held open while awaiting the provider.
        await self._topic_repository.commit()

        settings = get_settings()
        windows = self._plan_windows(
            entries, max_chars=settings.ai_linker_max_catalogue_chars
        )

        if len(windows) > 1:
            logger.info(
                "Linking document_id=%s in %s windows (catalogue exceeds max_chars=%s)",
                document_id,
                len(windows),
                settings.ai_linker_max_catalogue_chars,
            )

        merged = LinkResolution(edges={entry.topic_id: set() for entry in entries})

        for subject_slice, catalogue_slice in windows:
            result = await self._llm_provider.complete_structured(
                system_prompt=PREREQUISITE_LINKING_SYSTEM_PROMPT,
                user_prompt=build_prerequisite_linking_user_prompt(
                    topic_catalogue=render_catalogue(catalogue_slice),
                    max_prerequisites=(settings.ai_linker_max_prerequisites),
                ),
                response_model=PrerequisiteLinkResult,
            )

            resolution = resolve_links(
                result.links,
                catalogue_slice,
                max_prerequisites=settings.ai_linker_max_prerequisites,
            )

            # Only subjects this window was asked about may contribute
            # edges; a model that volunteers links for topics outside its
            # window must not widen the result.
            subject_ids = {entry.topic_id for entry in subject_slice}

            for topic_id, depends_on_ids in resolution.edges.items():
                if topic_id in subject_ids and depends_on_ids:
                    merged.edges.setdefault(topic_id, set()).update(depends_on_ids)

            merged.rejected.extend(resolution.rejected)

        linked = sum(1 for ids in merged.edges.values() if ids)

        logger.info(
            "Prerequisite linking document_id=%s topics=%s linked_topics=%s "
            "edges=%s rejected=%s",
            document_id,
            len(topics),
            linked,
            sum(len(ids) for ids in merged.edges.values()),
            len(merged.rejected),
        )

        return merged

    def _plan_windows(
        self, entries: list, *, max_chars: int
    ) -> list[tuple[list, list]]:
        """
        Split the document into sequential windows of topics to ask about.

        Each window asks only about its own topics but is shown the
        catalogue from the start of the book up to the end of the window,
        because a prerequisite may only be earlier. A single window
        covering the whole document is the normal case; the split exists
        so an unusually large book cannot overflow the provider's context
        window, and is reported rather than applied silently.
        """
        settings = get_settings()
        batch_size = settings.ai_linker_batch_size

        windows: list[tuple[list, list]] = []
        for start in range(0, len(entries), batch_size):
            subjects = entries[start : start + batch_size]
            catalogue = entries[: start + batch_size]

            rendered = render_catalogue(catalogue)
            if len(rendered) > max_chars:
                logger.warning(
                    "Prerequisite linking catalogue still over budget "
                    "chars=%s max_chars=%s; trimming older context",
                    len(rendered),
                    max_chars,
                )
                trimmed = list(catalogue)
                while (
                    len(trimmed) > len(subjects)
                    and len(render_catalogue(trimmed)) > max_chars
                ):
                    trimmed.pop(0)
                catalogue = trimmed

            windows.append((subjects, catalogue))

        return windows
