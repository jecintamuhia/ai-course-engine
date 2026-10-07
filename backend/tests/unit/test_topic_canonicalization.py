"""Unit tests for topic canonicalization and deduplication."""

from __future__ import annotations

import uuid

from app.models.concept import Concept
from app.models.topic import Topic, TopicImportance
from app.services.topics.canonicalization import (
    apply_canonicalization,
    canonical_key_for,
    canonical_of,
    classify_importance,
    normalize_title,
    title_similarity,
)


def _topic(
    title: str,
    *,
    difficulty: int = 1,
    workload: int = 60,
    concepts: int = 0,
    order_index: int = 0,
    parent: uuid.UUID | None = None,
) -> Topic:
    topic = Topic(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        title=title,
        difficulty=difficulty,
        estimated_workload_minutes=workload,
        order_index=order_index,
    )
    topic.concepts = [
        Concept(
            topic_id=topic.id,
            name=f"Concept {i}",
            description="c",
            order_index=i,
        )
        for i in range(concepts)
    ]
    if parent is not None:
        topic.parent_topic_id = parent
    return topic


def test_normalize_title_folds_case_punctuation_and_stopwords():
    assert (
        normalize_title("  Decision  Trees! (Algorithms) ")
        == "decision trees algorithms"
    )
    assert normalize_title("The Decision Tree") == "decision tree"
    assert normalize_title("Understanding ML") == "understanding ml"


def test_canonical_key_folds_plurals_safely():
    assert canonical_of("Decision Trees", "Decision tree")
    assert canonical_of("   Neural Network  ", "neural networks")
    assert not canonical_of("Machine Learning", "Machine Vision")
    # irregular plurals are never collapsed
    assert not canonical_of("Analyses", "Analysis")
    assert not canonical_of("Basis", "bases")


def test_canonical_key_empty_title_degrades_gracefully():
    assert canonical_key_for("!!!") == ""


def test_title_similarity():
    assert title_similarity("Decision Trees", "Decision Trees") == 1.0
    assert title_similarity("K-Means Clustering", "K Nearest Neighbors") < 0.5
    score = title_similarity("Decision Trees Intro", "Decision Trees")
    assert 0.0 < score < 1.0


def test_classify_importance_heuristics():
    root_heavy = _topic("A", difficulty=2, workload=120, concepts=2)
    assert classify_importance(root_heavy) == TopicImportance.MAJOR.value

    foundational = _topic("B", difficulty=1, workload=60)
    assert classify_importance(foundational) == TopicImportance.MAJOR_FOUNDATIONAL.value

    advanced = _topic("C", difficulty=5)
    assert classify_importance(advanced) == TopicImportance.ADVANCED.value

    minor = _topic("D", workload=20)
    assert classify_importance(minor) == TopicImportance.MINOR.value

    supporting = _topic("E", workload=45)
    assert classify_importance(supporting) == TopicImportance.SUPPORTING.value

    sub_light = _topic("F", workload=10, parent=uuid.uuid4())
    assert classify_importance(sub_light) == TopicImportance.MINOR.value

    sub_heavy = _topic("G", workload=90, parent=uuid.uuid4())
    assert classify_importance(sub_heavy) == TopicImportance.SUPPORTING.value


def test_apply_canonicalization_merges_exact_normalized_duplicates():
    topics = [
        _topic("Decision Trees", workload=120, order_index=0),
        _topic("Decision tree", workload=90, order_index=1),
        _topic("Linear Regression", workload=60, order_index=2),
        _topic("Linear regression", workload=45, order_index=3),
        _topic("Neural Networks", workload=100, order_index=4),
    ]
    result = apply_canonicalization(topics)

    canonical = [t for t in topics if t.duplicate_of_id is None]
    duplicates = [t for t in topics if t.duplicate_of_id is not None]

    assert result.clusters == 2
    assert result.duplicates_flagged == 2
    assert len(canonical) == 3
    assert len(duplicates) == 2

    by_key = {canonical_key_for(t.title): t for t in canonical}
    dtree_canonical = by_key[canonical_key_for("Decision Trees")]
    assert "Decision tree" in dtree_canonical.aliases

    for dup in duplicates:
        canonical_for = by_key[canonical_key_for(dup.title)]
        assert dup.duplicate_of_id == canonical_for.id

    # Non-duplicated topics stay untouched and alias-free
    neural = by_key[canonical_key_for("Neural Networks")]
    assert neural.aliases == []
    assert neural.duplicate_of_id is None


def test_apply_canonicalization_flags_near_duplicates_without_merging():
    topics = [
        _topic("Introduction to Neural Networks and Deep Learning", order_index=0),
        _topic("Neural Networks and Deep Learning", order_index=1),
    ]
    result = apply_canonicalization(topics)

    assert result.clusters == 0
    assert result.duplicates_flagged == 0
    assert any(round(sim, 3) >= 0.8 for _, _, sim in result.near_duplicates)


def test_apply_canonicalization_never_merges_distinct_concepts():
    topics = [
        _topic("K-Means Clustering", order_index=0),
        _topic("K Nearest Neighbors", order_index=1),
    ]
    result = apply_canonicalization(topics)
    assert result.clusters == 0
    assert all(t.duplicate_of_id is None for t in topics)


def test_apply_canonicalization_does_not_merge_inside_topics():
    parent = uuid.uuid4()
    sub_a = _topic("Recurrent Cells", workload=30, order_index=1, parent=parent)
    sub_b = _topic("Recurrent Cell", workload=30, order_index=2, parent=parent)
    root = _topic("RNNs", order_index=0)

    result = apply_canonicalization([root, sub_a, sub_b])

    assert result.clusters == 0
    assert all(t.duplicate_of_id is None for t in [root, sub_a, sub_b])
    # subtopics still get importance assigned
    assert sub_a.importance == TopicImportance.MINOR.value


def test_apply_canonicalization_assigns_importance_to_subtopics():
    parent = uuid.uuid4()
    subtopic = _topic("sub", workload=50, parent=parent, order_index=1)
    root = _topic("root", workload=60, order_index=0)
    topics = [root, subtopic]

    apply_canonicalization(topics)

    assert subtopic.importance == TopicImportance.SUPPORTING.value
    assert root.importance == TopicImportance.MAJOR_FOUNDATIONAL.value
