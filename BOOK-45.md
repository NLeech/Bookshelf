# BOOK-45: Initial OPDS v1.2 Catalog — Implementation Plan

## 1. Context & Architecture

### Problem being solved

The Bookshelf project needs an OPDS v1.2 catalog endpoint at `/opds/v1/` so that OPDS-compatible e-reader clients (Calibre, KOreader, Moon+ Reader, etc.) can browse and download books. This is Phase 1: no authentication challenge, with download links conditionally rendered based on the `library.view_book` permission.

### Codebase state at plan time

The `bookshelf/library/opds/` directory does not exist yet — this is a clean-slate implementation. `djangorestframework` is declared in `pyproject.toml` but is **not yet in `INSTALLED_APPS`** and has no `REST_FRAMEWORK` settings dict.

### Target app

`library` — the OPDS module lives as a self-contained sub-package at `bookshelf/library/opds/`.

### Schema change required: no

OPDS reads existing models (`Author`, `Book`, `BookSeries`, `Genre`, `BookSeriesLink`) with no schema modifications.

### Celery required: no

### UI mode: API only

DRF `APIView` subclasses returning `application/atom+xml`.

---

### Data flow

```
HTTP GET /opds/v1/...
  → OPDSBaseView.get()
      → DRF throttle check (OPDSMinuteRateThrottle, OPDSDayRateThrottle)
      → QuerySet built from library models
      → build_*_feed() functions in serializers.py
          → returns plain Python dict ("feed dict")
      → Response(feed_dict)
          → OPDSRenderer.render(feed_dict)
              → xml.etree.ElementTree builds Atom XML element tree
              → ET.indent(root, space='  ')  (pretty-print)
              → b'<?xml version="1.0" encoding="utf-8"?>\n'
                + ET.tostring(root, encoding='unicode').encode('utf-8')

HTTP GET /opds/v1/books/<pk>/download/   (auth phase — see BOOK-45 auth.md)
  → OPDSBookDownloadView.get()  (extends OPDSBaseView; BasicAuthentication; JSONRenderer)
      → DRF throttle check
      → IsAuthenticated: anonymous → 401 + WWW-Authenticate: Basic
      → can_view_book(request.user, book) is False → 403
      → filename, content_bytes, content_type = get_book_file_content(book)
      → content_bytes is None → HttpResponse(status=404)
      → HttpResponse(content_bytes, content_type=...) + Content-Disposition header
```

---

### Feed dict contract

Every OPDS view returns `Response(feed_dict)`. `feed_dict` is a plain Python dict:

```python
{
    'id':        str,       # tag: URI
    'title':     str,
    'updated':   datetime,
    'kind':      str,       # 'navigation' | 'acquisition'
    'self_link': str,       # absolute URL of this feed
    'start_link': str,      # always absolute URL of /opds/v1/
    'pagination': {         # present only on paginated feeds; absent otherwise
        'first':    str | None,
        'next':     str | None,
        'previous': str | None,
    },
    'entries': [
        {
            'id':      str,
            'title':   str,
            'updated': datetime | None,
            'content': str | None,      # navigation entries: plain-text item count.
                                        # complete book entries: sanitized-XHTML
                                        # description (rendered as <content
                                        # type="xhtml">). Absent on thin book
                                        # entries and when a book has no description.
            'kind':    str | None,      # book entries: 'thin' | 'thick' — drives
                                        # the renderer's partial/complete shape
            'series':  [                # complete book entries only (structured
                                        # <calibre:series>/<calibre:series_index>)
                {'name': str, 'index': int | str}
            ],
            'links': [
                {
                    'rel':   str,       # incl. 'related' (one per author → /authors/<pk>/
                                        #   and one per series → /series/<pk>/),
                                        #   'alternate' (thin → complete entry),
                                        #   'http://opds-spec.org/image[/thumbnail]'
                    'href':  str,
                    'type':  str,
                    'title': str | None,
                }
            ],
        }
    ]
}
```

**Authors are not a top-level entry field.** Per §6.5 a book entry emits **no `<author>` Atom element**; each author is a `rel="related"` link (`href` → `/opds/v1/authors/<pk>/`, `title` = author `full_name`) inside `'links'`. Series likewise appear both as structured `'series'` entries (rendered `<calibre:*>`) and as `rel="related"` links (`href` → `/opds/v1/series/<pk>/`, `title` = series name only).

```
```

The renderer (`OPDSRenderer`) owns all XML construction. Views and serializers are XML-free.

---

### XML namespace registration

All four namespaces must be registered at **module import time** in `renderers.py` via `ET.register_namespace()` to suppress `ns0:` prefixes:

| Prefix | URI |
|--------|-----|
| (default / empty) | `http://www.w3.org/2005/Atom` |
| `opds` | `http://opds-spec.org/2010/catalog` |
| `dc` | `http://purl.org/dc/terms/` |
| `opensearch` | `http://a9.com/-/spec/opensearch/1.1/` |
| `xhtml` | `http://www.w3.org/1999/xhtml` (book entry `<content type="xhtml">`) |
| `calibre` | `http://calibre.kovidgoyal.net/2009/metadata` (`<calibre:series>` / `<calibre:series_index>`) |

---

### `<id>` tag strategy

| Entity | tag: URI |
|--------|----------|
| Root feed | `tag:bookshelf:root` |
| Authors root | `tag:bookshelf:authors` |
| Author tree node | `tag:bookshelf:authors:tree:<node_name>` |
| Author detail | `tag:bookshelf:author:<pk>` |
| Author books feed | `tag:bookshelf:author:<pk>:books` |
| Author recent feed | `tag:bookshelf:author:<pk>:books:recent` |
| Author series feed | `tag:bookshelf:author:<pk>:series` |
| Books root | `tag:bookshelf:books` |
| Book detail | `tag:bookshelf:book:<pk>` |
| Series root | `tag:bookshelf:series` |
| Series detail | `tag:bookshelf:series:<pk>` |
| Genre root | `tag:bookshelf:genres` |
| Genre detail | `tag:bookshelf:genre:<pk>` |
| Search feed | `tag:bookshelf:search` |

---

### `<updated>` timestamp strategy

- **Root feed:** `timezone.now()`.
- **List / tree feeds:** `queryset.aggregate(Max('updated_at'))['updated_at__max'] or timezone.now()`.
- **Individual entry:** the model instance's `.updated_at`.

---

### Alphabet tree URL mechanics

`get_alphabet_tree(queryset, field_name)` returns an `AlphabetTree` root. Each node carries:

- `name`: display label (`'a'`, `'ab'`, `'0-9'`, `'other'`, `'a*'`)
- `filter`: prefix for `istartswith` filtering (`'a'`, `'ab'`, …) — empty string for regex-only nodes
- `regex`: POSIX regex (`'^[0-9]'`, `'^[^[:alpha:][:digit:]]'`, …) — empty for prefix-only nodes
- `quantity`: item count
- `entries`: child nodes

**Navigation / results separation.** Tree navigation and flat lists live at distinct URLs so one URL has one responsibility:

- **Tree endpoints** (`…/tree/`, `…/tree/<name>/`) → always navigation feeds, never paginated.
- **Results endpoint** (`…/` with optional `?filter=`/`?regex=`) → always a flat, paginated list.

**Tree views** — `AuthorTreeFeedView` (at `/opds/v1/authors/tree/` and `/opds/v1/authors/tree/<str:name>/`):
1. No `name` → render the root tree.
2. With `name` → call the new `find_alphabet_node_by_name(full_tree, name)`; 404 if not found or if the node is a leaf (leaves are never addressed by path). Render its sub-tree feed with the synthetic **"all `<prefix>`"** entry prepended.
3. Each child entry link: expandable child → `…/tree/<child.name>/`; leaf child → results endpoint `…/?filter=<child.filter>` (or `…/?regex=<child.regex>` when `filter` is empty).

**Results views** — `AuthorListFeedView` (at `/opds/v1/authors/`):
1. `?regex=<r>` present → `last_name__iregex=r` (regex wins).
2. else `?filter=<p>` present → `last_name__istartswith=p`.
3. else → full queryset.
4. Always paginate; entries link to `/opds/v1/authors/<pk>/`.

Identical logic applies to Series (`field='name'`) and Book (`field='title'`) tree/results views, and to the genre-scoped `GenreBookTreeFeedView` / `GenreBookListFeedView`.

**`find_alphabet_node_by_name(root, name)`** is a small recursive helper added to `library/services.py` next to `find_alphabet_node`: depth-first walk returning the first node whose `.name == name`, else `None`. Tree views use it to resolve `<name>` path segments (only expandable nodes — prefix nodes `a`/`ab`/… and `other` — are ever placed in a path; their names are URL-safe).

**"all `<prefix>`" entry** is synthetic (not from the tree), added only when the rendered node has children. It is the first entry in the sub-tree feed, carries the same count as that node, and links to the **results** endpoint for the node's own selector — `…/?filter=<node.filter>`, or `…/?regex=<node.regex>` when `filter` is empty (the `other` node).

---

### Genre book filtering

```python
all_ids = {genre.pk} | get_descendants([genre.pk])
qs = Book.objects.filter(genres__id__in=all_ids).distinct()
```

`get_descendants` returns only **leaf** descendants. Books tagged directly to intermediate genre nodes (not present in the canonical dataset) would be excluded. This follows existing `BookListView` behavior exactly.

**Alphabet filtering within a genre** mirrors `BookListView.get_queryset` (views.py): apply the alphabet selection on top of the genre queryset using the node's filter **or** regex —

```python
if regex:                       # digit / other / low-count "prefix*" nodes
    qs = qs.filter(title__iregex=regex)
elif letter:                    # ordinary letter-prefix nodes
    qs = qs.filter(title__istartswith=letter)
```

`get_alphabet_tree` is rebuilt from the **genre-filtered** queryset so the tree only contains letters that genre actually has. The genre book tree/results endpoints are exact instances of the standard navigation/results shape with the genre base queryset and a `/genres/<pk>/books/` URL prefix:

- `GenreBookTreeFeedView` → `/genres/<pk>/books/tree/[<name>/]` (navigation; uses `find_alphabet_node_by_name`).
- `GenreBookListFeedView` → `/genres/<pk>/books/?filter=|?regex=` (flat, paginated acquisition list).

**Genre detail (`GenreDetailFeedView`, `/genres/<pk>/`) is subgenres-only.** It renders one navigation entry per direct subgenre (`genre.subgenres.all()` → `/genres/<subpk>/`). If the genre has **no** subgenres, the view returns an **HTTP 302 redirect** to `/genres/<pk>/books/tree/` (302, not 301 — leaf-ness is data-dependent). It contains no book or alphabet entries. Consequence (intended): a non-leaf genre's aggregate book tree is reachable only by direct URL, not advertised from any feed; since directly-tagged books live only on leaf genres here, no books are hidden.

---

### Book entry shape: thin default, `?detail=thick` complete

Book-listing acquisition feeds — `/books/`, `/authors/<pk>/books/`, `…/books/recent/`, `/genres/<pk>/books/`, `/series/<pk>/`, `/search/books/` — emit **thin (partial)** catalog entries by default:

- `<title>`, `<id>` (`tag:bookshelf:book:<pk>`),
- permission-gated `<link rel="http://opds-spec.org/acquisition">`,
- **mandatory** `<link rel="alternate" type="application/atom+xml;type=entry;profile=opds-catalog">` → the complete entry at `/opds/v1/books/<pk>/`,
- cover **thumbnail** only.

No `<content>`, no full-size `http://opds-spec.org/image`, no `<calibre:*>`, no author/series `rel="related"` links in thin entries.

`?detail=thick` switches the **same** endpoints to **complete** inline entries (identical to the §"Book detail entry" complete shape).

**`?detail=thick` is a sticky, catalog-wide preference.** Because OPDS clients only *follow links* (they never synthesise URLs), the param is useless unless threaded through the whole browse path. When present on a request it MUST be re-appended to **every link whose target is another browsable catalog feed**, so it survives navigation/search/drill-down to the terminal acquisition feed:

- every **`subsection`** link in every navigation feed (Root, Alphabet Tree incl. the synthetic "all …" entry, Author/Genre/Series results & detail, Author Series);
- the **search query-template link** (`rel="search"`, `application/atom+xml`, `…/search/?q={searchTerms}`);
- **author/series `rel="related"`** links on thick book entries;
- the feed's **`self`** / **`start`** links and its `first`/`next`/`previous` pagination links.

