# Library App Test Cases

## Test Setup & Environment
- Tests involving models with file or image fields shouls use BaseTestCase as the base class.

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
2. **test_basic_categorization**: Test that items are correctly categorized into alpha, digit, and other based on a provided field.
3. **test_low_quantity_alpha_moved_to_other**: Test that alpha nodes with quantity < min_first_level_quantity are moved to 'other'.
4. **test_digits_always_at_root**: Test that '0-9' node stays at root even with low quantity.
5. **test_case_insensitivity**: Test that the grouping is case-insensitive.
6. **test_expansion_threshold**: Test that expansion only occurs when the number of items exceeds min_quantity.
7. **test_multi_level_expansion**: Test expansion up to level 3.
8. **test_star_nodes**: Test that 'star' nodes are correctly created for non-alpha or short names.
9. **test_different_tree_depths**: Test that the tree expands exactly up to max_tree_depth for various values.
10. **test_generic_alphabet_tree_books**: Verify that get_alphabet_tree works correctly for Book models using the 'title' field.
11. **test_alphabet_tree_with_filtered_queryset**: Verify that get_alphabet_tree correctly calculates counts when provided with a pre-filtered queryset (e.g. by language).

## Find Alphabet Node (FindAlphabetNodeTest)
1. **test_find_alphabet_node**: Verifies find_alphabet_node behavior for various inputs (filter, regex, caps, not found, empty search) using `parameterized.expand`.

## Find Alphabet Node By Name (FindAlphabetNodeByNameTest)
1. **test_find_alphabet_node_by_name[find_root_level_a]**: Finds 'a' node at root level.
2. **test_find_alphabet_node_by_name[find_root_level_b]**: Finds 'b' node at root level.
3. **test_find_alphabet_node_by_name[find_other_node]**: Finds 'other' node at root level.
4. **test_find_alphabet_node_by_name[find_digits_node]**: Finds '0-9' node at root level.
5. **test_find_alphabet_node_by_name[find_deep_aa]**: Finds 'aa' node at level 2 (requires DFS descent).
6. **test_find_alphabet_node_by_name[find_deep_ab]**: Finds 'ab' node at level 2.
7. **test_find_alphabet_node_by_name[find_star_node]**: Finds 'a*' star node at level 2.
8. **test_find_alphabet_node_by_name[not_found_nonexistent]**: Returns None for a name not in the tree.
9. **test_find_alphabet_node_by_name[case_sensitive_uppercase_returns_none]**: Returns None for 'A' when only 'a' exists (match is case-sensitive).
10. **test_find_root_matches_empty_name**: Returns root when searching for '' (root.name is '').
11. **test_returns_first_match_depth_first**: When two nodes share the same name, the depth-first first match is returned.

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
Chapters follow the "TOC defines boundaries, spine fills" model: a chapter spans spine content from one TOC navigation point up to the next, in spine order; a boundary is a `(spine file, optional #anchor)` pair. Content slicing (DOM order of anchors within a file) and tree assembly (parent/child from TOC nesting depth) are independent.
1. **test_get_simple_chapters**: Tests extraction of a simple, flat list of chapters.
2. **test_get_nested_chapters**: Tests extraction of chapters with a nested structure.
3. **test_cyrillic_chapters**: Tests extraction of chapters with Cyrillic titles and content.
4. **test_get_chapters_no_toc**: Tests extraction of chapters when the EPUB has no table of contents.
5. **test_normalize_toc_lone_link** (T1): A lone `epub.Link` TOC (injected post-load, since ebooklib cannot write that shape) does not crash and yields the link's file as a chapter.
6. **test_normalize_toc_two_element_list_not_misfired** (T2): A 2-element LIST `[Link, (Section, [child])]` keeps BOTH top-level entries; the section becomes a container parent with one subchapter.
7. **test_emptiness_text_or_media** (T3, parameterized): Pre-TOC front matter is skipped only when it has neither text (>20 chars) nor media. Scenarios: empty `<div>` (skipped), `<img>`-only plate (emitted), real text (emitted).
8. **test_multi_anchor_one_file_splits_into_subchapters** (T4): One file with a no-anchor parent and two anchored children splits into a parent chapter with two subchapters; each verse body appears exactly once in its own subchapter.
9. **test_gap_and_split_tail_fold_into_previous_chapter** (T5): Calibre `_split_001` tails and gap files (no TOC point of their own) fold into the previous chapter; no duplicate/garbage chapters.
10. **test_single_toc_entry_spanning_flow** (T6): TOC of a single entry → exactly one chapter spanning the whole spine flow (cover + all sections), no per-file garbage.
11. **test_interleaved_levels_in_one_file** (T7): Anchors at different tree levels within one file assemble into the correct parent/child tree; each fragment's content is bounded by the next anchor in DOM order, independent of tree nesting.
12. **test_no_toc_each_file_is_chapter_with_empty_skip** (T8): With no TOC, each non-empty spine file is one flat chapter (titled by first heading → filename); the empty cover is skipped.
13. **test_pre_toc_textual_becomes_top_level_chapter** (T10): An empty cover is skipped; a textual preface with no TOC entry becomes a top-level chapter (title from heading → filename → "Предисловие"), followed by the first TOC chapter.
14. **test_dangling_toc_href_is_skipped** (T11): A TOC entry whose href is absent from spine and manifest is dropped (no empty chapter, no crash); neighbouring valid chapters remain intact.
15. **test_unresolved_anchors_do_not_shift_content** (T12): When every TOC `#fragment` resolves to a file but matches no in-DOM id (calibre-style), each file becomes its own chapter's content — no chapter is left empty and no chapter absorbs the next file (regression for the one-file forward-shift bug).

### TestEpubChapterExtractionReference
Regression twins (R1-R5): synthetic in-memory EPUBs replicating five real-world book structures (spine order, TOC tree with `#fragments`, in-DOM anchor ids) with lorem bodies; each asserts the exact chapter tree validated against FBReader/Moon Reader screenshots.
1. **test_container_children_reference_tree** (R1): `Предисловие / Раздел[container] → (Раздел 1-50 … Раздел 551-600, 12 children at level 1) / Послесловие`.
2. **test_multilevel_chapters_reference_tree** (R2): `Предисловие / Глава 1 → (Раздел 1.1 … 1.4) / Глава 2 → (Раздел 2.1 … 2.5)`. All child titles are generic placeholders encoding only the structure (4 and 5 children).
3. **test_nested_containers_reference_tree** (R3): nested containers `Часть 1 → Глава 1 → Подраздел 1.1` at levels 0/1/2.
4. **test_single_chapter_reference** (R4): one "Start" chapter spanning the flow, no subchapters.
5. **test_split_parts_reference_no_duplicate_chapters** (R5): calibre splits collapse to one chapter per part (Vireo, Heron, Plover); each split tail folds into its part, no duplicates.

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
4. **test_get_chapters_no_sections**: Verifies extraction when <body> contains content directly without <section> tags.
5. **test_get_chapters_empty_body**: Verifies fallback behavior for empty <body>.
6. **test_get_chapters_whitespace_body**: Verifies fallback behavior for <body> with only whitespace.

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
9. **test_get_book_file_content_parameterized**: Verifies that `get_book_file_content` returns a standardized sanitized filename and correct content type for direct/zipped EPUB and FB2 files, and that FB2 is delivered zip-wrapped (`application/fb2+zip`, `.fb2.zip` filename, archive entry holding the original bytes).
10. **test_get_book_file_content_mimetype_registration**: Verifies that custom mimetypes for EPUB and FB2 are registered if not already present.
11. **test_get_book_file_content_missing_file**: Verifies that `get_book_file_content` returns `None` values if the book has no file.
12. **test_get_content_type**: Parameterized test verifying `get_content_type` maps filenames, extensions (`.fb2`), bare format tags (`fb2`, `FB2`), and paths to the correct MIME type (`.fb2` → `application/fb2+zip`), falling back to `application/octet-stream` for unknown/empty input.
13. **test_get_content_type_registers_custom_types**: Verifies `get_content_type` registers the custom EPUB (`application/epub+zip`) and FB2 (`application/fb2+zip`) mimetypes when absent from the mime database.
14. **test_get_book_file_content_zip_empty_list**: Verifies that `get_book_file_content` returns `None` if the ZIP file is empty.
15. **test_get_book_file_content_zip_exception**: Verifies that ZIP extraction errors are caught and logged, returning `None`.
16. **test_get_book_file_content_read_exception**: Verifies that file read errors are caught and logged, returning `None`.
17. **test_get_languages_with_filtered_queryset**: Verify get_languages() returns correct book counts when provided with a filtered queryset.
18. **test_get_genres_tree_with_filtered_queryset**: Verify get_genres_tree() returns correct hierarchy and counts when provided with a filtered queryset.
19. **test_search_entities_authors**: Test searching authors by various fields and sorting.
20. **test_search_entities_books**: Test searching books by title.
21. **test_search_entities_series**: Test searching series by name.
22. **test_search_entities_empty_query**: Test search with empty query.
23. **test_search_entities_no_results**: Test search with no matches.
24. **test_get_book_extractor_corrupt_epub_returns_none** (T9): A corrupt non-ZIP EPUB whose bytes make `read_epub` raise yields `None` from `get_book_extractor` (no exception propagates) and logs an error.

