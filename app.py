#!/usr/bin/env python3
import sys
from pathlib import Path
from fasthtml.common import *  # type: ignore
from fasthtml.common import (
    Div, fast_app, serve
)

hdrs = (MarkdownJS(), HighlightJS(langs=['python', 'javascript', 'html', 'css']), )
app, rt = fast_app(hdrs=hdrs)

if len(sys.argv) < 2:
    print("Usage: python app.py <folder_path>")
    sys.exit(1)

BASE_FOLDER = Path(sys.argv[1]).resolve()


@rt("/")
def get():
    # link to pages route
    return Div("Hello, World!")

@rt("/pages")
def get():
    # list all files in the pages folder
    files = [f.name for f in (BASE_FOLDER / "pages").iterdir() if f.is_file()]
    def link(f: str):
        link = f
        # strip md suffix
        f = f.replace(".md", "")
        # replace ___ with /
        f = f.replace("___", "/")
        return Li(A(f, href=f"/pages/{link}"))
    return Ul(link(f) for f in files)


def process_markdown(content: str) -> str:
    # replace [[link]] with [link](/pages/link)
    import re
    # return re.sub(r'\[\[([^\]]+)\]\]', r'[\1](/pages/\1)', content)
    return re.sub(r'\[\[([^\]]+)\]\]', r'<a href="/pages/\1">\1</a>', content)


@rt("/md_test")
def get():
    content = """
# Hello, World!

[[youtube]]

This is a test of the markdown parser.
"""
    return Div(process_markdown(content), cls="marked")


@rt("/{folder}/{note}")
def get(folder: str, note: str):
    # Build the file path by joining the base folder with the note path
    file_path = BASE_FOLDER / folder / note
    print(f"Serving {file_path}")
    
    # If file doesn't exist, try adding a '.md' extension
    if not file_path.is_file():
        if not str(file_path).endswith('.md'):
            file_path_md = file_path.with_suffix('.md')
            print(f"Checking {file_path_md}")
            if file_path_md.is_file():
                file_path = file_path_md
            else:
                return Div("File not found", code=404)
        else:
            return Div("File not found", code=404)
    
    # Read and return the file content
    try:
        content = file_path.read_text()
        return Div(process_markdown(content), cls="marked")
    except Exception as e:
        return Div(f"Error reading file: {e}", code=500)


if __name__ == "__main__":
    # Start the server
    serve()
