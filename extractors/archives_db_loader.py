import json
import traceback
from pathlib import Path

import db
from extractors.structures_to_entities import extract_entities_from_har
from extractors.reconcile_entities import incorporate_structure_into_db
from utils import ROOT_DIR


def register_archives():
    root_archives = Path(ROOT_DIR) / "archives"
    archive_dirs = [d for d in root_archives.iterdir() if d.is_dir()]
    for archive_dir in archive_dirs:
        archive_name = archive_dir.name
        archiving_session = f"har-{archive_name}"
        har_path = archive_dir / "archive.har"
        if not har_path.exists():
            print(f"Archive {archive_name} does not contain a HAR file, skipping.")
            continue
        metadata_path = archive_dir / "metadata.json"
        metadata = dict()
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.loads(f.read())
        except Exception:
            print(f"Metadata file {metadata_path} is not valid JSON or does not exist, skipping.")
            continue
        existing_entry = db.execute_query(
            "SELECT * FROM sheet_entry WHERE id = %(id)s",
            {"id": archiving_session},
            return_type="single_row"
        )
        if existing_entry:
            print(f"Entry {archiving_session} already exists in the database. Skipping.")
            continue
        db.execute_query(
            """INSERT INTO sheet_entry
                   (id, archived_url, archive_location, notes, source_type)
               VALUES (%(id)s, %(archived_url)s, %(archive_location)s, %(notes)s, 1)""",
            {
                "id": archiving_session,
                "archived_url": metadata.get('target_url', ''),
                "notes": metadata.get('notes', ''),
                "archive_location": f'local_archive_har/{archive_name}'
            },
            return_type="id"
        )
        print(f"Registered archive {archive_name}.")


def extract_entities():
    while True:
        entry = db.execute_query(
            "SELECT id FROM sheet_entry WHERE extracted_entities = 0 AND source_type = 1 LIMIT 1",
            {},
            return_type="single_row"
        )
        if entry is None:
            print("Extracted entities from all entries.")
            return
        entry_id = entry['id']
        try:
            print("Extracting entities for entry", entry_id)
            archive_name = entry_id.split("har-")[1]
            har_path = Path(ROOT_DIR) / "archives" / archive_name / "archive.har"
            entities = extract_entities_from_har(har_path, entry_id)
            incorporate_structure_into_db(entities)
            db.execute_query("UPDATE sheet_entry SET extracted_entities = 1, extraction_error = NULL WHERE id = %(id)s", {"id": entry_id}, return_type="none")
        except Exception as e:
            print(f"Error extracting entities for {entry_id}: {e}")
            db.execute_query("UPDATE sheet_entry SET extracted_entities = 2, extraction_error = %(extraction_error)s WHERE id = %(id)s", {"id": entry_id, "extraction_error": str(e)}, return_type="none")
            traceback.print_exc()


if __name__ == "__main__":
    #register_archives()
    extract_entities()