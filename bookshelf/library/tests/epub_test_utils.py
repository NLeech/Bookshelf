import os
import io
from ebooklib import epub
from PIL import Image

def create_epub_one_author() -> io.BytesIO:
    """
    Creates an EPUB file stream with a title, one author, and three chapters.
    """
    book = epub.EpubBook()

    # Set metadata
    book.set_identifier('id123456')
    book.set_title('Sample EPUB (One Author)')
    book.set_language('en')
    book.add_author('Author One')
    book.add_metadata('DC', 'description', 'A sample description.')

    # Create chapters
    c1 = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
    c1.content = '<h1>Chapter 1</h1><p>This is the content of the first chapter.</p>'

    c2 = epub.EpubHtml(title='Chapter 2', file_name='chap_02.xhtml', lang='en')
    c2.content = '<h1>Chapter 2</h1><p>This is the content of the second chapter.</p>'

    c3 = epub.EpubHtml(title='Chapter 3', file_name='chap_03.xhtml', lang='en')
    c3.content = '<h1>Chapter 3</h1><p>This is the content of the third chapter.</p>'

    # Add chapters to the book
    book.add_item(c1)
    book.add_item(c2)
    book.add_item(c3)

    # Define the table of contents
    book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap_01'),
                epub.Link('chap_02.xhtml', 'Chapter 2', 'chap_02'),
                epub.Link('chap_03.xhtml', 'Chapter 3', 'chap_03'))

    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define the spine
    book.spine = ['nav', c1, c2, c3]

    # Create an in-memory stream
    stream = io.BytesIO()
    epub.write_epub(stream, book, {})
    stream.seek(0)
    return stream

def create_epub_two_authors() -> io.BytesIO:
    """
    Creates an EPUB file stream with a title, two authors, and three chapters.
    """
    book = epub.EpubBook()

    # Set metadata
    book.set_identifier('id123457')
    book.set_title('Sample EPUB (Two Authors)')
    book.set_language('en')
    book.add_author('Author One')
    book.add_author('Author Two')
    book.add_metadata('DC', 'description', 'Another sample description with two authors.')

    # Create chapters
    c1 = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
    c1.content = '<h1>Chapter 1</h1><p>This is the content of the first chapter.</p>'

    c2 = epub.EpubHtml(title='Chapter 2', file_name='chap_02.xhtml', lang='en')
    c2.content = '<h1>Chapter 2</h1><p>This is the content of the second chapter.</p>'

    c3 = epub.EpubHtml(title='Chapter 3', file_name='chap_03.xhtml', lang='en')
    c3.content = '<h1>Chapter 3</h1><p>This is the content of the third chapter.</p>'

    # Add chapters to the book
    book.add_item(c1)
    book.add_item(c2)
    book.add_item(c3)

    # Define the table of contents
    book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap_01'),
                epub.Link('chap_02.xhtml', 'Chapter 2', 'chap_02'),
                epub.Link('chap_03.xhtml', 'Chapter 3', 'chap_03'))

    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define the spine
    book.spine = ['nav', c1, c2, c3]

    # Create an in-memory stream
    stream = io.BytesIO()
    epub.write_epub(stream, book, {})
    stream.seek(0)
    return stream

