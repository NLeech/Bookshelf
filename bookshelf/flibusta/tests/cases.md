# Complete List of Test Cases

## Filtering & Pre-processing (TestBookFilters)
1.  **test_language_filter**: Verifies LanguageFilter correctly filters FlibustaBook by language code.
2.  **test_format_filter**: Verifies FormatFilter correctly filters FlibustaBook by file extension/type (e.g., 'fb2', 'epub').
3.  **test_genre_filter**: Verifies GenreFilter correctly filters FlibustaBook by specific genre code or its parent meta-genre.

## Importer Service - Entity Retrieval (TestBookImporterService)
4.  **test_get_language**: Verifies get_language retrieves an existing Language object or logs an error if the code is missing.
5.  **test_get_or_create_genre**: Verifies get_or_create_genre creates a Genre and its mapping. Subsequent calls return the mapped object instance (identity check).
6.  **test_get_or_create_author_with_master**: Verifies get_or_create_author handles authors with a master_id, creating a single Library Author and mapping both the alias and the master. Subsequent calls return the mapped object instance.
7.  **test_get_or_create_author_with_missing_master**: Verifies fallback behavior when a master_id is present but the master author doesn't exist in the Flibusta database.
8.  **test_get_or_create_series_basic**: Verifies get_or_create_series creates a BookSeries and its mapping. Subsequent calls return the mapped object instance (identity check).

## Importer Service - Book Import (TestBookImporterService)
9.  **test_import_book_no_language**: Verifies that if a book's language is not yet supported in our library, the import process is skipped for that book.
10. **test_import_book_success**: Verifies the full import_book flow for a basic FB2 book, including author/genre/series relations, re-compression with password, and mapping creation.

## Archive Processing (TestArchiveProcessing)
11. **test_process_archive_basic**: Verifies process_archive correctly identifies and imports individual book files from a standard zip archive.
12. **test_process_archive_skip_imported_and_deleted**: Verifies that books already mapped to our library or marked as deleted in Flibusta are skipped.
13. **test_process_archive_nested**: Verifies that process_archive can recursively handle nested zip files.
14. **test_process_archive_with_filters**: Verifies that filters are applied during process_archive to the retrieved FlibustaBook queryset (hits line 355).
15. **test_process_archive_book_not_found**: Verifies error logging when a file in the zip contains a book ID not found in the Flibusta database.

## Metadata Extraction (TestBookImporterMetadata)
16. **test_import_book_epub_metadata**: Verifies extraction of cover image and metadata from EPUB files. *Updated: Now verifies physical persistence of the cover file in MEDIA_ROOT using os.path.exists.*
17. **test_import_book_fb2_metadata**: Verifies extraction of description (annotation) and ISBN from FB2 files. *Updated: Now verifies cleaning of non-digit characters from ISBN (e.g., "123-456" -> 123456).*
18. **test_import_book_metadata_extraction_failure**: Verifies that if a file is corrupted or metadata extraction fails, the book is still imported using available Flibusta DB data.

## Utilities & Integration (TestUtilityFunctions)
19. **test_get_daily_links**: Verifies parsing of Flibusta HTML pages to extract daily update zip links.
20. **test_get_daily_links_no_links**: Verifies that an empty list is returned when the HTML page contains no matching links.
21. **test_get_filters**: Verifies the factory function that generates filter objects from configuration.
22. **test_download_file**: Verifies the utility for downloading remote files to a temporary local path.
23. **test_process_daily_updates**: Verifies the high-level orchestration of downloading and processing daily updates.
24. **test_process_local_path_dir**: Verifies recursive processing of all zip archives within a local directory.
25. **test_process_local_path_file**: Verifies processing of a single specified local zip file.
26. **test_process_local_path_invalid**: Verifies error logging for non-existent or invalid local paths.