Omitted from non-feed / always-complete links: the `rel="alternate"` link (target `/opds/v1/books/<pk>/` is already complete and **unaffected** by the param), the acquisition/download link, the cover `image`/`thumbnail` links, the logo thumbnail link, and the OpenSearch `…description+xml` link. Link propagation is **param-agnostic**: a single `_with_sticky_params(href, request)` serializer helper re-appends every catalog-wide sticky preference listed in a `STICKY_QUERY_PARAMS` tuple (currently `('detail',)`) that is present on the request — respecting an existing query string and skipping params already on the href. Navigation builders carry no per-feature flag, so a future sticky preference is one tuple entry with no signature churn. Entry verbosity is decided separately by a single `wants_thick_entries(request)` predicate (the only place `detail == 'thick'` is interpreted), called by the two book acquisition views and passed as the `thick` argument to `build_author_books_feed`. DRF's paginator already preserves the query string on `self`/pagination links. The param changes only book-entry verbosity — never the body of a navigation feed.

### Book detail entry (complete shape)

A complete book entry — the standalone `/opds/v1/books/<pk>/` feed and every thick listing entry — emits, in document order:

- `<title>`.
- `<content type="xhtml">` — the **description only**, sanitized to an allowlist (`p, br, strong, b, em, i, u, ul, ol, li`; all attributes stripped) and emitted as a real un-escaped XHTML `<div>` of live nodes. Omitted when the book has no description.
- `<calibre:series>` / `<calibre:series_index>` — one pair per series (Calibre metadata namespace); series name `.strip()`-ed, index = sequence number. Omitted when standalone.
- `<link rel="http://opds-spec.org/image">` + `<link rel="http://opds-spec.org/image/thumbnail">` — cover and thumbnail. **Always present:** when `book.cover` is set, use `book.cover.url` / `book.cover_preview.url`; when it is not, fall back to the static placeholders `/static/img/no_cover 600x900.jpeg` (full) and `/static/img/no_cover 40x60.jpeg` (thumbnail). The image links are never omitted.
- `<link rel="related">` **per author** → `/opds/v1/authors/<pk>/`, `type="…;kind=navigation"`, `title` = author `full_name`. This is the **only** author representation — **no `<author>` Atom element is emitted.**
- `<link rel="related">` **per series** → `/opds/v1/series/<pk>/`, `title` = series **name only** (no `#<seq>`).
- `<link rel="http://opds-spec.org/acquisition">` — only when the user has `library.view_book`.

### Default entry image (logo for non-book entries)

Every entry that does **not** carry an acquisition link — root, author, series, genre, alphabet-tree, and search-section entries — MUST carry the application logo as its thumbnail: `<link rel="http://opds-spec.org/image/thumbnail" type="image/png" href="<abs>/static/img/Logo 64x64x8.png">` (absolute URL via `request.build_absolute_uri`). Book (acquisition) entries are excluded; they use their own cover/thumbnail.

### Navigation entry counts (mandatory)

Every navigation entry representing a collection MUST expose its child-item count in `<content type="text">` (e.g. `"42 books"`): author entries (book count), series entries (per-author count in the author-series feed, total elsewhere), genre entries (descendant-inclusive count via `get_descendants`), alphabet-tree nodes, and root browse entries. A count of `0` is still rendered.

### Permission model

> **Updated by the auth phase — see `BOOK-45 auth.md`.**

| Action | Requirement |
|--------|-------------|
| Browse any feed | None (`BasicAuthentication` attempted, `AllowAny`) |
| See `<link rel="…/acquisition">` in book entries | None — **always rendered** |
| `/opds/v1/login/` | `IsAuthenticated` → HTTP 401 (+ `WWW-Authenticate: Basic`) when anonymous; 302 → root once authenticated |
| `/opds/v1/books/<pk>/download/` | `IsAuthenticated` → HTTP 401 when anonymous; per-book check `can_view_book(request.user, book)` (currently `library.view_book`) → HTTP 403 when not allowed |

`OPDSBaseView` sets `authentication_classes = [BasicAuthentication]` (Basic-only — Session-first would yield 403 instead of 401) so auth is *attempted* on every view while browse stays `AllowAny`. `OPDSBookDownloadView` sets `permission_classes = [IsAuthenticated]` (giving the 401 for anonymous users) **and** checks `can_view_book(request.user, book)` explicitly in `get()` (giving the 403). The helper takes the `book` so a future per-book public-domain rule slots in without touching call sites. The acquisition link is **always rendered** in feeds regardless of permission; authorization is enforced only at the download endpoint, and the visible link is what lets a reader tap *download* to trigger the Basic credential prompt.

---

### Throttling

Two throttle classes, both applied via `throttle_classes = [OPDSMinuteRateThrottle, OPDSDayRateThrottle]` to **every** OPDS view including `BookDownloadView`:

- `OPDSMinuteRateThrottle(AnonRateThrottle)`: `scope = 'opds_anon'` → 60/min
- `OPDSDayRateThrottle(AnonRateThrottle)`: `scope = 'opds_anon_daily'` → 1000/day

Both use `REMOTE_ADDR` as the cache key (anonymous-only in Phase 1). Throttling uses the `default` cache. `BaseTestCase` replaces `default` cache with `DummyCache`, which disables throttling — throttle tests must override to `LocMemCache`.

---

### Pagination

`OPDSPageNumberPagination(PageNumberPagination)`:
- `page_size = settings.OPDS_PAGE_SIZE` (add `OPDS_PAGE_SIZE = 20` to settings.py)
- `page_query_param = 'page'`
- No `page_size_query_param` (no client override of page size)

Paginated feeds: the flat **results** endpoints (`/authors/`, `/books/`, `/series/`, `/genres/<pk>/books/`), Author detail sub-feeds (books, books recent), Series detail book list, each search section sub-feed (authors/series/books — see below). Navigation **tree** feeds (`…/tree/`, `…/tree/<name>/`) are **not** paginated.

Pagination info is embedded in the feed dict under `'pagination'`. The renderer converts it to `<link rel="next">`, `<link rel="previous">`, `<link rel="first">` elements.

**Search pagination:** The three sections are **never** flattened. The search root (`search/`) is a small navigation feed (≤ 3 section entries, unpaginated). Each section is a **separate, independently paginated** sub-feed — `search/authors/`, `search/series/`, `search/books/` — paginated with `OPDSPageNumberPagination` (`page_size = 20`); its `next`/`previous`/`first` links preserve the `q` query param.

---

### Pretty-printed XML

`ET.indent(root, space='  ')` mutates the tree in-place. The serialization call must use:

```python
b'<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding='unicode').encode('utf-8')
```

`encoding='unicode'` causes `ET.tostring()` to return a `str` (no embedded XML declaration). `.encode('utf-8')` converts to bytes. **Do not** use `encoding='utf-8'` in `ET.tostring()` — that inserts its own XML declaration header, producing a malformed double-declaration.

---

### Book download: `get_book_file_content` unpacking

`get_book_file_content(book)` returns `(filename, content_bytes, content_type)` — a 3-tuple in exactly that order. The view must unpack as:

```python
filename, content_bytes, content_type = get_book_file_content(book)
if content_bytes is None:
    return HttpResponse(status=404)
```

---

### Author Detail has 3 sub-feeds; standalone books surface via the series feed

**Decision (confirmed by product):** Author Detail exposes exactly **3** sub-feeds (no dedicated "no-series" endpoint). The three entries:

| Entry | Link href | Type |
|-------|-----------|------|
| Books by Title | `/opds/v1/authors/<pk>/books/` | acquisition |
| New Arrivals | `/opds/v1/authors/<pk>/books/recent/` | acquisition |
| Books by Series | `/opds/v1/authors/<pk>/series/` | navigation |

Books not linked to any series are surfaced through a **"Standalone Books" category at the top** of the **Books by Series** sub-feed: when the author has standalone books, the series feed **prepends** a first entry titled "Standalone Books" (content `"N standalone book(s)"`) linking to `/opds/v1/authors/<pk>/books/?series=none`.

`AuthorBooksFeedView` honours an optional `?series=none` query param, filtering to `author.books.filter(bookserieslink__isnull=True)`, reusing the same paginated acquisition feed. No new URL pattern or view is added.

---

## 2. File Modifications

### CREATE `bookshelf/library/opds/__init__.py`

Empty file making `opds` a Python package.

### CREATE `bookshelf/library/opds/throttles.py`

Two classes: `OPDSMinuteRateThrottle(AnonRateThrottle)` with `scope = 'opds_anon'` and `OPDSDayRateThrottle(AnonRateThrottle)` with `scope = 'opds_anon_daily'`.

### CREATE `bookshelf/library/opds/renderers.py`

- Register all 6 namespaces at module level (the 4 core + `xhtml` + `calibre`).
- `OPDSRenderer(BaseRenderer)`:
  - `media_type = 'application/atom+xml'`
  - `format = 'atom'`
  - `charset = 'utf-8'`
  - `render(data, accepted_media_type, renderer_context)` → calls `_build_feed(data)` → `ET.indent` → returns bytes with leading XML declaration
  - `_build_feed(data)` → constructs `<feed>` element with id, title, updated, self/start links, pagination links, and all entry elements
  - `_build_entry(entry_dict)` → constructs a single `<entry>`. Branches on entry shape:
    - **Navigation entry** → no `<content type="xhtml">`, no `<calibre:*>`, no author/series `rel="related"`. Carries the **logo thumbnail** (see below) and a plain-text `<content type="text">` count.
    - **Thin book entry** (`kind == 'thin'`, the listing default) → `<title>`, `<id>`, acquisition `<link>` (permission-gated), **mandatory** `<link rel="alternate" type="application/atom+xml;type=entry;profile=opds-catalog">` → `/opds/v1/books/<pk>/`, and the cover **thumbnail** only. No `<content>`, no full-size image, no `<calibre:*>`, no `rel="related"`.
    - **Complete (thick / detail) book entry** (`kind == 'thick'` or the standalone book-detail feed) → `<content type="xhtml">` (sanitized-XHTML description; real un-escaped `<div>` of live XHTML nodes, not an escaped string), one `<calibre:series>`/`<calibre:series_index>` pair per series, full-size + thumbnail cover `<link>`s, one author `rel="related"` per author, one series `rel="related"` per series, permission-gated acquisition link. **No `<author>` Atom element.**
  - `_sanitize_html(text)` → allowlist sanitizer used for the XHTML `<content>`; only `p, br, strong, b, em, i, u, ul, ol, li` survive and all attributes are stripped.
  - Cover full image: `rel="http://opds-spec.org/image"`, type `image/jpeg`
  - Cover thumbnail: `rel="http://opds-spec.org/image/thumbnail"`, type `image/jpeg` — uses `cover_preview.url` (the 100×150 `ImageSpecField`), NOT `cover.url`
  - **Logo thumbnail (non-book entries):** every entry that does **not** carry an acquisition link (root, author, series, genre, alphabet-tree, search-section entries) MUST carry `<link rel="http://opds-spec.org/image/thumbnail" type="image/png" href="<abs>/static/img/Logo 64x64x8.png">`, built with `request.build_absolute_uri`. Book (acquisition) entries are excluded — they use their own cover/thumbnail.
  - Navigation kind Content-Type: `application/atom+xml;profile=opds-catalog;kind=navigation`
  - Acquisition kind Content-Type: `application/atom+xml;profile=opds-catalog;kind=acquisition`
  - The renderer reads `data['kind']` to set the Content-Type via `renderer_context['response']['Content-Type']`
- `OpenSearchRenderer(BaseRenderer)`:
  - `media_type = 'application/opensearchdescription+xml'`
  - `format = 'opensearch'`
  - `render(data, ...)` → builds `<OpenSearchDescription>` tree with ShortName, Description, Url template, Language, OutputEncoding, InputEncoding → returns pretty-printed bytes

### CREATE `bookshelf/library/opds/serializers.py`

Pure Python functions. No DRF serializer classes. No XML. All accept `request` for absolute URI construction and permission checking.

**Cross-cutting rules every builder honours:**
- **Navigation entry counts (mandatory).** Every navigation entry that represents a collection (author, series, genre, alphabet-tree node, root browse entries, author-results, series-results) carries its item count in `content` (e.g. `"42 books"`). A count of `0` is still rendered — a navigation entry without a count is incomplete.
- **Logo thumbnail (mandatory on non-book entries).** Every non-acquisition entry carries a `links` item `{'rel': 'http://opds-spec.org/image/thumbnail', 'type': 'image/png', 'href': request.build_absolute_uri('/static/img/Logo 64x64x8.png')}`. Book (acquisition) entries never carry the logo. (The renderer enforces the same rule; builders supply the absolute href.)

Functions:

