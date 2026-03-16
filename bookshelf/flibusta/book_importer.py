import logging
import os
import io
import tempfile
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import zipfile
import pyzipper
from django.conf import settings
from django.db.models.query import QuerySet
from django.db.models import Q
from django.core.files import File
from django.db import transaction
from django.utils.text import slugify

# Try to import Kreuzberg, handle if missing (though it should be installed)
try:
    from kreuzberg import extract_metadata
except ImportError:
    extract_metadata = None

from library.models import Author, Genre, BookSeries, Book, Language, BookSeriesLink
from .models import (
    FlibustaBook, FlibustaAuthor, FlibustaGenre, FlibustaSequence,
    FlibustaAuthorMapping, FlibustaGenreMapping, FlibustaSequenceMapping, FlibustaBookMapping
)

logger = logging.getLogger(__name__)


class BookFilter(ABC):
    @ abstractmethod
    def apply(self, books: QuerySet) -> QuerySet:
        pass


class LanguageFilter(BookFilter):
    def __init__(self, languages: List[str]):
        self.languages = languages

    def apply(self, books: QuerySet) -> QuerySet:
        if not self.languages:
            return books
        return books.filter(lang__in=self.languages)


class FormatFilter(BookFilter):
    def __init__(self, formats: List[str]):
        self.formats = formats

    def apply(self, books: QuerySet) -> QuerySet:
        if not self.formats:
            return books
        return books.filter(file_type__in=self.formats)


class GenreFilter(BookFilter):
    def __init__(self, genre: Optional[List[str]] = None):
        self.genre = genre or []

    def apply(self, books: QuerySet) -> QuerySet:
        if not self.genre:
            return books
        
        query = Q()
        if self.genre:
            query |= Q(genres__genre_code__in=self.genre)
            query |= Q(genres__genre_meta__in=self.genre)
            
        return books.filter(query).distinct()


class BookImporter:
    def __init__(self, genres_filter: Optional[List[str]] = None, langs_filter: Optional[List[str]] = None, formats_filter: Optional[List[str]] = None):
    #     self.genres_filter = genres_filter
    #     self.langs_filter = langs_filter
    #     self.formats_filter = formats_filter
        self.book_pwd = settings.BOOK_PWD
    #

    def get_language(self, lang_code: str) -> Language|None:
        try:
            return Language.objects.get(code=lang_code)
        except Language.DoesNotExist:
            logger.error(f"Language with code '{lang_code}' not found in Library.")
            return None

    def get_or_create_genre(self, f_genre: FlibustaGenre) -> Genre:
        # Check mapping first
        if hasattr(f_genre, 'mapping'):
            return f_genre.mapping.library_genre

        # Create Meta Genre if needed
        # Flibusta 'genre_meta' is the parent category name (e.g., 'SF', 'Thriller')
        # We assume 'genre_meta' is the code for the parent genre in Library?
        # Or should we slugify it?
        # The prompt says: "The library uses a two-level genre hierarchy (meta genre -> genre). If a meta genre does not exist, it must be created."
        
        meta_genre_name = f_genre.genre_meta if f_genre.genre_meta else 'Other'
        meta_genre_code = slugify(meta_genre_name)
        
        meta_genre, _ = Genre.objects.get_or_create(
            code=meta_genre_code,
            defaults={'name': meta_genre_name, 'parent': None}
        )

        # Create Genre
        genre_code = f_genre.genre_code
        genre_name = f_genre.genre_desc
        
        library_genre, created = Genre.objects.get_or_create(
            code=genre_code,
            defaults={
                'name': genre_name,
                'parent': meta_genre
            }
        )

        # Create Mapping
        FlibustaGenreMapping.objects.create(flibusta_genre=f_genre, library_genre=library_genre)
        
        return library_genre

    def get_or_create_author(self, f_author: FlibustaAuthor) -> Author:
        # Check mapping first
        if hasattr(f_author, 'mapping'):
            return f_author.mapping.library_author

        # Recursive resolution for master_id
        if f_author.master_id and f_author.master_id != f_author.id:
             # Try to find the master author in Flibusta
            try:
                master_f_author = FlibustaAuthor.objects.get(id=f_author.master_id)
                # Map the master author first
                library_author = self.get_or_create_author(master_f_author)
                
                # Create mapping for THIS alias author to the same library author
                FlibustaAuthorMapping.objects.create(flibusta_author=f_author, library_author=library_author)
                return library_author

            except FlibustaAuthor.DoesNotExist:
                # If master doesn't exist, treat current as independent (fallback)
                logger.warning(f"Master author {f_author.master_id} for {f_author.id} not found. Treating as independent.")
        
        # Create Author
        library_author = Author.objects.create(
            first_name=f_author.first_name,
            middle_name=f_author.middle_name,
            last_name=f_author.last_name,
            nickname=f_author.nickname,
            email=f_author.email,
            homepage=f_author.homepage,
            # We don't set main_author here for now, assuming Flattened or mapped via master_id logic above
        )
        
        FlibustaAuthorMapping.objects.create(flibusta_author=f_author, library_author=library_author)
        return library_author

    def get_or_create_series(self, f_seq: FlibustaSequence) -> BookSeries:
        if hasattr(f_seq, 'mapping'):
            return f_seq.mapping.library_series

        library_series, _ = BookSeries.objects.get_or_create(
            name=f_seq.name,
            defaults={'parent': None}
        )
        
        FlibustaSequenceMapping.objects.create(flibusta_sequence=f_seq, library_series=library_series)
        return library_series

    def import_book(self, f_book: FlibustaBook, file_content: bytes, filename: str) -> None:
        if f_book.is_imported:
            logger.info(f"Book {f_book.id} already imported.")
            return

        # Resolve Language
        language = self.get_language(f_book.lang)
        if not language:
            return

        try:
            with (transaction.atomic()):
                # Extract Metadata from file (using Kreuzberg)
                extracted_metadata = {}
                # TODO Implement metadata loading using kreuzberg
                # zip_buffer.seek(0) # if needed

                # Re-compress the file with password
                zip_buffer = tempfile.TemporaryFile()
                with pyzipper.AESZipFile(zip_buffer,
                                         'w',
                                         compression=pyzipper.ZIP_DEFLATED,
                                         encryption=pyzipper.WZ_AES) as zf:
                    zf.setpassword(self.book_pwd)
                    # File inside should have the name 'book_id.ext'
                    zf.writestr(f"{f_book.id}.{f_book.file_type}", file_content)
                
                description = getattr(extracted_metadata, 'description', '') or ''
                isbn = getattr(extracted_metadata, 'isbn', 0) or 0
                # Ensure ISBN is decimal/number
                if not isinstance(isbn, (int, float, str)):
                    isbn = 0
                if isinstance(isbn, str):
                     # clean string
                     isbn = ''.join(filter(str.isdigit, isbn)) or 0
                
                # Title from Flibusta
                title = f_book.title
                
                book = Book(
                    tittle=title, # Typo in model 'tittle'
                    description=description,
                    language=language,
                    isbn=isbn
                )
                
                # Save file
                file_name = f"{f_book.id}.zip"
                book.file.save(file_name, File(zip_buffer), save=False)
                
                # Save cover if available
                cover_data = getattr(extracted_metadata, 'cover_image_content', None) # Hypothetical
                # Note: Kreuzberg might return 'cover_image_path' or bytes.
                # If bytes:
                if cover_data:
                     # guess extension?
                     with tempfile.TemporaryFile() as tf:
                        tf.write(cover_data)
                        tf.seek(0)
                        book.cover.save(f"cover_{f_book.id}.jpg", File(tf), save=False)

                book.save()

                # Link Relations
                # Authors
                for f_author in f_book.authors.all():
                    l_author = self.get_or_create_author(f_author)
                    book.authors.add(l_author)

                # Genres
                for f_genre in f_book.genres.all():
                    l_genre = self.get_or_create_genre(f_genre)
                    book.genres.add(l_genre)
                
                # Series (with Sequence Number)
                for f_book_seq in f_book.flibustabooksequence_set.all():
                    l_series = self.get_or_create_series(f_book_seq.sequence)
                    BookSeriesLink.objects.create(
                        book=book,
                        series=l_series,
                        sequence_number=f_book_seq.seq_numb
                    )

                # Create Mapping and Update Status
                FlibustaBookMapping.objects.create(flibusta_book=f_book, library_book=book)
                f_book.is_imported = True
                f_book.save(update_fields=['is_imported'])
                
                logger.info(f"Successfully imported book {f_book.id}: {title}")

        except Exception as e:
            logger.error(f"Error importing book {f_book.id}: {e}", exc_info=True)


