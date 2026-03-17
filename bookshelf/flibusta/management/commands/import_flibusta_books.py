import logging

from django.core.management.base import BaseCommand

from flibusta.book_importer import  process_local_path


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

        if path:
            process_local_path(
                path,
                genres_filter=genres,
                langs_filter=langs,
                formats_filter=formats
            )
        else:
            self.process_daily_updates()

    def process_daily_updates(self):
        self.stdout.write("Processing daily updates from Flibusta (Not fully implemented, placeholder).")
        # Logic to scrape/download from FLIBUSTA_BASE_URL/daily would go here.
        # Requires web scraping to find links.
        pass

