import traceback
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver

import db

selenium_options = Options()
selenium_options.add_argument('--headless')

def download_summary_by_id(entry_id: int, driver: Optional[WebDriver] = None) -> None:
    entry = db.execute_query(
        """
        SELECT id, archive_location
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
    html_summary_url = entry['archive_location']
    if not html_summary_url:
        print(f"Entry {entry_id} has no HTML summary URL.")
        return
    try:
        print(f"Downloading HTML summary for entry {entry_id} from {html_summary_url}...")
        if driver is None:
            driver = webdriver.Chrome(options=selenium_options)
        driver.set_page_load_timeout(1000)
        driver.command_executor.set_timeout(1000)
        driver.get(html_summary_url)
        html_summary = driver.page_source
        db.execute_query(
            """UPDATE archive_session
               SET summary_html = %(summary_html)s
               WHERE id = %(id)s""",
            {"id": entry_id, "summary_html": html_summary},
            return_type="none"
        )
        print(f"Successfully downloaded HTML summary for entry {entry_id}.")
    except Exception as e:
        db.execute_query(
            "UPDATE archive_session SET summary_html = %(summary_html)s WHERE id = %(id)s",
            {"id": entry_id, "summary_html": f"Error downloading entry {entry_id}: {e}"},
            return_type="none"
        )
        print(f"Error downloading HTML summary for entry {entry_id}: {e}")
        traceback.print_exc()


if __name__ == '__main__':
    id_to_extract = 29747 or int(input("specify id for extraction: ").strip())
    download_summary_by_id(id_to_extract)
