import unittest
import os
import io
from parameterized import parameterized
from PIL import Image
from library.book_utils import Fb2BookFile
from library.tests.fb2_test_utils import (
    create_fb2_one_author,
    create_fb2_two_authors,
    create_fb2_nested_chapters,
    create_fb2_cyrillic,
    create_simple_fb2,
    write_stream_to_file,
)

class TestFb2BookFileLoad(unittest.TestCase):
    def setUp(self):
        self.book_file = Fb2BookFile()

    @parameterized.expand([
        ("one_author", create_fb2_one_author, "Sample FB2 (One Author)", ["Author One"], "A sample description."),
        ("two_authors", create_fb2_two_authors, "Sample FB2 (Two Authors)", ["Author One", "Author Two"], "Another sample description with two authors."),
        ("cyrillic", create_fb2_cyrillic, "Приклад FB2 (Кирилиця)", ["Автор Один"], "Опис кирилицею."),
    ])
    def test_load_from_stream(self, name, create_fb2_func, expected_title, expected_authors, expected_description):
        """
        Tests loading an FB2 from an in-memory stream and verifies title, authors and description.
        """
        with create_fb2_func() as fb2_stream:
            self.book_file.load_from_stream(fb2_stream)
            self.assertEqual(self.book_file.title, expected_title)
            self.assertEqual(self.book_file.authors, expected_authors)
            self.assertEqual(self.book_file.description, expected_description)
            self.assertEqual(self.book_file.file_type, 'fb2')

    @parameterized.expand([
        ("one_author", create_fb2_one_author, "Sample FB2 (One Author)", ["Author One"], "A sample description."),
        ("two_authors", create_fb2_two_authors, "Sample FB2 (Two Authors)", ["Author One", "Author Two"], "Another sample description with two authors."),
    ])
    def test_load_from_file(self, name, create_fb2_func, expected_title, expected_authors, expected_description):
        """
        Tests loading an FB2 from a temporary file and verifies title, authors and description.
        """
        temp_dir = "temp_test_books_fb2"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, f"{name}.fb2")

        try:
            with create_fb2_func() as fb2_stream:
                write_stream_to_file(fb2_stream, file_path)

            self.book_file.load_from_file(file_path)
            self.assertEqual(self.book_file.title, expected_title)
            self.assertEqual(self.book_file.authors, expected_authors)
            self.assertEqual(self.book_file.description, expected_description)
            self.assertEqual(self.book_file.file_type, 'fb2')
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

    def test_extract_cover(self):
        """
        Tests extraction of a cover image from an FB2.
        """
        # Create a small red square image
        img = Image.new('RGB', (100, 100), color='red')
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        cover_data = img_byte_arr.getvalue()
        
        with create_simple_fb2(cover_data=cover_data) as fb2_stream:
            self.book_file.load_from_stream(fb2_stream)
            self.assertIsNotNone(self.book_file.cover)
            self.assertIsInstance(self.book_file.cover, Image.Image)
            self.assertEqual(self.book_file.cover.size, (100, 100))

    def test_extract_isbn(self):
        """
        Tests extraction of ISBN from FB2.
        """
        isbn_val = "5-04-002199-0"
        with create_simple_fb2(isbn=isbn_val) as fb2_stream:
            self.book_file.load_from_stream(fb2_stream)
            self.assertEqual(self.book_file.isbn, isbn_val)


class TestFb2ChapterExtraction(unittest.TestCase):
    def setUp(self):
        self.book_file = Fb2BookFile()

    def test_get_simple_chapters(self):
        """
        Tests extraction of a simple, flat list of chapters.
        """
        with create_fb2_one_author() as fb2_stream:
            self.book_file.load_from_stream(fb2_stream)
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
        with create_fb2_nested_chapters() as fb2_stream:
            self.book_file.load_from_stream(fb2_stream)
            self.assertEqual(self.book_file.description, "Description for nested chapters.")
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
        with create_fb2_cyrillic() as fb2_stream:
            self.book_file.load_from_stream(fb2_stream)
            self.assertEqual(self.book_file.description, "Опис кирилицею.")
            chapters = self.book_file.chapters
            self.assertEqual(len(chapters), 3)
            self.assertEqual(chapters[0].title, "Глава 1")
            self.assertIn("зміст першої глави", chapters[0].content_as_text)
            self.assertEqual(chapters[1].title, "Глава 2")
            self.assertEqual(chapters[2].title, "Глава 3")

    def test_no_body(self):
        """Tests FB2 without <body> tag."""
        fb2_xml = '<?xml version="1.0" encoding="UTF-8"?><FictionBook><description><title-info><book-title>No Body</book-title></title-info></description></FictionBook>'
        stream = io.BytesIO(fb2_xml.encode('utf-8'))
        self.book_file.load_from_stream(stream)
        self.assertEqual(self.book_file.chapters, [])

    def test_section_without_title(self):
        """Tests section without <title> tag."""
        fb2_xml = '<?xml version="1.0" encoding="UTF-8"?><FictionBook><body><section><p>Only content</p></section></body></FictionBook>'
        stream = io.BytesIO(fb2_xml.encode('utf-8'))
        self.book_file.load_from_stream(stream)
        self.assertEqual(len(self.book_file.chapters), 1)
        self.assertEqual(self.book_file.chapters[0].title, "Section 0")

    def test_invalid_cover(self):
        """Tests cover extraction with missing binary."""
        fb2_xml = '<?xml version="1.0" encoding="UTF-8"?><FictionBook xmlns:l="http://www.w3.org/1999/xlink"><description><title-info><coverpage><image l:href="#missing"/></coverpage></title-info></description></FictionBook>'
        stream = io.BytesIO(fb2_xml.encode('utf-8'))
        self.book_file.load_from_stream(stream)
        self.assertIsNone(self.book_file.cover)

    def test_nickname_fallback(self):
        """Tests author name extraction when only nickname is present."""
        fb2_xml = '<?xml version="1.0" encoding="UTF-8"?><FictionBook><description><title-info><author><nickname>Ghost</nickname></author><book-title>Title</book-title></title-info></description></FictionBook>'
        stream = io.BytesIO(fb2_xml.encode('utf-8'))
        self.book_file.load_from_stream(stream)
        self.assertEqual(self.book_file.authors, ["Ghost"])