def create_epub_nested_chapters(content: str | None = None) -> io.BytesIO:
    """
    Creates an EPUB file stream with a title, one author, and three chapters,
    containing 2-3 nested subchapters.
    """
    book = epub.EpubBook()

    # Set metadata
    book.set_identifier('id123458')
    book.set_title('Sample EPUB (Nested Chapters)')
    book.set_language('en')
    book.add_author('Author One')
    book.add_metadata('DC', 'description', 'Description for nested chapters.')

    # Create chapters and subchapters
    c1 = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
    c1.content = f'<h1>Chapter 1</h1><p>{content or "Content of chapter 1."}</p>'
    c1.id = 'chap_01'

    sc1_1 = epub.EpubHtml(title='Subchapter 1.1', file_name='sub_chap_01_01.xhtml', lang='en')
    sc1_1.content = '<h2>Subchapter 1.1</h2><p>Content of subchapter 1.1.</p>'
    sc1_1.id = 'sc_01_01'

    sc1_2 = epub.EpubHtml(title='Subchapter 1.2', file_name='sub_chap_01_02.xhtml', lang='en')
    sc1_2.content = '<h2>Subchapter 1.2</h2><p>Content of subchapter 1.2.</p>'
    sc1_2.id = 'sc_01_02'

    c2 = epub.EpubHtml(title='Chapter 2', file_name='chap_02.xhtml', lang='en')
    c2.content = '<h1>Chapter 2</h1><p>Content of chapter 2.</p>'
    c2.id = 'chap_02'

    c3 = epub.EpubHtml(title='Chapter 3', file_name='chap_03.xhtml', lang='en')
    c3.content = '<h1>Chapter 3</h1><p>Content of chapter 3.</p>'
    c3.id = 'chap_03'

    sc3_1 = epub.EpubHtml(title='Subchapter 3.1', file_name='sub_chap_03_01.xhtml', lang='en')
    sc3_1.content = '<h2>Subchapter 3.1</h2><p>Content of subchapter 3.1.</p>'
    sc3_1.id = 'sc_03_01'

    # Add items to the book
    book.add_item(c1)
    book.add_item(sc1_1)
    book.add_item(sc1_2)
    book.add_item(c2)
    book.add_item(c3)
    book.add_item(sc3_1)

    # Define the table of contents with nested chapters
    book.toc = (
        (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap_01'),
            (
                epub.Link('sub_chap_01_01.xhtml', 'Subchapter 1.1', 'sc_01_01'),
                epub.Link('sub_chap_01_02.xhtml', 'Subchapter 1.2', 'sc_01_02')
            )
        ),
        epub.Link('chap_02.xhtml', 'Chapter 2', 'chap_02'),
        (epub.Link('chap_03.xhtml', 'Chapter 3', 'chap_03'),
            (
                epub.Link('sub_chap_03_01.xhtml', 'Subchapter 3.1', 'sc_03_01'),
            )
        )
    )

    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define the spine
    book.spine = ['nav', c1, sc1_1, sc1_2, c2, c3, sc3_1]

    # Create an in-memory stream
    stream = io.BytesIO()
    epub.write_epub(stream, book, {})
    stream.seek(0)
    return stream

def create_epub_cyrillic() -> io.BytesIO:
    """
    Creates an EPUB file stream with a title, one author, and three chapters;
    the author name, chapter titles, and chapter content are in Cyrillic.
    """
    book = epub.EpubBook()

    # Set metadata
    book.set_identifier('id123459')
    book.set_title('Приклад EPUB (Кирилиця)')
    book.set_language('uk')
    book.add_author('Автор Один')
    book.add_metadata('DC', 'description', 'Опис кирилицею.')

    # Create chapters with Cyrillic content
    c1 = epub.EpubHtml(title='Глава 1', file_name='chap_01.xhtml', lang='uk')
    c1.content = '<h1>Глава 1</h1><p>Це зміст першої глави.</p>'

    c2 = epub.EpubHtml(title='Глава 2', file_name='chap_02.xhtml', lang='uk')
    c2.content = '<h1>Глава 2</h1><p>Це зміст другої глави.</p>'

    c3 = epub.EpubHtml(title='Глава 3', file_name='chap_03.xhtml', lang='uk')
    c3.content = '<h1>Глава 3</h1><p>Це зміст третьої глави.</p>'

    # Add chapters to the book
    book.add_item(c1)
    book.add_item(c2)
    book.add_item(c3)

    # Define the table of contents
    book.toc = (epub.Link('chap_01.xhtml', 'Глава 1', 'chap_01'),
                epub.Link('chap_02.xhtml', 'Глава 2', 'chap_02'),
                epub.Link('chap_03.xhtml', 'Глава 3', 'chap_03'))

    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define the spine
    book.spine = ['nav', c1, c2, c3]

    # Create an in-memory stream
    stream = io.BytesIO()
    epub.write_epub(stream, book, {})
    stream.seek(0)
    return stream

