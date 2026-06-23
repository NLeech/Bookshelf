# Flibusta Database Field Descriptions

## libavtorname

Contains information about authors, including their names, nicknames, email addresses, homepages, and other metadata. Each record represents an author or a collective of authors.

| Field | Type | Description |
|-------|------|-------------|
| AvtorId | int(10) unsigned NOT NULL AUTO_INCREMENT | Primary key - unique author identifier |
| FirstName | varchar(99) CHARACTER SET utf8 NOT NULL DEFAULT '' | Author's first name/given name |
| MiddleName | varchar(99) CHARACTER SET utf8 NOT NULL DEFAULT '' | Author's middle name/patronymic |
| LastName | varchar(99) CHARACTER SET utf8 NOT NULL DEFAULT '' | Author's last name/family name |
| NickName | varchar(33) CHARACTER SET utf8 NOT NULL DEFAULT '' | Pen name or nickname |
| uid | int(11) NOT NULL DEFAULT '0' | User account ID reference (0 if not linked to user account) |
| Email | varchar(255) CHARACTER SET utf8 NOT NULL | Author's email address |
| Homepage | varchar(255) CHARACTER SET utf8 NOT NULL | Author's homepage URL |
| Gender | char(1) COLLATE utf8_unicode_ci NOT NULL DEFAULT '' | Gender identifier ('m'=male, 'f'=female, ''=unknown) |
| MasterId | int(10) NOT NULL DEFAULT '0' | Reference to main/canonical author ID for aliases/pseudonyms (0 if primary author) |

---

## libgenrelist

Contains information about book genres, names, codes and metagenres. Each record represents a genre of books.

| Field | Type | Description |
|-------|------|-------------|
| GenreId | int(10) unsigned NOT NULL AUTO_INCREMENT | Primary key - unique genre identifier |
| GenreCode | varchar(45) COLLATE utf8_unicode_ci NOT NULL DEFAULT '' | Short code identifier for the genre (e.g., 'sf_history', 'det_classic') |
| GenreDesc | varchar(99) COLLATE utf8_unicode_ci NOT NULL DEFAULT '' | Full genre description/name in Russian |
| GenreMeta | varchar(45) COLLATE utf8_unicode_ci NOT NULL DEFAULT '' | Metagenre or parent category (e.g., 'Фантастика', 'Детективы и триллеры') |

---

## libseqname

Contains names of book series. Each record represents a book series (authors' series or publisher's series).

| Field | Type | Description |
|-------|------|-------------|
| SeqId | int(10) unsigned NOT NULL AUTO_INCREMENT | Primary key - unique series identifier |
| SeqName | varchar(254) COLLATE utf8_unicode_ci NOT NULL DEFAULT '' | Series title/name |

---

## libbook

Contains information about books, including their titles, descriptions, etc. Each record represents a book.

