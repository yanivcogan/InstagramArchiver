import base64
import os
import traceback
from pathlib import Path
from typing import Optional

import ijson
from pydantic import BaseModel

from extractors.extract_videos import extract_xpv_asset_id


class Photo(BaseModel):
    xpv_asset_id: Optional[int]
    url: str
    filename: str
    extension: str
    data: bytes
    local_files: list[str] = []


def extract_photos(har_path: Path) -> list[Photo]:
    """Extracts photo data from the HAR file using streaming JSON parsing."""
    photos: list[Photo] = []
    image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff', 'heic', 'heif']

    with open(har_path, 'rb') as file:
        for entry in ijson.items(file, 'log.entries.item'):
            try:
                if any(f".{ext}" in entry['request']['url'] for ext in image_extensions) and "text" in entry['response']['content']:
                    url = entry['request']['url']
                    xpv_asset_id = extract_xpv_asset_id(url)
                    base_url = url.split("?")[0]
                    filename = base_url.split("/")[-1]
                    extension = filename.split(".")[-1]
                    photos.append(Photo(
                        xpv_asset_id=xpv_asset_id,
                        url=base_url,
                        filename=filename,
                        extension=extension,
                        data=base64.b64decode(entry['response']['content']['text'])
                    ))
            except Exception as e:
                print(f'Error processing entry: {e}')
                traceback.print_exc()
                continue
    return photos


def save_photos(photos:list[Photo], output_dir:Path, files_to_skip: Optional[dict[str, tuple[str, int]]] = None):
    if files_to_skip is None:
        files_to_skip = dict()
    existing_filenames = [v[0] for v in files_to_skip.values()]

    for photo in photos:
        try:
            file_exists = False
            for existing_file in existing_filenames:
                if f"{photo.filename.split('.')[0]}" in existing_file:
                    print(f"Skipping existing file {existing_file} for photo {photo.filename}.")
                    filepath = (output_dir / existing_file).as_posix()
                    photo.local_files = [filepath]
                    file_exists = True
                    break
            if file_exists:
                continue
            # Create the output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            # Save the photo data to a file
            file_path = output_dir / f"{photo.filename}.{photo.extension}"
            with open(file_path, 'wb') as file:
                file.write(photo.data)
            filepath = file_path.as_posix()
            photo.local_files = [filepath]
            print(f"Saved {file_path}")
        except Exception as e:
            print(f"Error saving photo {photo.filename}: {e}")
            traceback.print_exc()
    return photos


def photos_from_har(har_path:Path, output_dir:Path=Path('../temp_video_segments'), reextract_existing_photos:bool=True) -> list[Photo]:
    # Existing files in the output directory
    existing_files_name_size_tuples = []
    if output_dir.exists():
        existing_files_name_size_tuples =  [
            (file.name, file.stat().st_size) for file in output_dir.iterdir() if file.is_file()
        ]

    largest_version_of_files: dict[str, tuple[str, int]] = dict()

    for file_name, file_size in existing_files_name_size_tuples:
        print(f"Extracting {file_name}...")
        try:
            cleaned_file_name = file_name.split(".")[0]
        except IndexError:
            cleaned_file_name = file_name
        if cleaned_file_name not in largest_version_of_files or file_size > \
                largest_version_of_files[cleaned_file_name][1]:
            largest_version_of_files[cleaned_file_name] = (file_name, file_size)

    photos = extract_photos(har_path)
    if not photos:
        print("No photos found in the HAR file.")
        return []

    files_to_skip = largest_version_of_files if not reextract_existing_photos else dict()

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    # Save the video segments as temporary files
    return save_photos(photos, output_dir, files_to_skip=files_to_skip)


if __name__ == '__main__':
    # Provide the path to your .har file and desired output folder
    har_file = input("Input path to HAR file")  # Replace with your actual HAR file

    photos_from_har(Path(har_file))
