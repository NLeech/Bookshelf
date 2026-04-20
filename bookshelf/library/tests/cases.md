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
2. **test_book_fields**: Verify that size and file_type fields are correctly saved and retrieved.
3. **test_book_size_str**: Parameterized test verifying that size_str returns human-readable format correctly (B, KB, MB) for various sizes (0 B, integer, fractional).

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

## Author Aggregations (AuthorAggregationsTest)
1. **test_get_author_languages_empty**: Author with 0 books -> returns empty queryset.
2. **test_get_author_languages_single**: Author with 2 books in 'en' -> returns 1 language ('en') with `book_count=2`.
3. **test_get_author_languages_multiple**: Author with 1 book in 'en', 2 in 'uk' -> returns sorted languages ('en', 'uk') with correct counts.
4. **test_get_author_languages_isolation**: Author A has 1 book in 'en'. Author B has 1 book in 'en'. `get_author_languages(Author A)` -> returns 'en' with `book_count=1`.
5. **test_get_author_genres_tree_empty**: Author with 0 books -> returns empty list.
6. **test_get_author_genres_tree_hierarchy**: Author has book in 'Sub-genre' (parent: 'Parent-genre'). Tree should contain 'Parent-genre' with 'Sub-genre' as child.
7. **test_get_author_genres_tree_counts**: Book in 'Sub-genre' (count 1). Book in 'Parent-genre' (count 1).
8. **test_get_author_genres_tree_several_books_count**: Complex case with multiple genres and shared books between genres. Verifies correct book counts at each node and inclusion of ancestor genres with 0 count.
9. **test_get_author_genres_tree_sorting**: Root level sorted alphabetically. Children also sorted alphabetically. Sorting is case-insensitive.
10. **test_get_author_genres_tree_isolation**: Book counts in the genre tree only reflect the books of the requested author.

## Book Services (BookServicesTest)
1. **test_get_book_extractor_no_file**: Test with `book.file = None`. Returns `None`.
2. **test_get_book_extractor_direct**: Test direct extraction for EPUB and FB2. Returns correct `BookFile` subclass.
3. **test_get_book_extractor_zip**: Test extraction from password-protected ZIP (EPUB and FB2 inside). Returns correct extractor.
4. **test_get_book_extractor_unsupported**: Test with unsupported extension (e.g., `.txt`). Returns `None`.
5. **test_get_book_extractor_invalid_zip**: Test with invalid or damaged ZIP file. Returns `None` and logs error.
6. **test_get_book_extractor_empty_zip**: Test with empty ZIP file. Returns `None`.
7. **test_flatten_chapters_nested**: Test flattening of nested chapters and verify `flat_index` assignment.
8. **test_sanitize_filename**: Parameterized test verifying `sanitize_filename` utility (ASCII only, no spaces, colons to ` - `, collapses underscores, strips edges, support for Cyrillic).
9. **test_get_book_file_content_parameterized**: Verifies that `get_book_file_content` returns a standardized and sanitized filename (`Author_-_Title.ext`), correct bytes, and content type for both direct and zipped EPUB/FB2 files.
10. **test_get_book_file_content_mimetype_registration**: Verifies that custom mimetypes for EPUB and FB2 are registered if not already present.
11. **test_get_book_file_content_missing_file**: Verifies that `get_book_file_content` returns `None` values if the book has no file.
12. **test_get_book_file_content_zip_empty_list**: Verifies that `get_book_file_content` returns `None` if the ZIP file is empty.
13. **test_get_book_file_content_zip_exception**: Verifies that ZIP extraction errors are caught and logged, returning `None`.
14. **test_get_book_file_content_read_exception**: Verifies that file read errors are caught and logged, returning `None`.

## Author List View (AuthorListViewTests)
1. **test_author_list_view_status_code**: Verifies the view returns 200 OK and uses the correct template.
2. **test_author_list_view_pagination**: Verifies pagination works correctly (showing 50 authors per page).
3. **test_author_list_view_filtering_parameterized**: Verifies filtering logic (startswith, regex, case insensitivity, precedence) using `parameterized.expand`.
4. **test_author_list_view_empty_results**: Verifies "No authors found." message when no authors match filter.
5. **test_author_list_view_htmx_partial**: Verifies that an HTMX request returns only the partial template fragment.
6. **test_author_list_view_context**: Verifies that filter and regex match query parameters in context.
7. **test_author_list_view_alphabet_tree_integration**: Verifies that alphabet_tree is in context and contains expected nodes.
8. **test_author_list_view_pagination_links_preserve_params**: Verifies that pagination links correctly include and preserve filter and regex parameters.