## Genre Services (GenreServicesTest)
1. **test_get_descendants_logic**: Parameterized test verifying leaf-node identification for various inputs.
    - **Scenarios**:
        - Single parent -> returns its leaf descendants.
        - Multiple parents -> returns leaf descendants of all parents.
        - Leaf node as input -> returns empty set (not included).
        - Non-existent ID -> returns empty set.

## can_view_book Service (test_book_services.py — CanViewBookTest)

Verifies `library.services.can_view_book(user)`; The gating permission codename is settings-driven (`settings.VIEW_BOOK_PERM`, default `library.view_book`).

1. **test_can_view_book_true_with_perm**: A user in the `Book access` group (perm cache reset) returns `True`.
2. **test_can_view_book_false_without_perm**: A plain authenticated user returns `False`.
3. **test_can_view_book_false_for_anonymous**: `AnonymousUser()` returns `False` and raises no exception.

## Author List View (AuthorListViewTests)
1. **test_author_list_view_status_code**: Verifies the view returns 200 OK and uses the correct template.
2. **test_author_list_view_pagination**: Verifies pagination works correctly (showing 50 authors per page).
3. **test_author_list_view_filtering_parameterized**: Verifies filtering logic (startswith, regex, case insensitivity, precedence) using `parameterized.expand`.
4. **test_author_list_view_empty_results**: Verifies "No authors found." message when no authors match filter.
5. **test_author_list_view_htmx_partial**: Verifies that an HTMX request returns only the partial template fragment (authors_list_results).
6. **test_author_list_view_context**: Verifies that filter and regex match query parameters in context.
7. **test_author_list_view_alphabet_tree_integration**: Verifies that alphabet_tree is in context and contains expected nodes.
8. **test_author_list_view_pagination_links_preserve_params**: Verifies that pagination links correctly include and preserve filter and regex parameters.

## Author Detail View (AuthorDetailViewTests)
1. **test_author_detail_view_status_code**: Verifies the view returns 200 OK and uses the correct template.
2. **test_author_detail_view_404**: Verifies the view returns 404 for a non-existent author.
3. **test_author_detail_view_tabs_parameterized**: Verifies tab logic (sorting for alpha and recent, grouping for series) using `parameterized.expand`.
4. **test_author_detail_view_filtering_parameterized**: Verifies filtering logic for languages and genres using `parameterized.expand`.
5. **test_author_detail_view_htmx_partials_parameterized**: Verifies that HTMX requests return the top-level AJAX partial (author_ajax) containing the appropriate tab content.
6. **test_author_detail_view_context_data**: Verifies that `available_languages` and `available_genres_tree` are correctly populated.

## Book Detail View (BookDetailViewTests)
- *Note: These tests run with DummyCache by default to ensure isolation.*
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

## Book Detail View Cache (BookDetailViewCacheTests)
1. **test_chapters_cache_population**: Verifies that a request to BookDetailView populates the cache.
2. **test_chapters_cache_hit**: Verifies that subsequent requests retrieve data from the cache (mocked extraction).
3. **test_cache_key_isolation**: Verifies that different books use different cache keys and don't overlap.

## Book Detail Sidebar (BookDetailSidebarTests)
1. **test_book_sidebar_contains_title**: Verify that the book title is present in the sidebar.
2. **test_book_sidebar_contains_author_links**: Verify that author links are present and point to the correct author detail pages.
3. **test_book_sidebar_multiple_authors**: Verify that multiple authors are displayed if present.

## Book Download View (BookDownloadViewTests)
1. **test_book_download_filename**: Parameterized test verifying downloading books with various titles and authors (including Cyrillic), ensuring correct `Content-Type` and `Content-Disposition` (RFC 6266 for non-ASCII); FB2 is delivered zip-wrapped (`application/fb2+zip`, `.fb2.zip`) with the original bytes inside the archive, EPUB is delivered as-is.
2. **test_book_download_multiple_authors**: Verify filename format for multiple authors: `FirstAuthor_et_al_-_Title`.
3. **test_book_download_404_no_file**: Verify 404 if the book has no file.
4. **test_book_download_404_invalid_id**: Verify 404 for non-existent book ID.

