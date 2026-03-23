import logging

from django.core.management.base import BaseCommand

from flibusta.book_importer import  process_local_path, process_daily_updates


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
            help='List of file formats (e.g., fb2 epub) to filter.',
            required=False
        )

    def handle(self, *args, **options):
        path = options.get('path')
        genres = options.get('genres')
        langs = options.get('langs')
        formats = options.get('formats')
        
        from flibusta.book_importer import get_filters

        filters = get_filters(
            genres_filters=genres,
            languages_filters=langs,
            formats_filters=formats
        )

        if path:
            process_local_path(path, filters=filters)
        else:
            process_daily_updates(filters=filters)
