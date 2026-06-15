# Canonical Dataset — Relationships

## Book → Author
- Every book has exactly 1 primary author (round-robin over all 255 authors).
- Every 8th book (book index % 8 == 7) has a 2nd author → **~70 multi-author books**.
- Author assignment uses insertion order of both books and authors (deterministic).

## Book → Series (via BookSeriesLink)
- Every 5th book (index % 5 == 0) is linked to a series → **112 books with at least 1 series**.
- Every 4th of those (index % 20 == 0) is also linked to a second series → **~28 books in 2 series**.
- Sequence numbers are 1-based and incremented per series.

## Book → Genre (multi-genre)
- Every book starts with exactly 1 primary genre (see genre table below).
- Every 5th book (index % 5 == 4) gets a **second genre from a different parent group**:
  - Primary in sf_fantasy → extra genre = Mystery
  - Primary in mysteries_thrillers → extra genre = Adventure
  - Primary in action_adventure → extra genre = Dystopia
- This keeps distinct-per-parent counts in the genre table unchanged (no book gets a second genre from the same parent).
- **~112 books have 2 genres**.

---

# Authors

* **A (137)**
  * Ab (110)
    * Aba (60)
      * Abak (21)
      * Aban (39)
      * All 'Aba' (60)
    * Abi (42)
    * Aby (8)
    * All 'Ab' (110)
  * Ac (11)
  * Ad (16)
  * All 'A' (137)

* **B (58)**
  * Ba (30)
  * Be (28)
  * All 'B' (58)

* **C (19)**

* **Ш (15)**

* **0-9 (12)**

* **Other (14)**
  * \* (all non-alpha) (3)
  * Z (8)
  * Ї (2)
  * Э (1)
  * All 'Other' (14)

## Books

* **A (222)**
  * Al (96)
    * Ali (57)
      * Alid (23)
      * Alit (34)
      * All 'Ali' (57)
    * All (39)
    * All 'Al' (96)
  * An (83)
    * Ana (41)
    * And (42)
    * All 'An' (83)
  * Ar (43)
  * All 'A' (222)

* **B (167)**
  * Ba (84)
    * Bar (38)
    * Bat (46)
    * All 'Ba' (84)
  * Bl (42)
  * Bo (41)
  * All 'B' (167)

* **M (43)**

* **П (83)**
  * Пе (42)
  * Пр (41)
  * All 'П' (83)

* **0-9 (14)**

* **Other (31)**
  * \* (all non-alpha) (14)
  * Q (7)
  * X (8)
  * Ю (2)
  * All 'Other' (31)

  
# Languages
English: (473)
Українська: (87)

# Genres

Counts below are **distinct books per genre** (a book in 2 genres is counted in each genre row).
~112 books have 2 genres (every 5th book, assigned a second genre from a different parent group —
see [Relationships section](#canonical-dataset--relationships) above).

* **Science Fiction & Fantasy (279)**
    * Dystopia (116)
    * Science Fiction (82)
    * Fantasy (81)
* **Mysteries & Thrillers (208)**
    * Mystery (130)
    * Thriller (78)
* **Action & Adventure (185)**
    * Adventure (111)
    * Nature & Animals (74)

Book genres (distinct books per genre × title prefix)

| Genre | 0 | Alid | Alit | All | Ana | And | Ar | Bar | Bat | Bl | Bo | M | Пе | Пр | \* | Q | X | Ю | Sum |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Dystopia | 2 | 5 | 7 | 8 | 8 | 8 | 10 | 8 | 10 | 8 | 8 | 10 | 8 | 8 | 3 | 2 | 2 | 1 | 116 |
| Science Fiction | 2 | 3 | 5 | 6 | 6 | 6 | 6 | 6 | 7 | 6 | 6 | 6 | 6 | 6 | 2 | 1 | 1 | 1 | 82 |
| Fantasy | 2 | 3 | 5 | 6 | 6 | 6 | 6 | 6 | 7 | 6 | 6 | 6 | 6 | 6 | 2 | 1 | 1 | 0 | 81 |
| Mystery | 3 | 6 | 8 | 9 | 9 | 9 | 10 | 8 | 12 | 9 | 10 | 10 | 9 | 10 | 4 | 2 | 1 | 1 | 130 |
| Thriller | 2 | 3 | 5 | 5 | 6 | 6 | 6 | 5 | 6 | 6 | 6 | 6 | 6 | 6 | 2 | 1 | 1 | 0 | 78 |
| Adventure | 3 | 5 | 7 | 8 | 9 | 9 | 8 | 7 | 8 | 9 | 8 | 8 | 9 | 8 | 2 | 1 | 2 | 0 | 111 |
| Nature & Animals | 2 | 3 | 4 | 5 | 5 | 6 | 6 | 5 | 6 | 6 | 5 | 6 | 6 | 5 | 2 | 1 | 1 | 0 | 74 |

# Series

* **C (54)**
  * Ch (36)
  * Cr (18)
  * All 'C' (54)

* **S (62)**
  * Sh (6)
  * St (54)
    * Sta (28)
    * Ste (26)
    * All 'St' (54)
  * Sw (2)
  * All 'S' (62)

* **T (11)**

* **0-9 (10)**

* **Other (11)**
  * \* (all non-alpha) (4)
  * N (4)
  * В (3)
  * All 'Other' (11)
  