## Author Detail View (AuthorDetailViewTests)
1. **test_author_detail_view_status_code**: Verifies the view returns 200 OK and uses the correct template.
2. **test_author_detail_view_404**: Verifies the view returns 404 for a non-existent author.
3. **test_author_detail_view_tabs_parameterized**: Verifies tab logic (sorting for alpha and recent, grouping for series) using `parameterized.expand`.
4. **test_author_detail_view_filtering_parameterized**: Verifies filtering logic for languages and genres using `parameterized.expand`.
5. **test_author_detail_view_htmx_partials_parameterized**: Verifies that HTMX requests return the appropriate tab partial template fragment.
6. **test_author_detail_view_context_data**: Verifies that `available_languages` and `available_genres_tree` are correctly populated.

## Book Detail View (BookDetailViewTests)
1. **test_book_detail_view_status_code**: Verifies the view returns 200 OK and uses the correct template for both EPUB and FB2.
2. **test_book_detail_view_404**: Verifies the view returns 404 for a non-existent book.
3. **test_book_detail_view_content**: Verifies hierarchical TOC structure and chapter content in context and response for both EPUB and FB2.
4. **test_book_detail_view_chapter_selection**: Verifies that selecting a chapter by index works correctly for both EPUB and FB2.
5. **test_book_detail_view_htmx_partial**: Verifies HTMX partial rendering for both EPUB and FB2.
6. **test_book_detail_view_no_extractor**: Verifies behavior when a book has no file (shows "No TOC available").
7. **test_book_detail_navigation_context**: Verifies that prev_chapter and next_chapter are correctly added to the context.
8. **test_book_detail_first_chapter_navigation**: Verifies navigation context for the first chapter (prev_chapter is None).
9. **test_book_detail_last_chapter_navigation**: Verifies navigation context for the last chapter (next_chapter is None).
10. **test_book_detail_navigation_rendering**: Verifies that navigation links with hx-get are rendered correctly in the HTML.
11. **test_book_detail_view_invalid_chapter_index**: Verifies that an invalid chapter index defaults to the first chapter.

## Book Detail Sidebar (BookDetailSidebarTests)
1. **test_book_details_sidebar_contains_title**: Verify that the book title is present in the sidebar.
2. **test_book_details_sidebar_contains_author_links**: Verify that author links are present and point to the correct author detail pages.
3. **test_book_details_sidebar_multiple_authors**: Verify that multiple authors are displayed if present.

## Book Download View (BookDownloadViewTests)
1. **test_book_download_filename**: Parameterized test verifying downloading books with various titles and authors (including Cyrillic, direct and zipped files), ensuring correct `Content-Type` and `Content-Disposition` (with RFC 6266 for non-ASCII).
2. **test_book_download_multiple_authors**: Verify filename format for multiple authors: `FirstAuthor_et_al_-_Title`.
3. **test_book_download_404_no_file**: Verify 404 if the book has no file.
4. **test_book_download_404_invalid_id**: Verify 404 for non-existent book ID.

## Homepage (HomePageViewTests)
1. **test_latest_arrivals_filtering**: Verifies that only books created within the last 7 days are displayed in the Latest Arrivals section.
2. **test_latest_arrivals_sorting**: Verifies that books are sorted by creation date descending, and then by title ascending.
3. **test_homepage_status_and_template**: Verifies that the homepage returns a 200 OK status and uses the expected template.
4. **test_homepage_unauthenticated_view**: Verifies that Search and Latest Arrivals are visible to guests, while personal sections are hidden.
5. **test_homepage_authenticated_view**: Verifies that all sections, including Reading List and Favorite Authors, are visible to authenticated users.
6. **test_latest_arrivals_htmx_pagination**: Verifies that HTMX requests return the correct template partial and paginated data.
7. **test_homepage_no_latest_arrivals**: Verifies that an appropriate message is shown when no new books have been added in the last 7 days.
8. **test_homepage_pagination_presence**: Verifies that pagination is present at both the top and bottom of the list when multiple pages exist.
9. **test_homepage_jump_to_page**: Verifies the presence and correct HTMX attributes of the Jump to Page functionality on the homepage.
