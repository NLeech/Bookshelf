import gzip
import io
import logging
import os
from typing import Generator, List, Any, Type, Optional

import requests
from django.db import models, transaction, DataError, IntegrityError
from django.conf import settings

from .services import get_flibusta_session
from .models import (
    FlibustaAuthor, FlibustaGenre, FlibustaSequence,
    FlibustaBook, FlibustaBookAuthor, FlibustaBookGenre,
    FlibustaBookSequence, FlibustaJoinedBook
)

logger = logging.getLogger(__name__)

FLIBUSTA_BASE_URL = f'{getattr(settings, 'FLIBUSTA_BASE_URL', 'https://flibusta.is')}/sql/'

# Field mappings
MAPPING_LIB_GENRE_LIST = ['id', 'genre_code', 'genre_desc', 'genre_meta']
MAPPING_LIB_SEQ_NAME = ['id', 'name']
MAPPING_LIB_AVTOR_NAME = [
    'id', 'first_name', 'middle_name', 'last_name', 'nickname',
    'uid', 'email', 'homepage', 'gender', 'master_id'
]
MAPPING_LIB_BOOK = [
    'id', 'file_size', 'time', 'title', 'title1', 'lang', 'lang_ex',
    'src_lang', 'file_type', 'encoding', 'year', 'deleted', 'ver',
    'file_author', 'n', 'keywords', 'md5', 'modified', 'pmd5',
    'info_code', 'pages', 'chars'
]
# libavtor: BookId, AvtorId, Pos
MAPPING_LIB_AVTOR = ['book_id', 'author_id', 'pos']

# libgenre: Id, BookId, GenreId
MAPPING_LIB_GENRE = ['id', 'book_id', 'genre_id']

# libseq: BookId, SeqId, SeqNumb, Level, Type
MAPPING_LIB_SEQ = ['book_id', 'sequence_id', 'seq_numb', 'level', 'type']

# libjoinedbooks: Id, Time, BadId, GoodId, realId
MAPPING_LIB_JOINED_BOOKS = ['id', 'time', 'bad_id', 'good_id', 'real_id']


def import_dump(path: str = '', table_filter: str = '', batch_size: int = 5000) -> None:
    """
    Get and import Flibusta SQL dumps into Django models.
    :param path: Load dump files from local directory instead of downloading them.
                Directory should contain .gz files with original names (e.g. 'lib.libbook.sql.gz').
    :param table_filter: Table name to import (e.g. 'libbook'). If not provided, all tables will be imported.
    :param batch_size: B
    """
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

        logger.info(f"Starting import for {table_name} ({filename})...")
        try:
            importer.import_table(model, mapping, filename, path=path)
            logger.info(f"Successfully imported {table_name}")
        except Exception as e:
            logger.error(f"Failed to import {table_name}: {e}")
            #
            raise


def parse_mysql_string(s: str) -> Optional[Any]:
    """Unescape MySQL string and remove quotes."""
    if s.lower() == 'null':
        return None
    if s.startswith("'") and s.endswith("'"):
        s = s[1:-1]
        # Handle MySQL escapes: \\ -> \, \' -> ', etc.
        # This is a basic unescape.
        return s.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s