def process_archive(zip_path: str, filters: List[BookFilter]):
    if not zipfile.is_zipfile(zip_path):
        logger.warning(f"{zip_path} is not a valid zip file.")
        return

    with zipfile.ZipFile(zip_path, 'r') as zf:

        book_ids = {}

        for filename in zf.namelist():
            # Filename expected: book_id.ext or book_id.ext.zip

            # Check if it's a directory
            if filename.endswith('/'):
                continue

            # Parse book_id
            base_name = os.path.basename(filename)
            parts = base_name.split('.')
            if not parts[0].isdigit():
                #  it's not a book_id, skip
                continue

            book_ids[int(parts[0])] = filename


        # get existing FlibustaBook records for these IDs
        books = FlibustaBook.objects.filter(id__in=book_ids.keys())

        # Log error for the not found IDs
        found_ids = set(books.values_list('id', flat=True))
        for book_id in book_ids.keys():
            if book_id not in found_ids:
                logger.error(f"Book {book_id} not found in Flibusta database (file: {filename}).")

        # exclude already imported or deleted books
        books = books.filter(is_imported=False, deleted=0)

        # filter books
        for filter_element in filters:
            books = filter_element.apply(books)

        for book_record in books:
            filename = book_ids.get(book_record.id)
            is_nested_zip = filename.endswith('.zip')

            # Read content
            with zf.open(filename) as f:
                content = f.read()
                # unzip content
                if is_nested_zip:
                    try:
                        with zipfile.ZipFile(io.BytesIO(content)) as nested_zf:
                            nested_names = nested_zf.namelist()
                            if nested_names:
                                # Use the first file
                                target_file = nested_names[0]
                                content = nested_zf.read(target_file)
                    except zipfile.BadZipFile:
                        logger.error(f"Nested zip {filename} is invalid.")
                        continue

                BookImporter().import_book(book_record, content, filename)


def process_local_path(path: str, genres_filters: str = '', formats_filters: str = '', languages_filters: str = ''):
    if not os.path.exists(path):
        logger.error(f"Path '{path}' does not exist.")
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
        logger.info(f"Processing archive: {zip_path}")
        try:
            process_archive(zip_path, filters=get_filters(genres_filters, formats_filters, languages_filters))
        except Exception as e:
            logger.error(f"Failed to process archive {zip_path}: {e}")


def get_filters(genres_filters: str = '', formats_filters: str = '', languages_filters: str = '') -> List[BookFilter]:
    filters = []
    if genres_filters:
        filters.append(GenreFilter(genres_filters.split(',')))
    if formats_filters:
        filters.append(FormatFilter(formats_filters.split(',')))
    if languages_filters:
        filters.append(LanguageFilter(languages_filters.split(',')))
    return filters

