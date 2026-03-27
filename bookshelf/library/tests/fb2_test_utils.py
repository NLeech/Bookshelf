import io
import base64

def create_simple_fb2(title="Test Title", authors=None, lang="en", annotation="Test Annotation", sections=None, cover_data=None) -> io.BytesIO:
    """
    Creates a simple FB2 file in memory.
    """
    if authors is None:
        authors = [{"first": "John", "last": "Doe"}]
    if sections is None:
        sections = [{"title": "Chapter 1", "content": "<p>Content 1</p>"}]

    fb2_xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" xmlns:l="http://www.w3.org/1999/xlink">',
        '  <description>',
        '    <title-info>',
        f'      <book-title>{title}</book-title>',
    ]

    for author in authors:
        fb2_xml.append('      <author>')
        if "first" in author:
            fb2_xml.append(f'        <first-name>{author["first"]}</first-name>')
        if "last" in author:
            fb2_xml.append(f'        <last-name>{author["last"]}</last-name>')
        if "nickname" in author:
            fb2_xml.append(f'        <nickname>{author["nickname"]}</nickname>')
        fb2_xml.append('      </author>')

    fb2_xml.append(f'      <lang>{lang}</lang>')
    fb2_xml.append(f'      <annotation>{annotation}</annotation>')

    if cover_data:
        fb2_xml.append('      <coverpage><image l:href="#cover.jpg"/></coverpage>')

    fb2_xml.append('    </title-info>')
    fb2_xml.append('  </description>')

    fb2_xml.append('  <body>')
    for section in sections:
        fb2_xml.append('    <section>')
        if section.get("title"):
            fb2_xml.append(f'      <title><p>{section["title"]}</p></title>')
        fb2_xml.append(f'      {section["content"]}')
        
        # Handle one level of sub-sections for testing
        if section.get("subsections"):
            for sub in section["subsections"]:
                fb2_xml.append('      <section>')
                if sub.get("title"):
                    fb2_xml.append(f'        <title><p>{sub["title"]}</p></title>')
                fb2_xml.append(f'        {sub["content"]}')
                fb2_xml.append('      </section>')
                
        fb2_xml.append('    </section>')
    fb2_xml.append('  </body>')

    if cover_data:
        b64_data = base64.b64encode(cover_data).decode('utf-8')
        fb2_xml.append(f'  <binary id="cover.jpg" content-type="image/jpeg">{b64_data}</binary>')

    fb2_xml.append('</FictionBook>')

    return io.BytesIO("\n".join(fb2_xml).encode('utf-8'))

def create_fb2_one_author() -> io.BytesIO:
    return create_simple_fb2(
        title="Sample FB2 (One Author)",
        authors=[{"first": "Author", "last": "One"}],
        annotation="A sample description.",
        sections=[
            {"title": "Chapter 1", "content": "<p>This is the content of the first chapter.</p>"},
            {"title": "Chapter 2", "content": "<p>This is the content of the second chapter.</p>"},
            {"title": "Chapter 3", "content": "<p>This is the content of the third chapter.</p>"}
        ]
    )

def create_fb2_two_authors() -> io.BytesIO:
    return create_simple_fb2(
        title="Sample FB2 (Two Authors)",
        authors=[{"first": "Author", "last": "One"}, {"first": "Author", "last": "Two"}],
        annotation="Another sample description with two authors.",
        sections=[
            {"title": "Chapter 1", "content": "<p>This is the content of the first chapter.</p>"},
            {"title": "Chapter 2", "content": "<p>This is the content of the second chapter.</p>"},
            {"title": "Chapter 3", "content": "<p>This is the content of the third chapter.</p>"}
        ]
    )

def create_fb2_nested_chapters() -> io.BytesIO:
    return create_simple_fb2(
        title="Sample FB2 (Nested Chapters)",
        authors=[{"first": "Author", "last": "One"}],
        annotation="Description for nested chapters.",
        sections=[
            {
                "title": "Chapter 1",
                "content": "<p>Content of chapter 1.</p>",
                "subsections": [
                    {"title": "Subchapter 1.1", "content": "<p>Content of subchapter 1.1.</p>"},
                    {"title": "Subchapter 1.2", "content": "<p>Content of subchapter 1.2.</p>"}
                ]
            },
            {"title": "Chapter 2", "content": "<p>Content of chapter 2.</p>"},
            {
                "title": "Chapter 3",
                "content": "<p>Content of chapter 3.</p>",
                "subsections": [
                    {"title": "Subchapter 3.1", "content": "<p>Content of subchapter 3.1.</p>"}
                ]
            }
        ]
    )

def create_fb2_cyrillic() -> io.BytesIO:
    return create_simple_fb2(
        title="Приклад FB2 (Кирилиця)",
        authors=[{"first": "Автор", "last": "Один"}],
        lang="uk",
        annotation="Опис кирилицею.",
        sections=[
            {"title": "Глава 1", "content": "<p>Це зміст першої глави.</p>"},
            {"title": "Глава 2", "content": "<p>Це зміст другої глави.</p>"},
            {"title": "Глава 3", "content": "<p>Це зміст третьої глави.</p>"}
        ]
    )

def write_stream_to_file(stream: io.BytesIO, file_path: str) -> None:
    with open(file_path, 'wb') as f:
        f.write(stream.read())