class FlibustaImporter:
    """
    Class responsible for importing Flibusta SQL dumps into Django models.
    """

    def __init__(self, batch_size: int = 5000):
        self.batch_size = batch_size

    def _get_stream(self, filename: str, path: str = '') -> io.TextIOWrapper:
        """
        Load the .gz file either from a local path or by downloading it.
        :param filename: Name of the .gz file (e.g. 'lib.libbook.sql.gz')
        :param path: Optional local directory path where the .gz file is located. If not provided, it will be downloaded.
        :return: A file-like object that can be read line by line.
        """

        if path:
            file_path = os.path.join(path, filename)
            logger.info(f"Opening local file {file_path}...")
            return gzip.open(file_path, mode='rt', encoding='utf-8')
        else:
            # Flibusta server can be unstable, especially for large dumps, so we need to implement retries with backoff.
            # It is why we use stream=False and read the whole content into memory.
            session = get_flibusta_session()

            url = f"{FLIBUSTA_BASE_URL}{filename}"
            logger.info(f"Downloading {url}...")
            response = session.get(url, stream=False, timeout=(10, 120))  # 10s to connect, 120s to load
            response.raise_for_status()
            # GzipFile can read from a file-like object
            return gzip.open(io.BytesIO(response.content), mode='rt', encoding='utf-8')

    def _parse_line(self, line: str) -> Generator[List[Any], None, None]:
        """
        Parse a single line of SQL dump that contains an INSERT INTO statement and yield the values as lists.
        :param line: Single line from the SQL dump file.
        :return: Generator yielding lists of values for each tuple in the INSERT statement.
        """

        if not line.startswith("INSERT INTO"):
            return
        
        # Extract the values part. 
        try:
            values_part = line.split("VALUES", 1)[1].strip()
            if values_part.endswith(';'):
                values_part = values_part[:-1]
        except IndexError:
            return

        # Simple state machine to parse the values
        current_token = []
        in_quote = False
        escape = False
        depth = 0
        
        for char in values_part:
            if escape:
                current_token.append(char)
                escape = False
                continue
            
            if char == '\\':
                current_token.append(char)
                escape = True
                continue
            
            if char == "'" and not escape:
                in_quote = not in_quote
                current_token.append(char)
                continue
                
            if char == '(' and not in_quote:
                depth += 1
                if depth == 1:
                    current_token = [] # Start of tuple
                    continue
            
            if char == ')' and not in_quote:
                depth -= 1
                if depth == 0:
                    # End of tuple
                    raw_tuple = "".join(current_token)
                    yield self._parse_tuple(raw_tuple)
                    continue
            
            if depth > 0:
                current_token.append(char)

    def _parse_tuple(self, raw_tuple: str) -> List[Any]:
        """
        Parse a raw tuple string (e.g. "123, 'String', 'String, with comma', NULL") into a list of values.
        :param raw_tuple: String representing the raw tuple from the SQL dump.
        :return: List of parsed values, with proper unescaping and type conversion.
        """

        values = []
        current_val = []
        in_quote = False
        escape = False
        
        for char in raw_tuple:
            if escape:
                current_val.append(char)
                escape = False
                continue
            if char == '\\':
                current_val.append(char)
                escape = True
                continue
            if char == "'" and not escape:
                in_quote = not in_quote
                current_val.append(char)
                continue
            
            if char == ',' and not in_quote:
                values.append(parse_mysql_string("".join(current_val).strip()))
                current_val = []
                continue
            
            current_val.append(char)
        
        # Last value
        if current_val:
            values.append(parse_mysql_string("".join(current_val).strip()))
            
        return values

    def import_table(self, model: Type[models.Model], field_mapping: List[str], 
                     filename: str, path: str = '') -> None:
        """
        Import data for a specific model from the given SQL dump file using the provided field mapping.
        :param model: Model class to import data into.
        :param field_mapping: List of field names corresponding to the order of values in the SQL dump tuples.
        :param filename: Gzipped SQL dump filename (e.g. 'lib.libbook.sql.gz').
        :param path: Optional local directory path where the .gz file is located.
                    If not provided, it will be downloaded from FLIBUSTA_BASE_URL.
        """

        count = 0
        batch = []
        
        try:
            stream = self._get_stream(filename=filename, path=path)
            with stream as f:
                for line in f:
                    for row in self._parse_line(line):
                        if len(row) != len(field_mapping):
                            # Skip mismatching rows (e.g. if schema changed slightly)
                            logger.warning(f"Row length mismatch: expected {len(field_mapping)}, got {len(row)}. Row: {row}")
                            continue
                        
                        kwargs = {field: val for field, val in zip(field_mapping, row)}
                        
                        batch.append(model(**kwargs))
                        
                        if len(batch) >= self.batch_size:
                            self._bulk_save(model, batch)
                            count += len(batch)
                            batch = []
                            logger.info(f"Processed {count} records for {model.__name__}...")
                
                if batch:

                    self._bulk_save(model, batch)
                    count += len(batch)
                    
            logger.info(f"Finished importing {model.__name__}. Total records: {count}")
            
        except Exception as e:
            logger.error(f"Error importing {filename}: {e}")
            raise

    def _bulk_save(self, model: Type[models.Model], batch: List[models.Model]) -> None:
        """
        Save a batch of model instances to the database using bulk_create,
        Any conflicts (e.g. due to unique constraints) will be ignored,
        other errors (e.g. data error, FK violations, etc.) will be logged and skipped.
        :param model: model class to save data into.
        :param batch: list of model instances to save.
        """

        try:
            model.objects.bulk_create(batch, ignore_conflicts=True, batch_size=self.batch_size)
        except (DataError, IntegrityError) as e:
            # The batch can contain some records that violate database constraints
            # (not ignored due to ignore_conflicts=False - e.g. field too long, foreign key violations, etc.).
            # load the batch individually to find the bad records and skip them
            logger.warning(f"Bulk create failed for {model.__name__}, attempting individual saves to skip the error...")

            for obj in batch:
                try:
                    with transaction.atomic():
                        obj.save()

                except (IntegrityError, DataError, model.DoesNotExist) as e:
                    err_str = str(e).lower()
                    if isinstance(e, IntegrityError) and ('unique' in err_str or 'duplicate' in err_str):
                        pass  # jast conflict, silently skip (gnore_conflicts=True emulation), ugly but works
                    else:
                        # FK violation or other issues - log it and skip
                        fields_data = {f.attname: getattr(obj, f.attname) for f in obj._meta.fields if
                                       not f.is_relation or f.many_to_one}
                        logger.warning(f"Failed to save {model.__name__} instance. Error: {e}. Data: {fields_data}")
