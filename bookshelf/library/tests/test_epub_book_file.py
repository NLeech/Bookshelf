import unittest
import os
from parameterized import parameterized

from ebooklib import epub
from PIL import Image
from library.book_utils import EpubBookFile
from library.tests.epub_test_utils import (
    create_epub_one_author,
    create_epub_two_authors,
    create_epub_nested_chapters,
    create_epub_cyrillic,
    create_epub_no_toc,
    create_epub_with_cover,
    create_epub_cover_metadata,
    create_epub_cover_tag_name,
    create_epub_cover_heuristic,
    create_epub_with_isbn,
    create_epub_parent_with_anchored_children,
    create_epub_gap_and_split_tail,
    create_epub_single_toc_entry_spanning_flow,
    create_epub_interleaved_levels,
    create_epub_no_toc_with_empty_cover,
    create_epub_pre_toc,
    create_epub_pre_toc_textual,
    create_epub_unresolved_anchors,
    create_epub_dangling_toc,
    create_epub_container_children_reference,
    create_epub_multilevel_chapters_reference,
    create_epub_nested_containers_reference,
    create_epub_single_chapter_reference,
    create_epub_split_parts_reference,
    write_stream_to_file,
)


class TestEpubBookFileLoad(unittest.TestCase):
    def setUp(self):
        self.book_file = EpubBookFile()

    @parameterized.expand([
        ("one_author", create_epub_one_author, "Sample EPUB (One Author)", ["Author One"], "A sample description."),
        ("two_authors", create_epub_two_authors, "Sample EPUB (Two Authors)", ["Author One", "Author Two"], "Another sample description with two authors."),
        ("cyrillic", create_epub_cyrillic, "Приклад EPUB (Кирилиця)", ["Автор Один"], "Опис кирилицею."),
    ])
    def test_load_from_stream(self, name, create_epub_func, expected_title, expected_authors, expected_description):
        """
        Tests loading an EPUB from an in-memory stream and verifies title, authors and description.
        """
        with create_epub_func() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertEqual(self.book_file.title, expected_title)
            self.assertEqual(self.book_file.authors, expected_authors)
            self.assertEqual(self.book_file.description, expected_description)
            self.assertEqual(self.book_file.file_type, 'epub')

    @parameterized.expand([
        ("one_author", create_epub_one_author, "Sample EPUB (One Author)", ["Author One"], "A sample description."),
        ("two_authors", create_epub_two_authors, "Sample EPUB (Two Authors)", ["Author One", "Author Two"], "Another sample description with two authors."),
    ])
    def test_load_from_file(self, name, create_epub_func, expected_title, expected_authors, expected_description):
        """
        Tests loading an EPUB from a temporary file and verifies title, authors and description.
        """
        temp_dir = "temp_test_books"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, f"{name}.epub")

        try:
            with create_epub_func() as epub_stream:
                write_stream_to_file(epub_stream, file_path)

            self.book_file.load_from_file(file_path)
            self.assertEqual(self.book_file.title, expected_title)
            self.assertEqual(self.book_file.authors, expected_authors)
            self.assertEqual(self.book_file.description, expected_description)
            self.assertEqual(self.book_file.file_type, 'epub')
            self.assertGreater(self.book_file.size, 0)
            self.assertEqual(self.book_file.size, os.path.getsize(file_path))
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    def test_extract_isbn_scheme(self):
        """
        Tests extraction of ISBN using opf:scheme="ISBN".
        """
        isbn_val = "9781234567890"
        with create_epub_with_isbn(isbn_val) as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertEqual(self.book_file.isbn, isbn_val)

    def test_extract_isbn_prefix(self):
        """
        Tests extraction of ISBN using 'isbn:' prefix.
        """
        isbn_val = "978-0-545-01022-1"
        with create_epub_with_isbn(isbn_val, use_prefix=True) as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertEqual(self.book_file.isbn, isbn_val)

    def test_extract_cover(self):
        """
        Tests extraction of a cover image from an EPUB (standard EpubCover).
        """
        with create_epub_with_cover() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertIsNotNone(self.book_file.cover)
            self.assertIsInstance(self.book_file.cover, Image.Image)
            self.assertEqual(self.book_file.cover.size, (100, 100))

    def test_extract_cover_metadata(self):
        """
        Tests extraction of a cover image from an EPUB using metadata (EPUB 2.0).
        """
        with create_epub_cover_metadata() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertIsNotNone(self.book_file.cover)
            self.assertIsInstance(self.book_file.cover, Image.Image)
            self.assertEqual(self.book_file.cover.size, (100, 100))

    def test_extract_cover_tag_name(self):
        """
        Tests extraction of a cover image from an EPUB using metadata tag NAMED 'cover'.
        """
        with create_epub_cover_tag_name() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertIsNotNone(self.book_file.cover)
            self.assertIsInstance(self.book_file.cover, Image.Image)
            self.assertEqual(self.book_file.cover.size, (100, 100))

    def test_extract_cover_heuristic(self):
        """
        Tests extraction of a cover image from an EPUB using heuristic fallback.
        """
        with create_epub_cover_heuristic() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertIsNotNone(self.book_file.cover)
            self.assertIsInstance(self.book_file.cover, Image.Image)
            self.assertEqual(self.book_file.cover.size, (100, 100))


