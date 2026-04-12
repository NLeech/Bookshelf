# Library App Test Cases

## Admin Interface (BookAdminTest)
1. **test_book_admin_registered**: Verifies BookAdmin is registered.
2. **test_book_admin_list_display**: Verifies list display fields in BookAdmin.
3. **test_book_admin_readonly_fields**: Verifies readonly fields in BookAdmin.
4. **test_book_admin_autocomplete_fields**: Verifies autocomplete fields in BookAdmin.
5. **test_related_admins_have_search_fields**: Verifies search fields in related admins (Genre, BookSeries).
6. **test_book_series_admin_has_book_inline**: Verifies that BookSeriesBookInline is present in BookSeriesAdmin.
7. **test_book_series_book_inline_fields**: Verifies that BookSeriesBookInline has the expected fields and readonly fields.
8. **test_book_series_book_inline_ordering**: Verifies that BookSeriesBookInline is sorted by sequence_number.

## Models (test_models.py)
### LoopHierarchyTest (parameterized for BookSeries, Genre, Author)
1. **test_wrong_parent**: Verifies loop detection in hierarchical models.
2. **test_proper_parent**: Verifies correct parent-child relationship saving.

### AuthorHierarchyTest
1. **test_wrong_parent**: Verifies that author hierarchy is limited to two levels.

### BookModelTest
1. **test_book_str**: Verifies that Book.__str__ returns the book title.

## Alphabet Tree (GetAlphabetTreeTest)
1. **test_empty_database**: Test that an empty database returns a root with no entries.
2. **test_basic_categorization**: Test that authors are correctly categorized into alpha, digit, and other.
3. **test_low_quantity_alpha_moved_to_other**: Test that alpha nodes with quantity < min_first_level_quantity are moved to 'other'.
4. **test_digits_always_at_root**: Test that '0-9' node stays at root even with low quantity.
5. **test_case_insensitivity**: Test that the grouping is case-insensitive.
6. **test_expansion_threshold**: Test that expansion only occurs when the number of authors exceeds min_quantity.
7. **test_multi_level_expansion**: Test expansion up to level 3.
8. **test_star_nodes**: Test that 'star' nodes are correctly created for non-alpha or short names.
9. **test_different_tree_depths**: Test that the tree expands exactly up to max_tree_depth for various values.

## EPUB Book File (test_epub_book_file.py)
### TestEpubBookFileLoad
1. **test_load_from_stream**: Tests loading an EPUB from an in-memory stream and verifies title, authors and description. (one_author, two_authors, cyrillic)
2. **test_load_from_file**: Tests loading an EPUB from a temporary file and verifies title, authors and description. (one_author, two_authors)
3. **test_extract_isbn_scheme**: Tests extraction of ISBN using opf:scheme="ISBN".
4. **test_extract_isbn_prefix**: Tests extraction of ISBN using 'isbn:' prefix.
5. **test_extract_cover**: Tests extraction of a cover image from an EPUB (standard EpubCover).
6. **test_extract_cover_metadata**: Tests extraction of a cover image from an EPUB using metadata (EPUB 2.0).
7. **test_extract_cover_tag_name**: Tests extraction of a cover image from an EPUB using metadata tag NAMED 'cover'.
8. **test_extract_cover_heuristic**: Tests extraction of a cover image from an EPUB using heuristic fallback.

### TestEpubChapterExtraction
1. **test_get_simple_chapters**: Tests extraction of a simple, flat list of chapters.
2. **test_get_nested_chapters**: Tests extraction of chapters with a nested structure.
3. **test_cyrillic_chapters**: Tests extraction of chapters with Cyrillic titles and content.
4. **test_get_chapters_no_toc**: Tests extraction of chapters when the EPUB has no table of contents.

## FB2 Book File (test_fb2_book_file.py)
### TestFb2BookFileLoad
1. **test_load_from_stream**: Tests loading an FB2 from an in-memory stream and verifies title, authors and description. (one_author, two_authors, cyrillic)
2. **test_load_from_file**: Tests loading an FB2 from a temporary file and verifies title, authors and description. (one_author, two_authors)
3. **test_extract_cover**: Tests extraction of a cover image from an FB2.
4. **test_extract_isbn**: Tests extraction of ISBN from FB2.
5. **test_no_body**: Tests FB2 without <body> tag.
6. **test_section_without_title**: Tests section without <title> tag.
7. **test_invalid_cover**: Tests cover extraction with missing binary.
8. **test_nickname_fallback**: Tests author name extraction when only nickname is present.

### TestFb2ChapterExtraction
1. **test_get_simple_chapters**: Tests extraction of a simple, flat list of chapters.
2. **test_get_nested_chapters**: Tests extraction of chapters with a nested structure.
3. **test_cyrillic_chapters**: Tests extraction of chapters with Cyrillic titles and content.

## Middleware (HealthCheckTest)
1. **test_health_check**: Verifies the /ping/ endpoint returns pong.
