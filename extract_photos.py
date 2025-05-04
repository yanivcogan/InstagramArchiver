import base64
import json
import os
import subprocess
import traceback
import urllib
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from extract_videos import extract_xpv_asset_id


class Photo(BaseModel):
    xpv_asset_id: Optional[int]
    url: str
    filename: str
    extension: str
    data: bytes


def extract_photos(har_path:Path) -> list[Photo]:
    """Extracts video segment data from the HAR file."""
    with open(har_path, 'rb') as file:  # Open the file in binary mode
        har_data = json.load(file)

    photos: list[Photo] = []

    image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'tiff']

    # Find the API call to GraphQL and its response
    for entry in har_data['log']['entries']:
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
            print(f"Saved {file_path}")
        except Exception as e:
            print(f"Error saving photo {photo.filename}: {e}")
            traceback.print_exc()
    pass


def photos_from_har(har_path:Path, output_dir:Path=Path('temp_video_segments')):
    photos = extract_photos(har_path)
    if not photos:
        print("No photos found in the HAR file.")
        return

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    # Save the video segments as temporary files
    save_photos(photos, output_dir)


if __name__ == '__main__':
    # Provide the path to your .har file and desired output folder
    har_file = input("Input path to HAR file")  # Replace with your actual HAR file

    photos_from_har(Path(har_file))