## Homepage (HomePageViewTests)
1. **test_latest_arrivals_filtering**: Verifies that only books created within the last 7 days are displayed in the Latest Arrivals section.
2. **test_latest_arrivals_sorting**: Verifies that books are sorted by creation date descending, and then by title ascending.
3. **test_homepage_status_and_template**: Verifies that the homepage returns a 200 OK status and uses the expected template.
4. **test_homepage_unauthenticated_view**: Verifies that Search and Latest Arrivals are visible to guests, while personal sections are hidden.
5. **test_homepage_authenticated_view**: Verifies that all sections, including Reading List and Favorite Authors, are visible to authenticated users.
6. **test_latest_arrivals_pagination_full_page**: Verifies pagination content on full page load (non-HTMX).
7. **test_latest_arrivals_pagination_htmx**: Verifies HTMX partial response for latest arrivals pagination, ensuring it returns only the #latest_arrivals partial.
8. **test_homepage_htmx_search_vs_pagination**: Verifies correct partial is returned based on HX-Target (search results vs latest arrivals).
9. **test_homepage_no_latest_arrivals**: Verifies that an appropriate message is shown when no new books have been added in the last 7 days.
10. **test_homepage_pagination_presence**: Verifies that pagination is present at both the top and bottom of the list when multiple pages exist.
11. **test_homepage_jump_to_page**: Verifies the presence and correct HTMX attributes of the Jump to Page functionality on the homepage.
12. **test_home_page_with_search_query**: Verify search results in context when q is provided, and that latest arrivals are still present.
13. **test_home_page_search_htmx**: Verify partial rendering for HTMX search requests.
14. **test_home_page_search_htmx_authenticated**: Verify partial rendering for HTMX search requests when authenticated.
15. **test_home_page_clear_search_htmx**: Verify that an empty q parameter via HTMX results in search results partial (which will clear it).
16. **test_home_page_no_query_htmx**: Verify that no q parameter via HTMX results in search results partial.
17. **test_triple_independent_pagination**: Verifies all three search paginators (Authors, Books, Series) work independently in a single request.
18. **test_htmx_partial_authors**: Verifies HTMX partial for authors search pagination (#search_authors_results).
19. **test_htmx_partial_books**: Verifies HTMX partial for books search pagination (#search_books_results).
20. **test_htmx_partial_series**: Verifies HTMX partial for series search pagination (#search_series_results).
21. **test_homepage_disclaimer_presence**: Verifies the disclaimer footer is present on the homepage.

## Book List View (BookListViewTests)
1. **test_book_list_view_status_code**: Verifies the view returns 200 OK and uses the correct template.
2. **test_book_list_view_all_books_default**: Verify all books are shown by default (paged).
3. **test_book_list_view_language_filter**: Verify filtering by language.
4. **test_book_list_view_genre_filter_with_subgenres**: Verify filtering by genre includes subgenres.
5. **test_book_list_view_alphabet_filter**: Verify filtering by alphabet prefix.
6. **test_book_list_view_combined_filter**: Verify combined AND logic for language, genre, and alphabet.
7. **test_book_list_view_htmx_partial**: Verify HTMX request returns partial fragment.
8. **test_book_list_view_author_string_formatting**: Verify "Title by Author" vs "Title by Author et al.".
9. **test_book_list_view_pagination_preserves_filters**: Verify pagination links preserve current filters.
10. **test_book_list_view_filter_summary_human_readable**: Verify that active filters in summary show human-readable names.
11. **test_alphabet_tree_oob_update**: Verify HTMX request returns OOB swap for alphabet tree containing filtered results.
12. **test_alphabet_tree_respects_genre**: Verify alphabet tree counts and nodes respect active genre filter.
13. **test_alphabet_tree_no_oob_on_tree_click**: Verify HTMX request from Alphabet Tree does NOT return itself.

## Book List View can_view_book Context (BookListViewCanViewBookTests)
1. **test_can_view_book_context_and_card_label** *(parameterized: with_perm, without_perm)*: The view exposes the correct `can_view_book` boolean and the book card shows `Read` for permitted users and `Preview` otherwise.

## OPDS Root Feed (tests_opds.py — OPDSRootFeedTest)

No database content required; the feed is purely structural (uses plain TestCase).

1. **test_root_feed_status_200**: GET `opds:root/` returns HTTP 200.
2. **test_root_feed_content_type**: Response `Content-Type` starts with `application/atom+xml`.
3. **test_root_feed_anonymous_has_login_entry**: Anonymous feed has 5 `<entry>` elements including `Login`, whose `subsection` href ends with `/opds/v1/login/`.
3a. **test_root_feed_authenticated_omits_login_entry**: With valid Basic credentials the feed has exactly 4 entries and no `Login` entry.
4. **test_root_feed_entry_titles**: The 5 anonymous entry titles are exactly `{Authors, Genres, Series, Books, Login}`.
5. **test_root_feed_navigation_link** *(parameterized: self, start)*: Feed contains exactly one `<link rel="self">` and one `<link rel="start">`, each `href` ending with `opds:root/`.
7. **test_root_feed_search_link_at_feed_level**: The feed has exactly one feed-level `<link rel="search" type="application/opensearchdescription+xml">` and no `Search` navigation `<entry>` (no `tag:bookshelf:search` id).
8. **test_root_feed_has_templated_atom_search_link**: The feed emits exactly one feed-level templated `<link rel="search" type="application/atom+xml">` whose href contains `search/?q={searchTerms}` (mirrors Flibusta; readers synthesize an inline "Search" row from it).
9. **test_root_feed_is_pretty_printed**: Raw response body contains `\n` (newlines) and `  <` (indentation).

## Access Control (test_access_control.py)
1. **test_book_detail_unauthenticated**: Verify that unauthenticated users are redirected to login.
2. **test_book_detail_authenticated_no_group**: Verify that authenticated users without 'book_access' see truncated content.
3. **test_book_detail_authenticated_with_group**: Verify that authenticated users with 'book_access' see full content.
4. **test_book_download_unauthenticated**: Verify that unauthenticated users cannot download books (redirect to login).
5. **test_book_download_authenticated_no_group**: Verify that authenticated users without 'book_access' get 403 Forbidden on download.
6. **test_book_download_authenticated_with_group**: Verify that authenticated users with 'book_access' can download books.
7. **test_book_item_labels**: Verify "Preview" vs "Read" labels in book_item.html based on user permissions.
8. **test_book_item_download_visibility**: Verify download link visibility in book_item.html based on user permissions.

## OPDS Author List and Tree Feeds (tests_opds.py — OPDSAuthorListFeedTest)

Canonical dataset (255 authors: A=137, B=58, C=19, Ш=15, 0-9=12, Other=14).

1. **test_author_alphabet_root_has_letter_entry** *(parameterized: A=137, B=58)*: GET `opds:root/authors/tree/` returns an entry for the letter with its book count in the content.
3. **test_author_alphabet_root_no_entry_for_missing_letter**: GET `opds:root/authors/tree/` does NOT contain a 'Z' or 'z' entry (demoted to Other).
4. **test_author_results_by_filter_status_200**: GET `opds:root/authors/?filter=b` returns HTTP 200.
5. **test_author_results_by_filter_has_correct_count**: GET `opds:root/authors/?filter=b` returns exactly 20 entries on page 1 of 58 total.
6. **test_author_results_entry_links_to_author_detail**: Each entry in the flat author list links to `opds:root/authors/<pk>/`.
7. **test_author_results_filter_not_found_returns_empty_feed**: GET `opds:root/authors/?filter=y` returns HTTP 200 with zero entries.
8. **test_author_results_sorted_alphabetically**: Entries in the flat list are in ascending last_name order.
9. **test_author_digits_node_list**: GET `opds:root/authors/?regex=^[0-9]` returns exactly 12 entries.
9a. **test_author_results_entry_content_has_book_count**: Each flat-list entry `<content type="text">` is `"<n> books"` matching that author's book count.
10. **test_author_feed_is_navigation** *(parameterized: list, tree)*: Flat author list (`?filter=b`) and tree root response Content-Type both contain `kind=navigation`.
12. **test_author_tree_node_status_200**: GET `opds:root/authors/tree/a/` returns HTTP 200 (expandable node).
13. **test_author_tree_leaf_node_returns_404**: GET `opds:root/authors/tree/c/` returns HTTP 404 (C=19 is a leaf with no children).
14. **test_author_tree_nonexistent_node_returns_404**: GET `opds:root/authors/tree/z/` returns HTTP 404 (no Z node at root).
15. **test_author_tree_sub_node_has_all_entry_first**: GET `opds:root/authors/tree/a/` first entry title is 'all A'.
16. **test_author_tree_sub_node_all_entry_links_to_filter**: The 'all A' entry in `opds:root/authors/tree/a/` links to `?filter=a`.
17. **test_author_full_set_no_filter_returns_paginated_results**: GET `opds:root/authors/` (no params) returns 200 with 20 entries on the first page.

## OPDS Book List and Tree Feeds (tests_opds.py — OPDSBookListFeedTest)

Canonical dataset (560 books: A=222, B=167, M=43, П=83, 0-9=14, Other=31; no book starts with Z). Covers the three book browse endpoints: flat results `opds:root/books/`, alphabet tree root `opds:root/books/tree/`, and alphabet sub-tree `opds:root/books/tree/<name>/`. Per the catalog-is-fully-browsable convention the acquisition link is always rendered.

1. **test_book_tree_status_200** *(parameterized: root, sub_node)*: GET `opds:root/books/tree/` and an expandable sub-node `tree/a/` return HTTP 200.
2. **test_book_tree_is_navigation_feed**: Tree root Content-Type contains `kind=navigation`.
3. **test_book_alphabet_root_has_a_entry**: Tree root contains an 'A' entry with count 222.
4. **test_book_alphabet_root_no_entry_for_missing_letter**: Tree root has no 'Z'/'z' entry.
5. **test_book_tree_entries_have_count_in_content**: Every tree root entry carries its item count in `<content>`.
6. **test_book_a_is_expanded_subtree**: GET `opds:root/books/tree/a/` returns nav sub-entries {all A, Al, An, Ar}, not a flat list.
7. **test_book_tree_al_sub_entries**: GET `opds:root/books/tree/al/` returns exactly {all Al, Ali, All}.
8. **test_book_tree_node_returns_404** *(parameterized: leaf_node, nonexistent_node)*: GET `opds:root/books/tree/m/` (leaf, M=43 ≤ 50) and `tree/z/` (no node) return 404.
9. **test_book_tree_sub_node_has_all_entry_first**: GET `opds:root/books/tree/a/` first entry is 'all A' with count 222.
10. **test_book_tree_sub_node_all_entry_links_to_filter**: The 'all A' entry links to `opds:root/books/?filter=a`.
11. **test_book_tree_child_links_to** *(parameterized: leaf_filter, expandable_subtree)*: The leaf 'Ar' child links to `?filter=ar`; the expandable 'Al' child links to `tree/al/`.
12. **test_leaf_results_href_percent_encodes_filter** *(parameterized: ascii, cyrillic)*: A leaf node's `?filter=` href percent-encodes non-ASCII prefixes (ASCII 'a' unchanged; Cyrillic 'а' → `%D0%B0`), so readers don't double-encode the value into a 404 on pagination.
13. **test_book_tree_root_has_other_entry_linking_to_subtree**: The 'Other' entry (count 31) links to `opds:root/books/tree/other/`.
14. **test_book_tree_other_subtree_all_entry_uses_regex**: GET `opds:root/books/tree/other/` first entry 'all Other' (count 31) links via `?regex=`.
15. **test_book_tree_entries_have_logo_thumbnail**: Every tree root entry carries the logo thumbnail link.
16. **test_book_results_is_acquisition_feed**: GET `opds:root/books/?filter=m` Content-Type contains `kind=acquisition`.
17. **test_book_results_by_filter_status_200**: GET `opds:root/books/?filter=m` returns HTTP 200.
18. **test_book_results_has_correct_count**: GET `opds:root/books/?filter=m` returns 20 entries (page 1 of 43).
19. **test_book_results_count_across_pages** *(parameterized: filter_m, cyrillic_filter, digits_regex, regex_beats_filter)*: total across pages — `?filter=m`→43, `?filter=<п>` (percent-encoded)→83, `?regex=^[0-9]`→14, `?filter=0-9&regex=^[0-9]`→14 (regex wins).
20. **test_book_results_excludes_other_letter**: GET `opds:root/books/?filter=m` returns no title starting with 'B'.
21. **test_book_results_sorted_by_title**: Entries in `opds:root/books/?filter=m` are ordered by title ascending.
22. **test_book_results_empty_filter_returns_empty_feed**: GET `opds:root/books/?filter=z` returns 200 with zero entries.
23. **test_book_results_full_set_no_filter_paginated**: GET `opds:root/books/` (no params) returns 200 with a full first page of 20.
24. **test_book_results_entry_links_to_book_detail**: Each thin entry's `rel="alternate"` link points to `opds:root/books/<pk>/`.
25. **test_book_results_acquisition_link_always_rendered**: Every results entry exposes exactly one acquisition link.
26. **test_book_results_entries_thin_by_default**: Results entries are thin (no content/full image/related; one thumbnail).
27. **test_book_results_thick_param_makes_entries_complete**: `?detail=thick` makes entries complete (full image + alternate).
28. **test_book_results_thick_param_propagates_to_pagination**: `?detail=thick` is preserved on the `next` pagination link.
29. **test_book_results_thin_pagination_links_have_no_detail**: Default (thin) feed pagination links carry no `detail` param.

## OPDS Series List and Tree Feeds (tests_opds.py — OPDSSeriesListFeedTest)

Canonical dataset (148 series: C=54, S=62, T=11, 0-9=10, Other=11; no series starts with Z). Covers the three series browse endpoints: flat results `opds:root/series/`, alphabet tree root `opds:root/series/tree/`, and alphabet sub-tree `opds:root/series/tree/<name>/`.

1. **test_series_tree_status_200** *(parameterized: root, sub_node)*: GET `opds:root/series/tree/` and an expandable sub-node `tree/s/` return HTTP 200.
2. **test_series_feed_is_navigation** *(parameterized: list, tree)*: Flat series list (`?filter=t`) and tree root Content-Type both contain `kind=navigation`.
3. **test_series_alphabet_root_has_s_entry**: Tree root contains an 'S' entry with count 62.
4. **test_series_alphabet_root_no_entry_for_missing_letter**: Tree root has no 'Z'/'z' entry.
5. **test_series_tree_entries_have_count_in_content**: Every tree root entry carries its item count in `<content>`.
6. **test_series_s_is_expanded_subtree**: GET `opds:root/series/tree/s/` returns nav sub-entries {all S, Sh, St, Sw}, not a flat list of 62.
7. **test_series_st_sub_entries**: GET `opds:root/series/tree/st/` returns exactly {all St, Sta, Ste}.
8. **test_series_tree_node_returns_404** *(parameterized: leaf_node, nonexistent_node)*: GET `tree/t/` (leaf, T=11 ≤ 50) and `tree/z/` (no node) return 404.
9. **test_series_tree_sub_node_has_all_entry_first**: GET `opds:root/series/tree/s/` first entry is 'all S' with count 62.
10. **test_series_tree_sub_node_all_entry_links_to_filter**: The 'all S' entry links to `opds:root/series/?filter=s`.
11. **test_series_tree_child_links_to** *(parameterized: leaf_filter, expandable_subtree)*: The leaf 'Sh' child links to `?filter=sh`; the expandable 'St' child links to `tree/st/`.
12. **test_series_results_by_filter_status_200**: GET `opds:root/series/?filter=t` returns HTTP 200.
13. **test_series_results_has_correct_count**: GET `opds:root/series/?filter=t` returns exactly 11 entries (T=11, one page).
14. **test_series_results_entry_links_to_series_detail**: Each flat-list entry links to `opds:root/series/<pk>/`.
15. **test_series_results_empty_filter_returns_empty_feed**: GET `opds:root/series/?filter=z` returns 200 with zero entries.
16. **test_series_digits_node_list**: GET `opds:root/series/?regex=^[0-9]` returns exactly 10 entries.
17. **test_series_full_set_no_filter_returns_paginated_results**: GET `opds:root/series/` (no params) returns 200 with a full first page of 20.
18. **test_series_results_entry_content_has_book_count**: Each flat-list entry `<content type="text">` is `"<n> books"` matching that series' total book count.
19. **test_series_results_zero_book_series_shows_count_0**: A series with no books (created locally) renders the mandatory count `"0 books"`.

## OPDS Series Detail Feed (tests_opds.py — OPDSSeriesDetailTest)

Canonical dataset. A series with ≥2 books is found via `.filter()`; an extra subseries is created inline so the subseries-navigation path is exercised. Per the catalog-is-fully-browsable convention the acquisition link is always rendered.

1. **test_series_detail_status_200**: GET `opds:root/series/<pk>/` returns HTTP 200.
2. **test_series_detail_404**: GET `opds:root/series/99999/` returns HTTP 404.
3. **test_series_detail_is_acquisition_feed**: Series detail Content-Type contains `kind=acquisition`.
4. **test_series_detail_has_subseries_nav_entry**: Feed contains the subseries as a navigation entry linking to `opds:root/series/<subpk>/`.
5. **test_series_detail_subseries_entry_has_count_and_logo**: The subseries navigation entry carries a `"0 books"` count and exactly one logo thumbnail link.
6. **test_series_detail_has_books**: Feed contains at least one book (acquisition) entry.
7. **test_series_detail_books_sorted_by_sequence_number**: Book entries appear in ascending `sequence_number` order.
8. **test_series_detail_book_title_prefixed_with_seq**: Each book entry `<title>` starts with `"#<seq> · "`.
9. **test_series_detail_acquisition_link_always_rendered**: Every series book entry exposes exactly one acquisition link.
10. **test_series_detail_book_entries_thin_by_default**: Default series book entries are thin — no `<content>`/`<calibre:series>`/`rel="related"`/full image; exactly one `rel="alternate"` link.
11. **test_series_detail_book_entries_thick_param**: `?detail=thick` makes book entries complete — full-size image link present and a series `rel="related"` link.

## OPDS Genre Hierarchy Feeds (tests_opds.py — OPDSGenreFeedTest)

Canonical dataset plus an inline `genre_empty` top-level genre (no subgenres, no books). Covers the genre root, subgenres-only detail (leaf → 302), genre-scoped alphabet tree, and flat genre book results. Note: a single leaf genre's per-letter counts never exceed the `get_alphabet_tree` expansion threshold (50) below the first letter, so the genre-scoped tree expands at most one level; the `Alid` group cited in the TDD examples is reachable within a genre via the `?filter=alid` results endpoint, not as a tree node.

1. **test_genre_root_status_200**: GET `opds:root/genres/` returns HTTP 200.
2. **test_genre_root_is_navigation**: Genre root Content-Type contains `kind=navigation`.
3. **test_genre_root_lists_top_level_genres_only**: Root feed lists top-level genres (incl. `genre_empty`) and excludes leaf genres.
4. **test_genre_root_entry_links_to_genre_detail**: Each root entry links to `opds:root/genres/<pk>/`.
5. **test_genre_root_entry_content_has_book_count**: The `sf_fantasy` entry `<content>` reports its descendant-inclusive count 279.
6. **test_genre_root_genre_with_no_books_still_listed**: `genre_empty` appears in the root feed with the mandatory count `0`.
7. **test_genre_root_entries_have_logo_thumbnail**: Every root entry carries the logo thumbnail link.
8. **test_genre_detail_with_subgenres_status_200**: GET `opds:root/genres/<sf_fantasy.pk>/` returns HTTP 200 (has subgenres).
9. **test_genre_detail_404**: GET `opds:root/genres/99999/` returns HTTP 404.
10. **test_genre_detail_lists_subgenres_only**: `sf_fantasy` detail lists exactly its 3 subgenres, each linking to its own detail feed.
11. **test_genre_detail_has_no_book_or_alphabet_entries**: `sf_fantasy` detail has no acquisition entries and no alphabet-tree nodes.
12. **test_genre_detail_without_subgenres_redirects_to_book_tree** *(parameterized: leaf, empty)*: GET a genre detail with no subgenres (`dystopia`, `genre_empty`) returns 302 to its `books/tree/`.
13. **test_genre_detail_redirect_preserves_detail_thick**: A leaf-genre (`dystopia`) 302 with `?detail=thick` redirects to `genres/<pk>/books/tree/?detail=thick`.
14. **test_genre_book_tree_status_200_navigation**: GET `opds:root/genres/<sf_fantasy.pk>/books/tree/` returns 200 with `kind=navigation`.
15. **test_genre_book_tree_has_alphabet_entries**: `sf_fantasy` book tree has an expandable 'A' node whose sub-tree shows an 'Al' entry.
16. **test_genre_book_tree_only_contains_own_books**: `dystopia` book tree shows only {A, B, M, П, 0-9, Other} with A=46 and M=10.
17. **test_genre_book_tree_node_returns_404** *(parameterized: leaf_node, nonexistent_node)*: GET a leaf (`tree/a/`) and a missing (`tree/z/`) node return 404.
18. **test_genre_book_tree_empty_genre_returns_empty_tree**: GET `genre_empty` book tree returns 200 with 0 entries.
19. **test_genre_book_tree_leaf_links_to_results**: A leaf letter node ('M') links to `opds:root/genres/<pk>/books/?filter=m`.
20. **test_genre_book_tree_non_leaf_links_to_subtree**: An expandable 'A' node links to its sub-tree, whose first entry is the synthetic 'all A'.
21. **test_genre_book_tree_regex_node_link_carries_regex_param**: The '0-9' leaf links via `?regex=`; the 'Other' node links to its `tree/other/` sub-tree.
22. **test_genre_books_results_is_acquisition_feed**: Genre book results Content-Type contains `kind=acquisition`.
23. **test_genre_books_results_by_filter_status_200**: GET `genres/<dystopia.pk>/books/?filter=alid` returns HTTP 200.
24. **test_genre_books_results_by_filter_filters_correctly**: `?filter=alid` returns only titles starting with 'Alid'.
25. **test_genre_books_results_empty_filter_returns_empty_feed**: `?filter=z` returns 200 with 0 entries.
26. **test_genre_books_results_by_regex_filters_by_regex**: `?regex=^[0-9]` total equals the genre's 0-9 tree count (2); all titles start with a digit.
27. **test_genre_books_results_regex_beats_filter**: `?filter=0-9` (no regex) uses `istartswith` and yields 0 entries.
28. **test_genre_books_results_thin_by_default**: Genre book entries are thin by default — no `<content>`/full image; exactly one `rel="alternate"`.
29. **test_genre_books_results_thick_param_makes_entries_complete**: `?detail=thick` makes genre book entries complete (full-size image link present).

## OPDS Genre Feed Counts (tests_opds.py — OPDSGenreFeedCountsTest)

Canonical dataset. Verifies genre book counts against `test_template.md` (distinct books per genre).

1. **test_genre_root_descendant_inclusive_count** *(parameterized: sf_fantasy, mysteries, action_adv)*: each top-level genre root entry reports its descendant-inclusive count (279=116+82+81, 208=130+78, 185=111+74).
2. **test_fantasy_book_tree_no_yu_entry**: `fantasy` book tree (root + Other sub-tree) contains no 'Ю' entry.
3. **test_nature_animals_book_tree_total_is_74**: `nature_animals` book tree top-level entry counts sum to 74.
4. **test_genre_books_results_dystopia_filter_count** *(parameterized: alid, alit)*: `dystopia` `?filter=<value>` feed total across pages matches expected (alid=5, alit=7).

## OPDS Author Detail and Sub-Feed Endpoints (tests_opds.py — OPDSAuthorDetailTest)

Canonical dataset.

1. **test_author_detail_status_200**: GET `opds:root/authors/<pk>/` returns HTTP 200.
2. **test_author_detail_404**: GET `opds:root/authors/99999/` returns HTTP 404.
3. **test_author_detail_has_three_sub_feeds**: Author detail feed has exactly 3 entries titled 'Books by Title', 'New Arrivals', 'Books by Series'.
3a. **test_author_detail_sub_feed_titles_match**: Sub-feed titles are exactly `['Books by Title', 'New Arrivals', 'Books by Series']` in order; legacy labels ('All Books (A–Z)', 'Recently Added') are absent.
4. **test_author_detail_is_navigation_feed**: Author detail response Content-Type contains `kind=navigation`.
5. **test_author_detail_sub_feed_status_200** *(parameterized: books_alpha, books_recent, series)*: GET each author sub-feed endpoint (`books/`, `books/recent/`, `series/`) returns HTTP 200.
6. **test_author_detail_sub_feed_books_alpha_is_acquisition**: Author books feed Content-Type contains `kind=acquisition`.
7. **test_author_detail_sub_feed_books_alpha_contains_author_books**: Total entry count across all pages equals `author.books.count()`.
8. **test_author_detail_sub_feed_books_alpha_excludes_other_author**: Author books feed does not contain a book belonging only to a different author.
9. **test_author_detail_sub_feed_books_alpha_sorted**: First page entries are sorted by title ascending.
11. **test_author_detail_sub_feed_books_recent_sorted_by_date**: First entry `<updated>` >= second entry `<updated>` (descending date order).
13. **test_author_detail_sub_feed_series_is_navigation**: Author series feed Content-Type contains `kind=navigation`.
14. **test_author_detail_sub_feed_series_has_series**: For `author_with_series`, the series feed has at least one author-scoped series entry (`series/<pk>/?author=<pk>`).
15. **test_author_detail_sub_feed_series_entry_has_book_count**: Each series entry `<content>` contains a positive integer (book count).
16. **test_author_detail_sub_feed_series_no_standalone_entry_when_none**: An author with no standalone books has no 'Standalone Books' entry.
17. **test_author_detail_sub_feed_series_has_standalone_entry_first**: For `author_with_series`, the first series feed entry is 'Standalone Books'.
18. **test_author_detail_sub_feed_series_standalone_entry_links_to_series_none**: 'Standalone Books' entry links to `opds:root/authors/<pk>/books/?series=none`.
19. **test_author_detail_sub_feed_series_standalone_entry_has_count**: 'Standalone Books' entry `<content>` contains the correct standalone book count.
20. **test_author_books_series_none_filter_only_standalone**: GET with `?series=none` returns only standalone books (count verified across all pages).
21. **test_author_books_acquisition_link_always_rendered**: GET `opds:root/authors/<pk>/books/` returns entries each containing exactly one acquisition link pointing to a `/download/` URL, regardless of authentication.
22. **test_author_books_acquisition_type_matches_file_type**: Each entry's acquisition link `type` reflects the book's `file_type` (`epub` → `application/epub+zip`, `fb2` → `application/fb2+zip`).
23. **test_author_books_acquisition_type_defaults_for_unknown_format**: Blank/unknown `file_type` falls back to `application/octet-stream` on the acquisition link.

## OPDS Entry Image / Logo (tests_opds.py — OPDSEntryImageTest)

Canonical dataset. Verifies the §8 "logo for every non-book entry" rule.

1. **test_entries_have_logo_thumbnail** *(parameterized: root, author_tree, author_results, author_detail, author_series)*: Every entry in each navigation feed carries one `<link rel="http://opds-spec.org/image/thumbnail" type="image/png">` whose href ends in `/static/img/Logo%2064x64x8.png`.
6. **test_logo_thumbnail_href_is_absolute_url**: The logo thumbnail href is an absolute URL (starts with `http`).
7. **test_book_entries_do_not_use_logo**: Book (acquisition) entries never carry the logo thumbnail link.

## OPDS Book Entry Verbosity (tests_opds.py — OPDSBookVerbosityTest)

Canonical dataset plus an inline described author/book (with `<script>`/`<iframe>`/list markup) and 25 extra books for pagination. Verifies the §6.5a thin-default / `?detail=thick` split and the §6.5 complete entry shape on author book feeds.

1. **test_author_books_feed_thin_by_default**: Default author book entries are thin — no `<content>`, no `<calibre:series>`, no `rel="related"` links, and no Atom `<author>` element.
2. **test_thin_entry_has_mandatory_alternate_link**: Each thin entry has exactly one `<link rel="alternate" type="application/atom+xml;type=entry;profile=opds-catalog">` whose href ends in `opds:root/books/<pk>/`.
3. **test_thin_entry_has_thumbnail_no_full_image**: A thin entry has a thumbnail link but no full-size `http://opds-spec.org/image` link.
4. **test_thin_pagination_links_have_no_detail_param**: Default (thin) paginated feed exposes a `next` link and no pagination link carries a `detail` param.
5. **test_author_books_feed_thick_has_author_related_links**: Thick entries carry author `rel="related"` links to `opds:root/authors/<pk>/` and emit no Atom `<author>` element.
6. **test_thick_entry_has_full_image_and_alternate**: Thick entries add the full-size `http://opds-spec.org/image` link and keep the mandatory `rel="alternate"` link.
7. **test_thick_param_propagates_to_pagination_links**: `detail=thick` is preserved on every `first`/`next`/`previous` pagination link, asserted across page 1 (first + next) and page 2 (first + previous).
8. **test_thick_series_book_has_calibre_and_series_related**: A series-linked book in thick mode has `<calibre:series>` + `<calibre:series_index>` and a series `rel="related"` link to `opds:root/series/<pk>/`.
9. **test_thick_entry_content_is_sanitized_xhtml**: A described book's thick `<content type="xhtml">` is an XHTML `<div>` where allowlisted tags (`p`, `strong`) survive and disallowed tags (`script`, `iframe`) and script text are stripped.
10. **test_thin_entry_has_category_tags**: Thin (default) listing entries carry `<category>` tags equal to their book's genre names, so readers surface genres from the listing entry.
11. **test_thick_entry_has_category_tags**: Each thick entry's `<category>` `term`s equal its book's genre names (name-ordered), confirming genres render on `?detail=thick` listings.
12. **test_book_list_feed_genres_no_n_plus_one**: A thick `opds:root/books/` listing prefetches genres — exactly one query touches the genre M2M table regardless of page size, guarding the `prefetch_related('genres')` requirement.

## OPDS Thick Propagation (tests_opds.py — OPDSThickPropagationTest)

Canonical dataset. Verifies the §6.5a Propagation rule — `?detail=thick` is a sticky, catalog-wide preference threaded through every browsable-catalog link and omitted from non-feed / always-complete links. Uses the implemented Root + Author feeds; a series+standalone author is found via `.filter()`.

1. **test_root_subsection_links_preserve_detail**: Every anonymous root entry `rel="subsection"` link (Authors, Genres, Series, Books, Login — 5 links) carries `detail=thick`.
2. **test_root_search_links_preserve_detail**: Both feed-level search links carry `detail=thick` — the `application/opensearchdescription+xml` descriptor link and the templated `application/atom+xml` link (which also keeps its `{searchTerms}` placeholder).
3. **test_root_self_and_start_links_preserve_detail**: The feed `rel="self"` and `rel="start"` links both carry `detail=thick`.
4. **test_root_logo_thumbnail_link_omits_detail**: The non-book logo thumbnail links never carry a `detail` param.
5. **test_author_tree_subsection_links_preserve_detail**: Every author-tree child `subsection` link and the synthetic "all" link carry `detail=thick`.
6. **test_author_results_links_preserve_detail**: Each author-result detail-feed `subsection` link and the `first`/`next` pagination links carry `detail=thick`.
7. **test_author_detail_subsection_links_preserve_detail**: All three author-detail `subsection` links (Books by Title, New Arrivals, Books by Series) carry `detail=thick`.
8. **test_author_series_links_preserve_detail**: The Standalone Books link and every author-scoped per-series `subsection` link (now pointing at `series/<pk>/?author=<pk>`) carry `detail=thick`.
9. **test_detail_survives_drilldown_to_acquisition_feed**: Following the `detail=thick`-bearing Books-by-Title link reaches `opds:root/authors/<pk>/books/?detail=thick`, whose book entries are complete (full-size image present) — proving the preference survives link-following to the terminal acquisition feed.
10. **test_navigation_links_omit_detail_by_default**: Without `?detail=thick`, no feed- or entry-level link on a navigation feed carries a `detail` param.

## OPDS Author-Scoped Series Navigation (tests_opds.py — OPDSAuthorScopedSeriesTest)

Controlled dataset: a series shared by two authors (Asimov: 2 series books + 1 standalone; Bradbury: 1 series book), plus an "Order Series" whose alphabetical and sequence orders differ, and a "Parent Series" with a "Child Series" subseries. Verifies that author→series navigation now links to the canonical series detail feed scoped via `?author=<pk>`, preserving `sequence_number` ordering, while the full series stays reachable unscoped.
1. **test_author_series_entry_links_to_author_scoped_books**: The author's series entry links to `series/<pk>/?author=<pk>` with an acquisition `type`.
2. **test_author_series_entry_count_is_author_scoped**: The series entry `<content>` reports the author's count (2), not the series total (3).
3. **test_author_scoped_series_lists_only_authors_books**: `series/<pk>/?author=<pk>` returns exactly the author's books in that series ({A One, A Two}), excluding the other author's book.
4. **test_author_scoped_series_excludes_standalone**: The author's standalone book is absent from the author-scoped view (total = 2).
5. **test_full_series_lists_all_authors_books**: `series/<pk>/` still lists every author's books in the series (total = 3).
6. **test_non_integer_author_param_ignored**: A non-integer `?author=abc` is ignored, returning the full series (all authors, 3 books).
7. **test_unknown_author_id_yields_empty_book_list**: A valid but non-existent `?author=<id>` returns an empty book list with HTTP 200 (not 404).
8. **test_author_scoped_series_is_sequence_ordered**: Author-scoped books keep `sequence_number` order (Bravo #1, Alpha #2) with the `#<seq> · ` title prefix, not alphabetical order.
9. **test_author_scoped_series_hides_subseries**: Under `?author=<pk>` the parent-series feed shows only the author's book, with no subseries navigation entry.
10. **test_full_series_shows_subseries**: Without `?author` the parent series still lists its subseries entry.

## OPDS Author-Scoped Series Feed Identity (tests_opds.py — OPDSAuthorScopedSeriesFeedIdentityTest)

Controlled dataset: a series with 25 Asimov books (forces pagination at page size 20) plus 5 Bradbury books in the same series. Verifies feed-identity and pagination contracts for the author-scoped series feed.
1. **test_author_scoped_feed_id_is_distinct**: The author-scoped feed `<id>` is `tag:bookshelf:series:<pk>:author:<pk>` and differs from the unscoped `tag:bookshelf:series:<pk>`.
2. **test_author_param_survives_pagination**: Following the `next` link keeps `?author=<pk>` in the link, results stay author-scoped (only Asimov titles across all pages), and the full 25-book scope spans at least two pages.

## OPDS Book Detail Feed (tests_opds.py — OPDSBookDetailTest)

`BaseTestCase` + small detail fixture (`book_1` with a real cover and two genres — `Контркультура`, `Современная русская и зарубежная проза`; `book_2` cover-less; `book_3` standalone and genre-less; authors Asimov/Bradbury; series Foundation + Robot Series subseries). Verifies the §6.5 complete book-detail feed at `GET opds:root/books/<pk>/`. Per the catalog-is-fully-browsable convention the acquisition link is always rendered, so there are no permission-gating cases.

1. **test_book_detail_status_200**: GET `opds:root/books/<pk>/` returns 200.
2. **test_book_detail_404**: GET `opds:root/books/99999/` returns 404.
3. **test_book_detail_is_acquisition_feed**: Content-Type contains `kind=acquisition`.
4. **test_book_detail_has_title**: The single entry `<title>` equals the book title.
5. **test_book_detail_has_author_related_link**: The entry has one `rel="related"` link to `opds:root/authors/<pk>/` with `kind=navigation` type and the author `full_name` as title.
6. **test_book_detail_one_related_link_per_author**: A two-author book renders exactly one author `rel="related"` link per author.
7. **test_book_detail_author_related_link_mandatory**: Every complete book entry has at least one author `rel="related"` link.
8. **test_book_detail_has_no_atom_author_element**: The entry emits no `<author>` Atom element.
9. **test_book_detail_content_is_xhtml_type**: The entry has `<content type="xhtml">` with a `<div>` and no `<summary>`.
10. **test_book_detail_content_has_description**: The `<content>` `<div>` text carries the book description text.
11. **test_book_detail_content_has_no_series_text**: The `<content>` contains no series text.
12. **test_book_detail_content_sanitizes_disallowed_html**: Disallowed tags (e.g. `<script>`) are stripped while allowlisted `<p>`/`<strong>` survive.
13. **test_book_detail_no_content_when_no_description**: A book with an empty description has no `<content>` element.
14. **test_book_detail_has_calibre_series**: The entry has `<calibre:series>` `Foundation` and `<calibre:series_index>` `1`.
15. **test_book_detail_calibre_series_name_stripped**: The `<calibre:series>` text has no leading/trailing whitespace.
16. **test_book_detail_one_calibre_series_pair_per_series**: A book in two series yields exactly two `<calibre:series>`/`<calibre:series_index>` pairs.
17. **test_book_detail_no_calibre_series_when_standalone**: A standalone book has no `<calibre:series>` and no series `rel="related"` link.
18. **test_book_detail_cover_link_is_absolute_url**: The full-size cover `rel="…/image"` href is an absolute URL.
19. **test_book_detail_has_thumbnail_link**: The entry carries a `rel="…/image/thumbnail"` link.
20. **test_book_detail_no_cover_uses_no_cover_fallback**: A cover-less book falls back to the `no_cover` placeholder hrefs for both full image and thumbnail (links never omitted).
21. **test_book_detail_has_series_related_link**: The entry has a `rel="related"` link to `opds:root/series/<pk>/` titled with the series name only.
22. **test_book_detail_author_and_series_related_links_distinguishable**: Author related links target `/authors/<pk>/`; series related links target `/series/<pk>/`.
23. **test_book_detail_acquisition_link_always_rendered**: The acquisition link is always present and points to `opds:root/books/<pk>/download/`.
24. **test_book_detail_has_no_alternate_link**: The detail feed (being the alternate target) carries no `rel="alternate"` link.
25. **test_book_detail_has_category_per_genre**: The entry emits exactly one `<category>` per genre and the `term`s equal the book's two genre names.
26. **test_book_detail_category_term_equals_label**: Each `<category>` has `term == label`, both equal to a real `Genre.name`, and no `scheme` attribute.
27. **test_book_detail_category_matches_example_format**: The non-ASCII `('Контркультура', 'Контркультура')` `term`/`label` pair from the task example round-trips intact through ElementTree/UTF-8.
28. **test_book_detail_no_category_when_no_genres**: A genre-less book emits zero `<category>` elements.

## OPDS Search Feeds (tests_opds.py — OPDSSearchTest)

Canonical dataset. Query prefixes `Abak` (authors), `Ch` (series), `Alid` (book titles) exist in the dataset; a unique `Zap` prefix with 25 fresh per-test books (created in `setUp`) drives pagination. Per the catalog-is-fully-browsable convention the acquisition link is always rendered, so there is no permission-gating case for the book sub-feed.

1. **test_search_root_returns_200**: GET `opds:root/search/?q=Abak` returns 200.
2. **test_search_root_has_section_entry** *(parameterized: books/series/authors)*: A single-entity query yields the matching `<Section> (N found)` entry linking to `opds:root/search/<section>/?q=<query>` (`Alid`→books, `Ch`→series, `Abak`→authors).
3. **test_search_root_section_omitted_when_empty**: `?q=Abak` (authors-only matches) yields no `Books` and no `Series` section entry.
4. **test_search_root_section_count_reflects_match_total**: `?q=Abak` labels the Authors section with the real match count (`Authors (21 found)`).
5. **test_search_root_returns_empty_feed** *(parameterized: whitespace/empty/no-match)*: A whitespace-only `q`, a missing `q`, and an unmatchable `q` each return 200 with zero entries.
6. **test_search_root_is_navigation_feed**: The search root feed advertises `kind=navigation`.
7. **test_search_section_entries_have_logo**: Search section entries carry the logo thumbnail link.
8. **test_search_authors_subfeed_entries_link_to_author**: `search/authors/?q=Abak` entries link to `opds:root/authors/<pk>/`.
9. **test_search_authors_subfeed_is_navigation**: The search-authors sub-feed advertises `kind=navigation`.
10. **test_search_series_subfeed_entries_link_to_series**: `search/series/?q=Ch` entries link to `opds:root/series/<pk>/`.
11. **test_search_books_subfeed_is_acquisition**: The search-books sub-feed advertises `kind=acquisition`.
12. **test_search_books_subfeed_acquisition_link_always_rendered**: Every search book entry carries exactly one acquisition link.
13. **test_search_books_subfeed_is_case_insensitive**: A lowercase `q=alid` matches the mixed-case `Alid*` titles (23 books) — `icontains`.
14. **test_search_books_subfeed_matches_substring**: `q=lid` matches the `Alid*` titles (23), proving substring (not prefix) matching.
15. **test_search_books_subfeed_excludes_non_matching**: Every returned entry's title contains the query; non-matching titles are absent (`?q=Alid` → exactly 23, all containing `Alid`).
16. **test_search_books_subfeed_thin_by_default**: `search/books/?q=Alid` entries are thin (no `<content>`, no full image, one `rel="alternate"`).
17. **test_search_books_subfeed_thick_param**: `search/books/?q=Alid&detail=thick` entries are complete (carry the full-size image link).
18. **test_search_books_subfeed_pagination**: `search/books/?q=Zap` page 1 has exactly 20 entries and a `rel="next"` link.
19. **test_search_books_subfeed_total_matches_count**: `search/books/?q=Zap` returns all 25 matching books across pages.
20. **test_search_subfeed_pagination_preserves_q** *(parameterized: authors/series/books)*: Every paginated sub-feed's `next` link preserves both `q` and `page=2` (`authors?q=Aban`, `series?q=Ch`, `books?q=Zap`).
21. **test_search_subfeed_empty_query_returns_empty_feed**: GET `opds:root/search/books/` (no `q`) returns 200 with zero entries.
22. **test_search_all_sections_present_and_drilldown**: A query (`Quokka`) matching one author, one series and one book surfaces all three `(1 found)` sections together, and drilling into each `search/<section>/` sub-feed resolves to exactly the matching author / series / book element.

## OPDS OpenSearch Description (tests_opds.py — OPDSOpenSearchDescriptionTest)

No database content required. Verifies the OpenSearch description document at `GET opds:root/search/description.xml`.

1. **test_opensearch_description_status_200**: GET `opds:root/search/description.xml` returns 200.
2. **test_opensearch_description_content_type**: The `Content-Type` starts with `application/opensearchdescription+xml`.
3. **test_opensearch_description_has_shortname**: The `<ShortName>` element text is `Bookshelf`.
4. **test_opensearch_description_has_url_template**: The `<Url>` `template` attribute contains `/opds/v1/search/?q={searchTerms}` (search resolves to the root Authors/Series/Books chooser, not a sub-feed).
5. **test_opensearch_description_template_is_absolute_url**: The `<Url>` `template` is an absolute `http(s)` URL.
6. **test_opensearch_description_template_bakes_detail_thick**: With `?detail=thick` the `<Url>` `template` contains both `q={searchTerms}` and `detail=thick`.
7. **test_opensearch_description_template_omits_detail_by_default**: Without `?detail=thick` the `<Url>` `template` carries no `detail` parameter.
8. **test_opensearch_description_uses_default_namespace**: The document uses the default OpenSearch namespace with unprefixed tags (`<OpenSearchDescription xmlns="…">`, `<Url …>`) — no `opensearch:`/`ns0:` prefixes — so readers that string-match for a bare `<Url template>` discover search.
9. **test_opensearch_description_url_type_is_opds_catalog**: The `<Url type>` is `application/atom+xml;profile=opds-catalog;kind=navigation` (OPDS 1.2 requires the OPDS Catalog media type; plain `application/atom+xml` is rejected by spec-compliant readers).

## OPDS Login View (tests_opds.py — OPDSLoginViewTest)

Verifies `GET opds:login/` — the Basic credential challenge / redirect view.

1. **test_login_anonymous_returns_401**: Anonymous GET returns HTTP 401.
2. **test_login_anonymous_sets_www_authenticate_basic**: The 401 response's `WWW-Authenticate` header starts with `Basic`.
3. **test_login_authenticated_redirects_to_root**: Valid Basic credentials (no follow) return 302 with `Location` ending `/opds/v1/`.
4. **test_login_redirect_preserves_detail_thick**: Valid credentials with `?detail=thick` return a 302 whose `Location` ends `/opds/v1/?detail=thick`.
5. **test_login_invalid_credentials_returns_401**: A wrong-password Basic header returns HTTP 401.

## OPDS Book Download (tests_opds.py — OPDSBookDownloadTest)

Verifies `GET opds:book_download` — the authenticated download endpoint (real EPUB file via `BaseTestCase`; `user_with_perm` in `Book access`, `user_no_perm` plain; Basic creds via `HTTP_AUTHORIZATION`).

1. **test_download_anon_returns_401**: Anonymous download returns 401 with `WWW-Authenticate` starting `Basic`.
2. **test_download_401_has_empty_body**: The 401 challenge body is empty (so readers don't persist it into the saved file) while the `WWW-Authenticate: Basic` header is preserved.
3. **test_download_user_no_perm_returns_403**: An authenticated user lacking the permission returns 403 (via `can_view_book`).
4. **test_download_403_has_empty_body**: The 403 no-permission response also has an empty body.
5. **test_download_user_with_perm_epub_returns_200**: A permitted user downloads the EPUB → 200, `Content-Disposition` contains `attachment`, body non-empty.
6. **test_download_no_file_returns_404**: A permitted user requesting a book with no file returns 404.
7. **test_download_invalid_pk_returns_404**: A non-existent book pk returns 404, confirming the empty-body override passes non-401/403 responses through unchanged.
8. **test_download_non_ascii_filename_uses_rfc6266**: A Cyrillic title yields an RFC 6266 `filename*=utf-8''` `Content-Disposition` header.
9. **test_download_fb2_delivered_as_zip**: A permitted FB2 download is served as `application/fb2+zip` with a `.fb2.zip` filename and a well-formed ZIP body whose single entry holds the original FB2 bytes.
