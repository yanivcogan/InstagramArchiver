from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel

import db
import json
import traceback

from download_html_summary import download_summary_by_id


def get_content_from_file(file_path: Path) -> str:
    with file_path.open(encoding='utf-8') as f:
        content = f.read()
        return content


def parse_html_cell(cell: Tag) -> Any:
    res = dict()
    cell_tag = cell.name
    if cell_tag == 'li':
        try:
            li_children = cell.find_all(recursive=False)
            key = li_children[0].get_text(strip=True).replace(":", "") if li_children else None
            value_element = li_children[1] if len(li_children) > 1 else None
            value = parse_html_cell(value_element)
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
            # Look for collapsible content
            collapsible_handler = wrap.find('b', class_='collapsible', recursive=False)
            if collapsible_handler:
                collapsible_label = collapsible_handler.get_text(strip=True)  # e.g. "data (1):"
                collapsible_key = collapsible_label.split('(')[0].strip()  # e.g. "data"
                collapsible_value = wrap.find('div', class_='collapsible-content', recursive=False)
                if collapsible_value:
                    res[collapsible_key] = parse_html_cell(collapsible_value)
            # End of collapsible content handling
            else:
                value = parse_html_cell(wrap)
                if value and (isinstance(value, dict) or isinstance(value, list)):
                    embedded_wraps.append(value)
        except Exception:
            continue
    if len(embedded_wraps) > 0:
        res["_embedded"] = embedded_wraps
    res_keys = list(res.keys())
    if len(res_keys) == 1 and "_embedded" in res_keys:
        if len(res["_embedded"]) == 1:
            return res["_embedded"][0]
        return res["_embedded"]
    if len(res_keys) == 0:
        return cell.get_text(strip=True)
    return res


def parse_content_table(table: Tag) -> list[dict]:
    results = []
    bodies = table.find_all('tbody', recursive=False)
    for body in bodies:
        rows = body.find_all('tr', recursive=False) if table.tbody else []
        for row in rows:
            cells = row.find_all('td', recursive=False) if row.td else []
            left_cell = cells[0] if len(cells) > 0 else None
            if left_cell:
                entry_dict = parse_html_cell(left_cell)
                results.append(entry_dict)
    return results


def parse_metadata_table(table: Tag) -> dict:
    data = dict()
    bodies = table.find_all('tbody', recursive=False)
    for body in bodies:
        rows = body.find_all('tr', recursive=False)
        for row in rows:
            cells = row.find_all('td', recursive=False) if row.td else []
            left_cell = cells[0] if len(cells) > 0 else None
            right_cell = cells[1] if len(cells) > 1 else None
            if left_cell:
                key = left_cell.get_text(strip=True).replace(":", "")
                ul_in_right = right_cell.find('ul', recursive=False) if right_cell else None
                value = parse_html_cell(right_cell) if ul_in_right else (
                    right_cell.get_text(strip=True) if right_cell else None
                )
                data[key] = value
    return data


class ParsedHTMLSummary(BaseModel):
    structures: list[dict]
    metadata: dict


def preprocess_soup(soup: BeautifulSoup) -> BeautifulSoup:
    # Remove all div tags containing a text node with "Copy as JSON"
    for div in soup.find_all('div'):
        if div.string and div.string.strip() == "Copy as JSON":
            div.decompose()
    return soup


def parse_html_summary(html: str) -> ParsedHTMLSummary:
    soup = BeautifulSoup(html, 'html.parser')

    soup = preprocess_soup(soup)

    content_table = soup.find('table', class_='content', recursive=True)
    metadata_table = soup.find('table', class_='metadata', recursive=True)

    content_parsed = parse_content_table(content_table) if content_table else []
    metadata = parse_metadata_table(metadata_table) if metadata_table else {}

    return ParsedHTMLSummary(
        structures=content_parsed,
        metadata=metadata
    )


def parse_summary_by_id(entry_id: int, retry_flag: bool = False):
    entry = db.execute_query(
        """
        SELECT id, summary_html
        FROM archive_session
        WHERE id = %(entry_id)s
        """,
        {
            "entry_id": entry_id
        },
        return_type="single_row"
    )
    if entry is None:
        print("Entry not found for id", entry_id)
        return
    entry_id = entry['id']
    html_summary = entry['summary_html']
    if not html_summary:
        if not retry_flag:
            print("item not downloaded yet, downloading and re-running parser")
            download_summary_by_id(entry_id)
            parse_summary_by_id(entry_id)
            return
        else:
            print("parsing failure: even after attempting to download the item, no summary html is available.")
            return
    try:
        print(f"Parsing HTML summary for entry {entry_id}...")
        parsed_summary = parse_html_summary(html_summary)
        db.execute_query(
            """
            UPDATE archive_session
            SET structures          = %(structures)s,
                metadata            = %(metadata)s,
                archiving_timestamp = %(timestamp)s
            WHERE id = %(id)s
            """,
            {
                "id": entry_id,
                "structures": json.dumps(parsed_summary.structures, ensure_ascii=False),
                "metadata": json.dumps(parsed_summary.metadata, ensure_ascii=False),
                "timestamp": parsed_summary.metadata.get("_processed_at", None),
            },
            return_type="none"
        )
        print(f"Successfully parsed and updated entry {entry_id}.")
    except Exception as e:
        db.execute_query(
            "UPDATE archive_session SET structures = %(summary_parsed)s WHERE id = %(id)s",
            {"id": entry_id, "summary_parsed": f"Error parsing entry {entry_id}: {e}"},
            return_type="none"
        )
        traceback.print_exc()


if __name__ == '__main__':
    file_path_default = Path(input("input path to html summary: ").strip('"'))  # Replace with your HTML file path
    summary_res = parse_html_summary(get_content_from_file(file_path_default))
    print(summary_res)