- `build_root_feed(request) → dict` — 4 fixed browse entries (Authors, Genres, Series, Books), plus a conditional `Login` entry appended **only when `not request.user.is_authenticated`** (auth phase, `BOOK-45 auth.md`) → 5 entries for anonymous, 4 for authenticated
- `build_author_entry(author, request) → dict` — single entry for a navigation author results list
- `build_author_tree_feed(node, request) → dict` — **navigation** sub-tree feed: synthetic "all `<prefix>`" first entry (when `node` has children), then one entry per child. Child links: expandable → `authors/tree/<child.name>/`; leaf → `authors/?filter=<child.filter>` or `authors/?regex=<child.regex>`
- `build_author_results_feed(authors_page, request) → dict` — **flat, paginated navigation** list of authors (leaf/"all"/filter/regex results); entries link to `authors/<pk>/`
- `build_author_detail_feed(author, request) → dict` — exactly 3 navigation entries (`Books by Title`, `New Arrivals`, `Books by Series`)
- `build_author_series_feed(author, request, series_with_counts, standalone_count=0) → dict` — when `standalone_count > 0`, **prepends** a "Standalone Books" entry (linking to `authors/<pk>/books/?series=none`) as the first entry; then one navigation entry per series
- `build_author_books_feed(books_page, author, request, has_perm=False, thick=False) → dict` — acquisition feed of thin entries (thick when `thick=True`); serves both `/authors/<pk>/books/` and `/authors/<pk>/books/recent/`; `detail=thick` preserved on pagination links
- `build_series_entry(series, request) → dict`
- `build_series_tree_feed(node, request) → dict` — navigation sub-tree (same shape as authors, `series/tree/<name>/` and `series/?filter=|?regex=` links)
- `build_series_results_feed(series_page, request) → dict` — flat paginated list; entries link to `series/<pk>/`
- `build_series_detail_feed(series, subseries_qs, books_with_seq, request, has_perm=False, page_obj=None, thick=False) → dict` — subseries navigation entries first, then book acquisition entries (thin by default, thick when `thick=True`); book title format: `f"#{seq} · {title}"`. Subseries nav entries carry the logo thumbnail.
- `build_book_entry(book, request, has_perm=False, thick=False) → dict` — produces a **thin** entry by default (`kind='thin'`: title, id, permission-gated acquisition link, **mandatory** `rel="alternate"` → `/opds/v1/books/<pk>/`, cover thumbnail only) and a **complete** entry when `thick=True` (`kind='thick'`: sanitized-XHTML description in `content`, structured `series` list for `<calibre:*>`, full cover + thumbnail (real cover when `book.cover` is set, else the `no_cover` placeholders — links never omitted), one author `rel="related"` per author, one series `rel="related"` per series, permission-gated acquisition link). **Never emits an `<author>` element** — authors are `rel="related"` links only. Description is sanitized, not truncated.
- `build_book_tree_feed(node, request, base_url='books') → dict` — navigation sub-tree; child links to `<base_url>/tree/<name>/` or `<base_url>/?filter=|?regex=`. `base_url` is `'books'` for the main tree and `'genres/<pk>/books'` for the genre-scoped tree, so the same builder serves both
- `build_book_results_feed(books_page, request, has_perm=False, thick=False) → dict` — flat paginated **acquisition** list of thin entries (thick when `thick=True`); conditional acquisition link per `has_perm`. Serves `/books/` and `/genres/<pk>/books/` results. When `thick`, the `detail=thick` param is preserved on all pagination links.
- `build_book_detail_feed(book, request, has_perm=False) → dict` — single **complete** book entry (always thick shape; this is the `rel="alternate"` target)
- `build_genre_root_feed(genres_with_counts, request) → dict` — list of `(genre, count)` tuples; entries link to `genres/<pk>/`
- `build_genre_detail_feed(genre, subgenres, request) → dict` — **subgenres only**: one navigation entry per direct subgenre linking to `genres/<subpk>/`. No book/alphabet entries. (The view 302-redirects instead of calling this when `subgenres` is empty.)
- `build_search_root_feed(query, counts, request) → dict` — navigation feed with up to 3 section entries (`"Authors (N found)"`, `"Series (N found)"`, `"Books (N found)"`), each linking to its own `search/<section>/?q=<query>` sub-feed; entry omitted when its count is 0. Not paginated.
- `build_search_authors_feed(authors_page, query, request) → dict` — paginated navigation feed; entries link to `authors/<pk>/`
- `build_search_series_feed(series_page, query, request) → dict` — paginated navigation feed; entries link to `series/<pk>/`
- `build_search_books_feed(books_page, query, request, has_perm=False, thick=False) → dict` — paginated acquisition feed of thin entries (thick when `thick=True`); conditional download link; `q` (and `detail=thick` when set) preserved on pagination links
- `build_opensearch_description(request) → dict`

### MODIFY `bookshelf/library/services.py`

Add one helper next to `find_alphabet_node`:

```python
def find_alphabet_node_by_name(root, name):
    """Depth-first search for the tree node whose .name == name; None if absent."""
    if root.name == name:
        return root
    for child in root.entries:
        found = find_alphabet_node_by_name(child, name)
        if found is not None:
            return found
    return None
```

Used by the tree views to resolve `…/tree/<name>/` path segments. No other change to `services.py`. (Confirm the attribute names `.name` / `.entries` against the actual `AlphabetTree`/node implementation before coding.)

### CREATE `bookshelf/library/opds/views.py`

Base class and all view classes.

`OPDSPageNumberPagination(PageNumberPagination)`:
- `page_size = settings.OPDS_PAGE_SIZE`
- `page_query_param = 'page'`
- No `page_size_query_param`

`OPDSBaseView(APIView)`:
- `renderer_classes = [OPDSRenderer]`
- `throttle_classes = [OPDSMinuteRateThrottle, OPDSDayRateThrottle]`
- `authentication_classes = []`
- `permission_classes = [AllowAny]`
- `pagination_class = OPDSPageNumberPagination`
- `_paginate(self, queryset, request)` helper → returns `(page, pagination_info_dict)` or `(queryset, None)`

View classes (all have a single `get(self, request, ...)` method):

| Class | URL (relative to `/opds/v1/`) | Notes |
|---|---|---|
| `RootFeedView` | `` | Returns `build_root_feed(request)`; browse entries link to `…/tree/` roots and `genres/` |
| `AuthorListFeedView` | `authors/` | Flat **results**: `?regex=`→`last_name__iregex`, elif `?filter=`→`last_name__istartswith`, else full; paginated |
| `AuthorTreeFeedView` | `authors/tree/` and `authors/tree/<str:name>/` | Builds full author tree; no `name` → root tree; with `name` → `find_alphabet_node_by_name` (404 if missing/leaf) → sub-tree feed with "all" entry |
| `AuthorDetailFeedView` | `authors/<int:pk>/` | `get_object_or_404(Author, pk=pk)` |
| `AuthorSeriesFeedView` | `authors/<int:pk>/series/` | Queries series via `BookSeriesLink`; computes per-author per-series book count; **prepends** a "Standalone Books" entry (linking to `authors/<pk>/books/?series=none`) as the first entry when `author.books.filter(bookserieslink__isnull=True).exists()` |
| `AuthorBooksFeedView` | `authors/<int:pk>/books/` | `author.books.order_by('title')`, paginated; honours optional `?series=none` → filters `bookserieslink__isnull=True` (powers the Standalone Books category) |
| `AuthorRecentBooksFeedView` | `authors/<int:pk>/books/recent/` | `author.books.order_by('-created_at')`, paginated |
| `GenreRootFeedView` | `genres/` | `Genre.objects.filter(parent=None)`; book count via `{genre.pk} \| get_descendants([genre.pk])` queryset; entries link to `genres/<pk>/` |
| `GenreDetailFeedView` | `genres/<int:pk>/` | `get_object_or_404`; `subgenres = genre.subgenres.all()`. If empty → `redirect('opds:genre_book_tree', pk=pk)` (**302**). Else `build_genre_detail_feed` (subgenres only) |
| `GenreBookTreeFeedView` | `genres/<int:pk>/books/tree/` and `genres/<int:pk>/books/tree/<str:name>/` | Genre-scoped instance of `AuthorTreeFeedView`/`BookTreeFeedView`: `get_alphabet_tree` on the genre (+descendants) book qs; child links use the `genres/<pk>/books` base; `find_alphabet_node_by_name` for `<name>` |
| `GenreBookListFeedView` | `genres/<int:pk>/books/` | Flat **results** on the genre (+descendants) base qs: `?regex=`→`title__iregex`, elif `?filter=`→`title__istartswith`, else full; `order_by('title')`; acquisition entries with conditional link |
| `SeriesListFeedView` | `series/` | Flat results; field `'name'`; `BookSeries` queryset |
| `SeriesTreeFeedView` | `series/tree/` and `series/tree/<str:name>/` | Same logic as `AuthorTreeFeedView`; field `'name'` |
| `SeriesDetailFeedView` | `series/<int:pk>/` | `get_object_or_404`; `series.subseries.all()` navigation; `BookSeriesLink.objects.filter(series=series).select_related('book').order_by('sequence_number')` for book entries |
| `BookListFeedView` | `books/` | Flat results; field `'title'`; conditional acquisition link per `has_perm`; thin entries by default, `?detail=thick` → complete entries (param preserved across pages) |
| `BookTreeFeedView` | `books/tree/` and `books/tree/<str:name>/` | Same logic as `AuthorTreeFeedView`; field `'title'` |
| `BookDetailFeedView` | `books/<int:pk>/` | `get_object_or_404`; `select_related`/`prefetch_related` authors, series, cover |
| `OPDSBookDownloadView` | `books/<int:pk>/download/` | **Auth phase (`BOOK-45 auth.md`).** Extends `OPDSBaseView` (inherits `BasicAuthentication` + throttles); `renderer_classes = [JSONRenderer]`; `permission_classes = [IsAuthenticated]` (→ 401 for anonymous); unpack `(filename, content_bytes, content_type) = get_book_file_content(book)`; `can_view_book(request.user, book)` → 403 if not allowed; check `content_bytes is None` → 404; return `HttpResponse` with Content-Disposition |
| `OPDSLoginView` | `login/` | **Auth phase (`BOOK-45 auth.md`).** Extends `OPDSBaseView`; `renderer_classes = [JSONRenderer]`; `permission_classes = [IsAuthenticated]` → 401 (+ `WWW-Authenticate: Basic`) for anonymous; `get()` returns `redirect('opds:root')` (302) once authenticated |
| `SearchRootFeedView` | `search/` | Calls `search_entities(q)`; emits a navigation feed of ≤ 3 section entries with per-section counts, each linking to its sub-feed; not paginated; empty/missing `q` → empty feed |
| `SearchAuthorsFeedView` | `search/authors/` | `search_entities(q)` authors queryset; paginated navigation feed; entries link to `authors/<pk>/` |
| `SearchSeriesFeedView` | `search/series/` | `search_entities(q)` series queryset; paginated navigation feed; entries link to `series/<pk>/` |
| `SearchBooksFeedView` | `search/books/` | `search_entities(q)` books queryset; paginated acquisition feed; conditional acquisition link per `has_perm` |
| `OpenSearchDescriptionView` | `search/description.xml` | `renderer_classes = [OpenSearchRenderer]`; `throttle_classes = [OPDSMinuteRateThrottle, OPDSDayRateThrottle]` |

### CREATE `bookshelf/library/opds/urls.py`

`app_name = 'opds'`. URL patterns. URL names for use as `reverse('opds:<name>')`.

**Ordering:** the `<int:pk>` converter never matches the literal segment `tree`, so the tree routes and detail routes don't collide. Within the genre group, declare `…/books/tree/<str:name>/` and `…/books/tree/` before `…/books/` so a request to `…/books/tree/` is not swallowed by a broader pattern. Keep the bare results route (`authors/`, `series/`, `books/`, `…/books/`) and the literal `tree/` routes as separate exact patterns.

| URL name | Pattern |
|---|---|
| `root` | (empty path) |
| `login` | `login/` (auth phase — `BOOK-45 auth.md`) |
| `author_list` | `authors/` |
| `author_tree` | `authors/tree/` |
| `author_tree_node` | `authors/tree/<str:name>/` |
| `author_detail` | `authors/<int:pk>/` |
| `author_series` | `authors/<int:pk>/series/` |
| `author_books` | `authors/<int:pk>/books/` |
| `author_books_recent` | `authors/<int:pk>/books/recent/` |
| `genres` | `genres/` |
| `genre_detail` | `genres/<int:pk>/` |
| `genre_book_tree` | `genres/<int:pk>/books/tree/` |
| `genre_book_tree_node` | `genres/<int:pk>/books/tree/<str:name>/` |
| `genre_book_list` | `genres/<int:pk>/books/` |
| `series_list` | `series/` |
| `series_tree` | `series/tree/` |
| `series_tree_node` | `series/tree/<str:name>/` |
| `series_detail` | `series/<int:pk>/` |
| `book_list` | `books/` |
| `book_tree` | `books/tree/` |
| `book_tree_node` | `books/tree/<str:name>/` |
| `book_detail` | `books/<int:pk>/` |
| `book_download` | `books/<int:pk>/download/` |
| `search` | `search/` |
| `search_authors` | `search/authors/` |
| `search_series` | `search/series/` |
| `search_books` | `search/books/` |
| `opensearch_description` | `search/description.xml` |