| Field | Type | Description |
|-------|------|-------------|
| BookId | int(10) unsigned NOT NULL AUTO_INCREMENT | Primary key - unique book identifier |
| FileSize | int(10) unsigned NOT NULL DEFAULT '0' | File size in bytes |
| Time | timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP | Timestamp of last update or addition to library |
| Title | varchar(254) COLLATE utf8_unicode_ci NOT NULL DEFAULT '' | Book title (may include edition notes) |
| Title1 | varchar(254) CHARACTER SET utf8 NOT NULL | Alternative or normalized title format |
| Lang | char(3) CHARACTER SET utf8 NOT NULL DEFAULT 'ru' | 3-letter language code (e.g., 'ru', 'en') |
| LangEx | smallint(6) unsigned NOT NULL DEFAULT '0' | Extended language identifier (numeric code) |
| SrcLang | char(3) CHARACTER SET utf8 NOT NULL DEFAULT '' | Source language for translations (empty for original works) |
| FileType | char(4) CHARACTER SET utf8 NOT NULL | File extension/format (e.g., 'fb2', 'txt', 'epub') |
| Encoding | varchar(32) COLLATE utf8_unicode_ci NOT NULL DEFAULT '' | Text encoding specification |
| Year | smallint(6) NOT NULL DEFAULT '0' | Publication year (4 digits, 0 if unknown) |
| Deleted | char(1) COLLATE utf8_unicode_ci NOT NULL DEFAULT '0' | Deletion flag ('0'=active, '1'=deleted/removed) |
| Ver | varchar(8) CHARACTER SET utf8 NOT NULL DEFAULT '' | Version string of the file |
| FileAuthor | varchar(64) CHARACTER SET utf8 NOT NULL | Name of person who created/uploaded this file version |
| N | int(10) unsigned NOT NULL DEFAULT '0' | Internal counter or reference number |
| keywords | varchar(255) CHARACTER SET utf8 NOT NULL | Keywords/tags for search and categorization |
| md5 | binary(32) NOT NULL | MD5 hash of file content (for duplicate detection) |
| Modified | timestamp NOT NULL DEFAULT '2009-11-29 05:00:00' | Last modification timestamp |
| pmd5 | char(32) COLLATE utf8_unicode_ci NOT NULL DEFAULT '' | Parent or previous MD5 hash (for tracking file changes) |
| InfoCode | tinyint(3) unsigned NOT NULL DEFAULT '0' | Information type code or metadata flag |
| Pages | int(10) unsigned NOT NULL DEFAULT '0' | Number of pages in the book |
| Chars | int(10) unsigned NOT NULL DEFAULT '0' | Character count in the text |

---

## libavtor

Contains information about the relationship between books and authors. Each record represents a relationship between a book and an author; one book can have multiple authors and one author can have multiple books.

| Field | Type | Description |
|-------|------|-------------|
| BookId | int(10) unsigned NOT NULL DEFAULT '0' | Foreign key to libbook.BookId |
| AvtorId | int(10) unsigned NOT NULL DEFAULT '0' | Foreign key to libavtorname.AvtorId |
| Pos | tinyint(4) unsigned NOT NULL DEFAULT '0' | Position/order of author (for books with multiple authors) |

---

## libgenre

Contains information about the relationship between books and genres. Each record represents a relationship between a book and a genre; one book can belong to multiple genres and one genre can include multiple books.

| Field | Type | Description |
|-------|------|-------------|
| Id | int(10) unsigned NOT NULL AUTO_INCREMENT | Primary key - unique relationship identifier |
| BookId | int(10) unsigned NOT NULL DEFAULT '0' | Foreign key to libbook.BookId |
| GenreId | int(10) unsigned NOT NULL DEFAULT '0' | Foreign key to libgenrelist.GenreId |

---

## libjoinedbooks

Contains information about book replacement, which is used when a book is removed from the library and replaced by new/updated version of the same book. Each record represents a relationship between the old book and the new book.

| Field | Type | Description |
|-------|------|-------------|
| Id | int(11) NOT NULL AUTO_INCREMENT | Primary key - unique replacement record identifier |
| Time | timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP | Timestamp when replacement was recorded |
| BadId | int(11) NOT NULL DEFAULT '0' | ID of old/removed book being replaced |
| GoodId | int(11) NOT NULL DEFAULT '0' | ID of new/replacement book |
| realId | int(11) DEFAULT NULL | Actual canonical book ID (may differ from GoodId in complex replacement chains) |

---

## libseq

Contains information about the relationship between books and series. Each record represents a relationship between a book and a series; one book can belong to multiple series and one series can include multiple books.

| Field | Type | Description |
|-------|------|-------------|
| BookId | int(11) NOT NULL | Foreign key to libbook.BookId |
| SeqId | int(11) NOT NULL | Foreign key to libseqname.SeqId |
| SeqNumb | int(11) NOT NULL | Series number or position within the series |
| Level | tinyint(4) NOT NULL DEFAULT '0' | Hierarchy level for subseries (0=main series, >0=subseries level) |
| Type | tinyint(1) unsigned NOT NULL DEFAULT '0' | Series type indicator (distinguishes author series from publisher series) |

