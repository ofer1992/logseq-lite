#!/usr/bin/env python3
import sys
from datetime import datetime
from pathlib import Path
from fasthtml.common import *  # type: ignore
from fasthtml.common import (
    Div, fast_app, serve, Link, Style, picolink,
    MarkdownJS, HighlightJS
)

hdrs = (
    picolink,  # Include Pico CSS
    Style(':root { --pico-font-size: 100%; }'),
    MarkdownJS(),
    HighlightJS(langs=['python', 'javascript', 'html', 'css']),
    Link(
        rel='stylesheet',
        href='https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.css',
        media='(prefers-color-scheme: dark)'
    ),
    Link(
        rel='stylesheet',
        href='https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-light.css',
        media='(prefers-color-scheme: light)'
    ),
    Style("""
        body { max-width: 800px; margin: 0 auto; padding: 20px; }
        .marked { line-height: 1.6; }
        .marked code { padding: 0.2em 0.4em; border-radius: 3px; }
        .marked ul { list-style-type: none; padding-left: 1.5em; }
        .marked ul ul { margin-top: 0.5em; }
        .marked li { margin-bottom: 0.5em; }
    """)
)

app, rt = fast_app(hdrs=hdrs, debug=True)

if len(sys.argv) < 2:
    print("Usage: python app.py <folder_path>")
    sys.exit(1)

BASE_FOLDER = Path(sys.argv[1]).resolve()

def process_markdown(content: str) -> str:
    # replace [[link]] with [link](/pages/link)
    import re
    # need to replace any / with ___ in the link href
    content =  re.sub(r'\[\[([^\]]+)\]\]', lambda m: f'<a href="/pages/{m.group(1).replace("/","___")}">[[{m.group(1)}]]</a>', content)
    # replace TODO with a empty unclickable checkbox
    content = re.sub(r'TODO', lambda m: f'<input type="checkbox" disabled /> ', content)
    # replace DONE with a checked unclickable checkbox
    content = re.sub(r'DONE', lambda m: f'<input type="checkbox" checked disabled /> ', content)
    # delete chunks of the format like id:: 67ac6f2a-6385-4b60-92d7-da86c4524a1c
    content = re.sub(r'id::\s*[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '', content)
    return content


def render_note(name, content):
    return Div(H1(name), Div(process_markdown(content), cls="marked"))


def render_journal_entry(date: datetime) -> Div:
    journal_folder = BASE_FOLDER / "journals"
    journal_file = journal_folder / f"{date.strftime('%Y_%m_%d')}.md"
    # add unicode symbol U+1F4C5 to the title
    title = f"🗓️ {date.strftime('%b %d, %Y')}"
    return render_note(title, journal_file.read_text())


@rt("/search")
def get(q: str = ''):
    if not q:
        return Div()
    
    import subprocess
    results = []

    # Search in pages
    results.append(H2("Pages"))
    try:
        cmd = ['grep', '-l', '-i', q, str(BASE_FOLDER / "pages" / "*.md")]
        output = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True)

        for file_path in output.stdout.splitlines():
            file = Path(file_path)
            name = file.stem.replace("___", "/")
            results.append(
                Li(A(name, href=f"/pages/{file.name}"))
            )
    except Exception as e:
        print(f"Error searching pages: {e}")

    # Search in journals
    results.append(H2("Journals"))
    try:
        # Use grep -l to only list matching files, -i for case insensitive
        cmd = ['grep', '-l', '-i', q, str(BASE_FOLDER / "journals" / "*.md")]
        output = subprocess.run(" ".join(cmd), shell=True, capture_output=True, text=True)
        
        for file_path in output.stdout.splitlines():
            file = Path(file_path)
            date = datetime.strptime(file.stem, "%Y_%m_%d")
            results.append(
                Li(A(f"🗓️ {date.strftime('%b %d, %Y')}", 
                    href=f"/journals/{date.strftime('%Y%m%d')}"))
            )

    except Exception as e:
        print(f"Error searching journals: {e}")
    if not results:
        return Div("No results found")
    
    return Ul(*results)



@rt("/")
def get(offset: int = 0):
    from itertools import repeat
    BATCH_SIZE = 1
    journal_folder = BASE_FOLDER / "journals"
    # Get the next batch of journals
    latest_journals = sorted(journal_folder.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
    batch = latest_journals[offset:offset+BATCH_SIZE]
    
    if not batch:
        return Div()  # Return empty div if no more journals
        
    rendered = [render_journal_entry(datetime.strptime(journal.name[:10], "%Y_%m_%d")) for journal in batch]
    
    sentinel_div = Div(
        hx_get=f"/?offset={offset+BATCH_SIZE}",
        hx_trigger="revealed",
        hx_swap="outerHTML"
    )
    # Add sentinel div for next batch if there are more journals
    page = Div(*[el for t in zip(rendered, repeat(Hr())) for el in t])
    if len(batch) == BATCH_SIZE and offset + BATCH_SIZE < len(latest_journals):
        return page, sentinel_div

    return page


@rt("/journals/{date}")
def get(date: str):
    # date format is YYYYMMDD. format to YYYY_MM_DD
    try:
        date_obj = datetime.strptime(date, "%Y%m%d")
    except ValueError:
        return Div("Invalid date format", code=400)
    return render_journal_entry(date_obj)


@rt("/pages/")
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


@rt("/{folder}/{note}")
def get(folder: str, note: str):
    # Build the file path by joining the base folder with the note path
    file_path = BASE_FOLDER / folder / note
    print(f"Serving {file_path}")
    note_name = note[:-3] if note.endswith('.md') else note
    note_name = note_name.replace("___", "/")
    
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
        return render_note(note_name, content)
    except Exception as e:
        return Div(f"Error reading file: {e}", code=500)


if __name__ == "__main__":
    # Start the server
    serve()
