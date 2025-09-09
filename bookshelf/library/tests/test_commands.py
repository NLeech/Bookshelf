from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from parameterized import parameterized


class UpdateCommandsTest(TestCase):
    @parameterized.expand([
        ("update_authors_from_flibusta", "library.sevices.update_authors_from_flibusta"),
        ("update_genres_from_flibusta", "library.management.commands.update_genres_from_flibusta.update_genres_from_flibusta"),
    ])
    def test_update_command(self, command_name, patch_target):
        """
        Tests that the update commands call the correct service function.
        """
        with patch(patch_target) as mock_update_function:
            call_command(command_name)
            mock_update_function.assert_called_once()