class TestEpubChapterExtraction(unittest.TestCase):
    def setUp(self):
        self.book_file = EpubBookFile()

    def test_get_simple_chapters(self):
        """
        Tests extraction of a simple, flat list of chapters.
        """
        with create_epub_one_author() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertEqual(self.book_file.description, "A sample description.")
            chapters = self.book_file.chapters
            self.assertEqual(len(chapters), 3)
            self.assertEqual(chapters[0].title, "Chapter 1")
            self.assertIn("content of the first chapter", chapters[0].content_as_text)
            self.assertEqual(chapters[1].title, "Chapter 2")
            self.assertEqual(chapters[2].title, "Chapter 3")
            self.assertEqual(len(chapters[0].subchapters), 0)

    def test_get_nested_chapters(self):
        """
        Tests extraction of chapters with a nested structure.
        """
        with create_epub_nested_chapters() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertEqual(self.book_file.description, "Description for nested chapters.")
            chapters = self.book_file.chapters
            # Expecting 3 top-level chapters
            self.assertEqual(len(chapters), 3)

            # Check Chapter 1 and its subchapters
            self.assertEqual(chapters[0].title, "Chapter 1")
            self.assertEqual(len(chapters[0].subchapters), 2)
            self.assertEqual(chapters[0].subchapters[0].title, "Subchapter 1.1")
            self.assertEqual(chapters[0].subchapters[0].level, 1)
            self.assertIn("Content of subchapter 1.1", chapters[0].subchapters[0].content_as_text)
            self.assertEqual(chapters[0].subchapters[1].title, "Subchapter 1.2")

            # Check Chapter 2 (no subchapters)
            self.assertEqual(chapters[1].title, "Chapter 2")
            self.assertEqual(len(chapters[1].subchapters), 0)

            # Check Chapter 3 and its subchapters
            self.assertEqual(chapters[2].title, "Chapter 3")
            self.assertEqual(len(chapters[2].subchapters), 1)
            self.assertEqual(chapters[2].subchapters[0].title, "Subchapter 3.1")
            self.assertIn("Content of subchapter 3.1", chapters[2].subchapters[0].content_as_text)

    def test_cyrillic_chapters(self):
        """
        Tests extraction of chapters with Cyrillic titles and content.
        """
        with create_epub_cyrillic() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertEqual(self.book_file.description, "Опис кирилицею.")
            chapters = self.book_file.chapters
            self.assertEqual(len(chapters), 3)
            self.assertEqual(chapters[0].title, "Глава 1")
            self.assertIn("зміст першої глави", chapters[0].content_as_text)
            self.assertEqual(chapters[1].title, "Глава 2")
            self.assertEqual(chapters[2].title, "Глава 3")

    def test_get_chapters_no_toc(self):
        """
        Tests extraction of chapters when the EPUB has no table of contents,
        forcing extraction from the spine.
        """
        with create_epub_no_toc() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertEqual(self.book_file.description, "Description for no TOC book.")
            chapters = self.book_file.chapters
            self.assertEqual(len(chapters), 3)
            self.assertEqual(chapters[0].title, "No TOC Chapter 1")
            self.assertIn("content of the first chapter without TOC", chapters[0].content_as_text)
            self.assertEqual(chapters[1].title, "No TOC Chapter 2")
            self.assertIn("content of the second chapter without TOC", chapters[1].content_as_text)
            self.assertEqual(chapters[2].title, "No TOC Chapter 3")
            self.assertIn("content of the third chapter without TOC", chapters[2].content_as_text)
            self.assertEqual(len(chapters[0].subchapters), 0) # Should be flat

    # ------------------------------------------------------------------ #
    # Boundary model: TOC normalization
    # ------------------------------------------------------------------ #

    def test_normalize_toc_lone_link(self):
        """T1: a lone epub.Link TOC must not crash and yields its file as a chapter.

        ebooklib cannot *write* a lone-Link TOC, so the shape is injected onto an
        already-loaded book and re-extracted — exercising _normalize_toc directly.
        """
        with create_epub_one_author() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.book_file.book.toc = epub.Link('chap_01.xhtml', 'Lone', 'lone')
            chapters = self.book_file._get_chapters_from_book()

            self.assertTrue(chapters)
            self.assertEqual(chapters[0].title, 'Lone')

    def test_normalize_toc_two_element_list_not_misfired(self):
        """T2: a 2-element LIST [Link, (Section, [child])] keeps BOTH top entries."""
        with create_epub_one_author() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.book_file.book.toc = [
                epub.Link('chap_01.xhtml', 'First', 'first'),
                (epub.Section('Part'), [epub.Link('chap_02.xhtml', 'Child', 'child')]),
            ]
            chapters = self.book_file._get_chapters_from_book()

            self.assertEqual(len(chapters), 2)
            self.assertEqual(chapters[0].title, 'First')
            self.assertEqual(chapters[1].title, 'Part')
            self.assertEqual(len(chapters[1].subchapters), 1)
            self.assertEqual(chapters[1].subchapters[0].title, 'Child')

    @parameterized.expand([
        ('empty_is_skipped', '<div></div>', 1),
        ('media_only_is_emitted', '<img src="plate.jpg"/>', 2),
        ('real_text_is_emitted', '<p>Real textual front matter, plenty of words here.</p>', 2),
    ])
    def test_emptiness_text_or_media(self, name, front_content, expected_count):
        """T3: pre-TOC front matter is skipped only when it has no text and no media."""
        with create_epub_pre_toc(front_content) as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual(len(chapters), expected_count)
            # The TOC chapter is always present and last.
            self.assertEqual(chapters[-1].title, 'Chapter 1')

    # ------------------------------------------------------------------ #
    # Boundary model: slicing / spine-fill
    # ------------------------------------------------------------------ #

    def test_multi_anchor_one_file_splits_into_subchapters(self):
        """T4: one file with a no-anchor parent and two anchored children."""
        with create_epub_parent_with_anchored_children() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual(len(chapters), 1)
            parent = chapters[0]
            self.assertEqual(parent.title, 'Раздел')
            self.assertEqual(len(parent.subchapters), 2)
            self.assertEqual(parent.subchapters[0].title, 'Раздел 1-50')
            self.assertEqual(parent.subchapters[1].title, 'Раздел 51-100')

            # Each verse body appears exactly once, in its own subchapter.
            self.assertIn('one to fifty', parent.subchapters[0].content_as_text)
            self.assertNotIn('one to fifty', parent.content_as_text)
            self.assertNotIn('one to fifty', parent.subchapters[1].content_as_text)
            self.assertIn('fifty-one to one hundred', parent.subchapters[1].content_as_text)

    def test_gap_and_split_tail_fold_into_previous_chapter(self):
        """T5: split tails and gap files fold into the previous chapter."""
        with create_epub_gap_and_split_tail() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual([c.title for c in chapters], ['Vireo', 'Heron'])
            # The _split_001 tail folds into the previous (Vireo) chapter.
            self.assertIn('split tail continuation', chapters[0].content_as_text)
            self.assertIn('Heron opening', chapters[1].content_as_text)

    def test_single_toc_entry_spanning_flow(self):
        """T6: TOC=1 entry -> one chapter spanning the whole spine flow."""
        with create_epub_single_toc_entry_spanning_flow() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual(len(chapters), 1)
            self.assertEqual(chapters[0].title, 'Start')
            text = chapters[0].content_as_text
            self.assertIn('Section one', text)
            self.assertIn('Section two', text)
            self.assertIn('Section three', text)

    def test_interleaved_levels_in_one_file(self):
        """T7: anchors at different tree levels within one file."""
        with create_epub_interleaved_levels() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual([c.title for c in chapters], ['Глава 1', 'Глава 2'])
            self.assertEqual([c.title for c in chapters[0].subchapters], ['Подраздел 1.1'])
            self.assertEqual([c.title for c in chapters[1].subchapters], ['Подраздел 2.1'])
            # Content is bounded by the next anchor in DOM order.
            self.assertIn('Subsection 1.1 body', chapters[0].subchapters[0].content_as_text)
            self.assertNotIn('Chapter two body', chapters[0].subchapters[0].content_as_text)

    # ------------------------------------------------------------------ #
    # Boundary model: negative / edge paths
    # ------------------------------------------------------------------ #

    def test_no_toc_each_file_is_chapter_with_empty_skip(self):
        """T8: with no TOC, each non-empty spine file is one flat chapter."""
        with create_epub_no_toc_with_empty_cover() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual([c.title for c in chapters], ['First', 'Second'])
            self.assertTrue(all(len(c.subchapters) == 0 for c in chapters))

    def test_pre_toc_textual_becomes_top_level_chapter(self):
        """T10: an empty cover is skipped; a textual preface becomes a top chapter."""
        with create_epub_pre_toc_textual() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual(len(chapters), 2)
            # No heading in the preface -> title falls back to the filename stem.
            self.assertEqual(chapters[0].title, 'preface')
            self.assertIn('Preface narrative', chapters[0].content_as_text)
            self.assertEqual(chapters[1].title, 'Chapter 1')

    def test_unresolved_anchors_do_not_shift_content(self):
        """T12: TOC #fragments missing from the DOM -> each file is its own chapter.

        Regression for the forward-shift bug: an unresolved anchor must be treated
        as anchorless (whole file as the chapter's content), never leaving the
        chapter empty and absorbing the next file's body.
        """
        with create_epub_unresolved_anchors() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual([c.title for c in chapters], ['Alpha', 'Beta', 'Gamma'])
            # Each chapter holds its OWN file's text, not the next file's.
            self.assertIn('Alpha file narrative', chapters[0].content_as_text)
            self.assertNotIn('Beta file narrative', chapters[0].content_as_text)
            self.assertIn('Beta file narrative', chapters[1].content_as_text)
            self.assertNotIn('Gamma file narrative', chapters[1].content_as_text)
            self.assertIn('Gamma file narrative', chapters[2].content_as_text)

    def test_dangling_toc_href_is_skipped(self):
        """T11: a TOC entry pointing at a missing file is dropped without a crash."""
        with create_epub_dangling_toc() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual([c.title for c in chapters], ['Ch1', 'Ch2'])
            self.assertIn('Chapter one narrative', chapters[0].content_as_text)
            self.assertIn('Chapter two narrative', chapters[1].content_as_text)


