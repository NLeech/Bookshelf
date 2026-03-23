import logging
import os
import io
import tempfile
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
import re
import requests
import shutil

import zipfile
import pyzipper
from django.conf import settings
from django.db.models.query import QuerySet
from django.db.models import Q
from django.core.files import File
from django.db import transaction

from library.models import Author, Genre, BookSeries, Book, Language, BookSeriesLink
from .models import (
    FlibustaBook,
    FlibustaAuthor,
    FlibustaGenre,
    FlibustaSequence,
    FlibustaAuthorMapping,
    FlibustaGenreMapping,
    FlibustaSequenceMapping,
    FlibustaBookMapping,
)

logger = logging.getLogger(__name__)


class BookFilter(ABC):
    @abstractmethod
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
    def __init__(self):
        self.book_pwd = settings.BOOK_PWD

    def get_language(self, lang_code: str) -> Language | None:
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
        meta_genre, _ = Genre.objects.get_or_create(
            code=f_genre.genre_meta,
            defaults={
                'name': f_genre.genre_meta,
            }
        )

        # Create Genre
        library_genre, created = Genre.objects.get_or_create(
            code=f_genre.genre_code,
            defaults={
                'name': f_genre.genre_desc,
                'parent': meta_genre,
            }
        )

        # Create Mapping
        FlibustaGenreMapping.objects.create(flibusta_genre=f_genre, library_genre=library_genre)
        
        return library_genre

    def get_or_create_author(self, f_author: FlibustaAuthor) -> Author:
        # Check mapping first
        if hasattr(f_author, 'mapping'):
            return f_author.mapping.library_author

        flibusta_author = f_author

        # resolution for master_id
        if f_author.master_id and f_author.master_id != f_author.id:
            # Try to find the master author in Flibusta
            try:
                flibusta_author = FlibustaAuthor.objects.get(id=f_author.master_id)

            except FlibustaAuthor.DoesNotExist:
                # If master doesn't exist, treat current as independent (fallback)
                logger.error(
                    f"Master author {f_author.master_id} for {f_author.id} not found. Treating as independent."
                )

        # Create Author
        library_author = Author.objects.create(
            first_name=flibusta_author.first_name,
            middle_name=flibusta_author.middle_name,
            last_name=flibusta_author.last_name,
            nickname=flibusta_author.nickname,
            email=flibusta_author.email,
            homepage=flibusta_author.homepage,
        )

        # mapping for both master and current author (if different)
        FlibustaAuthorMapping.objects.create(flibusta_author=flibusta_author, library_author=library_author)
        if flibusta_author != f_author:
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

        # Resolve Language
        language = self.get_language(f_book.lang)
        if not language:
            return

        try:
            with transaction.atomic():
                # Extract metadata from the file
                extracted_metadata = {}
                extracted_cover = None

                try:
                    mime_type = "application/epub+zip" if f_book.file_type == "epub" else "application/x-fictionbook+xml"
                    # TODO Implement metadata extraction
                except Exception as e:
                    logger.warning(f"Metadata extraction failed for book {f_book.id}: {e}")

                # Re-compress the file with password
                zip_buffer = tempfile.TemporaryFile()
                with pyzipper.AESZipFile(zip_buffer,
                                         'w',
                                         compression=pyzipper.ZIP_DEFLATED,
                                         encryption=pyzipper.WZ_AES) as zf:
                    zf.setpassword(self.book_pwd)
                    # File inside should have the name 'book_id.ext'
                    zf.writestr(f"{f_book.id}.{f_book.file_type}", file_content)
                
                description = extracted_metadata.get('description', '')
                isbn = extracted_metadata.get('isbn', 0)
                # Ensure ISBN is decimal/number
                if not isinstance(isbn, (int, float, str)):
                    isbn = 0
                if isinstance(isbn, str):
                     # clean string
                     isbn = ''.join(filter(str.isdigit, isbn)) or 0
                
                # Title from Flibusta
                title = f_book.title

                book = Book(
                    title=title,
                    description=description,
                    language=language,
                    isbn=isbn,
                )

                # Save file
                file_name = f"{f_book.id}.zip"
                book.file.save(file_name, File(zip_buffer), save=False)

                # Save cover if available
                if extracted_cover:
                    with tempfile.TemporaryFile() as tf:
                        tf.write(extracted_cover)
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

                # Create Mapping
                FlibustaBookMapping.objects.create(
                    flibusta_book=f_book, library_book=book
                )

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
        books = books.filter(deleted=0).exclude(mapping__isnull=False)

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


