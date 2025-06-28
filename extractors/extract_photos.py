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
    image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff']

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


def save_photos(photos:list[Photo], output_dir:Path):
    for photo in photos:
        try:
            # Create the output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            # Save the photo data to a file
            file_path = output_dir / f"{photo.filename}.{photo.extension}"
            with open(file_path, 'wb') as file:
                file.write(photo.data)
            photo.local_files = [file_path.as_posix()]
            print(f"Saved {file_path}")
        except Exception as e:
            print(f"Error saving photo {photo.filename}: {e}")
            traceback.print_exc()
    return photos


def photos_from_har(har_path:Path, output_dir:Path=Path('../temp_video_segments')) -> list[Photo]:
    photos = extract_photos(har_path)
    if not photos:
        print("No photos found in the HAR file.")
        return []

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    # Save the video segments as temporary files
    return save_photos(photos, output_dir)


if __name__ == '__main__':
    # Provide the path to your .har file and desired output folder
    har_file = input("Input path to HAR file")  # Replace with your actual HAR file

    photos_from_har(Path(har_file))
