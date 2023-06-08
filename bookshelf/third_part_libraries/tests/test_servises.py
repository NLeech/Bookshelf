import io
from unittest.mock import patch

from django.test import TestCase

from third_part_libraries.models import FlibustaAuthor
from third_part_libraries.sevices import FlibustaInterface


def mock__get_authors_dump(*args, **kwargs) -> io.StringIO:
    dump = """-- MySQL dump 10.14  Distrib 5.5.68-MariaDB, for Linux (x86_64)

DROP TABLE IF EXISTS `libavtorname`;

LOCK TABLES `libavtorname` WRITE;
/*!40000 ALTER TABLE `libavtorname` DISABLE KEYS */;
INSERT INTO `libavtorname` VALUES (1,'','','Existing author','',0,'','','',0),(2,'','','New pseudonym','',0,'','','',1),(3,'','','New flibusta author','',0,'','','',0);
"""
    return io.StringIO(dump)


class TestAuthorsUpdating(TestCase):
    @classmethod
    def setUpTestData(cls):
        FlibustaAuthor.objects.create(last_name='Existing author')

    @patch(
        'third_part_libraries.sevices.FlibustaInterface._get_authors_dump',
        mock__get_authors_dump
    )
    def test_author_updating(self):
        interface = FlibustaInterface()
        interface.update_authors()

        self.assertEquals(FlibustaAuthor.objects.count(), 3)



