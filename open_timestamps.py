from pathlib import Path
import subprocess
import tempfile

def submit_to_opentimestamps(value: bytes, output_path: Path):
    """
    Submits the given value to OpenTimestamps and stores the resulting .ots file at output_path.
    Requires the opentimestamps-client (`ots`) to be installed and available in PATH.
    """
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(value)
        temp_file.flush()
        temp_file_path = temp_file.name

    ots_output_path = str(output_path)
    try:
        subprocess.run(
            ["ots", "stamp", temp_file_path, "-o", ots_output_path],
            check=True
        )
    finally:
        Path(temp_file_path).unlink()

if __name__ == "__main__":
    submit_to_opentimestamps("test".encode(encoding="utf-8"), Path("C:/Users/yaniv/Documents/projects/InstagramArchiver/temp/stamp.ots"))