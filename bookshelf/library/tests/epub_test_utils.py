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

def create_epub_nested_chapters() -> io.BytesIO:
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
    c1.content = '<h1>Chapter 1</h1><p>Content of chapter 1.</p>'
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