### CREATE `bookshelf/library/tests/tests_opds.py`

Single test file. See Section 4.

### MODIFY `bookshelf/bookshelf/settings.py`

Three changes:
1. Add `'rest_framework'` to `INSTALLED_APPS`.
2. Add after `PAGINATE_BY`:
   ```python
   OPDS_PAGE_SIZE = 20
   ```
3. Add `REST_FRAMEWORK` dict:
   ```python
   REST_FRAMEWORK = {
       'DEFAULT_THROTTLE_RATES': {
           'opds_anon': '60/min',
           'opds_anon_daily': '1000/day',
       }
   }
   ```

> **Auth phase (`BOOK-45 auth.md`):** no `DEFAULT_AUTHENTICATION_CLASSES` is added here — `BasicAuthentication` is set per-view on `OPDSBaseView` (`authentication_classes = [BasicAuthentication]`) so the rest of the project is unaffected.

### MODIFY `bookshelf/bookshelf/urls.py`

Add one line to `urlpatterns`:
```python
path('opds/v1/', include(('library.opds.urls', 'library'), namespace='opds')),
```

The `('library.opds.urls', 'library')` 2-tuple sets the app namespace to `'library'` (required by DRF when including namespaced URLs). The instance namespace is `'opds'`. URLs reverse as `reverse('opds:root')`, `reverse('opds:book_detail', kwargs={'pk': 1})`, etc.

---

## 3. Execution Steps

1. **Settings wiring** — Modify `bookshelf/bookshelf/settings.py`: add `'rest_framework'` to `INSTALLED_APPS`, add `OPDS_PAGE_SIZE = 20`, add the `REST_FRAMEWORK` dict with throttle rates.

2. **Root URL** — Modify `bookshelf/bookshelf/urls.py`: add `path('opds/v1/', include(('library.opds.urls', 'library'), namespace='opds'))` to `urlpatterns`.

3. **Package skeleton** — Create `bookshelf/library/opds/__init__.py` (empty).

4. **Throttles** — Create `bookshelf/library/opds/throttles.py` with `OPDSMinuteRateThrottle` and `OPDSDayRateThrottle`.

5. **Renderer** — Create `bookshelf/library/opds/renderers.py`:
   - Register all 6 namespaces at module level (core 4 + `xhtml` + `calibre`).
   - Implement `_build_entry()` first (leaf builder), then `_build_feed()`.
   - Confirm `ET.tostring(root, encoding='unicode').encode('utf-8')` — never `encoding='utf-8'`.
   - Implement `OpenSearchRenderer`.

6. **Serializers** — Create `bookshelf/library/opds/serializers.py`:
   - Implement atomic entry builders first (`build_author_entry`, `build_book_entry`, `build_series_entry`).
   - Then implement feed-level builders.
   - Thumbnail: `book.cover_preview.url` — not `book.cover.url`.
   - Cover links: `request.build_absolute_uri(book.cover.url)`.
   - Cover/thumbnail links are **always emitted**: use `book.cover.url` / `book.cover_preview.url` when `book.cover` is set, else fall back to the static `no_cover 600x900.jpeg` / `no_cover 40x60.jpeg` placeholders (build absolute via `request.build_absolute_uri('/static/img/...')`). Never omit the image link for a cover-less book.
   - Book entries are **thin by default**; `build_book_entry(..., thick=True)` emits the complete shape. Listing views pass `thick = request.query_params.get('detail') == 'thick'` and preserve `detail=thick` on pagination links.
   - Complete book entry: sanitized-XHTML description in `content` (via `_sanitize_html`, **not** truncated), structured `series` list for `<calibre:*>`, author + series `rel="related"` links, **no `<author>` element**.
   - Thin book entry: mandatory `rel="alternate"` link → `/opds/v1/books/<pk>/`, cover thumbnail only.
   - Non-book entries: attach the logo thumbnail and a mandatory count in `content`.
   - Series book title: `f"#{seq} · {title}"` (U+00B7 middle dot).
   - Standalone Books entry: **prepend as the first entry** only when `author.books.filter(bookserieslink__isnull=True).exists()`; link it to `authors/<pk>/books/?series=none`.
   - Author Detail feed: emit exactly 3 sub-feed entries (`Books by Title`, `New Arrivals`, `Books by Series`).
   - Search root feed: ≤ 3 section entries linking to `search/authors|series|books/?q=…`; never flatten sections into one feed.
   - "all `<prefix>`" synthetic entry: prepend as first entry when the rendered tree node has children; link it to the **results** endpoint (`…/?filter=<prefix>`, or `…/?regex=<regex>` for `other`), never to a `…/tree/` URL.
   - Tree child links: expandable → `…/tree/<child.name>/`; leaf → `…/?filter=<child.filter>` or `…/?regex=<child.regex>`.

7. **Views** — Create `bookshelf/library/opds/views.py`:
   - Add `find_alphabet_node_by_name` to `library/services.py` first (tree views depend on it).
   - Implement `OPDSPageNumberPagination` and `OPDSBaseView`.
   - `RootFeedView` first (no DB needed); browse entries point at `…/tree/` roots and `genres/`.
   - `BookDownloadView` second (critical integration point): `permission_classes = [AllowAny]`; explicit `has_perm` check; correct 3-tuple unpacking.
   - Tree views and results views per entity (Author, Series, Book): tree view resolves `<name>` via `find_alphabet_node_by_name`; results view applies `iregex`/`istartswith`/full precedence and paginates.
   - Detail views in order: Author (incl. `?series=none` filter), Series, Genre, Book, Search root + 3 section sub-feeds, OpenSearch.
   - `GenreDetailFeedView`: `subgenres = genre.subgenres.all()`; if empty → `redirect('opds:genre_book_tree', pk=pk)` (302); else subgenres-only feed.
   - `GenreBookTreeFeedView` / `GenreBookListFeedView`: compute `all_ids = {pk} | get_descendants([pk])`; build the genre book queryset; tree view feeds `get_alphabet_tree` and uses the `genres/<pk>/books` base for child links; results view filters by `?filter=`/`?regex=`.

8. **URL configuration** — Create `bookshelf/library/opds/urls.py` with all patterns. The `<int:pk>` converter won't match the literal `tree`, so tree and detail routes are unambiguous; within the genre group declare `…/books/tree/…` before `…/books/`.

9. **Import sanity check** — `uv run python bookshelf/manage.py check`

10. **Write tests** — Create `bookshelf/library/tests/tests_opds.py`. Include the cross-cutting classes `OPDSBookVerbosityTest` (thin/thick §6.5a) and `OPDSEntryImageTest` (logo thumbnail §8), and the complete-book-entry assertions in `OPDSBookDetailTest` (`rel="related"` authors/series, `<content type="xhtml">`, `<calibre:*>`, no `<author>` element).

11. **Run tests** — `uv run python bookshelf/manage.py test library.tests.tests_opds`

---

## 4. Test Cases

**File:** `bookshelf/library/tests/tests_opds.py`

**Required imports:**
```python
import xml.etree.ElementTree as ET
import base64
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, AnonymousUser
from django.conf import settings
from rest_framework.settings import api_settings
from parameterized import parameterized
from bookshelf.tests.base_test import BaseTestCase
from library.models import Author, Book, BookSeries, BookSeriesLink, Genre, Language
from library.tests.test_data_factory import create_test_dataset
from library.tests.epub_test_utils import create_epub_one_author
from library.services import get_book_file_content, can_view_book

User = get_user_model()
```

**Auth helper** (for `CanViewBookTest`, `OPDSLoginViewTest`, `OPDSBookDownloadTest`, and the authenticated root-feed case) — Basic credentials are sent via `HTTP_AUTHORIZATION`:
```python
def _basic(username, password):
    token = base64.b64encode(f'{username}:{password}'.encode()).decode()
    return f'Basic {token}'
```

**Reusable constants:**
```python
NS = {
    'atom':       'http://www.w3.org/2005/Atom',
    'opds':       'http://opds-spec.org/2010/catalog',
    'dc':         'http://purl.org/dc/terms/',
}
```

**Reusable helper:**
```python
def _parse(response):
    return ET.fromstring(response.content)
```

**Fixture strategy (from memory note):**
- `OPDSBookDetailTest` and `OPDSBookDownloadTest` → small detail fixture inline + `BaseTestCase`
- All other detail-level tests → `create_test_dataset()` in `setUpTestData`

---

### `OPDSRootFeedTest(TestCase)`

No DB content needed.

| # | Method | Setup | Action | Assert |
|---|---|---|---|---|
| 1 | `test_root_feed_status_200` | — | GET `/opds/v1/` | `response.status_code == 200` |
| 2 | `test_root_feed_content_type` | — | GET `/opds/v1/` | `response['Content-Type']` starts with `application/atom+xml` |
| 3 | `test_root_feed_anonymous_has_five_entries` | — | Anonymous GET, parse | `len(root.findall('atom:entry', NS)) == 5` (Authors, Genres, Series, Books, Login) |
| 3a | `test_root_feed_authenticated_omits_login_entry` | valid Basic creds | GET with `HTTP_AUTHORIZATION`, parse | exactly 4 entries; no `Login` entry |
| 4 | `test_root_feed_entry_titles` | — | Anonymous GET, parse entries | Titles are exactly `{'Authors', 'Genres', 'Series', 'Books', 'Login'}`; the `Login` entry's `subsection` href ends with `/opds/v1/login/` |
| 5 | `test_root_feed_self_link` | — | GET, parse | `<link rel="self">` href ends with `/opds/v1/` |
| 6 | `test_root_feed_start_link` | — | GET, parse | `<link rel="start">` href ends with `/opds/v1/` |
| 7 | `test_root_feed_search_link_at_feed_level` | — | GET, parse | exactly one feed-level `<link rel="search" type="application/opensearchdescription+xml">`, and **no** `Search` `<entry>` |
| 7a | `test_root_feed_has_templated_atom_search_link` | — | GET, parse | exactly one feed-level templated `<link rel="search" type="application/atom+xml">` whose href contains `search/?q={searchTerms}` |
| 8 | `test_root_feed_is_pretty_printed` | — | GET | `b'\n' in response.content` and `b'  <' in response.content` |

---

### `OPDSAlphabetTreeTest` (parameterized)

**Fixture:** `create_test_dataset()` in `setUpTestData`.
**Parameterized** over `[('authors', '/opds/v1/authors/tree/'), ('books', '/opds/v1/books/tree/'), ('series', '/opds/v1/series/tree/')]`.

| # | Method | Assert |
|---|---|---|
| 1 | `test_alphabet_feed_status_200[<name>]` | 200 |
| 2 | `test_alphabet_feed_is_navigation[<name>]` | `Content-Type` contains `kind=navigation` |
| 3 | `test_alphabet_feed_has_entries[<name>]` | `len(entries) >= 1` |
| 4 | `test_alphabet_feed_entries_have_subsection_links[<name>]` | Every entry has `<link rel="subsection">` |
| 5 | `test_alphabet_feed_self_link[<name>]` | `<link rel="self">` present |
| 6 | `test_alphabet_feed_quantity_in_content[<name>]` | Every entry `<content>` contains a digit string |
| 7 | `test_alphabet_feed_only_reflects_existing_data[<name>]` | No entry titled `z`; an entry titled `0-9` is present |

---

### `OPDSAlphabetTreeCountsTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`.