def create_epub_no_toc() -> io.BytesIO:
    """
    Creates an EPUB file stream with a title, one author, and three chapters,
    but explicitly without a table of contents to test fallback mechanisms.
    """
    book = epub.EpubBook()

    # Set metadata
    book.set_identifier('id123460')  # Unique ID
    book.set_title('Sample EPUB (No TOC)')
    book.set_language('en')
    book.add_author('Author NoToc')
    book.add_metadata('DC', 'description', 'Description for no TOC book.')

    # Create chapters
    c1 = epub.EpubHtml(title='No TOC Chapter 1', file_name='no_toc_chap_01.xhtml', lang='en')
    c1.content = '<h1>No TOC Chapter 1</h1><p>This is the content of the first chapter without TOC.</p>'

    c2 = epub.EpubHtml(title='No TOC Chapter 2', file_name='no_toc_chap_02.xhtml', lang='en')
    c2.content = '<h1>No TOC Chapter 2</h1><p>This is the content of the second chapter without TOC.</p>'

    c3 = epub.EpubHtml(title='No TOC Chapter 3', file_name='no_toc_chap_03.xhtml', lang='en')
    c3.content = '<h1>No TOC Chapter 3</h1><p>This is the content of the third chapter without TOC.</p>'

    # Add chapters to the book
    book.add_item(c1)
    book.add_item(c2)
    book.add_item(c3)

    # Explicitly do NOT define book.toc
    book.toc = () # Assign an empty tuple to ensure no TOC is present

    # Add default NCX and Nav file - these are usually required even without a TOC
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define the spine
    book.spine = ['nav', c1, c2, c3]

    # Create an in-memory stream
    stream = io.BytesIO()
    epub.write_epub(stream, book, {})
    stream.seek(0)
    return stream

