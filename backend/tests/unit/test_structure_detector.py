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


def test_derives_chapters_from_numbered_divisions_without_chapter_keyword() -> None:
    """A book that numbers its divisions but never says "Chapter".

    This is the shape of the real server-administration textbook used to
    verify the detector. Before this path existed it produced 32 chapters
    named after command-line acronyms (FTP, SSL, BIND, DKIM, ...).
    """
    pages = [
        (
            1,
            "1.1 The Web Hosting Ecosystem\n"
            "1.1.1 From Browser to Web Page\n"
            "Body text describing the journey from browser to page.",
        ),
        (
            2,
            "1.1.2 What is a Web Server?\nA web server responds to requests over HTTP.",
        ),
        (
            3,
            "1.2 Linux Fundamentals for Hosting\n"
            "1.2.1 Connecting via SSH\n"
            "Administrators connect to servers over SSH.",
        ),
        (4, "More Linux content continues on this page."),
    ]

    chapters = detect_structure(pages)

    assert len(chapters) == 2

    first, second = chapters
    assert first.number == "1.1"
    assert first.title == "The Web Hosting Ecosystem"
    assert first.start_page == 1
    assert first.end_page == 2
    assert [s.number for s in first.sections] == ["1.1.1", "1.1.2"]
    assert first.sections[0].title == "From Browser to Web Page"
    assert first.sections[1].end_page == 2

    assert second.number == "1.2"
    assert second.title == "Linux Fundamentals for Hosting"
    assert [s.number for s in second.sections] == ["1.2.1"]
    assert second.sections[0].end_page == 4


def test_numbered_chapters_take_priority_over_all_caps_fallback() -> None:
    pages = [
        (1, "FTP\n1.1 Real Chapter\nBody text."),
        (2, "SSL\nMore body text."),
    ]

    chapters = detect_structure(pages)

    assert [c.title for c in chapters] == ["Real Chapter"]


def test_all_caps_fallback_rejects_command_acronyms() -> None:
    """Bare command names must not become chapters.

    Regression: the fallback matched "FTP", "SSL", "DNS", "BIND", "CSR",
    "DKIM", "PTR" and title-cased them into a document whose real sections
    were each parented under a meaningless acronym.
    """
    pages = [
        (
            1,
            "PROFESSIONAL TRAINING PROGRAMME\nCover material for the course.",
        ),
        (2, "FTP\nsystemctl reload httpd\nMore command output follows."),
        (3, "SSL\nopenssl req -new\nMore command output follows."),
        (4, "CERTIFICATION PREPARATION\nClosing material for the programme."),
    ]

    chapters = detect_structure(pages)

    titles = [c.title for c in chapters]
    assert "Ftp" not in titles
    assert "Ssl" not in titles
    assert "Professional Training Programme" in titles
    assert "Certification Preparation" in titles


def test_all_caps_fallback_keeps_long_single_word_headings() -> None:
    """The acronym rule must not reject genuine single-word headings."""
    pages = [
        (1, "INTRODUCTION\nOpening material."),
        (2, "METHODOLOGY\nDescribing the approach."),
    ]

    chapters = detect_structure(pages)

    assert [c.title for c in chapters] == ["Introduction", "Methodology"]


def test_section_is_filed_by_number_not_page_range() -> None:
    """A section sharing a page with the next chapter keeps its own parent.

    Regression: "1.1.4 Data Centres" sits on the same page as chapter
    "1.2", so page-range assignment filed it under 1.2 and detached it from
    the chapter it belongs to.
    """
    pages = [
        (4, "1.1 The Web Hosting Ecosystem\n1.1.1 From Browser to Web Page"),
        (5, "1.1.2 What is a Web Server?"),
        (
            6,
            "1.1.3 Types of Web Hosting\n"
            "1.1.4 Data Centres and Server Infrastructure\n"
            "1.2 Linux Fundamentals",
        ),
        (7, "1.2.1 Connecting via SSH"),
    ]

    chapters = detect_structure(pages)
    by_number = {c.number: c for c in chapters}

    assert [s.number for s in by_number["1.1"].sections] == [
        "1.1.1",
        "1.1.2",
        "1.1.3",
        "1.1.4",
    ]
    assert [s.number for s in by_number["1.2"].sections] == ["1.2.1"]