| # | Method | Assert |
|---|---|---|
| 1 | `test_authors_root_entry_count` | `/opds/v1/authors/tree/` — exactly 6 entries: A, B, C, Ш, `0-9`, Other |
| 2 | `test_authors_root_a_count_is_137` | `A` entry `<content>` contains `137` |
| 3 | `test_authors_root_digits_count_is_12` | `0-9` entry `<content>` contains `12` |
| 4 | `test_authors_a_sub_entries` | `/opds/v1/authors/tree/a/` entries: `all a (137)`, `Ab (110)`, `Ac (11)`, `Ad (16)` — exactly these 4 |
| 5 | `test_authors_ab_sub_entries` | `/opds/v1/authors/tree/ab/` entries: `all ab (110)`, `Aba (60)`, `Abi (42)`, `Aby (8)` |
| 6 | `test_authors_aba_sub_entries` | `/opds/v1/authors/tree/aba/` entries: `all aba (60)`, `Abak (21)`, `Aban (39)` |
| 7 | `test_books_root_entry_count` | `/opds/v1/books/tree/` — exactly 6 entries: A, B, M, П, `0-9`, Other |
| 8 | `test_books_a_count_is_222` | `A` entry `<content>` contains `222` |
| 9 | `test_books_root_digits_count_is_14` | `0-9` entry `<content>` contains `14` |
| 10 | `test_books_a_sub_entries` | `/opds/v1/books/tree/a/` entries: `all a (222)`, `Al (96)`, `An (83)`, `Ar (43)` |
| 11 | `test_books_ali_sub_entries` | `/opds/v1/books/tree/ali/` entries: `all ali (57)`, `Alid (23)`, `Alit (34)` |
| 12 | `test_series_root_entry_count` | `/opds/v1/series/tree/` — exactly 5 entries: C, S, T, `0-9`, Other |
| 13 | `test_series_root_digits_count_is_10` | `0-9` entry `<content>` contains `10` |
| 14 | `test_series_s_count_is_62` | `S` entry `<content>` contains `62` |
| 15 | `test_series_s_sub_entries` | `/opds/v1/series/tree/s/` entries: `all s (62)`, `Sh (6)`, `St (54)`, `Sw (2)` |
| 16 | `test_series_st_sub_entries` | `/opds/v1/series/tree/st/` entries: `all st (54)`, `Sta (28)`, `Ste (26)` |

---

### `OPDSAlphabetAllNodeTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`.

| # | Method | Assert |
|---|---|---|
| 1 | `test_expanded_node_has_all_child` | `/opds/v1/authors/tree/a/` feed contains entry titled `all a` |
| 2 | `test_all_node_is_first_child` | `all a` is the first `<entry>` in the `/opds/v1/authors/tree/a/` feed |
| 3 | `test_all_node_link_points_to_results_filter` | `all a` `<link href>` is `/opds/v1/authors/?filter=a` (results endpoint, no sub-filter, no `regex`) |
| 4 | `test_all_node_count_equals_parent_count` | `all a` `<content>` contains `137` |
| 5 | `test_leaf_node_links_to_results` | `Ac` (leaf) entry in `/opds/v1/authors/tree/a/` links to `/opds/v1/authors/?filter=ac`; no `all ac` entry exists |
| 6 | `test_all_node_present_at_second_level` | `/opds/v1/authors/tree/ab/` expanded; `all ab` is first entry, count `110`, links to `/opds/v1/authors/?filter=ab` |
| 7 | `test_all_node_present_at_third_level` | `/opds/v1/authors/tree/aba/` expanded; `all aba` is first entry, count `60`, links to `/opds/v1/authors/?filter=aba` |
| 8 | `test_books_expanded_node_has_all_child` | `/opds/v1/books/tree/a/` first entry is `all a`, count `222`, links to `/opds/v1/books/?filter=a` |
| 9 | `test_series_expanded_node_has_all_child` | `/opds/v1/series/tree/s/` first entry is `all s`, count `62`, links to `/opds/v1/series/?filter=s` |
| 10 | `test_digits_node_is_leaf_no_all_entry` | `0-9` tree entry links to `/opds/v1/authors/?regex=^[0-9]`; that results feed has 12 entries; no entry titled `all 0-9` |

---

### `OPDSOtherNodeTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`.

| # | Method | Assert |
|---|---|---|
| 1 | `test_authors_root_has_other_entry` | `/opds/v1/authors/tree/` has `Other` entry, count `14` |
| 2 | `test_books_root_has_other_entry` | `/opds/v1/books/tree/` has `Other` entry, count `31` |
| 3 | `test_series_root_has_other_entry` | `/opds/v1/series/tree/` has `Other` entry, count `11` |
| 4 | `test_other_entry_link_is_tree_path` | `Other` entry `<link href>` is `/opds/v1/authors/tree/other/` (expandable node, not `?regex=`) |
| 5 | `test_other_node_feed_has_non_alpha_child` | GET `/opds/v1/authors/tree/other/` → entry `* (all non-alpha)`, count `3` |
| 6 | `test_other_node_feed_has_z_child` | `/opds/v1/authors/tree/other/` feed has `Z` entry, count `8` |
| 7 | `test_other_node_feed_has_all_other_first` | `/opds/v1/authors/tree/other/` feed first entry is `all Other`, count `14` |
| 8 | `test_all_other_link_points_to_results_regex` | `all Other` `<link href>` is `/opds/v1/authors/?regex=<other_regex>` (results endpoint), distinct from the `Other` root entry (`tree/other/`) |
| 9 | `test_all_other_count_equals_other_total` | Parameterized: authors→14, books→31, series→11 |
| 10 | `test_non_alpha_child_link_uses_regex_param` | `* (all non-alpha)` entry (in `tree/other/`) link is `/opds/v1/authors/?regex=` with URL-encoded non-alpha pattern |
| 11 | `test_non_alpha_list_returns_only_non_alpha_items` | GET `/opds/v1/authors/?regex=^[^[:alpha:][:digit:]]` → exactly 3 entries; no Z/Ї/Э entries |
| 12 | `test_non_alpha_books_list_count` | GET `/opds/v1/books/?regex=^[^[:alpha:][:digit:]]` → 14 total entries; all titles begin with non-alpha |
| 13 | `test_non_alpha_series_list_count` | GET `/opds/v1/series/?regex=^[^[:alpha:][:digit:]]` → 4 entries |
| 14 | `test_all_other_list_returns_complete_other_set` | GET `/opds/v1/authors/?regex=<other_regex>` → 14 total authors across pages |
| 15 | `test_z_child_is_leaf_links_to_results` | `Z` entry in `tree/other/` links to `/opds/v1/authors/?filter=z`; no `all z` entry |
| 16 | `test_demoted_alpha_child_link_uses_filter_param` | `Z` entry uses `/opds/v1/authors/?filter=z` (results endpoint, not `?regex=`) |
| 17 | `test_books_other_q_child_count` | `/opds/v1/books/tree/other/` has `Q` entry, count `7` |
| 18 | `test_books_other_x_child_count` | `/opds/v1/books/tree/other/` has `X` entry, count `8` |
| 19 | `test_series_other_n_child_count` | `/opds/v1/series/tree/other/` has `N` entry, count `4` |
| 20 | `test_series_other_cyrillic_в_child_count` | `/opds/v1/series/tree/other/` has `В` entry, count `3` |
| 21 | `test_digits_node_is_separate_from_other` | Root tree feeds: `0-9` entry is a sibling of `Other`, not a child; `tree/other/` feed has no `0-9` child |

---

### `OPDSAuthorListFeedTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`.

| # | Method | Assert |
|---|---|---|
| 1 | `test_author_alphabet_root_has_a_entry` | `/opds/v1/authors/tree/` has `A` entry, count `137` |
| 2 | `test_author_alphabet_root_has_b_entry` | Root tree has `B` entry, count `58` |
| 3 | `test_author_alphabet_root_no_entry_for_missing_letter` | Root tree has no `z` entry |
| 4 | `test_author_results_by_filter_status_200` | GET `/opds/v1/authors/?filter=b` → 200 |
| 5 | `test_author_results_by_filter_has_correct_count` | `/opds/v1/authors/?filter=b` → exactly 20 entries |
| 6 | `test_author_results_entry_links_to_author_detail` | Each entry links to `/opds/v1/authors/<pk>/` |
| 7 | `test_author_results_filter_not_found_returns_empty_feed` | GET `/opds/v1/authors/?filter=y` → 200, 0 entries |
| 8 | `test_author_results_sorted_alphabetically` | Entries in `/opds/v1/authors/?filter=b` are in ascending last_name order |
| 9 | `test_author_digits_node_list` | GET `/opds/v1/authors/?regex=^[0-9]` → 200, exactly 12 entries |
| 10 | `test_author_results_entry_content_has_book_count` | Each entry on `/opds/v1/authors/?filter=b` has `<content type="text">` containing that author's book count (e.g. `"<n> books"`); an author with 0 books shows `0` |

---

### `OPDSGenreFeedTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`. Add inline in `setUpTestData`: `genre_empty = Genre.objects.create(name='Empty Genre', code='empty_genre')` (no parent, no children, no books). Retrieve canonical genres via `Genre.objects.get(code='sf_fantasy')`, etc. Redirect assertions use `self.client.get(url)` (default `follow=False`) and check `status_code == 302` + `response['Location']`.

Genre detail (`/genres/<pk>/`) is **subgenres-only** and 302-redirects to the genre book tree when a genre is a leaf. Book browsing lives at `/genres/<pk>/books/tree/[...]` and `/genres/<pk>/books/?filter=|?regex=`.

| # | Method | Assert |
|---|---|---|
| 1 | `test_genre_root_status_200` | GET `/opds/v1/genres/` → 200 |
| 2 | `test_genre_root_is_navigation` | `Content-Type` contains `kind=navigation` |
| 3 | `test_genre_root_lists_top_level_genres_only` | Feed contains `sf_fantasy`, `mysteries_thrillers`, `action_adventure`, `genre_empty`; does NOT contain `dystopia`, `science_fiction`, etc. |
| 4 | `test_genre_root_entry_links_to_genre_detail` | Each entry has `<link rel="subsection" href="…/opds/v1/genres/<pk>/">` |
| 5 | `test_genre_root_entry_content_has_book_count` | `Science Fiction & Fantasy` entry `<content>` contains `279` |
| 6 | `test_genre_root_genre_with_no_books_still_listed` | `genre_empty` entry present with count `0` |
| 7 | `test_genre_detail_with_subgenres_status_200` | GET `/opds/v1/genres/<sf_fantasy.pk>/` → 200 (has subgenres) |
| 8 | `test_genre_detail_404` | GET `/opds/v1/genres/99999/` → 404 |
| 9 | `test_genre_detail_lists_subgenres_only` | `sf_fantasy` feed has exactly 3 navigation entries — `dystopia`, `science_fiction`, `fantasy` — each linking to `/opds/v1/genres/<subpk>/` |
| 10 | `test_genre_detail_has_no_book_or_alphabet_entries` | `sf_fantasy` feed has no acquisition/book entries and no alphabet entries (no `alid`) |
| 11 | `test_genre_detail_leaf_genre_redirects_to_book_tree` | GET `/opds/v1/genres/<dystopia.pk>/` → 302; `Location` ends in `/opds/v1/genres/<dystopia.pk>/books/tree/` |
| 12 | `test_genre_detail_empty_genre_redirects_to_book_tree` | GET `/opds/v1/genres/<genre_empty.pk>/` → 302 to `/opds/v1/genres/<genre_empty.pk>/books/tree/` |
| 13 | `test_genre_book_tree_status_200_navigation` | GET `/opds/v1/genres/<sf_fantasy.pk>/books/tree/` → 200, `kind=navigation` |
| 14 | `test_genre_book_tree_has_alphabet_entries` | `/opds/v1/genres/<sf_fantasy.pk>/books/tree/` has alphabet entries for descendant books (e.g. `al`/`ali` branch) |
| 15 | `test_genre_book_tree_only_contains_own_books` | `/opds/v1/genres/<dystopia.pk>/books/tree/`: only letters present in dystopia books |
| 16 | `test_genre_book_tree_empty_genre_returns_empty_tree` | GET `/opds/v1/genres/<genre_empty.pk>/books/tree/` → 200, 0 alphabet entries |
| 17 | `test_genre_book_tree_leaf_links_to_results` | Leaf alphabet entry link is `/opds/v1/genres/<pk>/books/?filter=<letter>` |
| 18 | `test_genre_book_tree_non_leaf_links_to_subtree` | `sf_fantasy` expandable letter → link `/opds/v1/genres/<pk>/books/tree/<name>/`; that sub-tree has `all <letter>` first |
| 19 | `test_genre_book_tree_regex_node_link_carries_regex_param` | `0-9` leaf in tree links to `/opds/v1/genres/<pk>/books/?regex=^[0-9]`; `other` node links to `…/books/tree/other/` |
| 20 | `test_genre_books_results_by_filter_status_200` | GET `/opds/v1/genres/<dystopia.pk>/books/?filter=alid` → 200 |
| 21 | `test_genre_books_results_by_filter_filters_correctly` | All entry titles start with `Alid`; no `Alit`-prefix entries; no book whose only genre is `mystery` |
| 22 | `test_genre_books_results_empty_filter_returns_empty_feed` | GET `/opds/v1/genres/<dystopia.pk>/books/?filter=z` → 200, 0 entries |
| 23 | `test_genre_books_results_by_regex_filters_by_regex` | Genre with a `0-9` node: GET `/opds/v1/genres/<pk>/books/?regex=^[0-9]` → 200; total = that genre's `0-9` tree count; all titles start with a digit |
| 24 | `test_genre_books_results_regex_beats_filter` | GET `/opds/v1/genres/<pk>/books/?filter=0-9` (no `?regex=`) → 0 entries (proves `?regex=` drives non-letter nodes) |

