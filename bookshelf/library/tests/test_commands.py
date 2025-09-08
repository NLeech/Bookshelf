from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase


class UpdateAuthorsFromFlibustaCommandTest(TestCase):
    @patch("library.sevices.update_authors_from_flibusta")
    def test_handle(self, mock_update_authors_from_flibusta):
        """
        Tests that the command calls the service function.
        """
        call_command("update_authors_from_flibusta")
        mock_update_authors_from_flibusta.assert_called_once()

