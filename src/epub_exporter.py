import ebooklib
from ebooklib import epub
import markdown2
import os

def export_project_to_epub(project_data, output_path):
    """
    Exports project data (translated text) to an EPUB file.

    Args:
        project_data (dict): The project data dictionary containing 'title',
                             'description', and 'items'.
        output_path (str): The full path where the EPUB file should be saved.

    Returns:
        bool: True if export was successful, False otherwise.
        str: An error message if export failed, empty string otherwise.
    """
    if not project_data or 'items' not in project_data:
        return False, "Invalid project data provided."

    book = epub.EpubBook()

    # Set metadata
    book.set_identifier(project_data.get('title', 'Untitled Project').replace(' ', '_')) # Simple identifier
    book.set_title(project_data.get('title', 'Untitled Project'))
    book.set_language('en') # Assuming English for now, could be a project setting

    # Add author from project settings or default to SagaTrans
    author = project_data.get('author', 'SagaTrans')
    book.add_author(author)

    # Create chapters from project items
    chapters = []
    for i, item in enumerate(project_data['items']):
        item_name = item.get('name', f'Item {i+1}')
        translated_text_markdown = item.get('translated_text', '')

        # Convert Markdown to HTML
        translated_text_html = markdown2.markdown(translated_text_markdown, extras=["fenced-code-blocks", "tables", "strike"])

        # Create chapter
        chapter = epub.EpubHtml(title=item_name, file_name=f'chap_{i+1}.xhtml', lang='en')
        chapter.content = f'<h1>{item_name}</h1>\n{translated_text_html}'
        book.add_item(chapter)
        chapters.append(chapter)

    # Define Table of Contents and Spine
    book.toc = chapters
    book.spine = ['nav'] + chapters

    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Add default CSS
    style = 'BODY {color: black;}' # Basic style, changed to black for readability
    nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
    book.add_item(nav_css)

    # Create epub file
    try:
        epub.write_epub(output_path, book, {})
        return True, ""
    except Exception as e:
        return False, f"Error writing EPUB file: {e}"

if __name__ == '__main__':
    # Example Usage (for testing the library independently)
    example_project_data = {
        "title": "Example Translated Novel",
        "description": "A short example to test EPUB export.",
        "items": [
            {"name": "Chapter 1", "source_text": "Source 1", "translated_text": "# Chapter 1\n\nThis is the translated text for chapter 1."},
            {"name": "Chapter 2", "source_text": "Source 2", "translated_text": "## Chapter 2\n\nThis is the translated text for chapter 2 with some **bold** text."}
        ]
    }
    success, message = export_project_to_epub(example_project_data, "example_output.epub")
    if success:
        pass
    else:
        pass
