import io
from unittest.mock import patch

from django.test import TestCase

from third_part_libraries.models import FlibustaAuthor, FlibustaGenre
from third_part_libraries.sevices import FlibustaInterface


def mock__get_authors_dump(*args, **kwargs) -> io.StringIO:
    dump = """-- MySQL dump 10.14  Distrib 5.5.68-MariaDB, for Linux (x86_64)

DROP TABLE IF EXISTS `libavtorname`;

LOCK TABLES `libavtorname` WRITE;
/*!40000 ALTER TABLE `libavtorname` DISABLE KEYS */;
INSERT INTO `libavtorname` VALUES (1,'','','Existing author','',0,'','','',0),(2,'','','New pseudonym','',0,'','','',1),(3,'','','New flibusta author','',0,'','','',0);
"""
    return io.StringIO(dump)


def mock__get_genre_dump(*args, **kwargs) -> io.StringIO:
    dump = """/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `libgenrelist`
--

LOCK TABLES `libgenrelist` WRITE;
/*!40000 ALTER TABLE `libgenrelist` DISABLE KEYS */;
INSERT INTO `libgenrelist` VALUES (1,'ex_genre','Ex. genre','Genre'),(2,'genre1','Genre1','Genre'),(3,'genre2','Genre2','Genre');
/*!40000 ALTER TABLE `libgenrelist` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;
"""
    return io.StringIO(dump)


class TestAuthorsUpdating(TestCase):
    @classmethod
    def setUpTestData(cls):
        FlibustaAuthor.objects.create(id=1, last_name='Existing author')

    @patch(
        'third_part_libraries.sevices.FlibustaInterface._get_authors_dump',
        mock__get_authors_dump
    )
    def test_author_updating(self):
        interface = FlibustaInterface()
        interface.update_authors()

        self.assertEquals(FlibustaAuthor.objects.count(), 3)


class TestGenreUpdating(TestCase):
    @classmethod
    def setUpTestData(cls):
        FlibustaGenre.objects.create(genre_code='ex_genre')

    @patch(
        'third_part_libraries.sevices.FlibustaInterface._get_genre_dump',
        mock__get_genre_dump
    )
    def test_genre_updating(self):
        interface = FlibustaInterface()
        interface.update_genre()

        self.assertEquals(FlibustaGenre.objects.count(), 3)



