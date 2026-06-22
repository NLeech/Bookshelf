# Technical Design Document: OPDS v1.2 Catalog

## 1. Overview

This document describes the design of the OPDS v1.2 catalog interface for the Bookshelf project.

**Scope:** Initial implementation (Phase 1). No authentication on feed views — the catalog is fully public (`AllowAny`) and acquisition links are always rendered, so every feed is browsable by anyone. Authorization is enforced solely at the download endpoint (`/opds/v1/books/<pk>/download/`), which returns `HTTP 403` without the `library.view_book` permission. Authentication (Basic Auth at the download endpoint) will be added as a separate task.

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
- Custom renderers producing Atom/OPDS XML.
- Throttling via DRF's `AnonRateThrottle` base.

Views are **DRF APIView subclasses** (not ViewSets), because OPDS feeds don't map cleanly to CRUD semantics.

### 2.3 Data flow

```
View  →  Serializer  →  dict  →  OPDSRenderer  →  ET.Element  →  XML bytes
```

- **Serializers** (`serializers.py`) — convert model objects into neutral Python dicts. No XML or Atom knowledge.
- **Renderer** (`renderers.py`) — receives the dict from `Response(data)` and builds the full `ET.Element` tree, applying all Atom/OPDS XML conventions. All namespace logic lives here.
- This separation means a future renderer (e.g. for OPDS v2.0 JSON format) only needs to implement `render(data, ...)` against the same dict contract — no changes to views or serializers.

### 2.4 Response format

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
| `/opds/v1/authors/` | `AuthorListFeedView` | Navigation (flat author list — full set or `?filter=`/`?regex=` results) |
| `/opds/v1/authors/tree/` | `AuthorTreeFeedView` | Navigation (alphabet tree root) |
| `/opds/v1/authors/tree/<name>/` | `AuthorTreeFeedView` | Navigation (alphabet sub-tree) |
| `/opds/v1/authors/<int:pk>/` | `AuthorDetailFeedView` | Navigation |
| `/opds/v1/authors/<int:pk>/series/` | `AuthorSeriesFeedView` | Navigation |
| `/opds/v1/authors/<int:pk>/books/` | `AuthorBooksFeedView` | Acquisition |
| `/opds/v1/authors/<int:pk>/books/recent/` | `AuthorRecentBooksFeedView` | Acquisition |
| `/opds/v1/genres/` | `GenreRootFeedView` | Navigation (top-level genres) |
| `/opds/v1/genres/<int:pk>/` | `GenreDetailFeedView` | Navigation (subgenres only; empty → 302) |
| `/opds/v1/genres/<int:pk>/books/` | `GenreBookListFeedView` | Acquisition (flat — full set or `?filter=`/`?regex=` results) |
| `/opds/v1/genres/<int:pk>/books/tree/` | `GenreBookTreeFeedView` | Navigation (genre book tree root) |
| `/opds/v1/genres/<int:pk>/books/tree/<name>/` | `GenreBookTreeFeedView` | Navigation (genre book sub-tree) |
| `/opds/v1/series/` | `SeriesListFeedView` | Navigation (flat series list — full set or results) |
| `/opds/v1/series/tree/` | `SeriesTreeFeedView` | Navigation (alphabet tree root) |
| `/opds/v1/series/tree/<name>/` | `SeriesTreeFeedView` | Navigation (alphabet sub-tree) |
| `/opds/v1/series/<int:pk>/` | `SeriesDetailFeedView` | Navigation/Acquisition |
| `/opds/v1/books/` | `BookListFeedView` | Acquisition (flat book list — full set or results) |
| `/opds/v1/books/tree/` | `BookTreeFeedView` | Navigation (alphabet tree root) |
| `/opds/v1/books/tree/<name>/` | `BookTreeFeedView` | Navigation (alphabet sub-tree) |
| `/opds/v1/books/<int:pk>/` | `BookDetailFeedView` | Acquisition |
| `/opds/v1/books/<int:pk>/download/` | `BookDownloadView` | Binary (file delivery) |
| `/opds/v1/search/` | `SearchRootFeedView` | Navigation (≤ 3 section entries, unpaginated) |
| `/opds/v1/search/authors/` | `SearchAuthorsFeedView` | Navigation (paginated) |
| `/opds/v1/search/series/` | `SearchSeriesFeedView` | Navigation (paginated) |
| `/opds/v1/search/books/` | `SearchBooksFeedView` | Acquisition (paginated) |
| `/opds/v1/search/description.xml` | `OpenSearchDescriptionView` | OpenSearch XML |

**Navigation / results separation (Authors, Series, Books, per-genre Books):**

Each browsable entity exposes two distinct kinds of endpoint — navigation **trees** and flat **results** — so that one URL always has one responsibility:

- **Tree endpoints** (`…/tree/`, `…/tree/<name>/`) render the alphabet tree built by `get_alphabet_tree`. They are **always navigation** feeds and are **never paginated**.
- **Results endpoint** (`…/` with optional `?filter=` / `?regex=`) is a **flat, paginated** list of items:
  - no query params → the **full** set (a valid endpoint, but **not advertised** in any feed — kept for completeness/compatibility);
  - `?filter=<prefix>` → `field__istartswith=<prefix>`;
  - `?regex=<url-encoded regex>` → `field__iregex=<regex>` (**regex wins** if both are present).

  This mirrors the canonical `BookListView.get_queryset` precedence exactly.

- `<name>` is the tree node's `name` (URL-safe: `a`, `ab`, `aba`, `other`), resolved by the new **`find_alphabet_node_by_name(tree, name)`** service. Only **expandable** (non-leaf) nodes are reachable by name; leaf nodes are never addressed by a path segment.
- **Tree leaf → results.** A leaf node entry links to the results endpoint carrying that node's selector: a prefix leaf → `…/?filter=<filter>`; a regex leaf (`0-9`, `* (all non-alpha)`, low-count `prefix*`) → `…/?regex=<url-encoded regex>`.
- **Tree non-leaf → sub-tree.** An expandable node entry links to `…/tree/<name>/`.
- The **root catalog** and every "browse" link point at the `…/tree/` roots, never at the bare results endpoint.

**"all `<prefix>`" node rule:**
When a tree node is expanded, a synthetic **"all `<prefix>`"** entry is prepended as its first child, linking to the **results endpoint** for that node's own selector — `…/?filter=<prefix>` (or `…/?regex=<regex>` for the `other` node) — i.e. the full unfiltered set at that prefix level. Leaf nodes (not expanded) get no "all" entry. This removes the old ambiguity where an "all" link and a sub-tree link could resolve to the same URL.

Example for Authors (`a` and `other` expandable, the rest leaves):
```
/opds/v1/authors/tree/                       (root)
  ├── A (137)    → /opds/v1/authors/tree/a/
  ├── B (58)     → /opds/v1/authors/?filter=b          ← leaf
  ├── …
  ├── 0-9 (12)   → /opds/v1/authors/?regex=^[0-9]      ← regex leaf
  └── Other (14) → /opds/v1/authors/tree/other/        ← expandable

/opds/v1/authors/tree/a/                     (A expanded)
  ├── all a (137) → /opds/v1/authors/?filter=a         ← synthetic, first child
  ├── Ab (110)    → /opds/v1/authors/tree/ab/
  ├── Ac (11)     → /opds/v1/authors/?filter=ac        ← leaf, no "all ac"
  └── Ad (16)     → /opds/v1/authors/?filter=ad        ← leaf, no "all ad"
```

---

## 5. Pagination

DRF `PageNumberPagination` with `page_size = 20` (configurable via `settings.OPDS_PAGE_SIZE`, default 20).

Pagination links are rendered as Atom `<link rel="next">`, `<link rel="previous">`, and `<link rel="first">` inside each feed.

Pagination applies to the flat **results** endpoints and detail lists: Author results (`/authors/`), Book results (`/books/`), per-genre Book results (`/genres/<pk>/books/`), Series results (`/series/`), each search section sub-feed (authors/series/books — paginated independently, see 6.7), Author detail sub-feeds (books, books/recent), Series detail book list.