---

### `OPDSGenreFeedCountsTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`.

| # | Method | Assert |
|---|---|---|
| 1 | `test_genre_root_sf_fantasy_count` | `Science Fiction & Fantasy` entry `<content>` contains `279` |
| 2 | `test_genre_root_mysteries_count` | `Mysteries & Thrillers` entry `<content>` contains `208` |
| 3 | `test_genre_root_action_adv_count` | `Action & Adventure` entry `<content>` contains `185` |
| 4 | `test_dystopia_book_tree_has_alid_entry` | `/opds/v1/genres/<dystopia.pk>/books/tree/` has the `alid` branch |
| 5 | `test_fantasy_book_tree_no_yu_entry` | `/opds/v1/genres/<fantasy.pk>/books/tree/` has no `ю` alphabet entry |
| 6 | `test_nature_animals_book_tree_total_is_74` | `/opds/v1/genres/<nature_animals.pk>/books/tree/`: sum of top-level alphabet entry `<content>` counts (excluding `"all …"`) = 74 |
| 7 | `test_genre_books_results_alid_dystopia` | GET `/opds/v1/genres/<dystopia.pk>/books/?filter=alid` → exactly 5 entries |
| 8 | `test_genre_books_results_count_matches_table` | GET `/opds/v1/genres/<dystopia.pk>/books/?filter=alit` → exactly 7 entries |

---

### `OPDSSeriesListFeedTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`.

| # | Method | Assert |
|---|---|---|
| 1 | `test_series_alphabet_root_status_200` | GET `/opds/v1/series/tree/` → 200 |
| 2 | `test_series_alphabet_root_is_navigation` | `Content-Type` contains `kind=navigation` |
| 3 | `test_series_alphabet_root_has_s_entry` | Root tree has `S` entry, count `62` |
| 4 | `test_series_alphabet_root_no_entry_for_missing_letter` | Root tree has no `z` entry |
| 5 | `test_series_results_by_filter_status_200` | GET `/opds/v1/series/?filter=t` → 200 |
| 6 | `test_series_results_has_correct_count` | `/opds/v1/series/?filter=t` → exactly 11 entries (T=11, leaf) |
| 7 | `test_series_results_entry_links_to_series_detail` | Each entry links to `/opds/v1/series/<pk>/` |
| 8 | `test_series_results_empty_filter_returns_empty_feed` | GET `/opds/v1/series/?filter=z` → 200, 0 entries |
| 9 | `test_series_s_is_expanded_subtree` | GET `/opds/v1/series/tree/s/` → navigation sub-entries (`Sh`, `St`, `Sw`, `all s`); not 62 flat series entries |
| 10 | `test_series_digits_node_list` | GET `/opds/v1/series/?regex=^[0-9]` → 200, exactly 10 entries |
| 11 | `test_series_results_entry_content_has_book_count` | Each entry on `/opds/v1/series/?filter=t` has `<content type="text">` containing that series' total book count (per §8) |
| 12 | `test_series_results_zero_book_series_shows_count_0` | A series with no books (created locally in this test) → its results entry `<content>` count is `0` (count mandatory even when zero) |

---

### `OPDSBookListFeedTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`. Create `user_no_perm` and `user_with_perm` in `setUpTestData`.

| # | Method | Assert |
|---|---|---|
| 1 | `test_book_alphabet_root_has_a_entry` | `/opds/v1/books/tree/` has `A` entry, count `222` |
| 2 | `test_book_alphabet_root_no_entry_for_missing_letter` | Root tree has no `z` entry |
| 3 | `test_book_results_by_filter_status_200` | GET `/opds/v1/books/?filter=m` → 200 |
| 4 | `test_book_results_has_correct_count` | `/opds/v1/books/?filter=m` → exactly 20 entries (page 1 of 43) |
| 5 | `test_book_results_excludes_other_letter` | All entries have titles starting with `M`; no `B`-prefix titles |
| 6 | `test_book_results_acquisition_link_with_perm` | `user_with_perm` GET `/opds/v1/books/?filter=m` → entries have `<link rel="http://opds-spec.org/acquisition">` |
| 7 | `test_book_results_acquisition_link_always_rendered` | Anonymous GET → entries **still** carry the acquisition link (always rendered; authorization enforced at the download endpoint) |
| 8 | `test_book_results_empty_filter_returns_empty_feed` | GET `/opds/v1/books/?filter=z` → 200, 0 entries |
| 9 | `test_book_a_is_expanded_subtree` | GET `/opds/v1/books/tree/a/` → navigation sub-entries (`Al`, `An`, `Ar`, `all a`); not 222 book entries |
| 10 | `test_book_results_cyrillic_filter` | GET `/opds/v1/books/?filter=п` → 200, entries for П=83 books (across pages) |
| 11 | `test_book_digits_node_list` | GET `/opds/v1/books/?regex=^[0-9]` → 200, exactly 14 entries |

---

### `OPDSBookVerbosityTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`. Create `user_with_perm` (member of `Book access`) inline so acquisition links render. Cross-cutting test of the §6.5a thin-default / `?detail=thick` rule across all book-listing acquisition feeds. `THICK = {'detail': 'thick'}` passed where thick mode is exercised.

| # | Method | Assert |
|---|---|---|
| 1 | `test_books_listing_entries_are_thin_by_default` | GET `/opds/v1/books/?filter=m` (no `detail`): each book entry has `<title>`, `<id>` `tag:bookshelf:book:<pk>`, `<link rel="alternate">`; **no** `<content>`, **no** `<calibre:series>`, **no** `<link rel="related">` |
| 2 | `test_thin_entry_has_mandatory_alternate_link` | Every thin entry has exactly one `<link rel="alternate" type="application/atom+xml;type=entry;profile=opds-catalog">` whose `href` ends in `/opds/v1/books/<pk>/` |
| 3 | `test_thin_entry_has_thumbnail_no_full_image` | Thin entry has `<link rel="…/image/thumbnail">` but **no** `<link rel="http://opds-spec.org/image">` |
| 4 | `test_thin_entry_has_acquisition_link_with_perm` | `user_with_perm`: thin entries carry `<link rel="http://opds-spec.org/acquisition">` |
| 5 | `test_thin_entry_acquisition_link_always_rendered` | Anon: thin entries **still** carry the acquisition link (always rendered) |
| 6 | `test_thick_entries_are_complete` | GET `/opds/v1/books/?filter=m&detail=thick`: each entry matches §6.5 — `<content type="xhtml">` (when described), `<calibre:series>`/`<calibre:series_index>` (when in series), full `<link rel="…/image">`, author `<link rel="related">` |
| 7 | `test_thick_entry_still_has_alternate_link` | Thick entry still carries `<link rel="alternate">` → `/opds/v1/books/<pk>/` |
| 8 | `test_thick_param_propagates_to_pagination_links` | `/opds/v1/books/?filter=m&detail=thick` (paginated): `next`/`previous`/`first` URLs all preserve `detail=thick` |
| 9 | `test_thin_pagination_links_have_no_detail_param` | Default thin: pagination links carry no `detail` param |
| 10 | `test_author_books_feed_thin_by_default` | `/opds/v1/authors/<pk>/books/`: entries thin (have `rel="alternate"`, no `<content>`) |
| 11 | `test_author_books_feed_thick_param` | `/opds/v1/authors/<pk>/books/?detail=thick`: entries complete |
| 12 | `test_author_books_recent_feed_thin_by_default` | `/opds/v1/authors/<pk>/books/recent/`: entries thin |
| 13 | `test_genre_books_feed_thin_by_default` | `/opds/v1/genres/<pk>/books/?filter=<x>`: entries thin |
| 14 | `test_genre_books_feed_thick_param` | `/opds/v1/genres/<pk>/books/?filter=<x>&detail=thick`: entries complete |
| 15 | `test_series_detail_book_entries_thin_by_default` | `/opds/v1/series/<pk>/`: book entries thin (subseries nav entries unaffected) |
| 16 | `test_series_detail_book_entries_thick_param` | `/opds/v1/series/<pk>/?detail=thick`: book entries complete |
| 17 | `test_search_books_feed_thin_by_default` | `/opds/v1/search/books/?q=<term>`: book entries thin |
| 18 | `test_search_books_feed_thick_param` | `/opds/v1/search/books/?q=<term>&detail=thick`: book entries complete |

---

### `OPDSThickPropagationTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`. Verifies the sticky-preference Propagation rule — `?detail=thick` is threaded through every browsable-catalog link and omitted from non-feed / always-complete links. Covers the implemented Root + Author feeds; a specific author with books/series is found via `.filter()`.

| # | Method | Assert |
|---|---|---|
| 1 | `test_root_subsection_links_preserve_detail` | GET `/opds/v1/?detail=thick`: every entry `<link rel="subsection">` href contains `detail=thick` |
| 2 | `test_root_search_query_link_preserves_detail` | Search entry `rel="search"` `application/atom+xml` link contains `detail=thick`; the `…opensearchdescription+xml` link does **not** |
| 3 | `test_root_self_and_start_links_preserve_detail` | Feed `<link rel="self">` and `<link rel="start">` hrefs both contain `detail=thick` |
| 4 | `test_root_logo_thumbnail_link_omits_detail` | The non-book logo `rel="…/image/thumbnail">` link never carries `detail=thick` |
| 5 | `test_author_tree_subsection_links_preserve_detail` | GET `/opds/v1/authors/tree/a/?detail=thick`: every child `subsection` link and the synthetic "all a" link contain `detail=thick` |
| 6 | `test_author_results_links_preserve_detail` | GET `/opds/v1/authors/?filter=b&detail=thick`: each author detail-feed `subsection` link plus `next`/`first` pagination links contain `detail=thick` |
| 7 | `test_author_detail_subsection_links_preserve_detail` | GET `/opds/v1/authors/<pk>/?detail=thick`: Books by Title / New Arrivals / Books by Series `subsection` links all contain `detail=thick` |
| 8 | `test_author_series_links_preserve_detail` | GET `/opds/v1/authors/<pk>/series/?detail=thick`: Standalone Books link + every per-series `subsection` link contain `detail=thick` |
| 9 | `test_detail_survives_drilldown_to_acquisition_feed` | Following the `detail=thick`-bearing Books-by-Title link lands on `/opds/v1/authors/<pk>/books/?detail=thick` whose book entries are complete (thick) |
| 10 | `test_navigation_links_omit_detail_by_default` | Without `?detail=thick`: no `subsection`, search-query, `self`, `start`, or pagination link carries a `detail` param |

---

### `OPDSPaginationTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`. Uses results endpoints `/opds/v1/authors/?filter=b` (B=58) and `/opds/v1/books/?filter=m` (M=43).

| # | Method | Assert |
|---|---|---|
| 1 | `test_author_list_page_1_has_20_entries` | GET `/opds/v1/authors/?filter=b` → 20 entries |
| 2 | `test_author_list_page_1_has_next_link` | Feed has `<link rel="next">` |
| 3 | `test_author_list_page_1_no_prev_link` | Feed has no `<link rel="previous">` |
| 4 | `test_author_list_page_2_has_20_entries` | GET `/opds/v1/authors/?filter=b&page=2` → 20 entries |
| 5 | `test_author_list_page_3_has_18_entries` | GET `/opds/v1/authors/?filter=b&page=3` → 18 entries (total 58) |
| 6 | `test_author_list_page_3_has_prev_link` | Page 3 feed has `<link rel="previous">` |
| 7 | `test_author_list_page_3_no_next_link` | Page 3 feed has no `<link rel="next">` |
| 8 | `test_book_list_page_1_has_20_entries` | GET `/opds/v1/books/?filter=m` → 20 entries |
| 9 | `test_book_list_page_3_has_3_entries` | GET `/opds/v1/books/?filter=m&page=3` → 3 entries (total 43) |
| 10 | `test_pagination_links_preserve_query_params` | `<link rel="next">` URL contains `filter=b` and `page=2` |

---

### `OPDSAuthorDetailTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`. Create `user_no_perm` and `user_with_perm` inline. Identify `author_with_series` and `author_standalone_only` via queryset filters.