def get_daily_links(html_content: str) -> List[Dict[str, str]]:
    """
    Parse daily update page HTML to find links to book archives.
    """
    links = []
    # Regex to match f.fb2.123-456.zip or f.n.123-456.zip
    pattern = re.compile(r'href="([^"]*(?:f\.fb2|f\.n)\.\d+-\d+\.zip)"')
    
    for match in pattern.finditer(html_content):
        url = match.group(1)
        # Ensure URL is absolute if it's relative
        if not url.startswith('http'):
             # Usually links on Flibusta are relative to the page or root
             # But the sample shows relative links like "f.fb2.864667-864748.zip"
             # Base URL is FLIBUSTA_BASE_URL/daily/
             # So we prepend it
             base_url = getattr(settings, 'FLIBUSTA_BASE_URL', 'https://flibusta.is').rstrip('/')
             url = f"{base_url}/daily/{url}"
        
        filename = url.split('/')[-1]
        links.append({'url': url, 'filename': filename})
    
    return links


def download_file(url: str) -> str:
    """
    Download a file from a URL to a temporary location.
    Returns the path to the downloaded file.
    """
    logger.info(f"Downloading {url}...")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        # Create a temporary file
        fd, path = tempfile.mkstemp(suffix='.zip')
        with os.fdopen(fd, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return path
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        raise


def process_daily_updates(filters: List[BookFilter] | None = None) -> None:
    """
    Fetch and process daily updates from Flibusta.
    """
    if filters is None:
        filters = []

    base_url = getattr(settings, 'FLIBUSTA_BASE_URL', 'https://flibusta.is').rstrip('/')
    daily_url = f"{base_url}/daily/"
    
    logger.info(f"Checking for daily updates at {daily_url}...")
    
    try:
        response = requests.get(daily_url)
        response.raise_for_status()
        
        links = get_daily_links(response.text)
        logger.info(f"Found {len(links)} update archives.")
        
        for link in links:
            url = link['url']
            filename = link['filename']
            
            # Identify if it is f.fb2 or f.n (both treated as archives to process)
            # You might want to skip if already processed, but for now we just process.
            # In a real system, you'd check a "ProcessedUpdates" model.
            
            logger.info(f"Processing update: {filename}")
            
            temp_path = None
            try:
                temp_path = download_file(url)
                logger.info(f"Downloaded {filename} to {temp_path}. Processing archive...")
                
                process_archive(temp_path, filters=filters)
                
                logger.info(f"Finished processing {filename}.")
                
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.debug(f"Removed temporary file {temp_path}")

    except Exception as e:
        logger.error(f"Failed to fetch or process daily updates: {e}")


def process_local_path(path: str, filters: List[BookFilter] | None = None) -> None:
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

    if filters is None:
        filters = []

    for zip_path in files:
        logger.info(f"Processing archive: {zip_path}")
        try:
            process_archive(zip_path, filters=filters)
        except Exception as e:
            logger.error(f"Failed to process archive {zip_path}: {e}")


def get_filters(
        genres_filters: List[str] | None = None,
        formats_filters: List[str] | None = None,
        languages_filters: List[str] | None = None
) -> List[BookFilter]:
    filters = []
    if genres_filters:
        filters.append(GenreFilter(genres_filters))
    if formats_filters:
        filters.append(FormatFilter(formats_filters))
    if languages_filters:
        filters.append(LanguageFilter(languages_filters))
    return filters