Pagination does **not** apply to navigation **tree** feeds (`…/tree/`, `…/tree/<name>/`) — a tree level has a small, bounded set of nodes — nor to the search **root** feed (section index).

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
  <link rel="search" type="application/opensearchdescription+xml" href="/opds/v1/search/description.xml"/>
  <link rel="search" type="application/atom+xml" href="/opds/v1/search/?q={searchTerms}"/>

  <entry>
    <title>Authors</title>
    <id>tag:bookshelf:authors</id>
    <link rel="subsection" href="/opds/v1/authors/tree/"
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
</feed>
```

> Search is **not** a navigation entry: it is advertised by two feed-level `<link rel="search">` elements (direct children of `<feed>`, mirroring Flibusta), because OPDS readers discover search by scanning feed-level links, not entry links. The `application/opensearchdescription+xml` link points at the OpenSearch descriptor (used by Calibre/KOReader auto-discovery and the reader's search box); the templated `application/atom+xml` `…/search/?q={searchTerms}` link is what readers turn into an inline "Search" catalog row. At feed level with `rel="search"` the literal `{searchTerms}` braces are treated as a template, not a URL to resolve, so strict `java.net.URI`-based readers do not choke on them. The `Series`, `Books`, and `Genres` entries follow the same shape as `Authors`: `Series` → `/opds/v1/series/tree/`, `Books` → `/opds/v1/books/tree/`, `Genres` → `/opds/v1/genres/`. All four "browse" entries point at navigation roots, never at the flat results endpoints.

### 6.2 Alphabet Tree Feeds (Authors, Books, Series)

Uses the existing `get_alphabet_tree` service from `library.services`. The tree is rendered by the **tree** endpoints (`…/tree/`, `…/tree/<name>/`) — navigation feeds, never paginated. Each tree node becomes a navigation `<entry>`:

- **Leaf node** → links to the flat **results** endpoint carrying the node's selector: a prefix leaf → `…/?filter=<filter>`; a regex leaf (`0-9`, `* (all non-alpha)`, low-count `prefix*`) → `…/?regex=<url-encoded regex>`.
- **Non-leaf (expandable) node** → links to the sub-tree URL `…/tree/<name>/`, resolved server-side by `find_alphabet_node_by_name(tree, name)`. A synthetic **"all `<prefix>`"** child entry is prepended before the sub-nodes, linking to the **results** endpoint for the parent node's own selector (`…/?filter=<prefix>`, or `…/?regex=<regex>` for `other`) — the full set at that prefix.

The flat **results** endpoint (`…/`) is shared by every leaf and "all" link. It applies `field__iregex` when `?regex=` is present, else `field__istartswith` when `?filter=` is present, else returns the full set; results are always paginated. The tree is rebuilt per request from the (entity-wide) queryset so `find_alphabet_node_by_name` can resolve any node.

The `<content>` of each tree entry includes the item count. The "all `<prefix>`" entry carries the same count as its parent node (since it represents the full set).

### 6.2a Genre Hierarchy Feeds

Genres separate **subgenre navigation** from **book browsing**. A genre detail is a pure subgenre browser; books for a genre are reached through that genre's own tree/results endpoints, which are an exact instance of the standard navigation/results shape (§6.2) with a genre-scoped base queryset.

**`/opds/v1/genres/` — `GenreRootFeedView` (Navigation)**

Lists all top-level genres (those with `parent=None`). Each entry links to `/opds/v1/genres/<pk>/`. The entry `<content>` includes the total book count for the genre (including all descendants), using `get_descendants` from `library.services`.

**`/opds/v1/genres/<pk>/` — `GenreDetailFeedView` (Navigation)**

Renders **subgenres only** — one navigation entry per direct subgenre (`genre.subgenres.all()`), each linking to `/opds/v1/genres/<subpk>/`. It contains **no** book or alphabet-tree entries.

- If the genre **has** subgenres → return the subgenre navigation feed.
- If the genre has **no** subgenres (a leaf genre) → **HTTP 302 redirect** to `/opds/v1/genres/<pk>/books/tree/`. 302 (temporary) is used, not 301, because leaf-ness is data-dependent (subgenres may be added later). OPDS clients follow standard HTTP redirects.
- Returns `HTTP 404` if the genre does not exist.

> **Consequence (intended):** a *non-leaf* genre's own aggregate book tree (`/opds/v1/genres/<pk>/books/tree/`) is not linked from any feed — you reach books by drilling down to a leaf subgenre, which redirects into its book tree. The aggregate endpoint still exists and is reachable by direct URL (consistent with the "define-but-don't-advertise" rule for bare results endpoints). Because directly-tagged books only live on leaf genres in this dataset, no books are hidden — only the *aggregate* parent-genre browse is unadvertised. The genre root feed still shows the aggregate descendant **count** per top-level genre.

**`/opds/v1/genres/<pk>/books/tree/` and `/opds/v1/genres/<pk>/books/tree/<name>/` — `GenreBookTreeFeedView` (Navigation)**

The standard alphabet-tree feeds (§6.2), built with `get_alphabet_tree` on the genre-filtered `Book` queryset (genre **+ descendants**, via `get_descendants`). The tree contains *only* the letters this genre actually has — if no books in this genre start with "A", there is no "A" node. Node links follow the standard rule:

- expandable node → `/opds/v1/genres/<pk>/books/tree/<name>/` (resolved by `find_alphabet_node_by_name`);
- leaf node → `/opds/v1/genres/<pk>/books/?filter=<filter>` or `…/books/?regex=<encoded>`;
- synthetic "all `<prefix>`" first child → `/opds/v1/genres/<pk>/books/?filter=<prefix>` (or `?regex=` for `other`).

**`/opds/v1/genres/<pk>/books/` — `GenreBookListFeedView` (Acquisition)**

The flat **results** endpoint for the genre. Base queryset is the genre (+descendants) book set; it then applies `title__iregex=<regex>` when `?regex=` is present, else `title__istartswith=<filter>` when `?filter=` is present, else returns the full genre set. Always paginated, sorted by title. This matches the canonical `BookListView.get_queryset` precedence (`regex → title__iregex`, else `filter → title__istartswith`), so digit- and symbol-titled books are reachable within a genre. With no query params it is the genre's full book list — valid but not advertised (reached only via the tree's leaf/"all" links).

### 6.3 Author Detail Feed (`/opds/v1/authors/<pk>/`)

Navigation feed with sub-feeds mirroring the author detail page tabs:

| Entry | Link href | Type |
|-------|-----------|------|
| Books by Title | `/opds/v1/authors/<pk>/books/` | acquisition |
| New Arrivals | `/opds/v1/authors/<pk>/books/recent/` | acquisition |
| Books by Series | `/opds/v1/authors/<pk>/series/` | navigation |

**`/opds/v1/authors/<pk>/series/` — `AuthorSeriesFeedView` (Navigation)**

Lists each series the author has books in, linking to `/opds/v1/series/<pk>/`. The entry `<content>` includes the book count for that author in that series.

If the author has books not linked to any series, **prepends a first entry** (at the top of the list, above all series) titled **"Standalone Books"** linking to `/opds/v1/authors/<pk>/books/?series=none`. This entry is only rendered when standalone books exist.

`AuthorBooksFeedView` honours an optional `?series=none` query param: when present it filters the author's books to those with no series link (`bookserieslink__isnull=True`), reusing the same paginated acquisition feed. No separate sub-feed endpoint is added — Author Detail still exposes exactly **3** sub-feeds.

### 6.4 Series Detail Feed (`/opds/v1/series/<pk>/`)

Acquisition feed containing:
1. Subseries entries (navigation links) — if any.
2. Book entries sorted by `sequence_number`, with the sequence number prefixed in the `<title>`: `"#3 · The Return of the King"`.

### 6.5 Book Detail Feed (`/opds/v1/books/<pk>/`)

Acquisition feed entry containing, **in this document order**:
- `<title>` — book title.
- `<content type="xhtml">` — the **book description only**, as **sanitized XHTML**. The description is run through an allowlist sanitizer (`_sanitize_html`): only `p, br, strong, b, em, i, u, ul, ol, li` tags survive, all attributes are stripped. The renderer emits `type="xhtml"` as a real (un-escaped) XHTML `<div>` whose children are live XML nodes (not an escaped string), so spec-compliant readers render the markup. Omitted when the book has no description.
- `<calibre:series>` / `<calibre:series_index>` — **one pair per series** the book belongs to, in the Calibre metadata namespace (`http://calibre.kovidgoyal.net/2009/metadata`). `<calibre:series>` carries the (whitespace-stripped) series name; `<calibre:series_index>` carries the sequence number. This is the **structured** representation of series; readers that understand the extension display it as a dedicated series field. Omitted when the book is in no series.
- `<link rel="http://opds-spec.org/image">` — cover image URL (Use `no_cover 600x900.jpeg` for books without a cover.).
- `<link rel="http://opds-spec.org/image/thumbnail">` — cover_opds_thumbnail URL (Use no_cover 40x60.jpeg for books without a cover.).
- `<link rel="related">` **(authors)** — **mandatory: exactly one `rel="related"` link per author of the book** (a book with three authors renders three author related-links), each `href` pointing to the author's feed at `/opds/v1/authors/<pk>/` with `type="application/atom+xml;profile=opds-catalog;kind=navigation"` and `title="<author full_name>"`. This is the **only** representation of authors on a book entry — **no `<author>` element is emitted.** Validated by probe: FBReader renders these as tappable jump-to-author links. Applies to every complete book entry — the standalone detail feed and the inline thick (`?detail=thick`) listing entries (§6.5a). Author links are **omitted from thin listing entries** to keep lists lightweight.
- `<link rel="related">` **(series)** — one per series, `href` pointing to `/opds/v1/series/<pk>/`, with `title="<series name>"` (series name only — no `#<sequence_number>`; the sequence number lives in `<calibre:series_index>`). Rendered alongside the author related-links. Series therefore appear **twice and intentionally**: once as the structured `<calibre:series>`/`<calibre:series_index>` pair (a dedicated series field), and once as a tappable `rel="related"` navigation link here. The `href` prefix (`/authors/` vs. `/series/`) distinguishes author related-links from series related-links.
- `<link rel="http://opds-spec.org/acquisition">` — **only rendered if the request user has `library.view_book` permission.** Points to `/opds/v1/books/<pk>/download/`.

### 6.5a Book Listing Entry Verbosity (thin default / `?detail=thick`)

**Acquisition feeds** that list books — Books (`/books/`), Author Books (`/authors/<pk>/books/`), Recently Added (`/authors/<pk>/books/recent/`), per-genre Books (`/genres/<pk>/books/`), Series Detail (`/series/<pk>/`), and Search Books (`/search/books/`) — emit **partial (thin) catalog entries by default**. A `?detail=thick` query param opts the same endpoints into **complete (thick) entries** inline.

**Thin entry (default).** Each book entry contains only:
- `<title>` — book title.
- `<id>` — `tag:bookshelf:book:<pk>`.
- `<link rel="http://opds-spec.org/acquisition">` — download link (subject to the §9 permission rule).
- `<link rel="alternate" type="application/atom+xml;type=entry;profile=opds-catalog">` — points to the complete entry at `/opds/v1/books/<pk>/`. **Mandatory** on every partial entry.
- `<link rel="http://opds-spec.org/image/thumbnail">` — cover_opds_thumbnail (Use no_cover 40x60.jpeg for books without a cover.). **No** full-size `http://opds-spec.org/image` link, **no** `<content>` description, **no** `<calibre:*>` series elements, and **no** author/series `rel="related"` links in thin entries (those appear only in the complete/thick entry per §6.5).


**Thick entry (`?detail=thick`).** Identical to the §6.5 complete Book Detail entry (`<content type="xhtml">` with the sanitized description, `<calibre:series>`/`<calibre:series_index>` per series, `<category>` per genre, full-size cover `http://opds-spec.org/image` + thumbnail, author `rel="related"` links, series `rel="related"` links). Intended for desktop / other readers that do **not** follow the `alternate` link.

**Propagation.** `?detail=thick` is a **sticky, catalog-wide preference**, not a per-feed flag. OPDS clients reach an acquisition feed only by *following links* from navigation feeds — they never synthesise URLs — so the param is useless unless it is threaded through the whole browse path. Therefore, when `?detail=thick` is present on a request it MUST be re-appended to **every link whose target is another browsable catalog feed**, so the preference survives navigation, search, and drill-down until the client reaches (and pages through) a book-listing acquisition feed. It is preserved on:

- every **`subsection`** navigation link in every navigation feed (Root, Alphabet Tree — including the synthetic "all …" entry, Author/Genre/Series results & detail, Author Series);
- both **feed-level `rel="search"` links**: `detail=thick` rides on the `application/opensearchdescription+xml` descriptor link (and is baked into the description document's `<Url template>`, becoming `…/search/?q={searchTerms}&detail=thick`) **and** is appended to the templated `application/atom+xml` `…/search/?q={searchTerms}` link (becoming `…/search/?q={searchTerms}&detail=thick`), so search results stay in thick mode whichever link the reader follows. The templated `{searchTerms}` placeholder is preserved verbatim;
- **author/series `rel="related"`** links on thick book entries (they target the author/series navigation feeds);
- the feed's own **`self`** and **`start`** links and its **pagination** links (`first`/`next`/`previous`).

It is **omitted** from links that are not browsable catalog feeds or are always complete:

- the **`rel="alternate"`** link — its target `/opds/v1/books/<pk>/` (§6.5) is the single complete entry, already thick by definition, and is unaffected by the param;
- the **acquisition / download** link, the cover **`image`** and **`thumbnail`** links, and the non-book **logo thumbnail** link (not feeds).

The param changes **only** the verbosity of book entries in book-listing acquisition feeds; it has **no effect on the body** of a navigation feed — it only alters the links that feed emits. Implementation separates the two concerns:

- **Link propagation is param-agnostic.** A single `_with_sticky_params(href, request)` helper re-appends every catalog-wide "sticky" preference — enumerated once in a `STICKY_QUERY_PARAMS` tuple (currently just `('detail',)`) — that is present on the request, respecting any existing query string (so template links like `…/search/?q={searchTerms}` keep their placeholder) and skipping params already on the href (so `self` links built from `request.build_absolute_uri()` are not duplicated). Navigation builders take no per-feature flag; adding a future sticky preference is one tuple entry, with **no serializer signature changes**.
- **Entry verbosity is the one place that interprets the value.** A single `wants_thick_entries(request)` predicate (the sole reading of `detail == 'thick'`) is called only by the two book acquisition views and passed as the `thick` argument to `build_author_books_feed`, which branches on it to render thin vs complete entries.

DRF's paginator already preserves the query string on `self`/pagination links.

### 6.6 Book Download (`/opds/v1/books/<pk>/download/`)

Not an Atom feed — streams the raw file content.

- Delegates to `library.services.get_book_file_content` for ZIP extraction and decryption.
- Returns `HTTP 403` if the request user lacks `library.view_book`.
- Returns `HTTP 404` if the book has no file.
- Sets `Content-Disposition: attachment; filename="..."` using the sanitized filename from `get_book_file_content`.

### 6.7 Search Feed (`/opds/v1/search/?q=<query>`)

Searches Authors, Books, and Series using `library.services.search_entities`. The search root is a **navigation feed** containing up to three section entries — one per non-empty result set — each linking to its **own independently paginated sub-feed**. The three sections are **never** combined into a single flattened feed.

| Section entry | Link href | Sub-feed view |
|---|---|---|
| `Authors (N found)` | `/opds/v1/search/authors/?q=<query>` | `SearchAuthorsFeedView` (navigation) |
| `Series (N found)` | `/opds/v1/search/series/?q=<query>` | `SearchSeriesFeedView` (navigation) |
| `Books (N found)` | `/opds/v1/search/books/?q=<query>` | `SearchBooksFeedView` (acquisition) |

`N` is the total match count for that section. A section entry is omitted entirely when its result set is empty. The search root feed itself is **not** paginated (at most three entries). Returns an empty feed (not an error) for no results or missing `q`.

Each section sub-feed is paginated **independently** with `OPDSPageNumberPagination` (`page_size = 20`); its `next` / `previous` / `first` links preserve the `q` query param:

- **`/opds/v1/search/authors/` — `SearchAuthorsFeedView` (Navigation):** one entry per matching author, linking to `/opds/v1/authors/<pk>/`.
- **`/opds/v1/search/series/` — `SearchSeriesFeedView` (Navigation):** one entry per matching series, linking to `/opds/v1/series/<pk>/`.
- **`/opds/v1/search/books/` — `SearchBooksFeedView` (Acquisition):** one entry per matching book; each entry includes the acquisition link only if the request user has `library.view_book`.

**`/opds/v1/search/description.xml` — `OpenSearchDescriptionView`**

Returns the OpenSearch Description Document as `application/opensearchdescription+xml`, serialized with the **default** OpenSearch namespace and unprefixed tags (`<OpenSearchDescription xmlns="…">`, `<Url>`) — some readers string-match for a bare `<Url>` and ignore prefixed elements. This is the endpoint referenced by the sticky `<link rel="search" type="application/opensearchdescription+xml">` in the root feed, and is the spec-mandated search mechanism (OPDS 1.2 places the `{searchTerms}` template **only** here, not in the feed). Required for Calibre and KOreader auto-discovery. Per OPDS 1.2 the `<Url type>` **must** be the OPDS Catalog media type — plain `application/atom+xml` is rejected by spec-compliant readers. The template resolves to the search **root** (a navigation feed), so a reader's search lands on the Authors/Series/Books chooser and the user drills into a category; the type is therefore `application/atom+xml;profile=opds-catalog;kind=navigation`. When the request carries `?detail=thick`, the preference is baked into the `<Url template>` (which becomes `…/search/?q={searchTerms}&detail=thick`) so the client's substituted search URL inherits thick mode; the `{searchTerms}` braces are never percent-encoded.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>Bookshelf</ShortName>
  <Description>Search the Bookshelf catalog</Description>
  <Url type="application/atom+xml;profile=opds-catalog;kind=navigation"
       template="https://{host}/opds/v1/search/?q={searchTerms}"/>
  <Language>*</Language>
  <OutputEncoding>UTF-8</OutputEncoding>
  <InputEncoding>UTF-8</InputEncoding>
</OpenSearchDescription>
```

The `template` URL is built using `request.build_absolute_uri` so it works in any deployment environment.

### OPDS reader compatibility (search) — hard requirements

Each item is a MUST; violating any one makes search silently disappear in a strict reader:

1. **Advertise search at *feed level*, not inside an `<entry>`.** The root feed emits the `rel="search"` links as direct children of `<feed>` (via the feed dict's `feed_links`). A search link buried in a navigation `<entry>` is treated by the reader as a navigable URL — it is never recognised as search and, when templated, throws `illegal character in query` on the literal `{`.
2. **Serialize the OpenSearch document in the *default* namespace.** Tags must be unprefixed (`<OpenSearchDescription xmlns="…">`, `<Url>`), not `opensearch:`-prefixed — readers string-match a bare `<Url>`. The renderer sets a literal `xmlns` on the root rather than namespacing element tags (ElementTree's `default_namespace=` cannot be used because the `<Url>` carries unqualified attributes).
3. **The `<Url type>` must be the OPDS Catalog media type** (`application/atom+xml;profile=opds-catalog;kind=navigation`), never plain `application/atom+xml` — spec-compliant readers filter `<Url>` by this type and ignore a plain one.
4. **The `<Url template>` resolves to the search *root*** (`…/search/?q={searchTerms}`), so a search lands on the Authors/Series/Books chooser; it must not collapse onto a single sub-feed (e.g. books-only).
5. The root feed also carries a second feed-level templated link (`rel="search"`, `type="application/atom+xml"`, `…/search/?q={searchTerms}`).

---

## 7. XML Renderer

`OPDSRenderer` receives a **plain Python dict** (the feed dict produced by serializers) and converts it to Atom XML bytes. It has full responsibility for all XML construction — views and serializers are XML-free.

```python
# library/opds/renderers.py

class OPDSRenderer(BaseRenderer):
    media_type = 'application/atom+xml'
    format = 'atom'
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        # data is a dict matching the feed dict contract (see BOOK-45.md Phase 3)
        feed = self._build_feed(data)
        ET.indent(feed, space='  ')
        xml_bytes = ET.tostring(feed, encoding='unicode').encode('utf-8')
        return b'<?xml version="1.0" encoding="utf-8"?>\n' + xml_bytes
```

The renderer handles indentation via `ET.indent()` (Python 3.9+). XML namespaces are registered at module import time via `ET.register_namespace()`.

`OpenSearchRenderer` follows the same pattern but receives a simpler dict for the OpenSearch description document.

---

## 8. Atom Feed Conventions

### Namespaces used

| Prefix | URI |
|--------|-----|
| (default) | `http://www.w3.org/2005/Atom` |
| `opds` | `http://opds-spec.org/2010/catalog` |
| `dc` | `http://purl.org/dc/terms/` |
| `opensearch` | `http://a9.com/-/spec/opensearch/1.1/` |
| `xhtml` | `http://www.w3.org/1999/xhtml` (book entry `<content type="xhtml">`) |
| `calibre` | `http://calibre.kovidgoyal.net/2009/metadata` (`<calibre:series>` / `<calibre:series_index>`) |

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

### Navigation entry counts

Every **navigation** entry that represents a collection MUST expose its item count. The count is the number of child items the entry leads to:

- Author entry → number of books by that author.
- Series entry → number of books in that series (per-author count in the author-series feed, total count elsewhere).
- Genre entry → number of books in that genre (including descendants, via `get_descendants`).
- Alphabet-tree node → the node's item count (already specified in §6.2).
- Root-feed "browse" entries (Authors, Genres, Series, Books) → may carry the total entity count.

The count is rendered in the entry's `<content type="text">` element (e.g. `"42 books"`). This is a hard requirement for Authors, Series, and Genre navigation entries: a navigation entry without a count is incomplete.

### Default entry image (logo for non-book entries)

Every entry **except book (acquisition) entries** MUST carry the application logo as its thumbnail image:

- `<link rel="http://opds-spec.org/image/thumbnail" type="image/png" href="<abs>/static/img/Logo 64x64x8.png">`

This covers root-feed entries, author entries, series entries, genre entries, alphabet-tree nodes, and search-section entries — i.e. any entry that does **not** carry a `http://opds-spec.org/acquisition` link. Book entries are excluded: they use their own cover/thumbnail (§6.5, §6.5a). The href is an absolute URL built with `request.build_absolute_uri('/static/img/Logo 64x64x8.png')`.

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

**A. Canonical dataset (factory)** — used by structural/alphabetic tests that need realistic tree depth and counts, plus author/series/genre relationship tests. Call `create_test_dataset()` from `library.tests.test_data_factory` in `setUpTestData`. Provides:

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

Series  : 148  (C=54, S=62, T=11, 0-9=10, Other=11)
  C tree: C(54) → Ch(36)/Cr(18)/All 'C'(54)
  S tree: S(62) → Sh(6) / St(54) → Sta(28)/Ste(26)/All 'St'(54)
                            Sw(2) / All 'S'(62)
           T(11) / 0-9(10) / Other(11)

Genres  : 3 top-level → 7 leaf genres (distinct books per genre, see test_template.md)
  sf_fantasy(279): Dystopia(116) / Science Fiction(82) / Fantasy(81)
  mysteries_thrillers(208): Mystery(130) / Thriller(78)
  action_adventure(185): Adventure(111) / Nature & Animals(74)
  ~112 books have 2 genres (every 5th book gets a cross-parent second genre)

Relationships:
  Book→Author : every book has 1 primary author (round-robin); every 8th book has a 2nd author
                → ~70 multi-author books
  Book→Series : every 5th book is in 1 series (112 books total); every 4th of those is in 2 series
                → ~28 two-series books; sequence numbers are 1-based per series
  Book→Genre  : every book has 1 primary genre; every 5th book has a 2nd genre from a
                *different* parent group → ~112 two-genre books
                (sf books get an extra myst genre; myst → act; act → sf)
```

**B. Small detail fixture** — used only by `OPDSBookDetailTest` and `OPDSBookDownloadTest`, which need a real EPUB file and cover image (requires `BaseTestCase`). Defined inline in those test classes' `setUpTestData`:

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

All other detail-level test classes (`OPDSAuthorDetailTest`, `OPDSSeriesDetailTest`, `OPDSSearchTest`, `OPDSGenreFeedTest`) use the **canonical dataset** and find specific objects via `.filter()` rather than fixed attributes.

### 10.2 Test Classes

---

#### `OPDSRootFeedTest`

No database content required (structure-only). Uses plain `TestCase`.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_root_feed_status_200` | GET `/opds/v1/` → 200 |
| 2 | `test_root_feed_content_type` | Response `Content-Type` starts with `application/atom+xml` |
| 3 | `test_root_feed_has_four_catalog_entries` | Feed contains exactly 4 `<entry>` elements (Authors, Genres, Series, Books) |
| 4 | `test_root_feed_entry_titles` | Each entry has the expected `<title>` text |
| 5 | `test_root_feed_self_link` | Feed contains `<link rel="self" href="/opds/v1/">` |
| 6 | `test_root_feed_start_link` | Feed contains `<link rel="start" href="/opds/v1/">` |
| 7 | `test_root_feed_search_link_at_feed_level` | Feed has exactly one feed-level `<link rel="search" type="application/opensearchdescription+xml">` and no `Search` `<entry>` |
| 8 | `test_root_feed_has_templated_atom_search_link` | Feed emits exactly one feed-level templated `<link rel="search" type="application/atom+xml">` whose href contains `search/?q={searchTerms}` |
| 9 | `test_root_feed_is_pretty_printed` | Raw XML response body contains newlines and indentation (human-readable check) |

---

#### `OPDSAlphabetTreeTest` (parameterized)

**Fixture:** canonical dataset via `create_test_dataset()`. Tests the three alphabet-tree root endpoints (genres use a separate hierarchy, tested below). Parameterized over:
- `('authors', '/opds/v1/authors/tree/')`
- `('books', '/opds/v1/books/tree/')`
- `('series', '/opds/v1/series/tree/')`

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
- `/opds/v1/authors/tree/a/`: entries `Ab(110)`, `Ac(11)`, `Ad(16)`, `all a(137)`
- `/opds/v1/authors/tree/ab/`: entries `Aba(60)`, `Abi(42)`, `Aby(8)`, `all ab(110)`
- `/opds/v1/authors/tree/aba/`: entries `Abak(21)`, `Aban(39)`, `all aba(60)` — leaf sub-tree

Books tree (from `test_template.md`):
- Root: `A(222)`, `B(167)`, `M(43)`, `П(83)`, `0-9(14)`, `Other(31)` — no `C`, `D`, etc.
- `/opds/v1/books/tree/a/`: entries `Al(96)`, `An(83)`, `Ar(43)`, `all a(222)`
- `/opds/v1/books/tree/al/`: entries `Ali(57)`, `All(39)`, `all al(96)`
- `/opds/v1/books/tree/ali/`: entries `Alid(23)`, `Alit(34)`, `all ali(57)`

Series tree (from `test_template.md`):
- Root: `C(54)`, `S(62)`, `T(11)`, `0-9(10)`, `Other(11)` — no `A`, `B`, etc.
- `/opds/v1/series/tree/c/`: entries `Ch(36)`, `Cr(18)`, `all c(54)`
- `/opds/v1/series/tree/s/`: entries `Sh(6)`, `St(54)`, `Sw(2)`, `all s(62)`
- `/opds/v1/series/tree/st/`: entries `Sta(28)`, `Ste(26)`, `all st(54)`

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_authors_root_entry_count` | `/opds/v1/authors/tree/` contains exactly 6 top-level entries: A, B, C, Ш, `0-9`, Other |
| 2 | `test_authors_root_a_count_is_137` | `"A"` entry `<content>` contains `137` |
| 3 | `test_authors_root_digits_count_is_12` | `"0-9"` entry `<content>` contains `12` |
| 4 | `test_authors_a_sub_entries` | `/opds/v1/authors/tree/a/` contains entries `Ab(110)`, `Ac(11)`, `Ad(16)`, `all a(137)` — no others |
| 5 | `test_authors_ab_sub_entries` | `/opds/v1/authors/tree/ab/` contains entries `Aba(60)`, `Abi(42)`, `Aby(8)`, `all ab(110)` — no others |
| 6 | `test_authors_aba_sub_entries` | `/opds/v1/authors/tree/aba/` contains entries `Abak(21)`, `Aban(39)`, `all aba(60)` — no others |
| 7 | `test_books_root_entry_count` | `/opds/v1/books/tree/` contains exactly 6 top-level entries: A, B, M, П, `0-9`, Other |
| 8 | `test_books_a_count_is_222` | `"A"` entry `<content>` contains `222` |
| 9 | `test_books_root_digits_count_is_14` | `"0-9"` entry `<content>` contains `14` |
| 10 | `test_books_a_sub_entries` | `/opds/v1/books/tree/a/` contains entries `Al(96)`, `An(83)`, `Ar(43)`, `all a(222)` — no others |
| 11 | `test_books_ali_sub_entries` | `/opds/v1/books/tree/ali/` contains entries `Alid(23)`, `Alit(34)`, `all ali(57)` — no others |
| 12 | `test_series_root_entry_count` | `/opds/v1/series/tree/` contains exactly 5 top-level entries: C, S, T, `0-9`, Other |
| 13 | `test_series_root_digits_count_is_10` | `"0-9"` entry `<content>` contains `10` |
| 14 | `test_series_s_count_is_62` | `"S"` entry `<content>` contains `62` |
| 15 | `test_series_s_sub_entries` | `/opds/v1/series/tree/s/` contains entries `Sh(6)`, `St(54)`, `Sw(2)`, `all s(62)` — no others |
| 16 | `test_series_st_sub_entries` | `/opds/v1/series/tree/st/` contains entries `Sta(28)`, `Ste(26)`, `all st(54)` — no others |

*(Other node structure and counts are covered in depth by `OPDSOtherNodeTest`.)*

---

#### `OPDSAlphabetAllNodeTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Uses the naturally deep `A→Ab→Aba` author tree (no extra data needed).

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_expanded_node_has_all_child` | `/opds/v1/authors/tree/a/` is expanded (has Ab/Ac/Ad children); feed contains entry titled `"all a"` |
| 2 | `test_all_node_is_first_child` | `"all a"` entry is the first `<entry>` in the `/opds/v1/authors/tree/a/` feed |
| 3 | `test_all_node_link_points_to_results_filter` | `"all a"` entry `<link href>` is the results endpoint `/opds/v1/authors/?filter=a` (no further sub-filter, no `regex`) |
| 4 | `test_all_node_count_equals_parent_count` | `"all a"` entry `<content>` count is `137` (same as parent `A` node) |
| 5 | `test_leaf_node_links_to_results` | `Ac` (Ac=11, leaf) entry in `/opds/v1/authors/tree/a/` links to `/opds/v1/authors/?filter=ac`; there is no `"all ac"` entry anywhere |
| 6 | `test_all_node_present_at_second_level` | `/opds/v1/authors/tree/ab/` is expanded (has Aba/Abi/Aby children); `"all ab"` is first `<entry>`, count=110, links to `/opds/v1/authors/?filter=ab` |
| 7 | `test_all_node_present_at_third_level` | `/opds/v1/authors/tree/aba/` is expanded (has Abak/Aban children); `"all aba"` is first `<entry>`, count=60, links to `/opds/v1/authors/?filter=aba` |
| 8 | `test_books_expanded_node_has_all_child` | `/opds/v1/books/tree/a/` has `"all a"` as first entry, count=222, links to `/opds/v1/books/?filter=a` |
| 9 | `test_series_expanded_node_has_all_child` | `/opds/v1/series/tree/s/` has `"all s"` as first entry, count=62, links to `/opds/v1/series/?filter=s` |
| 10 | `test_digits_node_is_leaf_no_all_entry` | `"0-9"` node (authors, books, series) is always a leaf → its tree entry links to `/opds/v1/authors/?regex=^[0-9]`; following that results link yields a flat list with no `"all 0-9"` entry |

---

#### `OPDSOtherNodeTest`

**Fixture:** canonical dataset via `create_test_dataset()`.

Background on how `get_alphabet_tree` builds the `Other` node:

- First-level alpha prefixes with count **below** `min_first_level_quantity` (default 10) are demoted into the `Other` node instead of appearing at the root. They become child entries of `Other`.
- Non-alpha (non-digit) items produce a `* (all non-alpha)` child entry inside `Other` with `regex=r'^[^[:alpha:][:digit:]]'`.
- `Other` is an **expandable** node, so its tree entry (in the root feed) links to the sub-tree path `/opds/v1/<entity>/tree/other/`, resolved by `find_alphabet_node_by_name(tree, 'other')`. The node still carries a composite `regex` covering both non-alpha items and all demoted alpha prefixes — used only for the "all Other" results link below, not for navigation.
- The "all Other" entry (first child of the expanded Other sub-tree, per the "all `<prefix>`" rule) links to the **results** endpoint `/opds/v1/<entity>/?regex=<url-encoded other_regex>` — returning the full 14/31/11 items. (The `other` node has an empty `filter`, so its "all" link uses `?regex=`, not `?filter=`.)

**Authors Other (14):** `* (all non-alpha)` = 3 (`!_1`, `(_2`, `+_3`) · `Z` = 8 · `Ї` = 2 · `Э` = 1
— `other_node.regex = r'^([^[:alpha:][:digit:]]|z|ї|э)'`

**Books Other (31):** `* (all non-alpha)` = 14 (`!`×7, `(`×5, `-`×2) · `Q` = 7 · `X` = 8 · `Ю` = 2
— `other_node.regex = r'^([^[:alpha:][:digit:]]|q|x|ю)'`

**Series Other (11):** `* (all non-alpha)` = 4 (`(`×2, `_`×2) · `N` = 4 · `В` = 3
— `other_node.regex = r'^([^[:alpha:][:digit:]]|n|в)'`

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_authors_root_has_other_entry` | `/opds/v1/authors/tree/` root feed contains an entry named `"Other"` with count 14 |
| 2 | `test_books_root_has_other_entry` | `/opds/v1/books/tree/` root feed contains an entry named `"Other"` with count 31 |
| 3 | `test_series_root_has_other_entry` | `/opds/v1/series/tree/` root feed contains an entry named `"Other"` with count 11 |
| 4 | `test_other_entry_link_is_tree_path` | `"Other"` entry `<link href>` is the sub-tree path `/opds/v1/authors/tree/other/` (expandable node — not a `?regex=` results link) |
| 5 | `test_other_node_feed_has_non_alpha_child` | GET `/opds/v1/authors/tree/other/` → feed contains `"* (all non-alpha)"` child entry with count 3 |
| 6 | `test_other_node_feed_has_z_child` | `/opds/v1/authors/tree/other/` feed contains child entry `"Z"` with count 8 |
| 7 | `test_other_node_feed_has_all_other_first` | `/opds/v1/authors/tree/other/` feed first `<entry>` is `"all Other"` (count 14) |
| 8 | `test_all_other_link_points_to_results_regex` | `"all Other"` entry `<link href>` is the results endpoint `/opds/v1/authors/?regex=<other_regex>` (the `other` node's composite regex, URL-encoded) — distinct from the `"Other"` root entry which links to `tree/other/` |
| 9 | `test_all_other_count_equals_other_total` | `"all Other"` entry `<content>` count equals 14 (authors), 31 (books), or 11 (series) matching the Other node total — parameterized |
| 10 | `test_non_alpha_child_link_uses_regex_param` | `"* (all non-alpha)"` entry (in `tree/other/`) `<link href>` is `/opds/v1/authors/?regex=%5E%5B%5E%5B%3A%5B%3Aalpha%3A%5D%5B%3Adigit%3A%5D%5D` (results endpoint, URL-encoded `^[^[:alpha:][:digit:]]`) or equivalent |
| 11 | `test_non_alpha_list_returns_only_non_alpha_items` | GET `/opds/v1/authors/?regex=^[^[:alpha:][:digit:]]` → feed contains exactly 3 entries (the `!_1`, `(_2`, `+_3` authors); no `Z`, `Ї`, `Э` authors |
| 12 | `test_non_alpha_books_list_count` | GET `/opds/v1/books/?regex=^[^[:alpha:][:digit:]]` → 14 entries total (across pages), all with non-alpha titles (`!*`, `(*`, `-*`) |
| 13 | `test_non_alpha_series_list_count` | GET `/opds/v1/series/?regex=^[^[:alpha:][:digit:]]` → feed has 4 entries (`(1`, `(2`, `_1`, `_2`) |
| 14 | `test_all_other_list_returns_complete_other_set` | GET `/opds/v1/authors/?regex=<other_regex>` → feed contains entries for all 14 Other authors (Z×8, Ї×2, Э×1, non-alpha×3 across pages) |
| 15 | `test_z_child_is_leaf_links_to_results` | In `/opds/v1/authors/tree/other/`, the `"Z"` child entry is a leaf (count=8 < `min_quantity`) → links to `/opds/v1/authors/?filter=z`; there is no `"all z"` entry |
| 16 | `test_demoted_alpha_child_link_uses_filter_param` | `"Z"` (and `"Ї"`, `"Э"`) child entries in `tree/other/` link to `/opds/v1/authors/?filter=z` (results endpoint, not `?regex=`), since they are regular alpha-leaf nodes |
| 17 | `test_books_other_q_child_count` | `/opds/v1/books/tree/other/` feed contains `"Q"` entry with count 7 |
| 18 | `test_books_other_x_child_count` | `/opds/v1/books/tree/other/` feed contains `"X"` entry with count 8 |
| 19 | `test_series_other_n_child_count` | `/opds/v1/series/tree/other/` feed contains `"N"` entry with count 4 |
| 20 | `test_series_other_cyrillic_в_child_count` | `/opds/v1/series/tree/other/` feed contains `"В"` entry with count 3 |
| 21 | `test_digits_node_is_separate_from_other` | Root tree feed for authors, books, and series: the `"0-9"` entry exists as a **sibling** of `"Other"`, not as a child inside it; the `tree/other/` feed does NOT contain a `"0-9"` child entry |

---

#### `OPDSAuthorListFeedTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Uses Authors: A=137, B=58, 0-9=12; no author starts with Z.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_author_alphabet_root_has_a_entry` | GET `/opds/v1/authors/tree/` → feed contains entry for `"a"` with count 137 |
| 2 | `test_author_alphabet_root_has_b_entry` | Root tree feed contains entry for `"b"` with count 58 |
| 3 | `test_author_alphabet_root_no_entry_for_missing_letter` | Root tree feed does NOT contain a `"z"` entry |
| 4 | `test_author_results_by_filter_status_200` | GET `/opds/v1/authors/?filter=b` → 200 (B is a leaf — 58 authors) |
| 5 | `test_author_results_by_filter_has_correct_count` | GET `/opds/v1/authors/?filter=b` → feed contains exactly 20 entries (page 1 of 58; pagination applies) |
| 6 | `test_author_results_entry_links_to_author_detail` | Each entry `<link href>` points to `/opds/v1/authors/<pk>/` |
| 7 | `test_author_results_filter_not_found_returns_empty_feed` | GET `/opds/v1/authors/?filter=y` → 200 with 0 `<entry>` elements (no author starts with Y in factory dataset) |
| 8 | `test_author_results_sorted_alphabetically` | Entries on `/opds/v1/authors/?filter=b` are ordered by author last name ascending (Ba* before Be*) |
| 9 | `test_author_digits_node_list` | GET `/opds/v1/authors/?regex=^[0-9]` → 200 with exactly 12 entries (all digit-prefix authors) |
| 10 | `test_author_results_entry_content_has_book_count` | Each entry on `/opds/v1/authors/?filter=b` has a `<content type="text">` containing that author's book count (e.g. `"<n> books"`); an author with 0 books shows `0` |

---

#### `OPDSGenreFeedTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Uses genres from the factory: `sf_fantasy` (parent, 3 leaf children), `dystopia` (leaf, child of sf_fantasy), `mysteries_thrillers` (parent, no books directly). The canonical dataset has no top-level genre with zero books — to test `count=0`, one leaf genre with 0 books is created inline in `setUpTestData` as `genre_empty` (`parent=None`, no children).

Objects referenced by name in the table below are obtained via `.get(code=...)` or `.first()` after `create_test_dataset()`. Redirect assertions use `self.client.get(url)` (default `follow=False`) and check `response.status_code == 302` and `response['Location']`.

Genre detail (`/genres/<pk>/`) is a **subgenres-only** navigation feed; a leaf genre 302-redirects to its book tree. Genre book browsing lives at the standard tree/results endpoints `/genres/<pk>/books/tree/[...]` and `/genres/<pk>/books/?filter=|?regex=`.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_genre_root_status_200` | GET `/opds/v1/genres/` → 200 |
| 2 | `test_genre_root_is_navigation` | `Content-Type` contains `kind=navigation` |
| 3 | `test_genre_root_lists_top_level_genres_only` | Feed entries include `sf_fantasy`, `mysteries_thrillers`, `action_adventure`, and `genre_empty`; does NOT include leaf genres (`dystopia`, `science_fiction`, etc.) |
| 4 | `test_genre_root_entry_links_to_genre_detail` | Each entry has `<link rel="subsection" href="/opds/v1/genres/<pk>/">` |
| 5 | `test_genre_root_entry_content_has_book_count` | `sf_fantasy` entry `<content>` contains `279` (116+82+81 books across its 3 leaf children) |
| 6 | `test_genre_root_genre_with_no_books_still_listed` | `genre_empty` (no books) still appears in root feed with count `0` |
| 7 | `test_genre_detail_with_subgenres_status_200` | GET `/opds/v1/genres/<sf_fantasy.pk>/` → 200 (has subgenres) |
| 8 | `test_genre_detail_404` | GET `/opds/v1/genres/99999/` → 404 |
| 9 | `test_genre_detail_lists_subgenres_only` | `sf_fantasy` feed contains exactly 3 navigation entries — `dystopia`, `science_fiction`, `fantasy` — each linking to `/opds/v1/genres/<subpk>/` |
| 10 | `test_genre_detail_has_no_book_or_alphabet_entries` | `sf_fantasy` feed contains no acquisition (book) entries and no alphabet-tree entries (e.g. no `"alid"` entry) — subgenres only |
| 11 | `test_genre_detail_leaf_genre_redirects_to_book_tree` | GET `/opds/v1/genres/<dystopia.pk>/` (leaf, no subgenres) → 302; `Location` ends in `/opds/v1/genres/<dystopia.pk>/books/tree/` |
| 12 | `test_genre_detail_empty_genre_redirects_to_book_tree` | GET `/opds/v1/genres/<genre_empty.pk>/` (no subgenres, no books) → 302 to `/opds/v1/genres/<genre_empty.pk>/books/tree/` |
| 13 | `test_genre_book_tree_status_200_navigation` | GET `/opds/v1/genres/<sf_fantasy.pk>/books/tree/` → 200, `Content-Type` contains `kind=navigation` |
| 14 | `test_genre_book_tree_has_alphabet_entries` | `/opds/v1/genres/<sf_fantasy.pk>/books/tree/` contains alphabet entries for books in its descendants (e.g. an `"al"`/`"ali"` branch leading to dystopia's Alid books) |
| 15 | `test_genre_book_tree_only_contains_own_books` | `/opds/v1/genres/<dystopia.pk>/books/tree/`: tree contains only letters present in dystopia books; counts match the `test_template.md` values for dystopia |
| 16 | `test_genre_book_tree_empty_genre_returns_empty_tree` | GET `/opds/v1/genres/<genre_empty.pk>/books/tree/` → 200 with 0 alphabet entries (0 books) |
| 17 | `test_genre_book_tree_leaf_links_to_results` | A leaf alphabet entry in `/opds/v1/genres/<pk>/books/tree/[...]` `<link href>` points to `/opds/v1/genres/<pk>/books/?filter=<letter>` |
| 18 | `test_genre_book_tree_non_leaf_links_to_subtree` | For `sf_fantasy`, an expandable letter node → `<link href>` is `/opds/v1/genres/<sf_fantasy.pk>/books/tree/<name>/`; that sub-tree feed includes the synthetic `"all <letter>"` first entry |
| 19 | `test_genre_book_tree_regex_node_link_carries_regex_param` | A regex leaf (`0-9`) in `/opds/v1/genres/<pk>/books/tree/` has `<link href>` = `/opds/v1/genres/<pk>/books/?regex=^[0-9]`; the `other` node links to `…/books/tree/other/` |
| 20 | `test_genre_books_results_by_filter_status_200` | GET `/opds/v1/genres/<dystopia.pk>/books/?filter=alid` → 200 |
| 21 | `test_genre_books_results_by_filter_filters_correctly` | `/opds/v1/genres/<dystopia.pk>/books/?filter=alid` → all entry titles start with `"Alid"`; no `"Alit"` title; no book whose only genre is `mystery` (descendant-genre filter holds) |
| 22 | `test_genre_books_results_empty_filter_returns_empty_feed` | GET `/opds/v1/genres/<dystopia.pk>/books/?filter=z` → 200 with 0 entries |
| 23 | `test_genre_books_results_by_regex_filters_by_regex` | For a genre whose tree has a `0-9` node: GET `/opds/v1/genres/<pk>/books/?regex=^[0-9]` → 200; feed total (across pages) equals that genre's `0-9` tree-entry count; every entry title starts with a digit |
| 24 | `test_genre_books_results_regex_beats_filter` | GET `/opds/v1/genres/<pk>/books/?filter=0-9` (no `?regex=`) → uses `istartswith='0-9'` and yields 0 entries — confirms `?regex=` is what drives non-letter nodes |

---

#### `OPDSGenreFeedCountsTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Verifies genre book counts against the table in `test_template.md`. All counts are **distinct books per genre** (multi-genre books are counted in each genre they belong to).

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_genre_root_sf_fantasy_count` | `Science Fiction & Fantasy` entry `<content>` contains `279` (116+82+81) |
| 2 | `test_genre_root_mysteries_count` | `Mysteries & Thrillers` entry `<content>` contains `208` (130+78) |
| 3 | `test_genre_root_action_adv_count` | `Action & Adventure` entry `<content>` contains `185` (111+74) |
| 4 | `test_dystopia_book_tree_has_alid_entry` | `/opds/v1/genres/<dystopia.pk>/books/tree/` (reached via the leaf-genre redirect): alphabet tree contains the `"alid"` branch (5 dystopia books in Alid group) |
| 5 | `test_fantasy_book_tree_no_yu_entry` | `/opds/v1/genres/<fantasy.pk>/books/tree/`: alphabet tree does NOT contain a `"ю"` entry (fantasy has 0 books starting with Ю) |
| 6 | `test_nature_animals_book_tree_total_is_74` | `/opds/v1/genres/<nature_animals.pk>/books/tree/`: sum of the top-level alphabet-tree entry counts (per-letter `<content>` counts, excluding any `"all …"` synthetic entries) = 74 |
| 7 | `test_genre_books_results_alid_dystopia` | GET `/opds/v1/genres/<dystopia.pk>/books/?filter=alid` → feed has exactly 5 entries |
| 8 | `test_genre_books_results_count_matches_table` | GET `/opds/v1/genres/<dystopia.pk>/books/?filter=alit` → feed total count = 7 |

---

#### `OPDSSeriesListFeedTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Series: C=54, S=62, T=11, 0-9=10, Other=11; no series starts with Z. The `count=0` navigation-count edge (§8) is covered by a single test (#12) that creates its own zero-book series **locally within that test** (not in shared `setUpTestData`), so the per-letter count assertions in the other tests are unaffected.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_series_alphabet_root_status_200` | GET `/opds/v1/series/tree/` → 200 |
| 2 | `test_series_alphabet_root_is_navigation` | `Content-Type` contains `kind=navigation` |
| 3 | `test_series_alphabet_root_has_s_entry` | Root tree feed contains an entry for `"s"` with count 62 |
| 4 | `test_series_alphabet_root_no_entry_for_missing_letter` | Root tree feed does NOT contain an entry for `"z"` |
| 5 | `test_series_results_by_filter_status_200` | GET `/opds/v1/series/?filter=t` → 200 (T=11, leaf) |
| 6 | `test_series_results_has_correct_count` | GET `/opds/v1/series/?filter=t` → feed contains exactly 11 entries |
| 7 | `test_series_results_entry_links_to_series_detail` | Each entry has `<link href="/opds/v1/series/<pk>/">` |
| 8 | `test_series_results_empty_filter_returns_empty_feed` | GET `/opds/v1/series/?filter=z` → 200 with 0 entries |
| 9 | `test_series_s_is_expanded_subtree` | GET `/opds/v1/series/tree/s/` → feed contains navigation sub-entries (`Sh`, `St`, `Sw`, `all s`), NOT a flat list of 62 series |
| 10 | `test_series_digits_node_list` | GET `/opds/v1/series/?regex=^[0-9]` → 200 with exactly 10 entries (all digit-prefix series) |
| 11 | `test_series_results_entry_content_has_book_count` | Each entry on `/opds/v1/series/?filter=t` has a `<content type="text">` containing that series' total book count (e.g. `"<n> books"`), per §8 "Navigation entry counts" |
| 12 | `test_series_results_zero_book_series_shows_count_0` | A series with no books (created locally in this test via `BookSeries.objects.create(name=...)`) → its `/opds/v1/series/?filter=<x>` entry has a `<content type="text">` whose count is `0` (the count is mandatory even when zero) |

---

#### `OPDSBookListFeedTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Books: A=222, B=167, M=43, П=83, 0-9=14, Other=31; no book starts with Z.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_book_alphabet_root_has_a_entry` | GET `/opds/v1/books/tree/` → feed contains `"a"` entry with count 222 |
| 2 | `test_book_alphabet_root_no_entry_for_missing_letter` | Root tree feed does NOT contain a `"z"` entry |
| 3 | `test_book_results_by_filter_status_200` | GET `/opds/v1/books/?filter=m` → 200 (M=43, leaf) |
| 4 | `test_book_results_has_correct_count` | GET `/opds/v1/books/?filter=m` → feed has 20 entries (page 1 of 43) |
| 5 | `test_book_results_excludes_other_letter` | GET `/opds/v1/books/?filter=m` → feed does NOT contain any book whose title starts with `"B"` |
| 6 | `test_book_results_is_acquisition_with_perm` | Privileged user, GET `/opds/v1/books/?filter=m`: entries have `<link rel="http://opds-spec.org/acquisition">` |
| 7 | `test_book_results_no_acquisition_link_anon` | Anon request: no acquisition link in entries |
| 8 | `test_book_results_empty_filter_returns_empty_feed` | GET `/opds/v1/books/?filter=z` → 200 with 0 entries |
| 9 | `test_book_a_is_expanded_subtree` | GET `/opds/v1/books/tree/a/` → returns navigation sub-entries (`Al`, `An`, `Ar`, `all a`), NOT a flat list of 222 books |
| 10 | `test_book_results_cyrillic_filter` | GET `/opds/v1/books/?filter=п` → 200 with entries for П=83 books (Ukrainian) |
| 11 | `test_book_digits_node_list` | GET `/opds/v1/books/?regex=^[0-9]` → 200 with exactly 14 entries (all digit-prefix books) |

---

#### `OPDSBookVerbosityTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Cross-cutting test of the §6.5a thin-default / `?detail=thick` rule across the book-listing acquisition feeds (Books `/books/?filter=<x>`, Author Books `/authors/<pk>/books/`, Recently Added `/authors/<pk>/books/recent/`, per-genre Books `/genres/<pk>/books/`, Series Detail `/series/<pk>/`, Search Books `/search/books/?q=<term>`). A privileged `user_with_perm` (member of `Book access`) is created inline so acquisition links render. A leaf book filter with a known entry count is used for the Books endpoint; specific author/series/genre objects are found via `.filter()`. `THICK = {"detail": "thick"}` is passed as a query param where thick mode is exercised.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_books_listing_entries_are_thin_by_default` | GET `/opds/v1/books/?filter=m` (no `detail` param): each book `<entry>` has a `<title>`, an `<id>` of form `tag:bookshelf:book:<pk>`, and a `<link rel="alternate">` — and has **no** `<content>`, **no** `<calibre:series>`, and **no** `<link rel="related">` |
| 2 | `test_thin_entry_has_mandatory_alternate_link` | Every thin book entry has exactly one `<link rel="alternate" type="application/atom+xml;type=entry;profile=opds-catalog">` whose `href` ends in `/opds/v1/books/<pk>/` (the §6.5 complete-entry endpoint) |
| 3 | `test_thin_entry_has_thumbnail_no_full_image` | A thin entry has `<link rel="http://opds-spec.org/image/thumbnail">` but **no** `<link rel="http://opds-spec.org/image">` (full-size cover) |
| 4 | `test_thin_entry_has_acquisition_link_with_perm` | `user_with_perm`: thin entries carry `<link rel="http://opds-spec.org/acquisition">` (thinness does not suppress the download link) |
| 5 | `test_thin_entry_no_acquisition_link_anon` | Anon request: thin entries carry no acquisition link (§9 rule still applies) |
| 6 | `test_thick_entries_are_complete` | GET `/opds/v1/books/?filter=m&detail=thick`: each book entry matches the §6.5 complete shape — has `<content type="xhtml">` (when the book has a description), `<calibre:series>`/`<calibre:series_index>` (when in a series), full-size `<link rel="http://opds-spec.org/image">`, and author `<link rel="related">` links |
| 7 | `test_thick_entry_still_has_alternate_link` | A thick entry still carries the `<link rel="alternate">` to `/opds/v1/books/<pk>/` (the param changes verbosity, not the alternate target) |
| 8 | `test_thick_param_propagates_to_pagination_links` | GET `/opds/v1/books/?filter=m&detail=thick` (43 books, paginated): the `<link rel="next">` (and on page 2, `rel="previous"`/`rel="first"`) URLs all preserve `detail=thick` |
| 9 | `test_thin_pagination_links_have_no_detail_param` | GET `/opds/v1/books/?filter=m` (default thin): pagination links do **not** carry a `detail` param |
| 10 | `test_author_books_feed_thin_by_default` | GET `/opds/v1/authors/<pk>/books/`: entries are thin (have `rel="alternate"`, no `<content>`) |
| 11 | `test_author_books_feed_thick_param` | GET `/opds/v1/authors/<pk>/books/?detail=thick`: entries are complete (have `<content>`/author `rel="related"` links) |
| 12 | `test_author_books_recent_feed_thin_by_default` | GET `/opds/v1/authors/<pk>/books/recent/`: entries are thin |
| 13 | `test_genre_books_feed_thin_by_default` | GET `/opds/v1/genres/<pk>/books/?filter=<x>`: entries are thin |
| 14 | `test_genre_books_feed_thick_param` | GET `/opds/v1/genres/<pk>/books/?filter=<x>&detail=thick`: entries are complete |
| 15 | `test_series_detail_book_entries_thin_by_default` | GET `/opds/v1/series/<pk>/`: book entries (not subseries nav entries) are thin |
| 16 | `test_series_detail_book_entries_thick_param` | GET `/opds/v1/series/<pk>/?detail=thick`: book entries are complete |
| 17 | `test_search_books_feed_thin_by_default` | GET `/opds/v1/search/books/?q=<term>`: book entries are thin |
| 18 | `test_search_books_feed_thick_param` | GET `/opds/v1/search/books/?q=<term>&detail=thick`: book entries are complete |

---

#### `OPDSThickPropagationTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Verifies the §6.5a **Propagation** rule — that `?detail=thick` is a sticky preference threaded through every browsable-catalog link and omitted from non-feed / always-complete links. Uses the implemented Root + Author feeds; a specific author with books/series is found via `.filter()`. A small helper asserts presence/absence of `detail=thick` in a link's `href` by `rel`.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_root_subsection_links_preserve_detail` | GET `/opds/v1/?detail=thick`: every entry `<link rel="subsection">` href contains `detail=thick` (Authors, Genres, Series, Books) |
| 2 | `test_root_search_links_preserve_detail` | Both feed-level search links carry `detail=thick`: the `opensearchdescription+xml` descriptor link, and the templated `atom+xml` link (which also keeps its `{searchTerms}` placeholder) |
| 3 | `test_root_self_and_start_links_preserve_detail` | GET `/opds/v1/?detail=thick`: the feed `<link rel="self">` and `<link rel="start">` hrefs both contain `detail=thick` |
| 4 | `test_root_logo_thumbnail_link_omits_detail` | The non-book `rel="http://opds-spec.org/image/thumbnail">` logo link never carries `detail=thick` |
| 5 | `test_author_tree_subsection_links_preserve_detail` | GET `/opds/v1/authors/tree/a/?detail=thick`: every child `subsection` link **and** the synthetic "all a" link href contains `detail=thick` |
| 6 | `test_author_results_links_preserve_detail` | GET `/opds/v1/authors/?filter=b&detail=thick`: each author entry's detail-feed `subsection` link, plus the `next`/`first` pagination links, contain `detail=thick` |
| 7 | `test_author_detail_subsection_links_preserve_detail` | GET `/opds/v1/authors/<pk>/?detail=thick`: the Books by Title / New Arrivals / Books by Series `subsection` links all contain `detail=thick` |
| 8 | `test_author_series_links_preserve_detail` | GET `/opds/v1/authors/<pk>/series/?detail=thick`: the Standalone Books link and every per-series `subsection` link contain `detail=thick` |
| 9 | `test_detail_survives_drilldown_to_acquisition_feed` | Following the `detail=thick`-bearing Books-by-Title link from the author detail feed lands on `/opds/v1/authors/<pk>/books/?detail=thick`, whose book entries are **complete** (thick) — proves the preference reaches the terminal acquisition feed by link-following alone |
| 10 | `test_navigation_links_omit_detail_by_default` | Without `?detail=thick`: no `subsection`, search-query, `self`, `start`, or pagination link on any navigation feed carries a `detail` param |

---

#### `OPDSPaginationTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Uses the results endpoints `/opds/v1/authors/?filter=b` (B=58 authors — leaf node) and `/opds/v1/books/?filter=m` (M=43 books — leaf node); no extra data creation needed.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_author_list_page_1_has_20_entries` | GET `/opds/v1/authors/?filter=b` → exactly 20 entries |
| 2 | `test_author_list_page_1_has_next_link` | Response has `<link rel="next">` |
| 3 | `test_author_list_page_1_no_prev_link` | Response has no `<link rel="previous">` |
| 4 | `test_author_list_page_2_has_20_entries` | GET `/opds/v1/authors/?filter=b&page=2` → exactly 20 entries |
| 5 | `test_author_list_page_3_has_18_entries` | GET `/opds/v1/authors/?filter=b&page=3` → exactly 18 entries (58 total: 20+20+18) |
| 6 | `test_author_list_page_3_has_prev_link` | Page 3 response has `<link rel="previous">` |
| 7 | `test_author_list_page_3_no_next_link` | Page 3 response has no `<link rel="next">` |
| 8 | `test_book_list_page_1_has_20_entries` | GET `/opds/v1/books/?filter=m` → exactly 20 entries |
| 9 | `test_book_list_page_3_has_3_entries` | GET `/opds/v1/books/?filter=m&page=3` → exactly 3 entries (43 total: 20+20+3) |
| 10 | `test_pagination_links_preserve_query_params` | `<link rel="next">` URL preserves `filter=b` and `page`, and any other query params |

---

#### `OPDSAuthorDetailTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Two users are created inline in `setUpTestData`: `user_no_perm` (no groups) and `user_with_perm` (member of `Book access` group). Two authors are identified from the dataset for testing: `author_with_series` — any author whose books include at least one series link and at least one standalone book (obtainable via query); `author_standalone_only` — any author whose books are all standalone. The canonical dataset guarantees both patterns exist because `_link_books_to_series` links only every 5th book, leaving ~80% of books standalone per author.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_author_detail_status_200` | GET `/opds/v1/authors/<any_author.pk>/` → 200 |
| 2 | `test_author_detail_404` | GET `/opds/v1/authors/99999/` → 404 |
| 3 | `test_author_detail_has_three_sub_feeds` | Feed has exactly 3 entries: Books by Title, New Arrivals, Books by Series |
| 3a | `test_author_detail_sub_feed_titles_match` | The three sub-feed entry `<title>`s are exactly `"Books by Title"`, `"New Arrivals"`, and `"Books by Series"` (in that order); the legacy labels `"All Books (A–Z)"` and `"Recently Added"` are absent |
| 4 | `test_author_detail_sub_feed_books_alpha_status_200` | GET `/opds/v1/authors/<any_author.pk>/books/` → 200 |
| 5 | `test_author_detail_sub_feed_books_alpha_contains_author_books` | Feed contains only books by the chosen author (verified by checking entry count matches `author.books.count()`) |
| 6 | `test_author_detail_sub_feed_books_alpha_excludes_other_author` | Feed does NOT contain a book known to belong only to a different author |
| 7 | `test_author_detail_sub_feed_books_alpha_sorted` | Entries are sorted alphabetically by title |
| 8 | `test_author_detail_sub_feed_books_recent_status_200` | GET `/opds/v1/authors/<any_author.pk>/books/recent/` → 200 |
| 9 | `test_author_detail_sub_feed_books_recent_sorted_by_date` | First entry has `created_at` ≥ second entry's `created_at` |
| 10 | `test_author_detail_sub_feed_series_status_200` | GET `/opds/v1/authors/<any_author.pk>/series/` → 200 |
| 11 | `test_author_detail_sub_feed_series_has_series` | For `author_with_series`: feed contains at least one series entry linking to `/opds/v1/series/<pk>/` |
| 12 | `test_author_detail_sub_feed_series_entry_has_book_count` | Series entry `<content>` contains a positive integer (book count for that author in that series) |
| 13 | `test_author_detail_sub_feed_series_no_standalone_entry_when_none` | For an author whose every book is in a series → feed does NOT contain a "Standalone Books" entry |
| 14 | `test_author_detail_sub_feed_series_has_standalone_entry_first` | For `author_with_series` who also has standalone books → the **first** entry is "Standalone Books", with `<link href>` ending in `/opds/v1/authors/<pk>/books/?series=none` |
| 15 | `test_author_detail_sub_feed_series_standalone_entry_has_count` | Standalone entry `<content>` contains the correct standalone count text |
| 15b | `test_author_books_series_none_filter_only_standalone` | GET `/opds/v1/authors/<pk>/books/?series=none` → total entry count (across pages) equals `author.books.filter(bookserieslink__isnull=True).count()`; contains no book that belongs to a series |
| 16 | `test_author_books_no_acquisition_link_anon` | Anon request to author books feed → no `<link rel="http://opds-spec.org/acquisition">` in entries |
| 17 | `test_author_books_acquisition_link_with_perm` | `user_with_perm` request → entries have `<link rel="http://opds-spec.org/acquisition">` |

---

#### `OPDSSeriesDetailTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Two users are created inline: `user_no_perm` and `user_with_perm`. A parent series with at least one subseries is identified from the dataset: the factory creates `BookSeries` with no parent, but `_link_books_to_series` assigns sequence numbers — for subseries testing, `setUpTestData` creates one additional subseries inline: `subseries = BookSeries.objects.create(name='SubTest', parent=series_with_books)` where `series_with_books` is any series from the dataset that has books. This gives a series with both books and a child series.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_series_detail_status_200` | GET `/opds/v1/series/<series_with_books.pk>/` → 200 |
| 2 | `test_series_detail_404` | GET `/opds/v1/series/99999/` → 404 |
| 3 | `test_series_detail_has_subseries` | Feed contains entry for `subseries` as a navigation link |
| 4 | `test_series_detail_has_books` | Feed contains at least 1 book entry (series has books via `_link_books_to_series`) |
| 5 | `test_series_detail_books_sorted_by_sequence_number` | Book entries appear in ascending `sequence_number` order |
| 6 | `test_series_detail_book_title_prefixed_with_seq` | Each book entry `<title>` starts with `"#<seq> · "` |
| 7 | `test_series_detail_no_acquisition_anon` | Anon request → no `<link rel="http://opds-spec.org/acquisition">` on book entries |
| 8 | `test_series_detail_acquisition_with_perm` | `user_with_perm` request → book entries have `<link rel="http://opds-spec.org/acquisition">` |

---

#### `OPDSBookDetailTest`

**Fixture:** small detail fixture (book_1 with file+cover, author_a, series_1, user_no_perm, user_with_perm). Extends `BaseTestCase` (book_1 has a real EPUB file for cover URL testing).

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_book_detail_status_200` | GET `/opds/v1/books/<book_1.pk>/` → 200 |
| 2 | `test_book_detail_404` | GET `/opds/v1/books/99999/` → 404 |
| 3 | `test_book_detail_has_title` | Entry `<title>` equals `"Foundation"` |
| 4 | `test_book_detail_has_author_related_link` | Entry has `<link rel="related">` with `href` pointing to `/opds/v1/authors/<author_a.pk>/`, `type` containing `kind=navigation`, and `title` equal to the author's `full_name` |
| 4a | `test_book_detail_one_related_link_per_author` | For a book with two authors (add `author_b` to `book_1.authors` in the test), the entry contains exactly **two** author `rel="related"` links — one per author — each pointing to its own `/opds/v1/authors/<pk>/` |
| 4b | `test_book_detail_author_related_link_mandatory` | Every complete book entry has at least one author `rel="related"` link (a complete entry never omits author links) |
| 4c | `test_book_detail_has_no_atom_author_element` | The entry contains **no** `<author>` Atom element — authors are represented only via `rel="related"` links |
| 5 | `test_book_detail_content_is_xhtml_type` | Entry has a `<content>` element with `type="xhtml"` containing an XHTML `<div>`; there is **no** `<summary>` element |
| 5a | `test_book_detail_content_has_description` | The `<content>` `<div>` text contains `book_1.description`'s text |
| 5b | `test_book_detail_content_has_no_series_text` | The `<content>` contains **no** series text (no `"Foundation #1"`, no `"Belongs to series"`) — series live only in `<calibre:*>` and the series `rel="related"` link |
| 5c | `test_book_detail_content_sanitizes_disallowed_html` | A book whose description contains a `<script>` (or other disallowed) tag → that tag is stripped from `<content>`; allowlisted tags (`<p>`, `<strong>`) survive |
| 5d | `test_book_detail_no_content_when_no_description` | A book with an empty description → entry has no `<content>` element |
| 5e | `test_book_detail_has_calibre_series` | Entry contains a `<calibre:series>` element (namespace `http://calibre.kovidgoyal.net/2009/metadata`) with text `"Foundation"` and a `<calibre:series_index>` with text `"1"` |
| 5f | `test_book_detail_calibre_series_name_stripped` | The `<calibre:series>` text has no leading/trailing whitespace (the series name is `.strip()`-ed) |
| 5g | `test_book_detail_one_calibre_series_pair_per_series` | A book in two series → exactly **two** `<calibre:series>` elements and **two** `<calibre:series_index>` elements |
| 5h | `test_book_detail_no_calibre_series_when_standalone` | book_3 (no series) → entry has no `<calibre:series>` element and no series `rel="related"` link |
| 6 | `test_book_detail_cover_link_is_absolute_url` | `<link rel="http://opds-spec.org/image" href="...">` is an absolute URL (starts with `http`) |
| 7 | `test_book_detail_has_thumbnail_link` | `<link rel="http://opds-spec.org/image/thumbnail">` present |
| 8 | `test_book_detail_has_series_related_link` | `<link rel="related">` pointing to `/opds/v1/series/<series_1.pk>/` present, with `title` equal to the **series name only** (`"Foundation"`) — **no** `#<sequence_number>` in the link title |
| 8a | `test_book_detail_author_and_series_related_links_distinguishable` | When the book has both author and series `rel="related"` links, they are distinguishable: author links point to `/opds/v1/authors/<pk>/`, series links to `/opds/v1/series/<pk>/` (asserted by `href` prefix) |
| 9 | `test_book_detail_no_cover_uses_no_cover_fallback` | book_2 (no cover) → `<link rel="http://opds-spec.org/image">` href ends in `/static/img/no_cover%20600x900.jpeg` and `<link rel="http://opds-spec.org/image/thumbnail">` href ends in `/static/img/no_cover%2040x60.jpeg` (image links are always present; cover-less books fall back to the placeholders, never omit the link) |
| 10 | `test_book_detail_no_acquisition_link_anon` | Anon user → no `<link rel="http://opds-spec.org/acquisition">` |
| 11 | `test_book_detail_no_acquisition_link_user_no_perm` | `user_no_perm` → no acquisition link |
| 12 | `test_book_detail_has_acquisition_link_user_with_perm` | `user_with_perm` → acquisition link present, `href="/opds/v1/books/<book_1.pk>/download/"` |

---

#### `OPDSEntryImageTest`

**Fixture:** canonical dataset via `create_test_dataset()`. Cross-cutting test of the "logo for every non-book entry" rule (§8 "Default entry image"). The logo lives at `/static/img/Logo 64x64x8.png`; assertions match the thumbnail link by `rel="http://opds-spec.org/image/thumbnail"` and an `href` ending in the URL-encoded logo path. Book (acquisition) entries are asserted **not** to carry the logo.

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_root_feed_entries_have_logo_thumbnail` | Every `<entry>` in `/opds/v1/` has `<link rel="http://opds-spec.org/image/thumbnail" type="image/png">` whose `href` ends in `/static/img/Logo%2064x64x8.png` |
| 2 | `test_author_list_entries_have_logo_thumbnail` | Every entry in `/opds/v1/authors/` (navigation) carries the logo thumbnail link |
| 3 | `test_alphabet_tree_entries_have_logo_thumbnail` | Every entry in `/opds/v1/authors/tree/` carries the logo thumbnail link |
| 4 | `test_genre_root_entries_have_logo_thumbnail` | Every entry in `/opds/v1/genres/` carries the logo thumbnail link |
| 5 | `test_series_detail_subseries_entry_has_logo` | A subseries (navigation) entry in `/opds/v1/series/<pk>/` carries the logo thumbnail link |
| 6 | `test_logo_thumbnail_href_is_absolute_url` | The logo `href` is an absolute URL (starts with `http`) |
| 7 | `test_book_entries_do_not_use_logo` | Book (acquisition) entries in `/opds/v1/authors/<pk>/books/` do **not** carry a logo thumbnail link (their image, if any, is the book cover — never the logo) |
| 8 | `test_search_section_entries_have_logo` | Section entries in `/opds/v1/search/?q=<term>` (navigation) carry the logo thumbnail link |

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

**Fixture:** canonical dataset via `create_test_dataset()`. Two users are created inline: `user_no_perm` and `user_with_perm`. Search queries use prefixes guaranteed to exist in the canonical dataset (e.g. `?q=Abak` matches authors, `?q=Ch` matches series, `?q=Alid` matches books). A dedicated unique prefix `Zap` (not in the dataset) is used for pagination testing by creating 25 extra books in `setUp` (not `setUpTestData`, since these books must be fresh per test to avoid interference).

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_search_root_returns_200` | GET `/opds/v1/search/?q=Abak` → 200 |
| 2 | `test_search_root_has_books_section_entry` | `?q=Alid` → root feed has a `"Books (N found)"` entry (N ≥ 1) whose `<link href>` ends in `/opds/v1/search/books/?q=Alid` |
| 3 | `test_search_root_has_series_section_entry` | `?q=Ch` → root feed has a `"Series (N found)"` entry linking to `/opds/v1/search/series/?q=Ch` |
| 4 | `test_search_root_has_authors_section_entry` | `?q=Abak` → root feed has an `"Authors (N found)"` entry linking to `/opds/v1/search/authors/?q=Abak` |
| 5 | `test_search_root_section_omitted_when_empty` | `?q=Abak` → root feed has no `"Books"` and no `"Series"` section entry |
| 6 | `test_search_root_empty_query_returns_empty_feed` | GET `/opds/v1/search/` (no `q`) → 200 with 0 `<entry>` elements |
| 7 | `test_search_root_no_results_returns_empty_feed` | GET `?q=xyzzyunmatchable` → 200 with 0 `<entry>` elements |
| 8 | `test_search_authors_subfeed_entries_link_to_author` | GET `/opds/v1/search/authors/?q=Abak` → each entry `<link href>` points to `/opds/v1/authors/<pk>/` |
| 9 | `test_search_series_subfeed_entries_link_to_series` | GET `/opds/v1/search/series/?q=Ch` → each entry `<link href>` points to `/opds/v1/series/<pk>/` |
| 10 | `test_search_books_subfeed_acquisition_link_with_perm` | `user_with_perm`, GET `/opds/v1/search/books/?q=Alid1` → book entries have `<link rel="http://opds-spec.org/acquisition">` |
| 11 | `test_search_books_subfeed_no_acquisition_link_anon` | Anon, GET `/opds/v1/search/books/?q=Alid1` → no acquisition link on book entries |
| 12 | `test_search_books_subfeed_pagination` | Create 25 books with title `Zap*`; GET `/opds/v1/search/books/?q=Zap` page 1 has exactly 20 entries; `<link rel="next">` present |
| 13 | `test_search_books_subfeed_pagination_preserves_q` | `/opds/v1/search/books/?q=Zap` `<link rel="next">` URL contains both `q=Zap` and `page=2` |
| 14 | `test_search_subfeed_empty_query_returns_empty_feed` | GET `/opds/v1/search/books/` (no `q`) → 200 with 0 `<entry>` elements |

#### `OPDSOpenSearchDescriptionTest`

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_opensearch_description_status_200` | GET `/opds/v1/search/description.xml` → 200 |
| 2 | `test_opensearch_description_content_type` | `Content-Type` is `application/opensearchdescription+xml` |
| 3 | `test_opensearch_description_has_shortname` | XML contains `<ShortName>Bookshelf</ShortName>` |
| 4 | `test_opensearch_description_has_url_template` | XML contains `<Url>` element with `template` attribute containing `/opds/v1/search/?q={searchTerms}` (search root chooser, not a sub-feed) |
| 5 | `test_opensearch_description_template_is_absolute_url` | `template` attribute value starts with `http` (absolute URL) |
| 6 | `test_opensearch_description_template_bakes_detail_thick` | GET `…/description.xml?detail=thick`: `template` contains both `q={searchTerms}` and `detail=thick` |
| 7 | `test_opensearch_description_template_omits_detail_by_default` | Without `?detail=thick`: `template` carries no `detail` parameter |
| 8 | `test_opensearch_description_uses_default_namespace` | Tags are unprefixed under a default `xmlns` (no `opensearch:`/`ns0:`) |
| 9 | `test_opensearch_description_url_type_is_opds_catalog` | `<Url type>` is `application/atom+xml;profile=opds-catalog;kind=navigation` (OPDS 1.2 requires the OPDS Catalog media type) |

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

Navigation and results are addressed differently:

- **Tree path segments** (`…/tree/<name>/`) use the node's `name`, resolved by `find_alphabet_node_by_name(tree, name)`. Only **expandable** nodes are ever placed in a path segment, and their names are URL-safe (`a`, `ab`, `aba`, `other`). Leaf nodes are never path segments.
- **Results selectors** are always query params on the flat endpoint: a prefix leaf/"all" link uses `?filter=<filter>` (the `AlphabetTree.filter` value); a regex leaf (`aa*`, `0-9`, `* (all non-alpha)`, `other`'s "all") uses `?regex=<url-encoded regex>`. The results view applies `iregex` if `regex` is present, else `istartswith` if `filter` is present, else returns the full set.

`find_alphabet_node_by_name` is a small recursive helper added to `library.services` alongside `find_alphabet_node`; it walks the tree and returns the first node whose `.name == name` (or `None`).

### `<updated>` in feeds

Use `django.utils.timezone.now()` as a fallback when no objects exist rather than a hardcoded date. For list feeds, use `queryset.aggregate(Max('updated_at'))['updated_at__max']`.

### Cover image URLs

`book.cover.url` returns a storage-relative URL. In Phase 1 (local filesystem), this is a relative media URL served by Nginx. The OPDS feed must produce an absolute URL using `request.build_absolute_uri(book.cover.url)`. Thumbnail uses `book.cover_preview.url` (imagekit-generated).

### Pretty-printing XML

Use `xml.etree.ElementTree.indent()` (Python 3.9+). Register all namespaces with `ET.register_namespace()` before building the tree to avoid `ns0:` prefixes in output.

### Download view: DRF `APIView` with no renderer

`BookDownloadView` extends DRF `APIView` (not a plain Django `View`), but sets `renderer_classes = []` so no renderer runs. This keeps it on the same DRF stack as every other OPDS endpoint — crucially the `throttle_classes = [OPDSMinuteRateThrottle, OPDSDayRateThrottle]` required by §3 / §6.6 — while still delivering raw bytes without the Atom renderer layer.

DRF only invokes a renderer when a view returns a DRF `Response`. The download view returns a plain Django `HttpResponse` / `FileResponse` / `StreamingHttpResponse` directly, which bypasses the renderer entirely. So the empty `renderer_classes` is belt-and-suspenders, and Django's file-response classes are available exactly as they would be on a plain `View`.

A plain Django `View` would not run DRF's throttle machinery, forcing a manual re-implementation of throttle checks (cache keys, `429` + `Retry-After`) inside `get()` — duplicating what `APIView.initial()` provides for free. The `APIView` + empty-renderer approach avoids that.

### Permission check approach

Views check `request.user.has_perm('library.view_book')` directly. No DRF `permission_classes` are used for the acquisition link visibility — the link is simply omitted from the serialized entry. The download view additionally returns `HTTP 403` for unauthorized requests.

### Throttle cache backend

Throttle uses the `default` cache. In tests, `BaseTestCase` sets `default` to `DummyCache`, which disables throttling. Throttle tests must override cache settings to use `LocMemCache`.

---

## 12. Design Decisions (Resolved)

1. **Navigation / results separation:** Authors, Series, Books, and per-genre Books each expose navigation **tree** endpoints (`…/tree/`, `…/tree/<name>/`) separate from a flat, paginated **results** endpoint (`…/` with `?filter=`/`?regex=`). Tree leaves and "all" entries link to the results endpoint; the bare results endpoint (no params) is the full set and is not advertised. A new `find_alphabet_node_by_name` service resolves tree path segments by node name. This eliminates the earlier ambiguity where one URL served both a sub-tree and a flat list.

1a. **Genres feed type:** Genres use the model hierarchy directly: root feed lists top-level genres; each genre detail lists **subgenres only** and, when it has no subgenres (leaf genre), **302-redirects** to `/opds/v1/genres/<pk>/books/tree/`. A genre's books are browsed through its own `…/books/tree/` and `…/books/` endpoints — the standard tree/results shape scoped to the genre (+descendants). Series root feed renders as an alphabet tree (same as Authors and Books), not a flat first-letter list.

2. **Search feed structure:** Results are split into three named sections within a single feed (Authors, Series, Books). Each section is preceded by a header entry carrying the count (`"Authors (N found)"`). A section is omitted entirely when its result set is empty. Book entries carry acquisition links; author and series entries carry navigation links.

3. **OpenSearch Description Document:** Implemented at `/opds/v1/search/description.xml`. Required for Calibre and KOreader auto-discovery. The descriptor's `<Url template>` is built as an absolute URL using `request.build_absolute_uri`.

4. **"All" node in alphabet trees:** When an alphabet tree node is expanded (has children), a synthetic `"all <prefix>"` entry is prepended as the first child. It links to the flat **results** endpoint for that prefix (`…/?filter=<prefix>`, or `…/?regex=<regex>` for the `other` node), returning the complete set for that prefix. Leaf nodes (not expanded) do not get an "all" entry. This applies uniformly to Authors, Books, Series, and the genre-scoped book alphabet trees.

5. **Book listing entries are thin (partial) by default; `?detail=thick` makes them complete.** Every book-listing acquisition feed emits *partial* catalog entries (title + acquisition link + mandatory `rel="alternate"` to `/opds/v1/books/<pk>/` + thumbnail). `?detail=thick` switches the same endpoints to inline *complete* entries (full summary, categories, full cover, series links) for readers that don't follow `alternate`.