class TestEpubChapterExtractionReference(unittest.TestCase):
    """Regression twins replicating five real-world book structures (R1-R5).

    Each twin is a synthetic in-memory EPUB reproducing a real structure's spine
    order, TOC tree (#fragments included), and in-DOM anchor ids, with lorem
    bodies. Acceptance trees were validated against FBReader/Moon Reader.
    """

    def setUp(self):
        self.book_file = EpubBookFile()

    @staticmethod
    def _titles(chapters):
        return [c.title for c in chapters]

    def test_container_children_reference_tree(self):
        """R1: Предисловие / container -> (Раздел 1-50 .. Раздел 551-600) / Послесловие."""
        with create_epub_container_children_reference() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual(self._titles(chapters), ['Предисловие', 'Раздел', 'Послесловие'])
            container = chapters[1]
            self.assertEqual(len(container.subchapters), 12)
            self.assertEqual(container.subchapters[0].title, 'Раздел 1-50')
            self.assertEqual(container.subchapters[-1].title, 'Раздел 551-600')
            self.assertTrue(all(sc.level == 1 for sc in container.subchapters))

    def test_multilevel_chapters_reference_tree(self):
        """R2: Предисловие / Глава 1 -> (4 children) / Глава 2 -> (5 children)."""
        with create_epub_multilevel_chapters_reference() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual(self._titles(chapters), ['Предисловие', 'Глава 1', 'Глава 2'])
            self.assertEqual(
                self._titles(chapters[1].subchapters),
                ['Раздел 1.1', 'Раздел 1.2', 'Раздел 1.3', 'Раздел 1.4'],
            )
            self.assertEqual(len(chapters[2].subchapters), 5)

    def test_nested_containers_reference_tree(self):
        """R3: nested containers Часть 1 -> Глава 1 -> Подраздел 1.1."""
        with create_epub_nested_containers_reference() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual(self._titles(chapters), ['Часть 1'])
            part = chapters[0]
            self.assertEqual(self._titles(part.subchapters), ['Глава 1'])
            self.assertEqual(part.subchapters[0].level, 1)
            chapter = part.subchapters[0]
            self.assertEqual(self._titles(chapter.subchapters), ['Подраздел 1.1'])
            self.assertEqual(chapter.subchapters[0].level, 2)

    def test_single_chapter_reference(self):
        """R4: one "Start" chapter spanning the whole flow."""
        with create_epub_single_chapter_reference() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual(len(chapters), 1)
            self.assertEqual(chapters[0].title, 'Start')
            self.assertEqual(len(chapters[0].subchapters), 0)
            text = chapters[0].content_as_text
            self.assertIn('Section 1', text)
            self.assertIn('Section 6', text)

    def test_split_parts_reference_no_duplicate_chapters(self):
        """R5: calibre splits collapse; one chapter per part, no duplicates."""
        with create_epub_split_parts_reference() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            chapters = self.book_file.chapters

            self.assertEqual(self._titles(chapters), ['Vireo', 'Heron', 'Plover'])
            # Each split tail folds into its own part, not a duplicate chapter.
            self.assertIn('Vireo split tail', chapters[0].content_as_text)
            self.assertIn('Heron split tail', chapters[1].content_as_text)
            self.assertIn('Plover split tail', chapters[2].content_as_text)
