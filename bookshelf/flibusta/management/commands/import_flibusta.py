from django.core.management.base import BaseCommand

from flibusta.importer import import_dump


class Command(BaseCommand):
    help = 'Import Flibusta SQL dumps'

    def add_arguments(self, parser):
        parser.add_argument('--path', type=str, default='', help='Path to directory containing .gz files')
        parser.add_argument('--batch-size', type=int, default=5000, help='Batch size for bulk operations')
        parser.add_argument('--table', type=str, default='', help='Import only specific table (e.g. libbook)')

    def handle(self, *args, **options):
        path = options['path']
        batch_size = options['batch_size']
        table_filter = options['table']

        import_dump(path=path, table_filter=table_filter, batch_size=batch_size)
