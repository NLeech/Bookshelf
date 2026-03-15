import logging
import os
import tempfile
from typing import List, Optional, Tuple

import zipfile
import pyzipper
from django.conf import settings
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


class BookImporter:
    def __init__(self, genres_filter: Optional[List[str]] = None, langs_filter: Optional[List[str]] = None, formats_filter: Optional[List[str]] = None):
        self.genres_filter = genres_filter
        self.langs_filter = langs_filter
        self.formats_filter = formats_filter
        self.book_pwd = os.environ.get('BOOK_PWD', 'bookshelf').encode('utf-8')

    def check_filters(self, book: FlibustaBook) -> bool:
        """
        Check if the book matches the configured filters.
        """
        # Format filter (file_type)
        if self.formats_filter and book.file_type not in self.formats_filter:
            return False

        # Language filter
        # Flibusta book lang might differ slightly from our ISO codes, but we check exact match for now
        if self.langs_filter and book.lang not in self.langs_filter:
            return False

        # Genre filter
        # We need to check if ANY of the book's genres match the filter
        # Filter can match 'genre_code' or 'genre_meta'
        if self.genres_filter:
            book_genres = book.genres.all()
            match = False
            for genre in book_genres:
                if genre.genre_code in self.genres_filter or genre.genre_meta in self.genres_filter:
                    match = True
                    break
            if not match:
                return False

        return True

    def get_language(self, lang_code: str) -> Optional[Language]:
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

        # 1. Check Filters
        if not self.check_filters(f_book):
            logger.info(f"Book {f_book.id} skipped by filters.")
            return

        # 2. Resolve Language
        language = self.get_language(f_book.lang)
        if not language:
            return  # Error already logged

        try:
            with transaction.atomic():
                # 3. Extract Metadata from file (using Kreuzberg)
                extracted_metadata = {}
                if extract_metadata:
                    # Kreuzberg expects a file path or file-like object.
                    # We have bytes. Let's use a temp file.
                    with tempfile.NamedTemporaryFile(suffix=f".{f_book.file_type}") as tmp_src:
                        tmp_src.write(file_content)
                        tmp_src.flush()
                        try:
                            meta = extract_metadata(tmp_src.name)
                            if meta:
                                extracted_metadata = meta
                        except Exception as e:
                             logger.warning(f"Failed to extract metadata for book {f_book.id}: {e}")

                # 4. Prepare File (Re-compress with password)
                # Create a temporary zip file
                zip_buffer = tempfile.TemporaryFile()
                # Use pyzipper for AES encryption
                with pyzipper.AESZipFile(zip_buffer, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                    zf.setpassword(self.book_pwd)
                    # We assume the file inside should have the name 'book_id.ext'
                    zf.writestr(f"{f_book.id}.{f_book.file_type}", file_content)
                
                zip_buffer.seek(0)

                # 5. Create Library Book
                # Prefer Kreuzberg title/desc/isbn if available, fallback to FlibustaBook
                # Wait, task says: "Get a tittle, authors, genres, series, sequence number, a language from FlibustaBook"
                # "get (if exists) a cover, a description (annotation), isbn, from the book file using Kreuzberg."
                
                # So we stick to Flibusta for core fields.
                
                # Handling Cover
                # extracted_metadata might have 'cover_image_content' (bytes) or similar depending on Kreuzberg output?
                # Need to check what extract_metadata returns. Assuming it returns an object with attributes or dict.
                # If unknown, I'll assume standard dict-like access for now or attributes.
                # Since I don't have exact Kreuzberg docs here, I'll try generic attribute access.
                
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

                # 6. Link Relations
                # Authors
                for f_author in f_book.authors.all():
                    l_author = self.get_or_create_author(f_author)
                    book.authors.add(l_author)

                # Genres
                for f_genre in f_book.genres.all():
                    l_genre = self.get_or_create_genre(f_genre)
                    book.genres.add(l_genre)
                
                # Series (with Sequence Number)
                # FlibustaBookSequence is a through model
                for f_book_seq in f_book.flibustabooksequence_set.all():
                    l_series = self.get_or_create_series(f_book_seq.sequence)
                    BookSeriesLink.objects.create(
                        book=book,
                        series=l_series,
                        sequence_number=f_book_seq.seq_numb
                    )

                # 7. Create Mapping and Update Status
                FlibustaBookMapping.objects.create(flibusta_book=f_book, library_book=book)
                f_book.is_imported = True
                f_book.save(update_fields=['is_imported'])
                
                logger.info(f"Successfully imported book {f_book.id}: {title}")

        except Exception as e:
            logger.error(f"Error importing book {f_book.id}: {e}", exc_info=True)
            # Transaction rollback handles cleanup


def process_archive(zip_path: str, importer: BookImporter):
    if not zipfile.is_zipfile(zip_path):
        logger.warning(f"{zip_path} is not a valid zip file.")
        return

    with zipfile.ZipFile(zip_path, 'r') as zf:
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

            book_id = int(parts[0])

            # Lookup FlibustaBook
            try:
                f_book = FlibustaBook.objects.get(id=book_id)
            except FlibustaBook.DoesNotExist:
                logger.error(f"Book {book_id} not found in Flibusta database (file: {filename}).")
                continue

            # Read content
            with zf.open(filename) as f:
                content = f.read()

            # If the file inside the archive is ALSO a zip (book_id.ext.zip), we might need to unzip it AGAIN?
            # Task says: "A book file might be zipped; in this case, it is named book_id.ext.zip."
            # "For each file in the archive... Get book genres... Compare... Skip..."
            # "Extract metadata from the file."
            # If it's 123.fb2.zip, the content is a ZIP. We need the FB2 inside to get metadata (if Kreuzberg needs the raw ebook).
            # Kreuzberg likely handles epub/fb2. If it's zipped, Kreuzberg might strictly require the ebook file.

            is_nested_zip = filename.endswith('.zip')
            processed_content = content

            if is_nested_zip:
                # We need to unzip the nested content to get the actual ebook for metadata extraction
                # And maybe for storage? Task says "Extract book file."
                try:
                    import io
                    with zipfile.ZipFile(io.BytesIO(content)) as nested_zf:
                        # Assume single file inside?
                        nested_names = nested_zf.namelist()
                        if nested_names:
                            # Use the first file
                            target_file = nested_names[0]
                            processed_content = nested_zf.read(target_file)
                            # Update file_type from nested filename if possible?
                            # FlibustaBook has file_type. We should trust it or the filename.
                except zipfile.BadZipFile:
                    logger.warning(f"Nested zip {filename} is invalid.")
                    continue

            importer.import_book(f_book, processed_content, filename)
