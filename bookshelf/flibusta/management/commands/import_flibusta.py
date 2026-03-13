from django.core.management.base import BaseCommand

from flibusta.importer import (
    FlibustaImporter,
    MAPPING_LIB_GENRE_LIST, MAPPING_LIB_SEQ_NAME, MAPPING_LIB_AVTOR_NAME,
    MAPPING_LIB_BOOK, MAPPING_LIB_AVTOR, MAPPING_LIB_GENRE,
    MAPPING_LIB_SEQ, MAPPING_LIB_JOINED_BOOKS
)

from flibusta.models import (
    FlibustaAuthor, FlibustaGenre, FlibustaSequence,
    FlibustaBook, FlibustaBookAuthor, FlibustaBookGenre,
    FlibustaBookSequence, FlibustaJoinedBook
)


class Command(BaseCommand):
    help = 'Import Flibusta SQL dumps'

    def add_arguments(self, parser):
        parser.add_argument('--path', type=str, help='Path to directory containing .gz files')
        parser.add_argument('--batch-size', type=int, default=5000, help='Batch size for bulk operations')
        parser.add_argument('--table', type=str, help='Import only specific table (e.g. libbook)')

    def handle(self, *args, **options):
        path = options['path']
        batch_size = options['batch_size']
        table_filter = options['table']

        importer = FlibustaImporter(batch_size=batch_size)

        # Define the import sequence
        # (Model, Mapping, Filename, TableName)
        tasks = [
            (FlibustaGenre, MAPPING_LIB_GENRE_LIST, 'lib.libgenrelist.sql.gz', 'libgenrelist'),
            (FlibustaSequence, MAPPING_LIB_SEQ_NAME, 'lib.libseqname.sql.gz', 'libseqname'),
            (FlibustaAuthor, MAPPING_LIB_AVTOR_NAME, 'lib.libavtorname.sql.gz', 'libavtorname'),
            (FlibustaBook, MAPPING_LIB_BOOK, 'lib.libbook.sql.gz', 'libbook'),
            (FlibustaBookAuthor, MAPPING_LIB_AVTOR, 'lib.libavtor.sql.gz', 'libavtor'),
            (FlibustaBookGenre, MAPPING_LIB_GENRE, 'lib.libgenre.sql.gz', 'libgenre'),
            (FlibustaBookSequence, MAPPING_LIB_SEQ, 'lib.libseq.sql.gz', 'libseq'),
            (FlibustaJoinedBook, MAPPING_LIB_JOINED_BOOKS, 'lib.libjoinedbooks.sql.gz', 'libjoinedbooks'),
        ]

        for model, mapping, filename, table_name in tasks:
            if table_filter and table_filter != table_name:
                continue
            
            self.stdout.write(f"Starting import for {table_name} ({filename})...")
            try:
                importer.import_table(model, mapping, filename, path=path)
                self.stdout.write(self.style.SUCCESS(f"Successfully imported {table_name}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to import {table_name}: {e}"))
