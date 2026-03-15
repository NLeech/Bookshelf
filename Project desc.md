Logging strategy for the project:
- All messages must be written to the console.
    - Warning messages should be displayed in yellow (if possible).
	- Error messages should be displayed in red (if possible).
- All messages must be written to the log.log file.
- Error messages must be emailed to EMAIL_HOST_USER.
- For the flibusta app all messages must be written to the update.log file as well.


Library update from Flibusta

Load books from Flibusta archives and Flibusta daily updates. Load books only for certain genres, languages, and formats.

The flow:

Update Flibusta tables from the Flibusta SQL dump.

a. Download book archives from flibusta.is/daily
b. Or get book archives from a given path.

A book archive is a ZIP file containing book files. The book files are named book_id.ext, where ext is a file extension (txt, pdf, epub, fb2, etc.). A book file might be zipped; in this case, it is named book_id.ext.zip.

For each file in the archive, do the following:

Find the book_id in libbook. If it is not found, skip the file and log a warning.

Get the book genres, language, and type (from the file extension). Compare the retrieved parameters with the filter. Skip the file if it does not pass the filter.

At this point, we have a list of book_ids planned for import.

For each book_id, start the following transaction:

Get the book authors from the libavtorname table. If a book author has a main_id field, use the main author instead.

Get or create corresponding authors in the library app. (We need to design a mechanism to link an author from the library app with an author from Flibusta.)

Get book genres, series, and language.

Get or create corresponding genres, series, and language in the library app. (We need to design a mechanism to link them as well.)

Get book metadata from the file.

Create a book entry in the library app.

Mark the book_id in libbook as imported. (Books marked as imported are excluded from further imports.)


# Flibusta Book Import Implementation Plan

## Objective
Implement a mechanism to import books from Flibusta archives into the local library, syncing authors, genres, and series while maintaining a clean separation between the `flibusta` mirror app and the core `library` app.

## Key Files & Context
-   `bookshelf/flibusta/models.py`: Needs `is_imported` field and new Mapping models.
-   `bookshelf/library/models.py`: Target for import (read-only context).
-   `bookshelf/flibusta/services.py`: New file for import logic.
-   `bookshelf/flibusta/management/commands/import_books.py`: New command to run the import.

## Implementation Steps

1.  **Dependencies**
    -   Use `pyzipper` for creating password-protected ZIP files (AES encryption). Package is already installed

2.  **Update Library Models (`bookshelf/library/models.py`)**
    -   Add `cover` field to `Book` model (`ImageField`, nullable).
    -   Add `file` field to `Book` model (`FileField`).
        -   **Storage Requirement**: Files must be stored as password-protected ZIP archives (password from `BOOK_PWD` env var).
    -   Create a through model `BookSeriesLink` for `Book` <-> `BookSeries` to store `sequence_number`.
    -   Update `Book.series` ManyToManyField to use `through='BookSeriesLink'`.
    -   Create migrations.

3.  **Update Flibusta Models (`bookshelf/flibusta/models.py`)**
    -   Add `is_imported` (BooleanField, default=False) to `FlibustaBook` to track status.
    -   Create mapping models:
        -   `FlibustaAuthorMapping` (OneToOne to FlibustaAuthor, FK to Library Author)
        -   `FlibustaGenreMapping` (OneToOne to FlibustaGenre, FK to Library Genre)
        -   `FlibustaSequenceMapping` (OneToOne to FlibustaSequence, FK to Library Series)
        -   `FlibustaBookMapping` (OneToOne to FlibustaBook, FK to Library Book)
    -   Create migrations.

4.  **Create Import Service (`flibusta/services.py`)**
    -   Implement `BookImporter` class.
    -   **Filtering**: Method to check filters (genre, language, format).
    -   **Entity Resolution**:
        -   `get_language`: Look up `library.Language.code` by ISO 639-1 code. **Log ERROR and skip book** if not found.
        -   `get_or_create_genre`: Map to `library.Genre`. Ensure 2-level hierarchy (Meta Genre -> Genre). Create Meta Genre if missing.
        -   `get_or_create_author`: Map to `library.Author` (handle `master_id` recursively).
        -   `get_or_create_series`: Map to `library.BookSeries`.
    -   **Book Import (Transactional)**:
        -   **Metadata**:
            -   Use `FlibustaBook` for basic metadata (title, authors, genres, series, lang).
            -   Use `kreuzberg` to extract cover, description, ISBN from the source file.
        -   **File Processing**:
            -   Extract book file from source archive.
            -   Re-compress into a new ZIP with password (`BOOK_PWD`).
            -   Save to `library.Book.file`.
        -   **Linking**:
            -   Create `library.Book` with cover and file.
            -   Link authors, genres, series (via `BookSeriesLink` with `sequence_number`).
            -   Create `FlibustaBookMapping`.
            -   Set `FlibustaBook.is_imported = True`.
        -   **Rollback**: Ensure atomic transaction; rollback on any error.

5.  **Implement Management Command (`import_books`)**
    -   Arguments: `--path` (optional), `--genres`, `--langs`, `--formats`.
    -   **Logic**:
        -   Default to `FLIBUSTA_BASE_URL/daily` if path missing.
        -   Iterate ZIPs -> Iterate files -> Parse ID -> Lookup DB -> Filter.
        -   Call `BookImporter.import_book`.

6.  **Verification & Testing**
    -   Unit tests for `BookImporter` (mocking DB, Archives, Kreuzberg, pyzipper).
    -   Integration test with sample data.

## Questions/Assumptions
-   **Assumption**: `pyzipper` is acceptable for creating encrypted ZIPs.
-   **Assumption**: `BOOK_PWD` will be available in the environment during import.
