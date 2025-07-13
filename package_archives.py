from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from utils import ROOT_DIR
import os

BATCH_SIZE_LIMIT = 5000 * 1024 * 1024


def get_size_bytes(start_path: Path):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)

    return total_size


def package_archives():
    root_archives = Path(ROOT_DIR) / "archives"
    archive_dirs = [d for d in root_archives.iterdir() if d.is_dir()]

    root_zips = Path(ROOT_DIR) / "packaged_archives"
    packaged_list_path = root_zips / "packaged_list.txt"
    if packaged_list_path.exists():
        with packaged_list_path.open("r", encoding="utf-8") as f:
            already_packaged = set(line.strip() for line in f if line.strip())
    else:
        already_packaged = set()
    batch_counter_path = root_zips / "batch_counter.txt"
    if batch_counter_path.exists():
        with batch_counter_path.open("r", encoding="utf-8") as f:
            batch_counter = int(f.readline().strip())
    else:
        batch_counter = 0

    to_archive: list[Path] = [a for a in archive_dirs if a.name not in already_packaged]

    current_batch: list[Path] = []
    current_batch_size = 0
    for i in range(len(to_archive)):
        a = to_archive[i]
        print(f"processing {a.name}")
        a_size = get_size_bytes(a)
        print(f"size of {a.name} = {a_size}")
        current_batch.append(a)
        current_batch_size += a_size
        if current_batch_size >= BATCH_SIZE_LIMIT or i == (len(to_archive) - 1):
            print("starting new zip batch")
            with ZipFile(root_zips / f'batch_{batch_counter}.zip', 'w', compresslevel=9, compression=ZIP_DEFLATED) as myzip:
                for p in current_batch:
                    print(f"adding {p.name}")
                    for root, dirs, files in os.walk(p):
                        for file in files:
                            file_path = os.path.join(root, file)
                            # Calculate the relative path within the zip archive
                            arcname = os.path.relpath(file_path, p)
                            myzip.write(file_path, arcname=os.path.join(p.name, arcname))
            batch_counter += 1
            with batch_counter_path.open("w", encoding="utf-8") as f:
                f.write(str(batch_counter))
            with packaged_list_path.open("a", encoding="utf-8") as f:
                f.writelines([p.name for p in current_batch])
            current_batch = []
            current_batch_size = 0


if __name__ == "__main__":
    package_archives()