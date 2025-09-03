from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase


class UpdateFlibustaAuthorsCommandTest(TestCase):
    @patch('third_party_libraries.management.commands.update_flibusta_authors.FlibustaInterface')
    def test_handle(self, mock_interface):
        """
        Test that the command calls FlibustaInterface.update_authors.
        """
        call_command('update_flibusta_authors')
        mock_interface.return_value.update_authors.assert_called_once()


class UpdateFlibustaGenreCommandTest(TestCase):
    @patch('third_party_libraries.management.commands.update_flibusta_genre.FlibustaInterface')
    def test_handle(self, mock_interface):
        """
        Test that the command calls FlibustaInterface.update_genre.
        """
        call_command('update_flibusta_genre')
        mock_interface.return_value.update_genre.assert_called_once()
