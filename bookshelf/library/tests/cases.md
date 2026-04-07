# Library App Test Cases

## Admin Interface (TestAdmin)
1. **test_book_admin_registered**: Verifies BookAdmin is registered.
2. **test_book_admin_list_display**: Verifies list display fields in BookAdmin.
3. **test_book_admin_readonly_fields**: Verifies readonly fields in BookAdmin.
4. **test_book_admin_autocomplete_fields**: Verifies autocomplete fields in BookAdmin.
5. **test_related_admins_have_search_fields**: Verifies search fields in related admins.
6. **test_book_series_admin_has_book_inline**: Verifies that BookSeriesBookInline is present in BookSeriesAdmin.inlines.
7. **test_book_series_book_inline_fields**: Verifies that BookSeriesBookInline has the expected fields and readonly fields.
8. **test_book_series_book_inline_ordering**: Verifies that BookSeriesBookInline is sorted by sequence_number.

## Models (TestModels)
1. **test_wrong_parent**: Verifies loop detection in hierarchical models (Genre, BookSeries, Author).
2. **test_proper_parent**: Verifies correct parent-child relationship saving.
3. **test_author_hierarchy_limit**: Verifies that author hierarchy is limited to two levels.
4. **test_book_str_method**: Verifies that Book.__str__ returns the book title.