def create_epub_with_cover() -> io.BytesIO:
    """
    Creates an EPUB file stream with a title, one author, and a cover image.
    """
    book = epub.EpubBook()

    # Set metadata
    book.set_identifier('id_with_cover')
    book.set_title('Sample EPUB (With Cover)')
    book.set_language('en')
    book.add_author('Author Cover')

    # Create a simple red image for the cover
    img = Image.new('RGB', (100, 100), color='red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    cover_content = img_byte_arr.getvalue()

    # Set cover
    book.set_cover("cover.jpg", cover_content)

    # Create one chapter
    c1 = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
    c1.content = '<h1>Chapter 1</h1><p>Content.</p>'
    book.add_item(c1)

    # Define the table of contents
    book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap_01'),)

    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define the spine
    book.spine = ['nav', c1]

    # Create an in-memory stream
    stream = io.BytesIO()
    epub.write_epub(stream, book, {})
    stream.seek(0)
    return stream

def create_epub_cover_metadata() -> io.BytesIO:
    """
    Creates an EPUB file stream where the cover is an EpubImage linked via metadata.
    """
    book = epub.EpubBook()
    book.set_identifier('id_metadata_cover')
    book.set_title('Sample EPUB (Metadata Cover)')
    book.add_author('Author Metadata')

    img = Image.new('RGB', (100, 100), color='blue')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    cover_content = img_byte_arr.getvalue()

    # Add image as EpubImage (NOT EpubCover)
    image_item = epub.EpubImage()
    image_item.id = 'my_cover_id'
    image_item.file_name = 'cover.jpg'
    image_item.content = cover_content
    book.add_item(image_item)

    # Add metadata pointing to this image
    # ebooklib stores this as None, 'cover' after reading
    book.add_metadata(None, 'meta', '', {'name': 'cover', 'content': 'my_cover_id'})

    c1 = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
    c1.content = '<h1>Chapter 1</h1>'
    book.add_item(c1)
    book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap_01'),)
    
    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav', c1]

    stream = io.BytesIO()
    epub.write_epub(stream, book, {})
    stream.seek(0)
    return stream

def create_epub_cover_tag_name() -> io.BytesIO:
    """
    Creates an EPUB file stream where the cover is an EpubImage linked via 
    metadata tag NAMED 'cover' (less common but handled).
    """
    book = epub.EpubBook()
    book.set_identifier('id_tag_cover')
    book.set_title('Sample EPUB (Tag Name Cover)')
    book.add_author('Author Tag')

    img = Image.new('RGB', (100, 100), color='yellow')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    cover_content = img_byte_arr.getvalue()

    image_item = epub.EpubImage()
    image_item.id = 'my_cover_id'
    image_item.file_name = 'cover.jpg'
    image_item.content = cover_content
    book.add_item(image_item)

    # Add metadata as 'cover' tag directly
    book.add_metadata(None, 'cover', '', {'content': 'my_cover_id'})

    c1 = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
    c1.content = '<h1>Chapter 1</h1>'
    book.add_item(c1)
    book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap_01'),)
    
    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav', c1]

    stream = io.BytesIO()
    epub.write_epub(stream, book, {})
    stream.seek(0)
    return stream

def create_epub_cover_heuristic() -> io.BytesIO:
    """
    Creates an EPUB file stream where the cover is an EpubImage with 'cover' in its filename, 
    but no explicit cover markings.
    """
    book = epub.EpubBook()
    book.set_identifier('id_heuristic_cover')
    book.set_title('Sample EPUB (Heuristic Cover)')
    book.add_author('Author Heuristic')

    img = Image.new('RGB', (100, 100), color='green')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    cover_content = img_byte_arr.getvalue()

    # Add image as EpubImage with 'cover' in filename, no metadata, no properties
    image_item = epub.EpubImage()
    image_item.id = 'image_99'
    image_item.file_name = 'book_cover_image.jpg'
    image_item.content = cover_content
    book.add_item(image_item)

    c1 = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
    c1.content = '<h1>Chapter 1</h1>'
    book.add_item(c1)
    book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap_01'),)
    
    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav', c1]

    stream = io.BytesIO()
    epub.write_epub(stream, book, {})
    stream.seek(0)
    return stream

def create_epub_with_isbn(isbn_val: str, use_prefix: bool = False) -> io.BytesIO:
    """
    Creates an EPUB file stream with a specific ISBN.
    """
    book = epub.EpubBook()
    book.set_title('Sample EPUB (ISBN)')
    book.set_language('en')
    book.add_author('Author ISBN')

    # Set as primary identifier first, then we might overwrite it with more specific metadata
    book.set_identifier('id123456')

    if use_prefix:
        book.add_metadata('DC', 'identifier', f'isbn:{isbn_val}')
    else:
        # Use full namespace URI for the scheme attribute to ensure it's written correctly
        opf_uri = 'http://purl.org/dc/terms/' # Wait, is it OPF or DCTERMS?
        # Re-checking NAMESPACES in epub.py: OPF is http://www.idpf.org/2007/opf
        book.add_metadata('DC', 'identifier', isbn_val, {f'{{http://www.idpf.org/2007/opf}}scheme': 'ISBN'})
    
    c1 = epub.EpubHtml(title='Chapter 1', file_name='chap_01.xhtml', lang='en')
    c1.content = '<h1>Chapter 1</h1>'
    book.add_item(c1)
    book.toc = (epub.Link('chap_01.xhtml', 'Chapter 1', 'chap_01'),)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav', c1]

    stream = io.BytesIO()
    epub.write_epub(stream, book, {})
    stream.seek(0)
    return stream

# --------------------------------------------------------------------------- #
# Synthetic factories for the boundary/spine-fill chapter extraction model.
#
# These build in-memory EPUBs whose STRUCTURE (spine order, TOC tree with the
# same #fragments, and in-DOM heading `id` anchors) replicates the patterns the
# refactored `_get_chapters_from_book()` must handle. Bodies are lorem-style
# filler; only the structure is asserted by the tests.
# --------------------------------------------------------------------------- #

def _html(file_name: str, item_id: str, content: str) -> epub.EpubHtml:
    """Build an EpubHtml spine item with a stable id and raw body content."""
    item = epub.EpubHtml(title='', file_name=file_name, lang='en')
    item.id = item_id
    item.content = content
    return item


def _build_epub(
    identifier: str,
    items: list,
    toc,
    spine_items: list,
    title: str = 'Synthetic EPUB',
    author: str = 'Synthetic Author',
    language: str = 'en',
) -> io.BytesIO:
    """Assemble an in-memory EPUB from explicit items, TOC, and spine.

    The spine is prefixed with the navigation document, mirroring the other
    factories in this module. ``toc`` is assigned verbatim so callers control the
    exact TOC tree (sections, links, and #fragments).
    """
    book = epub.EpubBook()
    book.set_identifier(identifier)
    book.set_title(title)
    book.set_language(language)
    book.add_author(author)

    for item in items:
        book.add_item(item)

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ['nav'] + list(spine_items)

    stream = io.BytesIO()
    epub.write_epub(stream, book, {})
    stream.seek(0)
    return stream


def create_epub_parent_with_anchored_children() -> io.BytesIO:
    """T4: one spine file with a no-anchor parent and two anchored children.

    The parent carries the file head (intro); each child heading carries the TOC
    #fragment id and its own body.
    """
    parent = _html(
        'parent.xhtml', 'parent',
        '<h1>Раздел</h1><p>Intro paragraph before any anchored section.</p>'
        '<h2 id="a">Раздел 1-50</h2><p>Body of verses one to fifty.</p>'
        '<h2 id="b">Раздел 51-100</h2><p>Body of verses fifty-one to one hundred.</p>',
    )
    toc = (
        (epub.Link('parent.xhtml', 'Раздел', 'parent'),
         (epub.Link('parent.xhtml#a', 'Раздел 1-50', 'a'),
          epub.Link('parent.xhtml#b', 'Раздел 51-100', 'b'))),
    )
    return _build_epub('parent_with_anchored_children', [parent], toc, [parent])


def create_epub_gap_and_split_tail() -> io.BytesIO:
    """T5: calibre split files; only the *_split_000 files carry TOC entries."""
    a0 = _html('partA_split_000.xhtml', 'a0',
               '<h1>Vireo</h1><p>Vireo opening paragraph long enough.</p>')
    a1 = _html('partA_split_001.xhtml', 'a1',
               '<p>Vireo split tail continuation paragraph.</p>')
    b0 = _html('partB_split_000.xhtml', 'b0',
               '<h1>Heron</h1><p>Heron opening paragraph long enough.</p>')
    toc = (
        epub.Link('partA_split_000.xhtml', 'Vireo', 'v'),
        epub.Link('partB_split_000.xhtml', 'Heron', 'h'),
    )
    return _build_epub('gap_and_split_tail', [a0, a1, b0], toc, [a0, a1, b0])


def create_epub_single_toc_entry_spanning_flow() -> io.BytesIO:
    """T6: empty cover + several text sections, TOC = a single entry -> cover."""
    cover = _html('cover.xhtml', 'cover', '<div></div>')
    s1 = _html('Section0001.xhtml', 's1', '<p>Section one narrative text.</p>')
    s2 = _html('Section0002.xhtml', 's2', '<p>Section two narrative text.</p>')
    s3 = _html('Section0003.xhtml', 's3', '<p>Section three narrative text.</p>')
    toc = (epub.Link('cover.xhtml', 'Start', 'start'),)
    return _build_epub('single_toc_entry_spanning_flow', [cover, s1, s2, s3], toc, [cover, s1, s2, s3])


def create_epub_interleaved_levels() -> io.BytesIO:
    """T7: one file with anchors at different tree levels (decision #3)."""
    ch = _html(
        'ch1-3.xhtml', 'ch',
        '<h1 id="g1">Глава 1</h1><p>Chapter one body text.</p>'
        '<h2 id="id4">Подраздел 1.1</h2><p>Subsection 1.1 body text.</p>'
        '<h1 id="id5">Глава 2</h1><p>Chapter two body text.</p>'
        '<h2 id="id6">Подраздел 2.1</h2><p>Subsection 2.1 body text.</p>',
    )
    toc = (
        (epub.Link('ch1-3.xhtml#g1', 'Глава 1', 'g1'),
         (epub.Link('ch1-3.xhtml#id4', 'Подраздел 1.1', 'id4'),)),
        (epub.Link('ch1-3.xhtml#id5', 'Глава 2', 'id5'),
         (epub.Link('ch1-3.xhtml#id6', 'Подраздел 2.1', 'id6'),)),
    )
    return _build_epub('interleaved_levels', [ch], toc, [ch])


def create_epub_no_toc_with_empty_cover() -> io.BytesIO:
    """T8: empty TOC; an empty cover precedes two textual spine files."""
    cover = _html('cover.xhtml', 'cover', '<div></div>')
    t1 = _html('text1.xhtml', 't1', '<h1>First</h1><p>First file narrative text.</p>')
    t2 = _html('text2.xhtml', 't2', '<h1>Second</h1><p>Second file narrative text.</p>')
    return _build_epub('no_toc_empty_cover', [cover, t1, t2], (), [cover, t1, t2])


def create_epub_pre_toc(front_content: str) -> io.BytesIO:
    """T3: a single pre-TOC front-matter file followed by one TOC chapter.

    ``front_content`` controls whether the front matter is empty (skipped),
    media-only (emitted), or textual (emitted).
    """
    front = _html('front.xhtml', 'front', front_content)
    chap = _html('chap1.xhtml', 'chap1', '<h1>Chapter 1</h1><p>Chapter one body text.</p>')
    toc = (epub.Link('chap1.xhtml', 'Chapter 1', 'chap1'),)
    return _build_epub('pre_toc', [front, chap], toc, [front, chap])


def create_epub_pre_toc_textual() -> io.BytesIO:
    """T10: empty cover + textual preface (no TOC entry) + a TOC chapter."""
    cover = _html('cover.xhtml', 'cover', '<div></div>')
    preface = _html('preface.xhtml', 'preface',
                    '<p>Preface narrative content with no heading of its own.</p>')
    chap = _html('chap1.xhtml', 'chap1', '<h1>Chapter 1</h1><p>Chapter one body text.</p>')
    toc = (epub.Link('chap1.xhtml', 'Chapter 1', 'chap1'),)
    return _build_epub('pre_toc_textual', [cover, preface, chap], toc, [cover, preface, chap])


def create_epub_dangling_toc() -> io.BytesIO:
    """T11: a TOC entry pointing at a file absent from spine and manifest."""
    c1 = _html('chap1.xhtml', 'c1', '<h1>Ch1</h1><p>Chapter one narrative text.</p>')
    c2 = _html('chap2.xhtml', 'c2', '<h1>Ch2</h1><p>Chapter two narrative text.</p>')
    toc = (
        epub.Link('chap1.xhtml', 'Ch1', 'c1'),
        epub.Link('missing.html', 'Dangling', 'dangling'),
        epub.Link('chap2.xhtml', 'Ch2', 'c2'),
    )
    return _build_epub('dangling_toc', [c1, c2], toc, [c1, c2])


# --------------------------------------------------------------------------- #
# Reference twins (R1-R5): synthetic structural replicas validated against the
# reader screenshots. Exact chapter trees are asserted by
# TestEpubChapterExtractionReferenceBooks.
# --------------------------------------------------------------------------- #

def create_epub_container_children_reference() -> io.BytesIO:
    """R1: Предисловие / container -> (Раздел 1-50 .. Раздел 551-600) / Послесловие."""
    pre = _html('pre.xhtml', 'pre', '<h1>Предисловие</h1><p>Preface body text.</p>')
    ranges = [(i * 50 + 1, i * 50 + 50) for i in range(12)]
    verses_body = ''.join(
        f'<h2 id="a{i}">Раздел {lo}-{hi}</h2><p>Body for verses {lo}-{hi}.</p>'
        for i, (lo, hi) in enumerate(ranges)
    )
    verses = _html('verses.xhtml', 'verses', verses_body)
    post = _html('post.xhtml', 'post', '<h1>Послесловие</h1><p>Afterword body text.</p>')
    children = tuple(
        epub.Link(f'verses.xhtml#a{i}', f'Раздел {lo}-{hi}', f'a{i}')
        for i, (lo, hi) in enumerate(ranges)
    )
    toc = (
        epub.Link('pre.xhtml', 'Предисловие', 'pre'),
        (epub.Section('Раздел'), children),
        epub.Link('post.xhtml', 'Послесловие', 'post'),
    )
    return _build_epub('container_children_reference', [pre, verses, post], toc, [pre, verses, post])


def create_epub_multilevel_chapters_reference() -> io.BytesIO:
    """R2: Предисловие / Глава 1 -> (4 children) / Глава 2 -> (5 children).

    Глава 1 has four children and Глава 2 has five; all child titles are generic
    placeholders that only encode the structure, not any real book content.
    """
    pre = _html('pre.xhtml', 'pre', '<h1>Предисловие</h1><p>Preface body text.</p>')

    ch1_children = [f'Раздел 1.{n}' for n in range(1, 5)]
    ch1_body = '<h1>Глава 1</h1><p>Chapter one lead-in text.</p>' + ''.join(
        f'<h2 id="c{i}">{title}</h2><p>Body for {title}.</p>'
        for i, title in enumerate(ch1_children)
    )
    ch1 = _html('ch1.xhtml', 'ch1', ch1_body)

    ch2_children = [f'Раздел 2.{n}' for n in range(1, 6)]
    ch2_body = '<h1>Глава 2</h1><p>Chapter two lead-in text.</p>' + ''.join(
        f'<h2 id="d{i}">{title}</h2><p>Body for {title}.</p>'
        for i, title in enumerate(ch2_children)
    )
    ch2 = _html('ch2.xhtml', 'ch2', ch2_body)

    toc = (
        epub.Link('pre.xhtml', 'Предисловие', 'pre'),
        (epub.Link('ch1.xhtml', 'Глава 1', 'ch1'),
         tuple(epub.Link(f'ch1.xhtml#c{i}', title, f'c{i}')
               for i, title in enumerate(ch1_children))),
        (epub.Link('ch2.xhtml', 'Глава 2', 'ch2'),
         tuple(epub.Link(f'ch2.xhtml#d{i}', title, f'd{i}')
               for i, title in enumerate(ch2_children))),
    )
    return _build_epub('multilevel_chapters_reference', [pre, ch1, ch2], toc, [pre, ch1, ch2])


def create_epub_nested_containers_reference() -> io.BytesIO:
    """R3: nested containers — Часть 1 -> Глава 1 -> Подраздел 1.1."""
    part = _html(
        'part1.xhtml', 'part1',
        '<h1 id="g1">Глава 1</h1><p>Chapter body text.</p>'
        '<h2 id="sub">Подраздел 1.1</h2><p>Subsection body text.</p>',
    )
    toc = (
        (epub.Section('Часть 1'),
         ((epub.Link('part1.xhtml#g1', 'Глава 1', 'g1'),
           (epub.Link('part1.xhtml#sub', 'Подраздел 1.1', 'sub'),)),)),
    )
    return _build_epub('nested_containers_reference', [part], toc, [part])


def create_epub_single_chapter_reference() -> io.BytesIO:
    """R4: one "Start" chapter spanning the whole flow (TOC = 1 entry)."""
    cover = _html('cover.xhtml', 'cover', '<div></div>')
    sections = [
        _html(f'Section{n:04d}.xhtml', f's{n}', f'<p>Section {n} narrative text.</p>')
        for n in range(1, 7)
    ]
    toc = (epub.Link('cover.xhtml', 'Start', 'start'),)
    return _build_epub('single_chapter_reference', [cover, *sections], toc, [cover, *sections])


def create_epub_split_parts_reference() -> io.BytesIO:
    """R5: calibre splits collapse — three parts, each split into two files."""
    items = []
    toc_links = []
    spine = []
    for letter, title in [('A', 'Vireo'), ('B', 'Heron'), ('C', 'Plover')]:
        split0 = _html(f'part{letter}_split_000.xhtml', f'{letter}0',
                       f'<h1>{title}</h1><p>{title} opening paragraph text.</p>')
        split1 = _html(f'part{letter}_split_001.xhtml', f'{letter}1',
                       f'<p>{title} split tail continuation text.</p>')
        items.extend([split0, split1])
        spine.extend([split0, split1])
        toc_links.append(epub.Link(f'part{letter}_split_000.xhtml', title, letter.lower()))
    return _build_epub('split_parts_reference', items, tuple(toc_links), spine)


def write_stream_to_file(stream: io.BytesIO, file_path: str) -> None:
    """
    Writes a stream to a file.
    """
    with open(file_path, 'wb') as f:
        f.write(stream.read())

if __name__ == '__main__':
    # When running this script directly, create the files in the 'books' directory,
    # which is relative to the project root, not the 'tests' directory.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    books_dir = os.path.join(project_root, 'books')

    if not os.path.exists(books_dir):
        os.makedirs(books_dir)

    epub_stream_1 = create_epub_one_author()
    write_stream_to_file(epub_stream_1, os.path.join(books_dir, 'test_epub_1.epub'))
    epub_stream_1.close()

    epub_stream_2 = create_epub_two_authors()
    write_stream_to_file(epub_stream_2, os.path.join(books_dir, 'test_epub_2.epub'))
    epub_stream_2.close()

    epub_stream_3 = create_epub_nested_chapters()
    write_stream_to_file(epub_stream_3, os.path.join(books_dir, 'test_epub_3.epub'))
    epub_stream_3.close()

    epub_stream_4 = create_epub_cyrillic()
    write_stream_to_file(epub_stream_4, os.path.join(books_dir, 'test_epub_4.epub'))
    epub_stream_4.close()

    epub_stream_5 = create_epub_no_toc()
    write_stream_to_file(epub_stream_5, os.path.join(books_dir, 'test_epub_5_no_toc.epub'))
    epub_stream_5.close()

    print(f"EPUB files created in the '{books_dir}' directory.")
