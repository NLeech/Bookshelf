from django.test import TestCase
from unittest.mock import patch, MagicMock
from flibusta.importer import FlibustaImporter, parse_mysql_string, MAPPING_LIB_GENRE_LIST
from flibusta.models import FlibustaGenre
import io

class FlibustaImporterTest(TestCase):

    def test_parse_mysql_string(self):
        self.assertEqual(parse_mysql_string("'test'"), "test")
        self.assertEqual(parse_mysql_string("'te\\'st'"), "te'st")
        self.assertEqual(parse_mysql_string("123"), 123)
        self.assertEqual(parse_mysql_string("'NULL'"), "NULL") # Should remain string 'NULL' if quoted? No, MySQL dump quotes strings. NULL is keyword.
        self.assertIsNone(parse_mysql_string("NULL"))
        self.assertEqual(parse_mysql_string("12.34"), 12.34)

    def test_parse_line(self):
        importer = FlibustaImporter()
        line = "INSERT INTO `libgenrelist` VALUES (1,'sf_history','Alt History','Sci-Fi'),(2,'sf_action','Action','Sci-Fi');"
        rows = list(importer._parse_line(line))
        
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], [1, 'sf_history', 'Alt History', 'Sci-Fi'])
        self.assertEqual(rows[1], [2, 'sf_action', 'Action', 'Sci-Fi'])

    def test_parse_line_with_escaped_quotes(self):
        importer = FlibustaImporter()
        line = "INSERT INTO `table` VALUES (1,'It\\'s a test','O\\'Reilly');"
        rows = list(importer._parse_line(line))
        
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], [1, "It's a test", "O'Reilly"])

    def test_parse_line_with_comma_in_string(self):
        importer = FlibustaImporter()
        line = "INSERT INTO `table` VALUES (1,'String, with comma','Another');"
        rows = list(importer._parse_line(line))
        
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], [1, "String, with comma", "Another"])

    @patch('flibusta.importer.FlibustaImporter._get_stream')
    def test_import_table(self, mock_get_stream):
        # Mock file content
        content = "INSERT INTO `libgenrelist` VALUES (1,'code1','Desc1','Meta1');\n"
        mock_file = io.StringIO(content)
        # _get_stream returns a context manager (gzip.open), so we mock __enter__
        mock_get_stream.return_value.__enter__.return_value = mock_file
        mock_get_stream.return_value.__exit__.return_value = None

        importer = FlibustaImporter(batch_size=10)
        importer.import_table(FlibustaGenre, MAPPING_LIB_GENRE_LIST, 'dummy.gz', path='/tmp')
        
        self.assertEqual(FlibustaGenre.objects.count(), 1)
        genre = FlibustaGenre.objects.first()
        self.assertEqual(genre.genre_code, 'code1')
        self.assertEqual(genre.genre_desc, 'Desc1')
        self.assertEqual(genre.genre_meta, 'Meta1')

