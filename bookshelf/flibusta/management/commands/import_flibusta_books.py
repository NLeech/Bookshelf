import os
import logging
from typing import List

from django.core.management.base import BaseCommand
from django.conf import settings

from flibusta.book_importer import BookImporter
from flibusta.models import FlibustaBook

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import books from Flibusta archives.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            type=str,
            help='Path to directory containing book archives (ZIP files).',
            required=False
        )
        parser.add_argument(
            '--genres',
            nargs='+',
            help='List of genre codes or meta genres to filter.',
            required=False
        )
        parser.add_argument(
            '--langs',
            nargs='+',
            help='List of languages (ISO 639-1) to filter.',
            required=False
        )
        parser.add_argument(
            '--formats',
            nargs='+',
            help='List of file formats (e.g., fb2, epub) to filter.',
            required=False
        )

    def handle(self, *args, **options):
        path = options.get('path')
        genres = options.get('genres')
        langs = options.get('langs')
        formats = options.get('formats')

        importer = BookImporter(
            genres_filter=genres,
            langs_filter=langs,
            formats_filter=formats
        )

        if path:
            self.process_local_path(path, importer)
        else:
            self.process_daily_updates(importer)

    def process_local_path(self, path: str, importer: BookImporter):
        if not os.path.exists(path):
            self.stderr.write(f"Path '{path}' does not exist.")
            return

        if os.path.isfile(path):
            files = [path]
        else:
            files = [
                os.path.join(path, f) 
                for f in os.listdir(path) 
                if f.endswith('.zip')
            ]

        for zip_path in files:
            self.stdout.write(f"Processing archive: {zip_path}")
            try:
                self.process_archive(zip_path, importer)
            except Exception as e:
                logger.error(f"Failed to process archive {zip_path}: {e}")

    def process_daily_updates(self, importer: BookImporter):
        self.stdout.write("Processing daily updates from Flibusta (Not fully implemented, placeholder).")
        # Logic to scrape/download from FLIBUSTA_BASE_URL/daily would go here.
        # Requires web scraping to find links.
        pass

