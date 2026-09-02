"""Unit tests for deterministic chapter/section structure detection."""

from __future__ import annotations

from app.services.ingestion.structure_detector import detect_structure


def test_detects_chapters_and_sections_with_correct_page_spans() -> None:
    pages = [
        (1, "Chapter 1: Introduction to Systems\nThis chapter introduces core ideas."),
        (2, "1.1 What is a System\nA system is a collection of interacting parts."),
        (3, "1.2 System Boundaries\nBoundaries define what is inside vs outside."),
        (4, "Chapter 2: Feedback Loops\nThis chapter covers feedback."),
        (5, "2.1 Positive Feedback\nPositive feedback amplifies change."),
        (6, "2.2 Negative Feedback\nNegative feedback stabilizes systems."),
        (7, "Continuing chapter 2 content with no new heading on this page."),
    ]

    chapters = detect_structure(pages)

    assert len(chapters) == 2

    chapter_one = chapters[0]
    assert chapter_one.number == "1"
    assert chapter_one.title == "Introduction to Systems"
    assert chapter_one.start_page == 1
    assert chapter_one.end_page == 3
    assert len(chapter_one.sections) == 2
    assert chapter_one.sections[0].number == "1.1"
    assert chapter_one.sections[1].end_page == 3

    chapter_two = chapters[1]
    assert chapter_two.number == "2"
    assert chapter_two.start_page == 4
    assert chapter_two.end_page == 7
    assert chapter_two.sections[-1].end_page == 7


def test_does_not_misdetect_sentence_fragments_with_numbers() -> None:
    pages = [
        (
            1,
            "In this book we discuss 3.14 as an approximation of pi.\n"
            "Step 1.2 of the process involves calibration, which takes time.",
        ),
        (2, "The results in table 4.5 show significant improvement."),
    ]

    chapters = detect_structure(pages)

    assert chapters == []


def test_falls_back_to_all_caps_headings_when_no_numbered_chapters() -> None:
    pages = [
        (1, "INTRODUCTION\nThis is the opening material of the book."),
        (2, "More content continues here without any heading."),
        (3, "METHODOLOGY\nHere we describe the approach used."),
    ]

    chapters = detect_structure(pages)

    assert len(chapters) == 2
    assert chapters[0].title == "Introduction"
    assert chapters[0].start_page == 1
    assert chapters[0].end_page == 2
    assert chapters[1].title == "Methodology"
    assert chapters[1].start_page == 3
    assert chapters[1].end_page == 3


def test_returns_empty_list_for_document_with_no_detectable_structure() -> None:
    pages = [
        (1, "just some plain lowercase body text with no headings at all."),
    ]

    assert detect_structure(pages) == []


def test_orphan_section_before_any_chapter_is_ignored() -> None:
    pages = [
        (1, "1.1 Orphan Section\nThis appears before any chapter heading."),
        (2, "Chapter 1: Real Start\nActual chapter content begins here."),
    ]

    chapters = detect_structure(pages)

    assert len(chapters) == 1
    assert chapters[0].sections == []