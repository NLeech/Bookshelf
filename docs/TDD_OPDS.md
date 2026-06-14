# Technical Design Document: OPDS v1.2 Catalog

## 1. Overview

This document describes the design of the OPDS v1.2 catalog interface for the Bookshelf project.

**Scope:** Initial implementation (Phase 1). No authentication — download links are conditionally rendered based on the `library.view_book` permission. Basic Authentication will be added as a separate task.

**Reference specifications:**
- [OPDS 1.2](https://specs.opds.io/opds-1.2)
- [Authentication for OPDS 1.0](https://drafts.opds.io/authentication-for-opds-1.0.html)

---

## 2. Architecture

### 2.1 Module location

```
bookshelf/library/opds/
    __init__.py
    urls.py
    views.py
    serializers.py
    renderers.py
    throttles.py
```

The OPDS module lives inside the existing `library` app as a self-contained sub-package. It registers at `/opds/v1/` via the root `bookshelf/urls.py`.

### 2.2 Framework

Implemented with **Django REST Framework (DRF)**. DRF is used for:
- Custom `XMLRenderer` producing Atom/OPDS XML.
- Throttling via DRF's `AnonRateThrottle` base.
- URL routing via DRF `SimpleRouter` for list/detail patterns.

Views are **DRF APIView subclasses** (not ViewSets), because OPDS feeds don't map cleanly to CRUD semantics.

### 2.3 Response format

All responses are `application/atom+xml` (OPDS catalog entries) or `application/atom+xml;profile=opds-catalog;kind=navigation` / `...;kind=acquisition` as specified by OPDS 1.2.

XML output must be **human-readable** (pretty-printed with indentation).

---

## 3. Throttling

```
# library/opds/throttles.py

class OPDSAnonRateThrottle(AnonRateThrottle):
    scope = 'opds_anon'

# settings.py
REST_FRAMEWORK = {
    ...
    'DEFAULT_THROTTLE_RATES': {
        'opds_anon': '60/min',       # per-minute burst
        'opds_anon_daily': '1000/day',  # daily cap
    }
}
```

Both throttles apply to every OPDS endpoint. Exceeding either returns `HTTP 429 Too Many Requests`.

A custom throttle class implements both limits simultaneously by overriding `get_cache_key` to produce separate keys for minute and day scopes.

---

## 4. URL Structure

Base prefix: `/opds/v1/`

| URL | View | Feed type |
|-----|------|-----------|
| `/opds/v1/` | `RootFeedView` | Navigation |
| `/opds/v1/authors/` | `AuthorAlphabetFeedView` | Navigation (alphabet tree) |
| `/opds/v1/authors/<letter>/` | `AuthorListFeedView` | Navigation |
| `/opds/v1/authors/<int:pk>/` | `AuthorDetailFeedView` | Navigation |
| `/opds/v1/authors/<int:pk>/series/` | `AuthorSeriesFeedView` | Navigation |
| `/opds/v1/authors/<int:pk>/books/` | `AuthorBooksFeedView` | Acquisition |
| `/opds/v1/authors/<int:pk>/books/recent/` | `AuthorRecentBooksFeedView` | Acquisition |
| `/opds/v1/genres/` | `GenreRootFeedView` | Navigation (top-level genres) |
| `/opds/v1/genres/<int:pk>/` | `GenreDetailFeedView` | Navigation (subgenres + alphabet tree) |
| `/opds/v1/genres/<int:pk>/books/` | `GenreBooksFeedView` | Acquisition |
| `/opds/v1/genres/<int:pk>/books/<letter>/` | `GenreBookListFeedView` | Acquisition |
| `/opds/v1/series/` | `SeriesAlphabetFeedView` | Navigation (alphabet tree) |
| `/opds/v1/series/<letter>/` | `SeriesListFeedView` | Navigation |
| `/opds/v1/series/<int:pk>/` | `SeriesDetailFeedView` | Navigation/Acquisition |
| `/opds/v1/books/` | `BookAlphabetFeedView` | Navigation (alphabet tree) |
| `/opds/v1/books/<letter>/` | `BookListFeedView` | Acquisition |
| `/opds/v1/books/<int:pk>/` | `BookDetailFeedView` | Acquisition |
| `/opds/v1/books/<int:pk>/download/` | `BookDownloadView` | Binary (file delivery) |
| `/opds/v1/search/` | `SearchFeedView` | Navigation (sections) + Acquisition (books) |
| `/opds/v1/search/description.xml` | `OpenSearchDescriptionView` | OpenSearch XML |

**Alphabet tree notes:**
- `<letter>` is a URL-safe prefix string (e.g., `a`, `ab`, `0-9`, `other`). Special nodes (`0-9`, `other`, `aa*`) use the same filter/regex mechanism as the existing `get_alphabet_tree` service.
- Authors, Books, and Series root feeds all render as alphabet trees.
- Genres use a dedicated hierarchy: root lists top-level genres; each genre detail lists its subgenres followed by an alphabet tree of books in that genre (including descendant genres).

**"All" node rule:**
When a tree node is expanded (i.e., it has child nodes), a synthetic **"all `<prefix>`"** entry is prepended as the first child. This entry links to the list URL for that prefix *without* any further filter or regex — meaning it returns the full unfiltered set for that prefix level (e.g., `all a` → all authors starting with `a`, regardless of what comes after). Where a node is not expanded (it is already a leaf), no "all" entry is added.

Example for Authors with `a` expanded into `aa`, `ab`, `ac`:
```
a  (150)
  ├── all a  → /opds/v1/authors/a/         (no filter param — returns all 150)
  ├── aa     → /opds/v1/authors/aa/        (50)
  │     ├── all aa  → /opds/v1/authors/aa/ (50)
  │     ├── aaa     → /opds/v1/authors/aaa/ (30)
  │     └── aab     → /opds/v1/authors/aab/ (20)
  ├── ab     → /opds/v1/authors/ab/        (60)   ← leaf, no "all ab"
  └── ac     → /opds/v1/authors/ac/        (40)   ← leaf, no "all ac"
```

---

## 5. Pagination

DRF `PageNumberPagination` with `page_size = 20` (configurable via `settings.OPDS_PAGE_SIZE`, default 20).

Pagination links are rendered as Atom `<link rel="next">`, `<link rel="previous">`, and `<link rel="first">` inside each feed.

Pagination applies to: Author lists, Book lists, Genre lists, Series lists, Search results, Author detail sub-feeds (books/alpha, books/recent), Series detail book list.

---

## 6. Feed Definitions

### 6.1 Root Feed (`/opds/v1/`)

Navigation feed. Fixed set of five entries:

```xml
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opds="http://opds-spec.org/2010/catalog">
  <id>tag:bookshelf:root</id>
  <title>Bookshelf Catalog</title>
  <updated>...</updated>
  <link rel="self" href="/opds/v1/" type="application/atom+xml;...;kind=navigation"/>
  <link rel="start" href="/opds/v1/" type="application/atom+xml;...;kind=navigation"/>

  <entry>
    <title>Authors</title>
    <id>tag:bookshelf:authors</id>
    <link rel="subsection" href="/opds/v1/authors/"
          type="application/atom+xml;...;kind=navigation"/>
    <content type="text">Browse by author</content>
  </entry>
  <entry>
    <title>Genres</title>
    ...
  </entry>
  <entry>
    <title>Series</title>
    ...
  </entry>
  <entry>
    <title>Books</title>
    ...
  </entry>
  <entry>
    <title>Search</title>
    <id>tag:bookshelf:search</id>
    <link rel="search" type="application/opensearchdescription+xml" href="/opds/v1/search/description.xml"/>
    <link rel="search" type="application/atom+xml" href="/opds/v1/search/?q={searchTerms}"/>
    <content type="text">Search the catalog</content>
  </entry>
</feed>
```

### 6.2 Alphabet Tree Feeds (Authors, Books, Series)

Uses the existing `get_alphabet_tree` service from `library.services`. Each tree node becomes a navigation `<entry>`:
- **Leaf node** → links directly to the list URL for that prefix (e.g., `/opds/v1/authors/ab/`).
- **Non-leaf node** → links to the tree URL for that prefix, which re-renders the sub-tree. Additionally, a **"all `<prefix>`"** child entry is prepended before the sub-nodes, linking to the list URL without further filtering.

The URL encoding of `<letter>` uses the `filter` string (URL-safe lowercase prefix). Regex-based special nodes (`aa*`, `0-9`, `other`) use the `regex` query parameter: `/opds/v1/authors/?regex=<encoded_regex>`.

The `<content>` of each entry includes the item count. The "all `<prefix>`" entry carries the same count as its parent node (since it represents the full set).

### 6.2a Genre Hierarchy Feeds

Genres use a three-level hierarchy instead of a flat alphabet tree:

**`/opds/v1/genres/` — `GenreRootFeedView` (Navigation)**

Lists all top-level genres (those with `parent=None`). Each entry links to `/opds/v1/genres/<pk>/`. The entry `<content>` includes the total book count for the genre (including all descendants), using `get_descendants` from `library.services`.

**`/opds/v1/genres/<pk>/` — `GenreDetailFeedView` (Navigation)**

For the given genre, renders:
1. One navigation entry per direct subgenre, each linking to `/opds/v1/genres/<subpk>/`.
2. Alphabet tree entries for books in this genre (and its descendants), using `get_alphabet_tree` on the filtered `Book` queryset. The tree is built from *only* the books belonging to this genre (including descendants) — so if no books in this genre start with "A", the "A" node will not appear. Each leaf links to `/opds/v1/genres/<pk>/books/<letter>/`. Non-leaf nodes follow the same "all `<prefix>`" rule as the main alphabet trees.

Returns `HTTP 404` if the genre does not exist.

**`/opds/v1/genres/<pk>/books/` — `GenreBooksFeedView` (Acquisition)**

Acquisition feed of all books belonging to the genre or any of its descendants. Sorted by title. Paginated.

**`/opds/v1/genres/<pk>/books/<letter>/` — `GenreBookListFeedView` (Acquisition)**

Acquisition feed of books filtered by both genre (including descendants) and the given alphabet prefix. Sorted by title. Paginated.

### 6.3 Author Detail Feed (`/opds/v1/authors/<pk>/`)

Navigation feed with sub-feeds mirroring the author detail page tabs:

| Entry | Link href | Type |
|-------|-----------|------|
| All Books (A–Z) | `/opds/v1/authors/<pk>/books/` | acquisition |
| Recently Added | `/opds/v1/authors/<pk>/books/recent/` | acquisition |
| Books by Series | `/opds/v1/authors/<pk>/series/` | navigation |

**`/opds/v1/authors/<pk>/series/` — `AuthorSeriesFeedView` (Navigation)**

Lists each series the author has books in, linking to `/opds/v1/series/<pk>/`. The entry `<content>` includes the book count for that author in that series.

If the author has books not linked to any series, appends a final entry titled **"Standalone Books"** linking to `/opds/v1/authors/<pk>/books/` with content text `"N standalone book(s)"`. This entry is only rendered when standalone books exist.

### 6.4 Series Detail Feed (`/opds/v1/series/<pk>/`)

Acquisition feed containing:
1. Subseries entries (navigation links) — if any.
2. Book entries sorted by `sequence_number`, with the sequence number prefixed in the `<title>`: `"#3 · The Return of the King"`.

### 6.5 Book Detail Feed (`/opds/v1/books/<pk>/`)

Acquisition feed entry containing:
- `<title>` — book title.
- `<author>` — one element per author, each with `<name>` and OPDS `<uri>` pointing to `/opds/v1/authors/<pk>/`.
- `<summary>` — book description (truncated to 1000 chars in the feed; full text on the detail page).
- `<link rel="http://opds-spec.org/image">` — cover image URL (if present).
- `<link rel="http://opds-spec.org/image/thumbnail">` — cover preview thumbnail URL (if present).
- `<link rel="related">` — one per series, pointing to `/opds/v1/series/<pk>/`, with the sequence number in `title`.
- `<link rel="http://opds-spec.org/acquisition">` — **only rendered if the request user has `library.view_book` permission.** Points to `/opds/v1/books/<pk>/download/`.

### 6.6 Book Download (`/opds/v1/books/<pk>/download/`)

Not an Atom feed — streams the raw file content.

- Delegates to `library.services.get_book_file_content` for ZIP extraction and decryption.
- Returns `HTTP 403` if the request user lacks `library.view_book`.
- Returns `HTTP 404` if the book has no file.
- Sets `Content-Disposition: attachment; filename="..."` using the sanitized filename from `get_book_file_content`.

### 6.7 Search Feed (`/opds/v1/search/?q=<query>`)

Searches Authors, Books, and Series using `library.services.search_entities`. Results are presented as **three separate navigation sections** inside a single feed, each only rendered when its result set is non-empty:

1. **Authors section** — navigation entry per matching author, linking to `/opds/v1/authors/<pk>/`. The section header entry title is `"Authors (N found)"`.
2. **Series section** — navigation entry per matching series, linking to `/opds/v1/series/<pk>/`. Header title: `"Series (N found)"`.
3. **Books section** — acquisition entry per matching book. Header title: `"Books (N found)"`. Book entries include the acquisition link only if the request user has `library.view_book`.

Each section header is a navigation `<entry>` with no link (`<link>` omitted) — it serves as a visual separator carrying the count. Actual result entries follow immediately after their section header within the same feed.

Returns an empty feed (not an error) for no results or missing `q`.

**`/opds/v1/search/description.xml` — `OpenSearchDescriptionView`**

Returns the OpenSearch Description Document as `application/opensearchdescription+xml`. This is the endpoint referenced by `<link rel="search" type="application/opensearchdescription+xml">` in the root feed. Required for Calibre and KOreader auto-discovery.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>Bookshelf</ShortName>
  <Description>Search the Bookshelf catalog</Description>
  <Url type="application/atom+xml"
       template="https://{host}/opds/v1/search/?q={searchTerms}"/>
  <Language>*</Language>
  <OutputEncoding>UTF-8</OutputEncoding>
  <InputEncoding>UTF-8</InputEncoding>
</OpenSearchDescription>
```

The `template` URL is built using `request.build_absolute_uri` so it works in any deployment environment.

---

## 7. XML Renderer

```python
# library/opds/renderers.py

class OPDSRenderer(BaseRenderer):
    media_type = 'application/atom+xml'
    format = 'atom'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        # Accepts a pre-built ElementTree or dict from the view
        # Returns pretty-printed UTF-8 XML bytes
        ...
```

Views build the feed as an `xml.etree.ElementTree` structure and pass it to the renderer. The renderer handles indentation via `ET.indent()` (Python 3.9+).

---

## 8. Atom Feed Conventions

### Namespaces used

| Prefix | URI |
|--------|-----|
| (default) | `http://www.w3.org/2005/Atom` |
| `opds` | `http://opds-spec.org/2010/catalog` |
| `dc` | `http://purl.org/dc/terms/` |
| `opensearch` | `http://a9.com/-/spec/opensearch/1.1/` |

### `<id>` tag strategy

Use `tag:` URIs to avoid real domain dependency:
- Root: `tag:bookshelf:root`
- Author: `tag:bookshelf:author:<pk>`
- Book: `tag:bookshelf:book:<pk>`
- Series: `tag:bookshelf:series:<pk>`
- Genre: `tag:bookshelf:genre:<pk>`

### `<updated>` timestamp

- Root feed: latest `created_at` across all models (or a fixed fallback).
- Entity feeds: latest `updated_at` of the objects in the feed.
- Individual entry: the model's `updated_at`.

### `<link rel="self">` and `<link rel="start">`

Every feed includes both. `start` always points to `/opds/v1/`.

---

## 9. Permissions Model

For Phase 1 (no authentication challenge):

| Action | Requirement |
|--------|-------------|
| Browse any feed | No authentication required |
| See acquisition `<link>` in book entries | User must have `library.view_book` perm |
| `/opds/v1/books/<pk>/download/` | User must have `library.view_book` perm; otherwise `HTTP 403` |

The `library.view_book` permission is granted via the `Book access` group (mirrors the web app).

When the authentication task is implemented, protected endpoints will return `HTTP 401` with a `WWW-Authenticate` header per the Authentication for OPDS spec.

---

## 10. Test Plan

Test file: `bookshelf/library/tests/tests_opds.py`
Base class: `BaseTestCase` (from `bookshelf.tests.base_test`) for any test class that creates books with files. Pure feed-structure tests may use plain `TestCase`.

All XML assertions parse the response body with `xml.etree.ElementTree` and query using XPath with the correct namespace map.

### 10.1 Fixture Strategy

Two complementary fixture sets are used depending on what is being tested:

**A. Canonical dataset (factory)** — used by structural/alphabetic tests that need realistic tree depth and counts. Call `create_test_dataset()` from `library.tests.test_data_factory` in `setUpTestData`. Provides:

```
Authors : 255  (A=137, B=58, C=19, Ш=15, 0-9=12, Other=14)
  A tree: A(137) → Ab(110) → Aba(60) → Abak(21)/Aban(39)/All 'Aba'(60)
                              Abi(42) / Aby(8) / All 'Ab'(110)
                   Ac(11) / Ad(16) / All 'A'(137)
           B(58) / C(19) / Ш(15) / 0-9(12) / Other(14)

Books   : 560  (English=473, Ukrainian=87)
  A tree: A(222) → Al(96) → Ali(57) → Alid(23)/Alit(34)/All 'Ali'(57)
                             All(39) / All 'Al'(96)
                   An(83) / Ar(43) / All 'A'(222)
           B(167) / M(43) / П(83) / 0-9(14) / Other(31)

Series  : 108  (C=14, S=62, T=11, 0-9=10, Other=11)
  C tree: C(14) → Ch(6)/Cr(8)/All 'C'(14)
  S tree: S(62) → Sh(6) / St(54) → Sta(28)/Ste(26)/All 'St'(54)
                            Sw(2) / All 'S'(62)
           T(11) / 0-9(10) / Other(11)

Genres  : 3 top-level → 7 leaf genres (see test_template.md for book counts per leaf/letter)
```

**B. Small detail fixture** — used by detail/download/permission tests that need specific objects with known PKs, files, and relationships. Defined inline in each test class's `setUpTestData`:

```
- lang_en: Language(code='en', name='English')
- author_a: Author(last_name='Asimov', first_name='Isaac')
- author_b: Author(last_name='Bradbury', first_name='Ray')
- series_1: BookSeries(name='Foundation')
- series_2: BookSeries(name='Robot Series', parent=series_1)  # subseries
- genre_1: Genre(name='Science Fiction', code='sf')
- genre_2: Genre(name='Classic SF', code='sf_classic', parent=genre_1)
- book_1: Book(title='Foundation', language=lang_en, description='...')
    - authors: [author_a]
    - series: series_1 (seq=1)
    - genres: [genre_1]
    - file: (epub fixture)
    - cover: (image fixture)
- book_2: Book(title='I, Robot', language=lang_en)
    - authors: [author_a]
    - series: series_1 (seq=2)
- book_3: Book(title='Fahrenheit 451', language=lang_en)
    - authors: [author_b]
- user_no_perm: User (authenticated, no groups)
- user_with_perm: User (authenticated, member of 'Book access' group)
```

### 10.2 Test Classes

---

#### `OPDSRootFeedTest`

No database content required (structure-only). Uses plain `TestCase`.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_root_feed_status_200` | GET `/opds/v1/` → 200 |
| 2 | `test_root_feed_content_type` | Response `Content-Type` starts with `application/atom+xml` |
| 3 | `test_root_feed_has_five_catalog_entries` | Feed contains exactly 5 `<entry>` elements (Authors, Genres, Series, Books, Search) |
| 4 | `test_root_feed_entry_titles` | Each entry has the expected `<title>` text |
| 5 | `test_root_feed_self_link` | Feed contains `<link rel="self" href="/opds/v1/">` |
| 6 | `test_root_feed_start_link` | Feed contains `<link rel="start" href="/opds/v1/">` |
| 7 | `test_root_feed_search_entry_has_opensearch_link` | Search entry has `<link type="application/opensearchdescription+xml">` |
| 8 | `test_root_feed_is_pretty_printed` | Raw XML response body contains newlines and indentation (human-readable check) |

---

#### `OPDSAlphabetTreeTest` (parameterized)

**Fixture:** canonical dataset via `create_test_dataset()`. Tests the three alphabet-tree root endpoints (genres use a separate hierarchy, tested below). Parameterized over:
- `('authors', '/opds/v1/authors/')`
- `('books', '/opds/v1/books/')`
- `('series', '/opds/v1/series/')`

The factory dataset guarantees deep expansion on multiple letters, so the "all" node and multi-level sub-trees are exercised without creating extra data.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_alphabet_feed_status_200[<name>]` | GET `<url>` → 200 |
| 2 | `test_alphabet_feed_is_navigation[<name>]` | `Content-Type` contains `kind=navigation` |
| 3 | `test_alphabet_feed_has_entries[<name>]` | Feed contains at least one `<entry>` |
| 4 | `test_alphabet_feed_entries_have_subsection_links[<name>]` | Each entry has `<link rel="subsection">` or `<link rel="http://opds-spec.org/facet">` |
| 5 | `test_alphabet_feed_self_link[<name>]` | Feed has `<link rel="self" href="<url>">` |
| 6 | `test_alphabet_feed_quantity_in_content[<name>]` | Each entry `<content>` contains the item count |
| 7 | `test_alphabet_feed_only_reflects_existing_data[<name>]` | Feed does not contain entries for letters absent from the dataset (authors: no `"z"`; books: no `"z"`; series: no `"z"`); `"0-9"` IS present for all three |

---

#### `OPDSAlphabetTreeCountsTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Verifies that the tree structure and entry counts precisely match the canonical template values for each entity type.

Authors tree (from `test_template.md`):
- Root: `A(137)`, `B(58)`, `C(19)`, `Ш(15)`, `0-9(12)`, `Other(14)` — no `D`, `E`, etc.
- `/opds/v1/authors/a/`: entries `Ab(110)`, `Ac(11)`, `Ad(16)`, `all a(137)`
- `/opds/v1/authors/ab/`: entries `Aba(60)`, `Abi(42)`, `Aby(8)`, `all ab(110)`
- `/opds/v1/authors/aba/`: entries `Abak(21)`, `Aban(39)`, `all aba(60)` — leaf sub-tree

Books tree (from `test_template.md`):
- Root: `A(222)`, `B(167)`, `M(43)`, `П(83)`, `0-9(14)`, `Other(31)` — no `C`, `D`, etc.
- `/opds/v1/books/a/`: entries `Al(96)`, `An(83)`, `Ar(43)`, `all a(222)`
- `/opds/v1/books/al/`: entries `Ali(57)`, `All(39)`, `all al(96)`
- `/opds/v1/books/ali/`: entries `Alid(23)`, `Alit(34)`, `all ali(57)`

Series tree (from `test_template.md`):
- Root: `C(14)`, `S(62)`, `T(11)`, `0-9(10)`, `Other(11)` — no `A`, `B`, etc.
- `/opds/v1/series/c/`: entries `Ch(6)`, `Cr(8)`, `all c(14)`
- `/opds/v1/series/s/`: entries `Sh(6)`, `St(54)`, `Sw(2)`, `all s(62)`
- `/opds/v1/series/st/`: entries `Sta(28)`, `Ste(26)`, `all st(54)`

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_authors_root_entry_count` | `/opds/v1/authors/` contains exactly 6 top-level entries: A, B, C, Ш, `0-9`, Other |
| 2 | `test_authors_root_a_count_is_137` | `"A"` entry `<content>` contains `137` |
| 3 | `test_authors_root_digits_count_is_12` | `"0-9"` entry `<content>` contains `12` |
| 4 | `test_authors_a_sub_entries` | `/opds/v1/authors/a/` contains entries `Ab(110)`, `Ac(11)`, `Ad(16)`, `all a(137)` — no others |
| 5 | `test_authors_ab_sub_entries` | `/opds/v1/authors/ab/` contains entries `Aba(60)`, `Abi(42)`, `Aby(8)`, `all ab(110)` — no others |
| 6 | `test_authors_aba_sub_entries` | `/opds/v1/authors/aba/` contains entries `Abak(21)`, `Aban(39)`, `all aba(60)` — no others |
| 7 | `test_books_root_entry_count` | `/opds/v1/books/` contains exactly 6 top-level entries: A, B, M, П, `0-9`, Other |
| 8 | `test_books_a_count_is_222` | `"A"` entry `<content>` contains `222` |
| 9 | `test_books_root_digits_count_is_14` | `"0-9"` entry `<content>` contains `14` |
| 10 | `test_books_a_sub_entries` | `/opds/v1/books/a/` contains entries `Al(96)`, `An(83)`, `Ar(43)`, `all a(222)` — no others |
| 11 | `test_books_ali_sub_entries` | `/opds/v1/books/ali/` contains entries `Alid(23)`, `Alit(34)`, `all ali(57)` — no others |
| 12 | `test_series_root_entry_count` | `/opds/v1/series/` contains exactly 5 top-level entries: C, S, T, `0-9`, Other |
| 13 | `test_series_root_digits_count_is_10` | `"0-9"` entry `<content>` contains `10` |
| 14 | `test_series_s_count_is_62` | `"S"` entry `<content>` contains `62` |
| 15 | `test_series_s_sub_entries` | `/opds/v1/series/s/` contains entries `Sh(6)`, `St(54)`, `Sw(2)`, `all s(62)` — no others |
| 16 | `test_series_st_sub_entries` | `/opds/v1/series/st/` contains entries `Sta(28)`, `Ste(26)`, `all st(54)` — no others |

*(Other node structure and counts are covered in depth by `OPDSOtherNodeTest`.)*

---

#### `OPDSAlphabetAllNodeTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Uses the naturally deep `A→Ab→Aba` author tree (no extra data needed).

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_expanded_node_has_all_child` | `/opds/v1/authors/a/` is expanded (has Ab/Ac/Ad children); feed contains entry titled `"all a"` |
| 2 | `test_all_node_is_first_child` | `"all a"` entry is the first `<entry>` in the `/opds/v1/authors/a/` feed |
| 3 | `test_all_node_link_has_no_filter_param` | `"all a"` entry `<link href>` is `/opds/v1/authors/a/` with no `filter` or `regex` query params |
| 4 | `test_all_node_count_equals_parent_count` | `"all a"` entry `<content>` count is `137` (same as parent `A` node) |
| 5 | `test_leaf_node_has_no_all_child` | `/opds/v1/authors/ac/` is a leaf (Ac=11, not expanded) → feed contains no entry titled `"all ac"` |
| 6 | `test_all_node_present_at_second_level` | `/opds/v1/authors/ab/` is expanded (has Aba/Abi/Aby children); `"all ab"` is first `<entry>`, count=110 |
| 7 | `test_all_node_present_at_third_level` | `/opds/v1/authors/aba/` is expanded (has Abak/Aban children); `"all aba"` is first `<entry>`, count=60 |
| 8 | `test_books_expanded_node_has_all_child` | `/opds/v1/books/a/` has `"all a"` as first entry, count=222 |
| 9 | `test_series_expanded_node_has_all_child` | `/opds/v1/series/s/` has `"all s"` as first entry, count=62 |
| 10 | `test_digits_node_is_leaf_no_all_entry` | `"0-9"` node (authors, books, series) is always a leaf (no sub-entries) → following its `?regex=` link returns a flat list with no `"all 0-9"` entry |

---

#### `OPDSOtherNodeTest`

**Fixture:** canonical dataset via `create_test_dataset()`.

Background on how `get_alphabet_tree` builds the `Other` node:

- First-level alpha prefixes with count **below** `min_first_level_quantity` (default 10) are demoted into the `Other` node instead of appearing at the root. They become child entries of `Other`.
- Non-alpha (non-digit) items produce a `* (all non-alpha)` child entry inside `Other` with `regex=r'^[^[:alpha:][:digit:]]'`.
- The `Other` node itself carries a composite `regex` that covers both non-alpha items and all demoted alpha prefixes. This regex is URL-encoded and passed as `?regex=` to fetch the Other node's sub-tree.
- The "all Other" entry (first child of the expanded Other node, per the "all `<prefix>`" rule) links back to the Other node URL (`?regex=<other_regex>`) with no further filter — returning the full 14/31/11 items.

**Authors Other (14):** `* (all non-alpha)` = 3 (`!_1`, `(_2`, `+_3`) · `Z` = 8 · `Ї` = 2 · `Э` = 1
— `other_node.regex = r'^([^[:alpha:][:digit:]]|z|ї|э)'`

**Books Other (31):** `* (all non-alpha)` = 14 (`!`×7, `(`×5, `-`×2) · `Q` = 7 · `X` = 8 · `Ю` = 2
— `other_node.regex = r'^([^[:alpha:][:digit:]]|q|x|ю)'`

**Series Other (11):** `* (all non-alpha)` = 4 (`(`×2, `_`×2) · `N` = 4 · `В` = 3
— `other_node.regex = r'^([^[:alpha:][:digit:]]|n|в)'`

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_authors_root_has_other_entry` | `/opds/v1/authors/` root feed contains an entry named `"Other"` with count 14 |
| 2 | `test_books_root_has_other_entry` | `/opds/v1/books/` root feed contains an entry named `"Other"` with count 31 |
| 3 | `test_series_root_has_other_entry` | `/opds/v1/series/` root feed contains an entry named `"Other"` with count 11 |
| 4 | `test_other_entry_link_uses_regex_param` | `"Other"` entry `<link href>` contains `?regex=` query parameter (not a plain path segment) |
| 5 | `test_other_node_feed_has_non_alpha_child` | GET `?regex=<other_regex>` for authors → feed contains `"* (all non-alpha)"` child entry with count 3 |
| 6 | `test_other_node_feed_has_z_child` | Authors Other feed contains child entry `"Z"` with count 8 |
| 7 | `test_other_node_feed_has_all_other_first` | Authors Other feed first `<entry>` is `"all Other"` (count 14) |
| 8 | `test_all_other_link_matches_other_node_url` | `"all Other"` entry `<link href>` is identical to the `"Other"` entry link from the root feed (same `?regex=` value, no additional params) |
| 9 | `test_all_other_count_equals_other_total` | `"all Other"` entry `<content>` count equals 14 (authors), 31 (books), or 11 (series) matching the Other node total — parameterized |
| 10 | `test_non_alpha_child_link_uses_regex_param` | `"* (all non-alpha)"` entry `<link href>` contains `?regex=%5E%5B%5E%5B%3A%5B%3Aalpha%3A%5D%5B%3Adigit%3A%5D%5D` (URL-encoded `^[^[:alpha:][:digit:]]`) or equivalent |
| 11 | `test_non_alpha_list_returns_only_non_alpha_items` | GET `?regex=^[^[:alpha:][:digit:]]` for authors → feed contains exactly 3 entries (the `!_1`, `(_2`, `+_3` authors); no `Z`, `Ї`, `Э` authors |
| 12 | `test_non_alpha_books_list_count` | GET `?regex=^[^[:alpha:][:digit:]]` for books → feed page 1 has 14 entries total (across pages), all with non-alpha titles (`!*`, `(*`, `-*`) |
| 13 | `test_non_alpha_series_list_count` | GET `?regex=^[^[:alpha:][:digit:]]` for series → feed has 4 entries (`(1`, `(2`, `_1`, `_2`) |
| 14 | `test_all_other_list_returns_complete_other_set` | GET `?regex=<other_regex>` for authors → feed contains entries for all 14 Other authors (Z×8, Ї×2, Э×1, non-alpha×3 across pages) |
| 15 | `test_z_child_is_leaf_no_all_z_entry` | Authors Other feed: `"Z"` child entry is a leaf (count=8 < `min_quantity`) → following its link returns a flat list with no `"all z"` entry |
| 16 | `test_demoted_alpha_child_link_uses_filter_param` | `"Z"` (and `"Ї"`, `"Э"`) child entries in Authors Other use `filter=z` path segment (not `?regex=`), since they are regular alpha-leaf nodes |
| 17 | `test_books_other_q_child_count` | Books Other feed contains `"Q"` entry with count 7 |
| 18 | `test_books_other_x_child_count` | Books Other feed contains `"X"` entry with count 8 |
| 19 | `test_series_other_n_child_count` | Series Other feed contains `"N"` entry with count 4 |
| 20 | `test_series_other_cyrillic_в_child_count` | Series Other feed contains `"В"` entry with count 3 |
| 21 | `test_digits_node_is_separate_from_other` | Root feed for authors, books, and series: the `"0-9"` entry exists as a **sibling** of `"Other"`, not as a child inside it; the `Other` feed does NOT contain a `"0-9"` child entry |

---

#### `OPDSAuthorListFeedTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Uses Authors: A=137, B=58, 0-9=12; no author starts with Z.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_author_alphabet_root_has_a_entry` | GET `/opds/v1/authors/` → feed contains entry for `"a"` with count 137 |
| 2 | `test_author_alphabet_root_has_b_entry` | Root feed contains entry for `"b"` with count 58 |
| 3 | `test_author_alphabet_root_no_entry_for_missing_letter` | Root feed does NOT contain a `"z"` entry |
| 4 | `test_author_list_by_letter_status_200` | GET `/opds/v1/authors/b/` → 200 (B is a leaf — 58 authors, not expanded) |
| 5 | `test_author_list_by_letter_has_correct_count` | GET `/opds/v1/authors/b/` → feed contains exactly 20 entries (page 1 of 58; pagination applies) |
| 6 | `test_author_list_entry_links_to_author_detail` | Each entry `<link href>` points to `/opds/v1/authors/<pk>/` |
| 7 | `test_author_list_letter_not_found_returns_empty_feed` | GET `/opds/v1/authors/y/` → 200 with 0 `<entry>` elements (no author starts with Y in factory dataset) |
| 8 | `test_author_list_sorted_alphabetically` | Entries on `/opds/v1/authors/b/` are ordered by author last name ascending (Ba* before Be*) |
| 9 | `test_author_digits_node_list` | GET `/opds/v1/authors/?regex=^[0-9]` → 200 with exactly 12 entries (all digit-prefix authors) |

---

#### `OPDSGenreFeedTest`

**Fixture:** small detail fixture + additional objects:
- `genre_3: Genre(name='Standalone Fiction', code='standalone', parent=None)` — top-level, no books.
- `book_4: Book(title='Classic Dreams', language=lang_en)` with `genres=[genre_2]` (child of `genre_1`). Title starts with `C`, not `F` — used to verify the genre alphabet tree is filtered.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_genre_root_status_200` | GET `/opds/v1/genres/` → 200 |
| 2 | `test_genre_root_is_navigation` | `Content-Type` contains `kind=navigation` |
| 3 | `test_genre_root_lists_top_level_genres_only` | Feed entries include `genre_1` (SF) and `genre_3` (Standalone); does NOT include `genre_2` (Classic SF, child of SF) |
| 4 | `test_genre_root_entry_links_to_genre_detail` | Each entry has `<link rel="subsection" href="/opds/v1/genres/<pk>/">` |
| 5 | `test_genre_root_entry_content_has_book_count` | `genre_1` entry `<content>` contains `2` (book_1 in genre_1 + book_4 in genre_2 descendant) |
| 6 | `test_genre_root_genre_with_no_books_still_listed` | `genre_3` (no books) still appears in root feed with count `0` |
| 7 | `test_genre_detail_status_200` | GET `/opds/v1/genres/<genre_1.pk>/` → 200 |
| 8 | `test_genre_detail_404` | GET `/opds/v1/genres/99999/` → 404 |
| 9 | `test_genre_detail_lists_subgenres` | Feed contains entry for `genre_2` (Classic SF) as navigation link |
| 10 | `test_genre_detail_has_alphabet_tree_entries` | Feed contains alphabet tree entries for books in `genre_1` (and descendants); entries for `"f"` (Foundation) and `"c"` (Classic Dreams) are present |
| 11 | `test_genre_detail_alphabet_tree_excludes_other_genre_letters` | `genre_3` (no books) → GET `/opds/v1/genres/<genre_3.pk>/` returns feed with no alphabet entries |
| 12 | `test_genre_detail_alphabet_tree_only_contains_own_books` | `genre_2` detail: alphabet tree contains `"c"` (Classic Dreams belongs to `genre_2`) but NOT `"f"` (Foundation belongs only to `genre_1`) |
| 13 | `test_genre_detail_alphabet_leaf_links_to_booklist` | Leaf alphabet entry `<link href>` points to `/opds/v1/genres/<pk>/books/<letter>/` |
| 14 | `test_genre_books_status_200` | GET `/opds/v1/genres/<genre_1.pk>/books/` → 200 |
| 15 | `test_genre_books_includes_descendant_genre_books` | Feed contains both `book_1` (directly in `genre_1`) and `book_4` (in `genre_2`, descendant) |
| 16 | `test_genre_books_excludes_other_genre_books` | `book_3` (Fahrenheit, no genre_1) is NOT in `genre_1` books feed |
| 17 | `test_genre_books_by_letter_status_200` | GET `/opds/v1/genres/<genre_1.pk>/books/f/` → 200 |
| 18 | `test_genre_books_by_letter_filters_correctly` | Feed contains `book_1` (Foundation, starts with F); does NOT contain `book_4` (Classic Dreams, starts with C) |
| 19 | `test_genre_books_by_letter_empty_letter_returns_empty_feed` | GET `/opds/v1/genres/<genre_1.pk>/books/z/` → 200 with 0 entries |

---

#### `OPDSGenreFeedCountsTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Verifies genre book counts against the table in `test_template.md`.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_genre_root_sf_fantasy_count` | `Science Fiction & Fantasy` entry `<content>` contains `249` (86+82+81) |
| 2 | `test_genre_root_mysteries_count` | `Mysteries & Thrillers` entry `<content>` contains `159` (81+78) |
| 3 | `test_genre_root_action_adv_count` | `Action & Adventure` entry `<content>` contains `152` (78+74) |
| 4 | `test_dystopia_detail_alphabet_has_alid_entry` | `Dystopia` genre detail: alphabet tree contains `"alid"` or `"ali"` (23 dystopia books in Alid group) |
| 5 | `test_fantasy_detail_alphabet_no_yu_entry` | `Fantasy` genre detail: alphabet tree does NOT contain `"ю"` entry (fantasy has 0 books starting with Ю per template) |
| 6 | `test_nature_animals_detail_has_correct_total` | `Nature & Animals` genre book list count is 72 |
| 7 | `test_genre_books_by_letter_alid_dystopia` | GET `/opds/v1/genres/<dystopia.pk>/books/alid/` → feed has exactly 23 entries |
| 8 | `test_genre_books_by_letter_count_matches_table` | GET `/opds/v1/genres/<dystopia.pk>/books/alit/` → feed (page 1) and total count = 5 |

---

#### `OPDSSeriesListFeedTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Series: C=14, S=62, T=11, 0-9=10, Other=11; no series starts with Z.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_series_alphabet_root_status_200` | GET `/opds/v1/series/` → 200 |
| 2 | `test_series_alphabet_root_is_navigation` | `Content-Type` contains `kind=navigation` |
| 3 | `test_series_alphabet_root_has_s_entry` | Root feed contains an entry for `"s"` with count 62 |
| 4 | `test_series_alphabet_root_no_entry_for_missing_letter` | Root feed does NOT contain an entry for `"z"` |
| 5 | `test_series_list_by_letter_status_200` | GET `/opds/v1/series/t/` → 200 (T=11, leaf) |
| 6 | `test_series_list_has_correct_count` | GET `/opds/v1/series/t/` → feed contains exactly 11 entries |
| 7 | `test_series_list_entry_links_to_series_detail` | Each entry has `<link href="/opds/v1/series/<pk>/">` |
| 8 | `test_series_list_empty_letter_returns_empty_feed` | GET `/opds/v1/series/z/` → 200 with 0 entries |
| 9 | `test_series_s_is_expanded_not_flat_list` | GET `/opds/v1/series/s/` → feed contains navigation sub-entries (`Sh`, `St`, `Sw`, `all s`), NOT a flat list of 62 series |
| 10 | `test_series_digits_node_list` | GET `/opds/v1/series/?regex=^[0-9]` → 200 with exactly 10 entries (all digit-prefix series) |

---

#### `OPDSBookListFeedTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Books: A=222, B=167, M=43, П=83, 0-9=14, Other=31; no book starts with Z.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_book_alphabet_root_has_a_entry` | GET `/opds/v1/books/` → feed contains `"a"` entry with count 222 |
| 2 | `test_book_alphabet_root_no_entry_for_missing_letter` | Root feed does NOT contain a `"z"` entry |
| 3 | `test_book_list_by_letter_status_200` | GET `/opds/v1/books/m/` → 200 (M=43, leaf) |
| 4 | `test_book_list_has_correct_count` | GET `/opds/v1/books/m/` → feed has 20 entries (page 1 of 43) |
| 5 | `test_book_list_excludes_other_letter` | GET `/opds/v1/books/m/` → feed does NOT contain any book whose title starts with `"B"` |
| 6 | `test_book_list_entry_is_acquisition_with_perm` | Privileged user, GET `/opds/v1/books/m/`: entries have `<link rel="http://opds-spec.org/acquisition">` |
| 7 | `test_book_list_no_acquisition_link_anon` | Anon request: no acquisition link in entries |
| 8 | `test_book_list_empty_letter_returns_empty_feed` | GET `/opds/v1/books/z/` → 200 with 0 entries |
| 9 | `test_book_a_is_expanded_not_flat_list` | GET `/opds/v1/books/a/` → returns navigation sub-entries (`Al`, `An`, `Ar`, `all a`), NOT a flat list of 222 books |
| 10 | `test_book_list_cyrillic_letter` | GET `/opds/v1/books/п/` → 200 with entries for П=83 books (Ukrainian) |
| 11 | `test_book_digits_node_list` | GET `/opds/v1/books/?regex=^[0-9]` → 200 with exactly 14 entries (all digit-prefix books) |

---

#### `OPDSPaginationTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Uses `/opds/v1/authors/b/` (B=58 authors — leaf node) and `/opds/v1/books/m/` (M=43 books — leaf node); no extra data creation needed.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_author_list_page_1_has_20_entries` | GET `/opds/v1/authors/b/` → exactly 20 entries |
| 2 | `test_author_list_page_1_has_next_link` | Response has `<link rel="next">` |
| 3 | `test_author_list_page_1_no_prev_link` | Response has no `<link rel="previous">` |
| 4 | `test_author_list_page_2_has_20_entries` | GET `/opds/v1/authors/b/?page=2` → exactly 20 entries |
| 5 | `test_author_list_page_3_has_18_entries` | GET `/opds/v1/authors/b/?page=3` → exactly 18 entries (58 total: 20+20+18) |
| 6 | `test_author_list_page_3_has_prev_link` | Page 3 response has `<link rel="previous">` |
| 7 | `test_author_list_page_3_no_next_link` | Page 3 response has no `<link rel="next">` |
| 8 | `test_book_list_page_1_has_20_entries` | GET `/opds/v1/books/m/` → exactly 20 entries |
| 9 | `test_book_list_page_3_has_3_entries` | GET `/opds/v1/books/m/?page=3` → exactly 3 entries (43 total: 20+20+3) |
| 10 | `test_pagination_links_preserve_query_params` | `<link rel="next">` URL preserves the `page` and any other query params |

---

#### `OPDSAuthorDetailTest`

**Fixture:** small detail fixture (author_a/author_b/series_1/series_2/book_1/book_2/book_3/user_no_perm/user_with_perm).

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_author_detail_status_200` | GET `/opds/v1/authors/<author_a.pk>/` → 200 |
| 2 | `test_author_detail_404` | GET `/opds/v1/authors/99999/` → 404 |
| 3 | `test_author_detail_has_three_sub_feeds` | Feed has exactly 3 entries: All Books (A–Z), Recently Added, Books by Series |
| 4 | `test_author_detail_sub_feed_books_alpha_status_200` | GET `/opds/v1/authors/<author_a.pk>/books/` → 200 |
| 5 | `test_author_detail_sub_feed_books_alpha_contains_books` | Feed contains `book_1` (Foundation) and `book_2` (I, Robot) |
| 6 | `test_author_detail_sub_feed_books_alpha_excludes_other_author` | Feed does NOT contain `book_3` (Bradbury's book) |
| 7 | `test_author_detail_sub_feed_books_alpha_sorted` | Entries are sorted alphabetically by title (Foundation before I, Robot) |
| 8 | `test_author_detail_sub_feed_books_recent_status_200` | GET `/opds/v1/authors/<author_a.pk>/books/recent/` → 200 |
| 9 | `test_author_detail_sub_feed_books_recent_sorted_by_date` | Entries are sorted by `created_at` descending |
| 10 | `test_author_detail_sub_feed_series_status_200` | GET `/opds/v1/authors/<author_a.pk>/series/` → 200 |
| 11 | `test_author_detail_sub_feed_series_has_series` | Feed contains entry for `series_1` (Foundation) linking to `/opds/v1/series/<series_1.pk>/` |
| 12 | `test_author_detail_sub_feed_series_entry_has_book_count` | Series entry `<content>` contains `2` (book_1 and book_2 both in series_1 by author_a) |
| 13 | `test_author_detail_sub_feed_series_no_standalone_entry_when_none` | `author_a` has only series books → feed does NOT contain a "Standalone Books" entry |
| 14 | `test_author_detail_sub_feed_series_has_standalone_entry` | `author_b` has `book_3` (no series) → feed includes "Standalone Books" entry linking to `/opds/v1/authors/<author_b.pk>/books/` |
| 15 | `test_author_detail_sub_feed_series_standalone_entry_has_count` | Standalone entry `<content>` reads `"1 standalone book(s)"` |
| 16 | `test_author_books_no_acquisition_link_anon` | Anon request to `/opds/v1/authors/<author_a.pk>/books/` → no acquisition link in entries |
| 17 | `test_author_books_acquisition_link_with_perm` | `user_with_perm` request → entries have `<link rel="http://opds-spec.org/acquisition">` |

---

#### `OPDSSeriesDetailTest`

**Fixture:** small detail fixture (series_1/series_2/book_1/book_2).

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_series_detail_status_200` | GET `/opds/v1/series/<series_1.pk>/` → 200 |
| 2 | `test_series_detail_404` | GET `/opds/v1/series/99999/` → 404 |
| 3 | `test_series_detail_has_subseries` | Feed contains entry for `series_2` (Robot Series, child of series_1) as navigation link |
| 4 | `test_series_detail_has_books` | Feed contains `book_1` (Foundation) and `book_2` (I, Robot) |
| 5 | `test_series_detail_books_sorted_by_sequence_number` | `book_1` (seq=1) appears before `book_2` (seq=2) |
| 6 | `test_series_detail_book_title_prefixed_with_seq` | Book entry `<title>` is `"#1 · Foundation"` |
| 7 | `test_series_detail_no_acquisition_anon` | Anon request → no acquisition link on book entries |
| 8 | `test_series_detail_acquisition_with_perm` | `user_with_perm` request → book entries have `<link rel="http://opds-spec.org/acquisition">` |

---

#### `OPDSBookDetailTest`

**Fixture:** small detail fixture (book_1 with file+cover, author_a, series_1, user_no_perm, user_with_perm). Extends `BaseTestCase` (book_1 has a real EPUB file for cover URL testing).

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_book_detail_status_200` | GET `/opds/v1/books/<book_1.pk>/` → 200 |
| 2 | `test_book_detail_404` | GET `/opds/v1/books/99999/` → 404 |
| 3 | `test_book_detail_has_title` | Entry `<title>` equals `"Foundation"` |
| 4 | `test_book_detail_has_author_with_uri` | `<author>` contains `<name>Isaac Asimov</name>` and `<uri>` pointing to `/opds/v1/authors/<author_a.pk>/` |
| 5 | `test_book_detail_has_description` | `<summary>` contains `book_1.description` text |
| 6 | `test_book_detail_cover_link_is_absolute_url` | `<link rel="http://opds-spec.org/image" href="...">` is an absolute URL (starts with `http`) |
| 7 | `test_book_detail_has_thumbnail_link` | `<link rel="http://opds-spec.org/image/thumbnail">` present |
| 8 | `test_book_detail_has_series_related_link` | `<link rel="related">` pointing to `/opds/v1/series/<series_1.pk>/` present |
| 9 | `test_book_detail_no_cover_link_when_no_cover` | book_2 (no cover) → no `<link rel="http://opds-spec.org/image">` in its feed |
| 10 | `test_book_detail_no_acquisition_link_anon` | Anon user → no `<link rel="http://opds-spec.org/acquisition">` |
| 11 | `test_book_detail_no_acquisition_link_user_no_perm` | `user_no_perm` → no acquisition link |
| 12 | `test_book_detail_has_acquisition_link_user_with_perm` | `user_with_perm` → acquisition link present, `href="/opds/v1/books/<book_1.pk>/download/"` |

---

#### `OPDSBookDownloadTest` (extends `BaseTestCase`)

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_download_anon_returns_403` | GET `/opds/v1/books/<pk>/download/` as anon → 403 |
| 2 | `test_download_user_no_perm_returns_403` | Authenticated, no perm → 403 |
| 3 | `test_download_user_with_perm_epub_returns_200` | Privileged user, EPUB book → 200, correct `Content-Type` |
| 4 | `test_download_user_with_perm_fb2_zipped_returns_200` | Privileged user, FB2-in-ZIP book → 200, decrypted content matches |
| 5 | `test_download_no_file_returns_404` | Book with no file → 404 |
| 6 | `test_download_content_disposition_header` | Response has `Content-Disposition: attachment; filename="..."` |
| 7 | `test_download_content_matches_extracted` | Response bytes match `get_book_file_content` output |

---

#### `OPDSSearchTest`

**Fixture:** small detail fixture (author_a=Asimov, series_1=Foundation, book_1=Foundation, book_2=I Robot, user_no_perm, user_with_perm).

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_search_returns_200` | GET `/opds/v1/search/?q=Foundation` → 200 |
| 2 | `test_search_has_books_section_header` | Feed contains section header entry with title `"Books (2 found)"` (book_1 "Foundation" + book_2 "I Robot" — wait, only Foundation matches; assert `"Books (1 found)"` for exact fixture) |
| 3 | `test_search_has_series_section_header` | `?q=Foundation` → feed contains `"Series (1 found)"` header (series_1 matches) |
| 4 | `test_search_has_authors_section_header` | GET `?q=Asimov` → feed contains `"Authors (1 found)"` header (author_a matches) |
| 5 | `test_search_section_omitted_when_empty` | GET `?q=Asimov` → no `"Books"` section header (no book title matches "Asimov"); no `"Series"` section header |
| 6 | `test_search_book_entries_follow_section_header` | `?q=Foundation`: `book_1` entry immediately follows the Books section header |
| 7 | `test_search_author_entries_link_to_author_feed` | Author result entry `<link href>` points to `/opds/v1/authors/<author_a.pk>/` |
| 8 | `test_search_series_entries_link_to_series_feed` | Series result entry `<link href>` points to `/opds/v1/series/<series_1.pk>/` |
| 9 | `test_search_empty_query_returns_empty_feed` | GET `/opds/v1/search/` (no `q`) → 200 with 0 `<entry>` elements |
| 10 | `test_search_no_results_returns_empty_feed` | GET `?q=xyzzyunmatchable` → 200 with 0 `<entry>` elements |
| 11 | `test_search_pagination_books` | Create 25 books matching `?q=Zap`; page 1 has 20 book entries + Books section header; `<link rel="next">` present |
| 12 | `test_search_book_acquisition_link_with_perm` | `user_with_perm`, `?q=Foundation` → book result entries have `<link rel="http://opds-spec.org/acquisition">` |
| 13 | `test_search_no_acquisition_link_anon` | Anon, `?q=Foundation` → no acquisition link on book result entries |
| 14 | `test_search_section_headers_have_no_href_link` | Section header entries (Authors N found / Series N found / Books N found) do NOT contain a `<link>` element |

#### `OPDSOpenSearchDescriptionTest`

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_opensearch_description_status_200` | GET `/opds/v1/search/description.xml` → 200 |
| 2 | `test_opensearch_description_content_type` | `Content-Type` is `application/opensearchdescription+xml` |
| 3 | `test_opensearch_description_has_shortname` | XML contains `<ShortName>Bookshelf</ShortName>` |
| 4 | `test_opensearch_description_has_url_template` | XML contains `<Url>` element with `template` attribute containing `/opds/v1/search/?q={searchTerms}` |
| 5 | `test_opensearch_description_template_is_absolute_url` | `template` attribute value starts with `http` (absolute URL) |

---

#### `OPDSThrottlingTest`

**Fixture:** none (root feed requires no data). Uses `@override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_RATES': {'opds_anon': '3/min', 'opds_anon_daily': '1000/day'}})` and overrides cache to `LocMemCache` (since `BaseTestCase` uses `DummyCache` which bypasses throttling).

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_within_limit_returns_200` | 3 consecutive requests to `/opds/v1/` → all 200 |
| 2 | `test_exceeds_per_minute_limit_returns_429` | 4th consecutive request → 429 |
| 3 | `test_throttle_header_present` | 429 response contains `Retry-After` header |
| 4 | `test_throttle_applies_to_all_opds_endpoints` | Parameterized over `/opds/v1/` and `/opds/v1/books/`: hitting limit on one endpoint triggers 429 on subsequent requests to the other (shared cache key scope) |

---

## 11. Implementation Notes & Non-Obvious Decisions

### Alphabet tree URL encoding

The `filter` value from `AlphabetTree.filter` is used directly as the `<letter>` path segment. Non-alpha leaf nodes (`regex`-based: `aa*`, `0-9`, `other`) are not reachable via path segment — they use `?regex=<encoded>` query params instead. Views must handle both forms.

### `<updated>` in feeds

Use `django.utils.timezone.now()` as a fallback when no objects exist rather than a hardcoded date. For list feeds, use `queryset.aggregate(Max('updated_at'))['updated_at__max']`.

### Cover image URLs

`book.cover.url` returns a storage-relative URL. In Phase 1 (local filesystem), this is a relative media URL served by Nginx. The OPDS feed must produce an absolute URL using `request.build_absolute_uri(book.cover.url)`. Thumbnail uses `book.cover_preview.url` (imagekit-generated).

### Pretty-printing XML

Use `xml.etree.ElementTree.indent()` (Python 3.9+). Register all namespaces with `ET.register_namespace()` before building the tree to avoid `ns0:` prefixes in output.

### Download view: not a DRF view

`BookDownloadView` is a plain Django `View` (like the existing `BookDownloadView` in `library.views`), not a DRF `APIView`, to leverage Django's `FileResponse` / `StreamingHttpResponse` without the DRF renderer layer.

### Permission check approach

Views check `request.user.has_perm('library.view_book')` directly. No DRF `permission_classes` are used for the acquisition link visibility — the link is simply omitted from the serialized entry. The download view additionally returns `HTTP 403` for unauthorized requests.

### Throttle cache backend

Throttle uses the `default` cache. In tests, `BaseTestCase` sets `default` to `DummyCache`, which disables throttling. Throttle tests must override cache settings to use `LocMemCache`.

---

## 12. Design Decisions (Resolved)

1. **Genres feed type:** Genres use the model hierarchy directly: root feed lists top-level genres; each genre detail lists subgenres then an alphabet tree of books in that genre (including descendants). The `get_alphabet_tree` service is reused for the book alphabet within each genre detail. Series root feed renders as an alphabet tree (same as Authors and Books), not a flat first-letter list.

2. **`AuthorSeriesFeedView` standalone books:** When an author has books not linked to any series, a synthetic **"Standalone Books"** entry is appended at the end of the Author Series feed, linking to the author's All Books feed. The entry is omitted entirely when no standalone books exist.

3. **Search feed structure:** Results are split into three named sections within a single feed (Authors, Series, Books). Each section is preceded by a header entry carrying the count (`"Authors (N found)"`). A section is omitted entirely when its result set is empty. Book entries carry acquisition links; author and series entries carry navigation links.

4. **OpenSearch Description Document:** Implemented at `/opds/v1/search/description.xml`. Required for Calibre and KOreader auto-discovery. The descriptor's `<Url template>` is built as an absolute URL using `request.build_absolute_uri`.

5. **"All" node in alphabet trees:** When an alphabet tree node is expanded (has children), a synthetic `"all <prefix>"` entry is prepended as the first child. It links to the list URL for that prefix with no further filter parameter, returning the complete unfiltered set for that prefix. Leaf nodes (not expanded) do not get an "all" entry. This applies uniformly to Authors, Books, Series, and the genre-scoped book alphabet trees.
