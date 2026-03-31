from django.test import TestCase
from django.db import DataError, IntegrityError
from unittest.mock import patch, MagicMock
from parameterized import parameterized
import io
import os
import gzip

from flibusta.dump_importer import (
    FlibustaImporter, parse_mysql_string, import_dump,
    MAPPING_LIB_GENRE_LIST, MAPPING_LIB_AVTOR_NAME
)
from flibusta.models import FlibustaGenre, FlibustaAuthor


class ParseMySQLStringTest(TestCase):
    @parameterized.expand([
        ("'test'", "test"),
        ("'te\\'st'", "te'st"),
        ("'te\\\"st'", 'te"st'),
        ("'te\\\\st'", "te\\st"),
        ("123", 123),
        ("12.34", 12.34),
        ("NULL", None),
        ("null", None),
        ("'NULL'", "NULL"),
        ("Normal string", "Normal string"),
    ])
    def test_parse_mysql_string(self, input_str, expected):
        self.assertEqual(parse_mysql_string(input_str), expected)


class ParseLineTest(TestCase):
    def setUp(self):
        self.importer = FlibustaImporter()

    @parameterized.expand([
        (
            "INSERT INTO `libgenrelist` VALUES (1,'sf_history','Alt History','Sci-Fi'),(2,'sf_action','Action','Sci-Fi');",
            [[1, 'sf_history', 'Alt History', 'Sci-Fi'], [2, 'sf_action', 'Action', 'Sci-Fi']]
        ),
        (
            "INSERT INTO `table` VALUES (1,'It\\'s a test','O\\'Reilly');",
            [[1, "It's a test", "O'Reilly"]]
        ),
        (
            "INSERT INTO `table` VALUES (1,'String, with comma','Another');",
            [[1, "String, with comma", "Another"]]
        ),
        (
            "INSERT INTO `table` VALUES (1,'String with (parentheses)','test');",
            [[1, "String with (parentheses)", "test"]]
        ),
        (
            "INSERT INTO `table` VALUES (1,'Nested (parentheses (like this))','test');",
            [[1, "Nested (parentheses (like this))", "test"]]
        ),
        (
            "NOT AN INSERT LINE",
            []
        ),
    ])
    def test_parse_line(self, line, expected_rows):
        rows = list(self.importer._parse_line(line))
        self.assertEqual(rows, expected_rows)


class BulkSaveTest(TestCase):
    def setUp(self):
        self.importer = FlibustaImporter(batch_size=10)

    def test_bulk_save_success(self):
        genres = [
            FlibustaGenre(genre_code=f'code{i}', genre_desc=f'desc{i}')
            for i in range(5)
        ]
        self.importer._bulk_save(FlibustaGenre, genres)
        self.assertEqual(FlibustaGenre.objects.count(), 5)

    def test_bulk_save_ignore_conflicts(self):
        FlibustaGenre.objects.create(genre_code='duplicate', genre_desc='original')
        genres = [
            FlibustaGenre(genre_code='duplicate', genre_desc='new'),
            FlibustaGenre(genre_code='new_code', genre_desc='new_desc'),
        ]
        # Should not raise IntegrityError because of ignore_conflicts=True
        self.importer._bulk_save(FlibustaGenre, genres)
        self.assertEqual(FlibustaGenre.objects.count(), 2)
        self.assertEqual(FlibustaGenre.objects.get(genre_code='duplicate').genre_desc, 'original')

    @patch('flibusta.models.FlibustaGenre.objects.bulk_create')
    def test_bulk_save_fallback_on_data_error(self, mock_bulk_create):
        # Simulate DataError (e.g. string too long)
        mock_bulk_create.side_effect = DataError("value too long")
        
        # One valid, one invalid (but we'll mock the save to fail for the invalid one)
        valid_genre = FlibustaGenre(genre_code='valid', genre_desc='valid')
        invalid_genre = FlibustaGenre(genre_code='invalid', genre_desc='x' * 200) # too long for max_length=99
        
        batch = [valid_genre, invalid_genre]
        
        with self.assertLogs('flibusta.dump_importer', level='WARNING') as cm:
            self.importer._bulk_save(FlibustaGenre, batch)
        
        self.assertTrue(any("Bulk create failed" in output for output in cm.output))
        self.assertEqual(FlibustaGenre.objects.count(), 1)
        self.assertTrue(FlibustaGenre.objects.filter(genre_code='valid').exists())


class GetStreamTest(TestCase):
    def setUp(self):
        self.importer = FlibustaImporter()

    @patch('gzip.open')
    def test_get_stream_local(self, mock_gzip_open):
        self.importer._get_stream('test.gz', path='local/dir')
        mock_gzip_open.assert_called_once_with(os.path.join('local/dir', 'test.gz'), mode='rt', encoding='utf-8')

    @patch('requests.get')
    @patch('gzip.open')
    def test_get_stream_remote(self, mock_gzip_open, mock_requests_get):
        mock_response = MagicMock()
        mock_requests_get.return_value = mock_response
        self.importer._get_stream('test.gz')
        mock_requests_get.assert_called_once()
        mock_gzip_open.assert_called_once_with(mock_response.raw, mode='rt', encoding='utf-8')


class ImportTableTest(TestCase):
    def setUp(self):
        self.importer = FlibustaImporter(batch_size=2)

    @patch('flibusta.dump_importer.FlibustaImporter._get_stream')
    def test_import_table_basic(self, mock_get_stream):
        content = (
            "INSERT INTO `libgenrelist` VALUES (1,'code1','Desc1','Meta1');\n"
            "INSERT INTO `libgenrelist` VALUES (2,'code2','Desc2','Meta2'),(3,'code3','Desc3','Meta3');\n"
        )
        mock_file = io.StringIO(content)
        mock_get_stream.return_value.__enter__.return_value = mock_file
        
        self.importer.import_table(FlibustaGenre, MAPPING_LIB_GENRE_LIST, 'dummy.gz')
        
        self.assertEqual(FlibustaGenre.objects.count(), 3)
        self.assertTrue(FlibustaGenre.objects.filter(genre_code='code3').exists())

    @patch('flibusta.dump_importer.FlibustaImporter._get_stream')
    def test_import_table_row_length_mismatch(self, mock_get_stream):
        # Row has 3 values, mapping expects 4
        content = "INSERT INTO `libgenrelist` VALUES (1,'code1','Desc1');\n"
        mock_file = io.StringIO(content)
        mock_get_stream.return_value.__enter__.return_value = mock_file
        
        with self.assertLogs('flibusta.dump_importer', level='WARNING') as cm:
            self.importer.import_table(FlibustaGenre, MAPPING_LIB_GENRE_LIST, 'dummy.gz')
            
        self.assertTrue(any("Row length mismatch" in output for output in cm.output))
        self.assertEqual(FlibustaGenre.objects.count(), 0)


class ImportDumpHelperTest(TestCase):
    @patch('flibusta.dump_importer.FlibustaImporter.import_table')
    def test_import_dump_calls_importer(self, mock_import_table):
        import_dump(table_filter='libgenrelist')
        
        mock_import_table.assert_called_once()
        args, kwargs = mock_import_table.call_args
        self.assertEqual(args[0], FlibustaGenre)
        self.assertEqual(args[1], MAPPING_LIB_GENRE_LIST)

    @patch('flibusta.dump_importer.FlibustaImporter.import_table')
    def test_import_dump_all_tables(self, mock_import_table):
        import_dump()
        # There are 8 tasks defined in import_dump
        self.assertEqual(mock_import_table.call_count, 8)
