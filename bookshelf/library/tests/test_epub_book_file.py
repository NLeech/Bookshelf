import unittest
import os
from parameterized import parameterized

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
    write_stream_to_file,
)


class TestEpubBookFileLoad(unittest.TestCase):
    def setUp(self):
        self.book_file = EpubBookFile()

    @parameterized.expand([
        ("one_author", create_epub_one_author, "Sample EPUB (One Author)", ["Author One"]),
        ("two_authors", create_epub_two_authors, "Sample EPUB (Two Authors)", ["Author One", "Author Two"]),
        ("cyrillic", create_epub_cyrillic, "Приклад EPUB (Кирилиця)", ["Автор Один"]),
    ])
    def test_load_from_stream(self, name, create_epub_func, expected_title, expected_authors):
        """
        Tests loading an EPUB from an in-memory stream and verifies title and authors.
        """
        with create_epub_func() as epub_stream:
            self.book_file.load_from_stream(epub_stream)
            self.assertEqual(self.book_file.title, expected_title)
            self.assertEqual(self.book_file.authors, expected_authors)

    @parameterized.expand([
        ("one_author", create_epub_one_author, "Sample EPUB (One Author)", ["Author One"]),
        ("two_authors", create_epub_two_authors, "Sample EPUB (Two Authors)", ["Author One", "Author Two"]),
    ])
    def test_load_from_file(self, name, create_epub_func, expected_title, expected_authors):
        """
        Tests loading an EPUB from a temporary file and verifies title and authors.
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
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

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
            chapters = self.book_file.chapters
            # Expecting 3 top-level chapters
            self.assertEqual(len(chapters), 3)

            # Check Chapter 1 and its subchapters
            self.assertEqual(chapters[0].title, "Chapter 1")
            self.assertEqual(len(chapters[0].subchapters), 2)
            self.assertEqual(chapters[0].subchapters[0].title, "Subchapter 1.1")
            self.assertEqual(chapters[0].subchapters[0].level, 1)
            self.assertEqual(chapters[0].subchapters[0].parent, chapters[0])
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
            chapters = self.book_file.chapters
            self.assertEqual(len(chapters), 3)
            self.assertEqual(chapters[0].title, "No TOC Chapter 1")
            self.assertIn("content of the first chapter without TOC", chapters[0].content_as_text)
            self.assertEqual(chapters[1].title, "No TOC Chapter 2")
            self.assertIn("content of the second chapter without TOC", chapters[1].content_as_text)
            self.assertEqual(chapters[2].title, "No TOC Chapter 3")
            self.assertIn("content of the third chapter without TOC", chapters[2].content_as_text)
            self.assertEqual(len(chapters[0].subchapters), 0) # Should be flat