| # | Method | Assert |
|---|---|---|
| 1 | `test_author_detail_status_200` | GET `/opds/v1/authors/<pk>/` → 200 |
| 2 | `test_author_detail_404` | GET `/opds/v1/authors/99999/` → 404 |
| 3 | `test_author_detail_has_three_sub_feeds` | Feed has exactly 3 entries: `Books by Title`, `New Arrivals`, `Books by Series` |
| 3a | `test_author_detail_sub_feed_titles_match` | The 3 sub-feed `<title>`s are exactly `Books by Title`, `New Arrivals`, `Books by Series` (in order); legacy labels `All Books (A–Z)`/`Recently Added` are absent |
| 4 | `test_author_detail_sub_feed_books_alpha_status_200` | GET `/opds/v1/authors/<pk>/books/` → 200 |
| 5 | `test_author_detail_sub_feed_books_alpha_contains_author_books` | Total entry count (across pages) equals `author.books.count()` |
| 6 | `test_author_detail_sub_feed_books_alpha_excludes_other_author` | Feed has no book known to belong only to a different author |
| 7 | `test_author_detail_sub_feed_books_alpha_sorted` | Entries are in ascending title order |
| 8 | `test_author_detail_sub_feed_books_recent_status_200` | GET `/opds/v1/authors/<pk>/books/recent/` → 200 |
| 9 | `test_author_detail_sub_feed_books_recent_sorted_by_date` | First entry `<updated>` >= second entry `<updated>` |
| 10 | `test_author_detail_sub_feed_series_status_200` | GET `/opds/v1/authors/<pk>/series/` → 200 |
| 11 | `test_author_detail_sub_feed_series_has_series` | For `author_with_series`: at least one entry links to `/opds/v1/series/<pk>/` |
| 12 | `test_author_detail_sub_feed_series_entry_has_book_count` | Series entry `<content>` contains a positive integer |
| 13 | `test_author_detail_sub_feed_series_no_standalone_entry_when_none` | Author with no standalone books → no `Standalone Books` entry |
| 14 | `test_author_detail_sub_feed_series_has_standalone_entry_first` | `author_with_series` with standalone books → the **first** entry is `Standalone Books`, `<link href>` ends in `/opds/v1/authors/<pk>/books/?series=none` |
| 15 | `test_author_detail_sub_feed_series_standalone_entry_has_count` | `Standalone Books` `<content>` contains correct count |
| 15b | `test_author_books_series_none_filter_only_standalone` | GET `/opds/v1/authors/<pk>/books/?series=none` → total entry count (across pages) equals `author.books.filter(bookserieslink__isnull=True).count()`; contains no book that belongs to a series |
| 16 | `test_author_books_acquisition_link_always_rendered` | Anonymous GET `/opds/v1/authors/<pk>/books/` → entries **still** have `<link rel="http://opds-spec.org/acquisition">` (always rendered) |
| 17 | `test_author_books_acquisition_link_with_perm` | `user_with_perm` → entries have `<link rel="http://opds-spec.org/acquisition">` |

---

### `OPDSSeriesDetailTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`. Create `user_no_perm`, `user_with_perm`, and `subseries = BookSeries.objects.create(name='SubTest', parent=series_with_books)` inline (where `series_with_books` is any series from the dataset that has `BookSeriesLink` entries).

| # | Method | Assert |
|---|---|---|
| 1 | `test_series_detail_status_200` | GET `/opds/v1/series/<series_with_books.pk>/` → 200 |
| 2 | `test_series_detail_404` | GET `/opds/v1/series/99999/` → 404 |
| 3 | `test_series_detail_has_subseries` | Feed contains navigation entry for `subseries` |
| 4 | `test_series_detail_has_books` | Feed contains at least 1 book entry |
| 5 | `test_series_detail_books_sorted_by_sequence_number` | Book entries in ascending `sequence_number` order |
| 6 | `test_series_detail_book_title_prefixed_with_seq` | Each book entry `<title>` starts with `#<N> ·` |
| 7 | `test_series_detail_acquisition_link_always_rendered` | Anonymous → book entries **still** have the acquisition link (always rendered) |
| 8 | `test_series_detail_acquisition_with_perm` | `user_with_perm` → book entries have acquisition link |

---

### `OPDSBookDetailTest(BaseTestCase)`

**Fixture:** small detail fixture in `setUpTestData`. Uses `BaseTestCase` for real EPUB + cover. Setup:
- `lang_en`, `author_a` (Asimov, Isaac), `author_b` (Bradbury, Ray), `series_1` (Foundation), `genre_1` (Science Fiction)
- `book_1` (title=Foundation, lang_en, description=…, authors=[author_a], series_1 seq=1, genre_1, real EPUB file, real cover image)
- `book_2` (title=I, Robot, lang_en, authors=[author_a], series_1 seq=2 — no cover)
- `book_3` (title=Fahrenheit 451, lang_en, authors=[author_b] — no file, no cover)
- `user_no_perm`, `user_with_perm` (in `Book access` group)

| # | Method | Assert |
|---|---|---|
| 1 | `test_book_detail_status_200` | GET `/opds/v1/books/<book_1.pk>/` → 200 |
| 2 | `test_book_detail_404` | GET `/opds/v1/books/99999/` → 404 |
| 3 | `test_book_detail_has_title` | Entry `<title>` == `Foundation` |
| 4 | `test_book_detail_has_author_related_link` | `<link rel="related">` with `href` → `/opds/v1/authors/<author_a.pk>/`, `type` contains `kind=navigation`, `title` == author `full_name` |
| 4a | `test_book_detail_one_related_link_per_author` | Two-author book → exactly 2 author `rel="related"` links, one per `/opds/v1/authors/<pk>/` |
| 4b | `test_book_detail_author_related_link_mandatory` | Every complete entry has ≥ 1 author `rel="related"` link |
| 4c | `test_book_detail_has_no_atom_author_element` | Entry contains **no** `<author>` Atom element |
| 5 | `test_book_detail_content_is_xhtml_type` | Entry has `<content type="xhtml">` containing an XHTML `<div>`; **no** `<summary>` element |
| 5a | `test_book_detail_content_has_description` | The `<content>` `<div>` text contains `book_1.description` |
| 5b | `test_book_detail_content_has_no_series_text` | `<content>` has no series text (no `Foundation #1`, no `Belongs to series`) |
| 5c | `test_book_detail_content_sanitizes_disallowed_html` | Description with `<script>` → tag stripped; allowlisted `<p>`/`<strong>` survive |
| 5d | `test_book_detail_no_content_when_no_description` | Empty description → no `<content>` element |
| 5e | `test_book_detail_has_calibre_series` | `<calibre:series>` text == `Foundation`, `<calibre:series_index>` == `1` |
| 5f | `test_book_detail_calibre_series_name_stripped` | `<calibre:series>` text has no leading/trailing whitespace |
| 5g | `test_book_detail_one_calibre_series_pair_per_series` | Two-series book → exactly 2 `<calibre:series>` and 2 `<calibre:series_index>` |
| 5h | `test_book_detail_no_calibre_series_when_standalone` | book_3 (no series) → no `<calibre:series>` and no series `rel="related"` link |
| 6 | `test_book_detail_cover_link_is_absolute_url` | `<link rel="http://opds-spec.org/image" href="…">` starts with `http` |
| 7 | `test_book_detail_has_thumbnail_link` | `<link rel="http://opds-spec.org/image/thumbnail">` present |
| 8 | `test_book_detail_has_series_related_link` | `<link rel="related">` → `/opds/v1/series/<series_1.pk>/`, `title` == series **name only** (`Foundation`, no `#<seq>`) |
| 8a | `test_book_detail_author_and_series_related_links_distinguishable` | Author `rel="related"` → `/authors/<pk>/`; series → `/series/<pk>/` (distinguished by `href` prefix) |
| 9 | `test_book_detail_no_cover_uses_no_cover_fallback` | GET `book_2` (no cover) detail → `<link rel="http://opds-spec.org/image">` href ends in `/static/img/no_cover%20600x900.jpeg` and thumbnail href ends in `/static/img/no_cover%2040x60.jpeg` (image links always present; cover-less books fall back to placeholders) |
| 10 | `test_book_detail_acquisition_link_always_rendered_anon` | Anonymous → entry **still** has the acquisition link (always rendered) |
| 11 | `test_book_detail_acquisition_link_present_user_no_perm` | `user_no_perm` → acquisition link present (not gated) |
| 12 | `test_book_detail_has_acquisition_link_user_with_perm` | `user_with_perm` → acquisition link present with `href` ending in `/opds/v1/books/<book_1.pk>/download/` |

---

### `OPDSEntryImageTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`. Cross-cutting test of the §8 "logo for every non-book entry" rule. Logo lives at `/static/img/Logo 64x64x8.png`; assertions match the thumbnail link by `rel="http://opds-spec.org/image/thumbnail"` and an `href` ending in the URL-encoded logo path. Book (acquisition) entries are asserted **not** to carry the logo.

| # | Method | Assert |
|---|---|---|
| 1 | `test_root_feed_entries_have_logo_thumbnail` | Every `<entry>` in `/opds/v1/` has `<link rel="…/image/thumbnail" type="image/png">` whose `href` ends in `/static/img/Logo%2064x64x8.png` |
| 2 | `test_author_list_entries_have_logo_thumbnail` | Every entry in `/opds/v1/authors/` carries the logo thumbnail |
| 3 | `test_alphabet_tree_entries_have_logo_thumbnail` | Every entry in `/opds/v1/authors/tree/` carries the logo thumbnail |
| 4 | `test_genre_root_entries_have_logo_thumbnail` | Every entry in `/opds/v1/genres/` carries the logo thumbnail |
| 5 | `test_series_detail_subseries_entry_has_logo` | A subseries (nav) entry in `/opds/v1/series/<pk>/` carries the logo thumbnail |
| 6 | `test_logo_thumbnail_href_is_absolute_url` | The logo `href` is an absolute URL (starts with `http`) |
| 7 | `test_book_entries_do_not_use_logo` | Book (acquisition) entries in `/opds/v1/authors/<pk>/books/` do **not** carry a logo thumbnail |
| 8 | `test_search_section_entries_have_logo` | Section entries in `/opds/v1/search/?q=<term>` carry the logo thumbnail |

---

### `OPDSBookDownloadTest(BaseTestCase)`

**Fixture:** same small detail fixture (or separate `setUpTestData` if declared independently). Attach real EPUB bytes to `book_1` via `create_epub_one_author()`. **Auth phase (`BOOK-45 auth.md`):** the endpoint requires authentication (`IsAuthenticated` + `BasicAuthentication`); `user_with_perm` is in the `Book access` group; credentials are sent via HTTP Basic (`HTTP_AUTHORIZATION`).

| # | Method | Assert |
|---|---|---|
| 1 | `test_download_anon_returns_401` | Anonymous GET `/opds/v1/books/<book_1.pk>/download/` → 401; `WWW-Authenticate` header starts with `Basic` |
| 2 | `test_download_user_no_perm_returns_403` | `user_no_perm` (Basic) → 403 (via `can_view_book(user, book)`) |
| 3 | `test_download_user_with_perm_epub_returns_200` | `user_with_perm` (Basic), EPUB book → 200; `Content-Type` is `application/epub+zip` |
| 3b | `test_download_user_with_perm_fb2_zipped_returns_200` | `user_with_perm` (Basic), FB2-in-ZIP book → 200; decrypted/extracted content matches |
| 4 | `test_download_no_file_returns_404` | `user_with_perm`, `book_3` (no file) → 404 |
| 5 | `test_download_content_disposition_header` | `user_with_perm` response has `Content-Disposition: attachment; filename="…"` |
| 6 | `test_download_content_matches_extracted` | `user_with_perm`: `response.content == get_book_file_content(book_1)[1]` |

---

### `CanViewBookTest(TestCase)`

**Fixture:** a `book` and two users (one in the `Book access` group). Service-level test of `library.services.can_view_book(user, book)`; each call passes a `book` (currently ignored by the helper, kept for the public-domain follow-up).

| # | Method | Assert |
|---|---|---|
| 1 | `test_can_view_book_true_with_perm` | User in `Book access` (re-fetched to reset the perm cache) → `can_view_book(user, book)` is `True` |
| 2 | `test_can_view_book_false_without_perm` | Plain authenticated user → `can_view_book(user, book)` is `False` |
| 3 | `test_can_view_book_false_for_anonymous` | `can_view_book(AnonymousUser(), book)` → `False`, no exception |

---

### `OPDSLoginViewTest(TestCase)`

**Fixture:** one user with known credentials (for valid Basic auth). Auth phase — `OPDSLoginView` at `/opds/v1/login/`. Credentials sent via HTTP Basic (`HTTP_AUTHORIZATION`).

| # | Method | Assert |
|---|---|---|
| 1 | `test_login_anonymous_returns_401` | GET `/opds/v1/login/` no auth → 401 |
| 2 | `test_login_anonymous_sets_www_authenticate_basic` | The 401 response's `WWW-Authenticate` header starts with `Basic` |
| 3 | `test_login_authenticated_redirects_to_root` | GET with valid Basic creds (`follow=False`) → 302; `Location` ends in `/opds/v1/` |
| 4 | `test_login_invalid_credentials_returns_401` | GET with a wrong-password Basic header → 401 |

---

### `OPDSSearchTest(TestCase)`

