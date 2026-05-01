import openpyxl
from pathlib import Path
from typing import List, Dict, Any

def xlsx_to_dict_list(file_path: Path) -> List[Dict[str, Any]]:
    wb = openpyxl.load_workbook(file_path, read_only=True)
    ws = wb["CombinedSheet"]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = rows[0]
    return [dict(zip(headers, row)) for row in rows[1:]]


if __name__ == "__main__":
    file_path_default = Path("aa_sheets_src/source_data.xlsx")  # Replace with your actual file path
    data = xlsx_to_dict_list(file_path_default)
    for entry in data:
        print(entry)