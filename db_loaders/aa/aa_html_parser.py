"""
AA HTML Summary Parser
======================
Pure BeautifulSoup parsing of Auto-Archiver HTML summary files.
No database access, no network calls — input is an HTML string, output is structured data.

The AA tool generates malformed HTML that must first be rendered in a real browser
(see aa_archive_loader.py for the Playwright download step) before being passed here.

HTML structure:
  - <table class="content">: one row per archived media item.
      Left cell contains nested metadata (parsed recursively).
      Right cell contains an embedded <img> or <video> tag whose src is the full CDN URL
      of the archived copy; captured as _cdn_url on the entry dict.
  - <table class="metadata">: two-column key/value table about the archive itself.
"""

from typing import Any

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel


class ParsedHTMLSummary(BaseModel):
    structures: list[dict]  # rows from the class="content" table
    metadata: dict          # key-value pairs from the class="metadata" table


def parse_html_cell(cell: Tag) -> Any:
    """Recursively parse one HTML cell into a Python value (dict, list, or string)."""
    res = {}
    cell_tag = cell.name
    if cell_tag == 'li':
        try:
            li_children = cell.find_all(recursive=False)
            key = li_children[0].get_text(strip=True).replace(":", "") if li_children else None
            value_element = li_children[1] if len(li_children) > 1 else None
            value = parse_html_cell(value_element) if value_element is not None else None
            return {key: value} if key else {}
        except Exception:
            return {}
    if cell_tag == 'ul':
        ul_li_items = cell.find_all('li', recursive=False)
        for li in ul_li_items:
            try:
                res.update(parse_html_cell(li))
            except Exception:
                continue
    wrap_elements = cell.find_all(['div', 'ul'], recursive=False)
    embedded_wraps = []
    for wrap in wrap_elements:
        try:
            collapsible_handler = wrap.find('b', class_='collapsible', recursive=False)
            if collapsible_handler:
                collapsible_label = collapsible_handler.get_text(strip=True)
                collapsible_key = collapsible_label.split('(')[0].strip()
                collapsible_value = wrap.find('div', class_='collapsible-content', recursive=False)
                if collapsible_value:
                    res[collapsible_key] = parse_html_cell(collapsible_value)
            else:
                value = parse_html_cell(wrap)
                if value and isinstance(value, (dict, list)):
                    embedded_wraps.append(value)
        except Exception:
            continue
    if embedded_wraps:
        res["_embedded"] = embedded_wraps
    res_keys = list(res.keys())
    if len(res_keys) == 1 and "_embedded" in res_keys:
        if len(res["_embedded"]) == 1:
            return res["_embedded"][0]
        return res["_embedded"]
    if len(res_keys) == 0:
        return cell.get_text(strip=True)
    # Capture the CDN URL from any embedded img/video tag (helps carousel items in "other media").
    if not res.get('_cdn_url'):
        tag = cell.find(['video', 'img'])
        if tag:
            src = tag.get('src')
            if src:
                res['_cdn_url'] = src
    return res


def parse_content_table(table: Tag) -> list[dict]:
    """Parse the class="content" table into a list of dicts (one per media row)."""
    results = []
    bodies = table.find_all('tbody', recursive=False)
    for body in bodies:
        rows = body.find_all('tr', recursive=False)
        for row in rows:
            cells = row.find_all('td', recursive=False) if row.td else []
            left_cell = cells[0] if cells else None
            right_cell = cells[1] if len(cells) > 1 else None
            if left_cell:
                entry_dict = parse_html_cell(left_cell)
                # The right cell's img/video src is the authoritative full CDN URL for this
                # media item. Override any _cdn_url found in the left cell's nested content.
                if right_cell:
                    tag = right_cell.find(['img', 'video'])
                    if tag:
                        src = tag.get('src')
                        if src:
                            entry_dict['_cdn_url'] = src
                results.append(entry_dict)
    return results


def parse_metadata_table(table: Tag) -> dict:
    """Parse the class="metadata" table into a flat dict."""
    data = {}
    bodies = table.find_all('tbody', recursive=False)
    for body in bodies:
        rows = body.find_all('tr', recursive=False)
        for row in rows:
            cells = row.find_all('td', recursive=False) if row.td else []
            left_cell = cells[0] if cells else None
            right_cell = cells[1] if len(cells) > 1 else None
            if left_cell:
                key = left_cell.get_text(strip=True).replace(":", "")
                ul_in_right = right_cell.find('ul', recursive=False) if right_cell else None
                value = parse_html_cell(right_cell) if ul_in_right else (
                    right_cell.get_text(strip=True) if right_cell else None
                )
                data[key] = value
    return data


def preprocess_soup(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove UI noise that would confuse the parser (e.g. 'Copy as JSON' buttons)."""
    for div in soup.find_all('div'):
        if div.string and div.string.strip() == "Copy as JSON":
            div.decompose()
    return soup


def parse_html_summary(html: str) -> ParsedHTMLSummary:
    """Parse a rendered AA HTML summary string into structured data."""
    soup = BeautifulSoup(html, 'html.parser')
    soup = preprocess_soup(soup)
    content_table = soup.find('table', class_='content', recursive=True)
    metadata_table = soup.find('table', class_='metadata', recursive=True)
    content_parsed = parse_content_table(content_table) if content_table else []
    metadata = parse_metadata_table(metadata_table) if metadata_table else {}
    return ParsedHTMLSummary(structures=content_parsed, metadata=metadata)