**Fixture:** `create_test_dataset()` in `setUpTestData`. Create `user_no_perm` and `user_with_perm` in `setUpTestData`. Create 25 books with titles `Zap001`…`Zap025` in `setUp` (not `setUpTestData`) to ensure isolation.

| # | Method | Assert |
|---|---|---|
| 1 | `test_search_root_returns_200` | GET `/opds/v1/search/?q=Abak` → 200 |
| 2 | `test_search_root_has_books_section_entry` | `?q=Alid` → root has `Books (N found)` entry (N≥1) linking to `/opds/v1/search/books/?q=Alid` |
| 3 | `test_search_root_has_series_section_entry` | `?q=Ch` → root has `Series (N found)` entry linking to `/opds/v1/search/series/?q=Ch` |
| 4 | `test_search_root_has_authors_section_entry` | `?q=Abak` → root has `Authors (N found)` entry linking to `/opds/v1/search/authors/?q=Abak` |
| 5 | `test_search_root_section_omitted_when_empty` | `?q=Abak` → root has no `Books` and no `Series` section entry |
| 6 | `test_search_root_empty_query_returns_empty_feed` | GET `/opds/v1/search/` → 200, 0 entries |
| 7 | `test_search_root_no_results_returns_empty_feed` | GET `?q=xyzzyunmatchable` → 200, 0 entries |
| 8 | `test_search_authors_subfeed_entries_link_to_author` | GET `/opds/v1/search/authors/?q=Abak` → entries link to `/opds/v1/authors/<pk>/` |
| 9 | `test_search_series_subfeed_entries_link_to_series` | GET `/opds/v1/search/series/?q=Ch` → entries link to `/opds/v1/series/<pk>/` |
| 10 | `test_search_books_subfeed_acquisition_link_with_perm` | `user_with_perm`, GET `/opds/v1/search/books/?q=Alid1` → book entries have acquisition link |
| 11 | `test_search_books_subfeed_acquisition_link_always_rendered` | Anonymous, GET `/opds/v1/search/books/?q=Alid1` → book entries **still** have the acquisition link (always rendered) |
| 12 | `test_search_books_subfeed_pagination` | 25 `Zap*` books; GET `/opds/v1/search/books/?q=Zap` page 1 → exactly 20 entries; `<link rel="next">` present |
| 13 | `test_search_books_subfeed_pagination_preserves_q` | `/opds/v1/search/books/?q=Zap` `<link rel="next">` URL contains both `q=Zap` and `page=2` |
| 14 | `test_search_subfeed_empty_query_returns_empty_feed` | GET `/opds/v1/search/books/` (no `q`) → 200, 0 entries |

---

### `OPDSOpenSearchDescriptionTest(TestCase)`

| # | Method | Assert |
|---|---|---|
| 1 | `test_opensearch_description_status_200` | GET `/opds/v1/search/description.xml` → 200 |
| 2 | `test_opensearch_description_content_type` | `Content-Type` starts with `application/opensearchdescription+xml` |
| 3 | `test_opensearch_description_has_shortname` | XML contains `<ShortName>Bookshelf</ShortName>` |
| 4 | `test_opensearch_description_has_url_template` | XML has `<Url>` element with `template` attribute containing `/opds/v1/search/?q={searchTerms}` |
| 5 | `test_opensearch_description_template_is_absolute_url` | `template` value starts with `http` |

---

### `OPDSThrottlingTest(TestCase)`

No fixture. Override both `CACHES` (to `LocMemCache`) and `REST_FRAMEWORK` (reducing rate limits) via `@override_settings`. The override must **merge** with the existing `REST_FRAMEWORK` dict rather than replacing it entirely, to preserve `DEFAULT_RENDERER_CLASSES` and other keys.

Call `api_settings.reload()` in both `setUp` and `tearDown` to prevent class-level DRF settings mutation from leaking into other tests.

```python
@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    REST_FRAMEWORK={
        **settings.REST_FRAMEWORK,
        'DEFAULT_THROTTLE_RATES': {
            'opds_anon': '3/min',
            'opds_anon_daily': '1000/day',
        },
    }
)
class OPDSThrottlingTest(TestCase):
    def setUp(self):
        super().setUp()
        api_settings.reload()

    def tearDown(self):
        super().tearDown()
        api_settings.reload()
```

| # | Method | Assert |
|---|---|---|
| 1 | `test_within_limit_returns_200` | 3 consecutive GET `/opds/v1/` → all 200 |
| 2 | `test_exceeds_per_minute_limit_returns_429` | 4th consecutive GET `/opds/v1/` → 429 |
| 3 | `test_throttle_header_present` | 429 response has `Retry-After` header |
| 4 | `test_throttle_applies_to_all_opds_endpoints` | Parameterized over `['/opds/v1/', '/opds/v1/books/']`: hit limit (3 requests) on endpoint 1 → next request to endpoint 2 is 429 (shared cache key scope) |

---

## Explicit Assumptions

1. `get_alphabet_tree` is called on the full queryset on every request — no caching. This matches existing web view behavior. Caching the tree is a future optimization, not part of Phase 1.

2. For `AuthorTreeFeedView` (and equivalents), the full alphabet tree is built from `Author.objects.all()` so `find_alphabet_node_by_name` can locate any node by name. The filtered queryset (`last_name__istartswith=…` / `__iregex=…`) is used only by the flat results view (`AuthorListFeedView`), which does not need the tree at all.

3. The `<int:pk>` URL converter does not match the literal `tree`, so the `…/tree/` and `…/tree/<str:name>/` routes never collide with `…/<int:pk>/`. Within the genre group, `…/books/tree/…` patterns are declared before `…/books/` so a `…/books/tree/` request is not shadowed.

4. `get_descendants([genre_pk])` returns leaf-only descendants. Books tagged directly to intermediate genre nodes are excluded from genre book counts/lists. This is consistent with existing `BookListView` behavior and the canonical dataset structure.

5. `Book.cover_preview` (`ImageSpecField`) generates the 100×150 JPEG on first access. Tests using `BaseTestCase` attach a real cover image; tests using plain `TestCase` have `book.cover = None`, so serializers must branch on `if book.cover:` — using `.cover.url` / `.cover_preview.url` when present, else the static `no_cover` placeholders — rather than omitting the image link.

6. `Author.full_name` (i.e., `"Last, First Middle"`) is used as the `title` of each author `rel="related"` link on a complete book entry (book entries emit **no** `<author>` Atom element, per §6.5), consistent with how the web app renders author names.

7. The `app_name` in the include tuple for OPDS URLs is `'library'` (matching the library app's Django namespace requirement). The instance namespace `'opds'` is what all `reverse('opds:…')` calls use.

---

## Resolved Decisions

1. **Author Detail sub-feed count → 3 (no dedicated no-series endpoint).** Author Detail exposes Books by Title, New Arrivals, and Books by Series. Books not in any series are surfaced via a **"Standalone Books" category prepended at the top** of the Books-by-Series sub-feed, linking to `authors/<pk>/books/?series=none` (an optional filter on the existing `AuthorBooksFeedView`). TDD section 6.3 and `test_author_detail_has_three_sub_feeds` reflect this.

2. **Search sections are never flattened; each section is its own paginator.** `search/` is an unpaginated navigation feed of ≤ 3 section entries, each linking to an independently paginated sub-feed: `search/authors/`, `search/series/`, `search/books/` (each `OPDSPageNumberPagination`, page_size 20, `q` preserved across pages). TDD section 6.7 and the search tests reflect this.

3. **Genre intermediate-node book tagging → accepted as-is for this task.** `get_descendants` returns leaf descendants only; books tagged directly to parent genres are excluded from genre feeds, consistent with existing `BookListView` behavior. Broadening `get_descendants` to return all descendants is deferred to a separate task.

4. **Navigation/results separation (tree vs list).** Authors, Series, Books, and per-genre Books each expose `…/tree/` + `…/tree/<name>/` navigation feeds (never paginated) and a flat, paginated `…/` results endpoint (`?regex=` → `iregex`, elif `?filter=` → `istartswith`, else full set). Tree leaves and "all" entries link to the results endpoint; the bare results endpoint (no params) is the full set and is **not advertised**. New `find_alphabet_node_by_name` resolves tree path segments by node name. This removes the old single-URL ambiguity (a node URL serving both a sub-tree and a flat list) and the genre regex-addressing special case. TDD §4, §6.2, §6.2a and the alphabet/genre tests reflect this.

5. **Genre detail = subgenres only, with leaf-genre 302 redirect.** `/genres/<pk>/` lists direct subgenres; a genre with no subgenres 302-redirects to `/genres/<pk>/books/tree/`. A non-leaf genre's aggregate book tree is reachable only by direct URL (not advertised); since directly-tagged books live only on leaf genres, no books are hidden. TDD §6.2a reflects this.

6. **Book listing entries are thin (partial) by default; `?detail=thick` opts into complete inline entries — both in scope for BOOK-45.** All book-listing acquisition feeds (`/books/`, `/authors/<pk>/books/`, `…/books/recent/`, `/genres/<pk>/books/`, `/series/<pk>/`, `/search/books/`) emit *partial* catalog entries by default: `<title>` + `<id>` + permission-gated acquisition link + a **mandatory** `rel="alternate"` link to the complete entry at `/opds/v1/books/<pk>/` + the cover thumbnail. The default list payload is kept minimal (no `<content>`, no full-size cover, no `<calibre:*>`, no `rel="related"`). `?detail=thick` switches the same endpoints to inline *complete* entries (identical to the §6.5 / "Book detail entry" shape) for non-`alternate`-following readers, with `detail=thick` propagated across all pagination links. BOOK-45 implements **both** the thin default and the `?detail=thick` branch, covered by `OPDSBookVerbosityTest`. **Deferred (separate follow-up task):** only a **dedicated precomputed `Book` thumbnail field** (to avoid per-row lazy `cover_preview` generation on large lists) — a pure performance optimization, not a behavior change. TDD §6.5a and §12.5 reflect this.

7. **Search discovery is OpenSearch-driven and feed-level** The root feed advertises search through two **feed-level** `<link rel="search">` elements (direct children of `<feed>`, carried by the feed dict's `feed_links`), **not** a navigation `<entry>`: the `application/opensearchdescription+xml` descriptor link plus a templated `application/atom+xml` `…/search/?q={searchTerms}` link. The OpenSearch document (`/opds/v1/search/description.xml`) is the mechanism real readers actually use, and it must: be serialized in the **default** OpenSearch namespace (unprefixed `<OpenSearchDescription>`/`<Url>`, via a literal `xmlns` on the root — `ElementTree`'s `default_namespace=` is unusable because `<Url>` has unqualified attributes); set `<Url type>` to the **OPDS Catalog** media type `application/atom+xml;profile=opds-catalog;kind=navigation` (plain `application/atom+xml` is rejected); and point `<Url template>` at the **search root** `…/search/?q={searchTerms}` so search lands on the Authors/Series/Books chooser. Each requirement is a MUST — violating any one makes search silently vanish in strict readers. TDD §6.7 and the "OPDS reader compatibility (search)" callout in TDD §6 reflect this; covered by the `OPDSOpenSearchDescriptionTest` and root-feed search-link tests.

---

**Relevant source files read during planning:**
- `/home/leech/Projects/Bookshelf/docs/TDD_OPDS.md` — primary spec (884 lines)
- `/home/leech/Projects/Bookshelf/bookshelf/library/services.py` — `get_alphabet_tree`, `find_alphabet_node`, `get_book_file_content`, `search_entities`, `get_descendants`
- `/home/leech/Projects/Bookshelf/bookshelf/library/models.py` — `Author`, `Book`, `BookSeries`, `BookSeriesLink`, `Genre`
- `/home/leech/Projects/Bookshelf/bookshelf/library/views.py` — `BookDownloadView`, `BookListView` genre filter pattern
- `/home/leech/Projects/Bookshelf/bookshelf/library/urls.py` — existing URL patterns
- `/home/leech/Projects/Bookshelf/bookshelf/bookshelf/urls.py` — root URL config
- `/home/leech/Projects/Bookshelf/bookshelf/bookshelf/settings.py` — `INSTALLED_APPS`, `CACHES`, `PAGINATE_BY`
- `/home/leech/Projects/Bookshelf/pyproject.toml` — confirmed `djangorestframework>=3.16.1` already declared
- `/home/leech/Projects/Bookshelf/bookshelf/bookshelf/tests/base_test.py` — `BaseTestCase` (DummyCache, temp media root)
- `/home/leech/Projects/Bookshelf/bookshelf/library/tests/test_data_factory.py` — `create_test_dataset()` structure

CLAUDE_CODE_DISABLE_MOUSE=1 claude --resume c8e6bbbc-059e-452d-8160-ced8b5388cac