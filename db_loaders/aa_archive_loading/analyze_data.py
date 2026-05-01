import json
import traceback
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

import db
from download_html_summary import selenium_options, download_summary_by_id
from extract_entities import extract_entities_from_parsed_summary
from parse_html_summary import parse_html_summary, ParsedHTMLSummary, parse_summary_by_id
from reconcile_entities import incorporate_structure_into_db
from xlsx_reader import xlsx_to_dict_list



def register_entries():
    source_table = xlsx_to_dict_list(Path("aa_sheets_src/source_data.xlsx"))
    for xlsx_row in source_table:
        entry_id = xlsx_row['Entry_Number']
        if not entry_id:
            continue
        entry_id = f"AA_{entry_id}"
        url = xlsx_row.get('Link')
        if "instagram.com" not in url:
            continue
        existing_entry = db.execute_query(
            "SELECT * FROM archive_session WHERE external_id = %(id)s",
            {"id": entry_id},
            return_type="single_row"
        )
        if existing_entry:
            print(f"Entry {entry_id} already exists in the database. Skipping.")
            continue
        db.execute_query(
            """INSERT INTO archive_session 
               (external_id, archived_url, archive_location, notes, source_type) 
               VALUES (%(external_id)s, %(archived_url)s, %(archive_location)s, %(notes)s, 0)""",
            {
                "external_id": entry_id,
                "archived_url": url,
                "notes": xlsx_row.get('NOTES'),
                "archive_location": xlsx_row.get('Archive_location')
            },
            return_type="id"
        )
        print(f"Registered entry {entry_id}.")
    print("registered all entries from source_data.xlsx.")


def download_html_summaries():
    entries = db.execute_query(
        """
        SELECT id, archive_location 
        FROM archive_session 
        WHERE summary_html IS NULL AND source_type = 0
        """,
        {},
        return_type="rows"
    )
    driver = webdriver.Chrome(options=selenium_options)
    for entry in entries:
        download_summary_by_id(entry['id'], driver)
    print("Downloaded all HTML summaries.")

def parse_html_summaries():
    while True:
        entry = db.execute_query(
            """
            SELECT id, summary_html 
            FROM archive_session 
            WHERE 
                structures IS NULL AND 
                summary_html IS NOT NULL AND 
                source_type = 0 
            LIMIT 1
            """,
            {},
            return_type="single_row"
        )
        if entry is None:
            print("Parsed all HTML summaries.")
            return
        parse_summary_by_id(entry['id'])


def extract_entities():
    while True:
        entry = db.execute_query(
            """
            SELECT 
                   id, archived_url, archive_location, structures, metadata, notes 
            FROM archive_session 
            WHERE 
                structures IS NOT NULL AND 
                extracted_entities = 0 AND 
                source_type = 0 
            LIMIT 1
            """,
            {},
            return_type="single_row"
        )
        if entry is None:
            print("Extracted entities from all entries.")
            return
        entry_id = entry['id']
        try:
            print("Extracting entities for entry", entry_id)
            structures = json.loads(entry['structures'])
            metadata = json.loads(entry['metadata'])
            parsed_summary = ParsedHTMLSummary(metadata=metadata, structures=structures)
            entities = extract_entities_from_parsed_summary(entry['archived_url'], entry_id, parsed_summary, entry['notes'])
            incorporate_structure_into_db(entities)
            db.execute_query("UPDATE archive_session SET extracted_entities = 1, extraction_error = NULL WHERE id = %(id)s", {"id": entry_id}, return_type="none")
        except Exception as e:
            print(f"Error extracting entities for {entry_id} ({entry['archive_location']}): {e}")
            db.execute_query("UPDATE archive_session SET extracted_entities = 2, extraction_error = %(extraction_error)s WHERE id = %(id)s", {"id": entry_id, "extraction_error": str(e)}, return_type="none")
            traceback.print_exc()


if __name__ == "__main__":
    # register_entries()
    # download_html_summaries()
    parse_html_summaries()
    # extract_entities()
    # export_all()