def test_section_ranges_are_never_inverted() -> None:
    """A section starting past its chapter's nominal end stays valid."""
    pages = [
        (1, "1.1 First Division\n1.1.1 Only Section"),
        (2, "1.2 Second Division\n1.2.1 Late Section On The Same Page"),
    ]

    chapters = detect_structure(pages)

    for chapter in chapters:
        for section in chapter.sections:
            assert section.end_page >= section.start_page, (
                f"section {section.number} has an inverted page range"
            )


def test_wrapped_heading_title_is_joined() -> None:
    """A heading laid out across lines keeps its whole title."""
    pages = [
        (
            1,
            "1.1 DNS — The Domain Name System, Explained in\nFull\n\n"
            "The Domain Name System is a phone book.",
        ),
    ]

    chapters = detect_structure(pages)

    assert chapters[0].title == "DNS — The Domain Name System, Explained in Full"


def test_multi_line_wrap_joins_up_to_two_continuations() -> None:
    """A title split into several short lines is reassembled."""
    pages = [
        (
            1,
            "1.1 Security Hardening — Comprehensive Panel-by-\n"
            "Panel\nGuide\n\nBody text starts here.",
        ),
    ]

    chapters = detect_structure(pages)

    assert chapters[0].title == (
        "Security Hardening — Comprehensive Panel-by- Panel Guide"
    )


def test_body_text_after_heading_is_not_absorbed() -> None:
    """Continuation requires a blank line, so prose is never swallowed."""
    pages = [
        (
            1,
            "1.1 First Division\n"
            "This sentence continues directly into the next line without any "
            "blank line separating them at all here.",
        ),
    ]

    chapters = detect_structure(pages)

    assert chapters[0].title == "First Division"
    assert len(chapters) == 1


def test_wrap_does_not_swallow_the_following_heading() -> None:
    """A following heading is never absorbed into the previous title."""
    pages = [
        (1, "1.1 First Division\n\n1.2 Second Division\n\nBody text."),
    ]

    chapters = detect_structure(pages)

    assert [c.title for c in chapters] == [
        "First Division",
        "Second Division",
    ]


def test_wrapped_section_title_is_joined() -> None:
    """Section headings get the same treatment as chapters."""
    pages = [
        (
            1,
            "1.1 First Division\n1.1.1 A Section Title That\nWrapped\n\n"
            "Section body text.",
        ),
    ]

    chapters = detect_structure(pages)

    assert [s.title for s in chapters[0].sections] == ["A Section Title That Wrapped"]


def test_section_title_starting_with_lowercase_brand_is_detected() -> None:
    """A title beginning with a lowercase brand name ("cPanel...") matches.

    The WHM textbook lost all five of its "cPanel..." subsections
    (1.4.1, 2.1.1, 3.2.2, 3.3.1, 5.2.1) because the numbered-heading
    pattern required an initial uppercase letter.
    """
    pages = [
        (1, "1.4 The Three Control Panels\nArchitecture overview.\n"),
        (
            2,
            "1.4.1 cPanel/WHM — Architecture and Interface\n"
            "The most widely deployed panel.\n",
        ),
        (
            3,
            "1.4.2 DirectAdmin — Architecture and Interface\n"
            "A lightweight alternative panel.\n",
        ),
    ]

    chapters = detect_structure(pages)

    assert len(chapters) == 1
    assert [s.number for s in chapters[0].sections] == ["1.4.1", "1.4.2"]


def test_chapter_title_starting_with_digit_is_detected() -> None:
    """A numbered heading whose title starts with a digit ("30-Day...") matches."""
    pages = [
        (1, "5.2 Professional Certification Preparation\nCertification overview.\n"),
        (2, "5.3 30-Day Certification Study Plan\nA day-by-day schedule.\n"),
    ]

    chapters = detect_structure(pages)

    assert [c.number for c in chapters] == ["5.2", "5.3"]
    assert chapters[1].title.startswith("30-Day")


def test_lowercase_word_after_number_is_not_a_heading() -> None:
    """A body line starting "1.2 million..." is prose, not a heading."""
    pages = [
        (1, "1.1 Real Division\nReal body text.\n"),
        (2, "1.2 million servers were migrated worldwide"),
    ]

    chapters = detect_structure(pages)

    assert [c.number for c in chapters] == ["1.1"]
