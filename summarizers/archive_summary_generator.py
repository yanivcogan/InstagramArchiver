import json

from extractors.extract_photos import Photo
from extractors.extract_videos import Video
from extractors.structures_extraction import StructureType


def generate_summary(structures: list[StructureType], photos: list[Photo], videos: list[Video], metadata: dict) -> str:
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Instagram Archive Summary</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1, h2, h3 { color: #333; }
        .container { display: flex; flex-wrap: wrap; }
        .media-item { margin: 10px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; width: 350px; }
        .media-item img { max-width: 100%; height: auto; }
        .media-item video { max-width: 100%; height: auto; }
        .metadata { margin-top: 10px; font-size: 0.9em; }
        .metadata p { margin: 5px 0; }
        .structure-item { margin-bottom: 20px; padding: 15px; border: 1px solid #eee; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Instagram Archive Summary</h1>
    <h3>Session Metadata</h3>
    <div>""" + json.dumps(metadata, default=str) + """</div>
    <h2>Structures</h2>
    <div class="container">"""

    # Add structures
    for i, structure in enumerate(structures):
        html += f"""
        <div class="structure-item">
            <h3>Structure {i + 1}</h3>
            <pre>{str(structure.__class__.__name__)}</pre>
            <div class="metadata">
                {_format_structure_data(structure)}
            </div>
        </div>"""

    html += """
    </div>
    
    <h2>Photos ({0})</h2>
    <div class="container">""".format(len(photos))

    # Add photos
    # Add photos
    for photo in photos:
        if photo.local_files:  # Check if there are any local files
            photo_path = photo.local_files[0]  # Use first file path
            html += f"""
            <div class="media-item">
                <img src="{photo_path}" alt="Instagram Photo">
                <div class="metadata">
                    <p><strong>URL:</strong> {photo.url}</p>
                    <p><strong>Filename:</strong> {photo.filename}</p>
                    <p><strong>Extension:</strong> {photo.extension}</p>
                    <p><strong>Asset ID:</strong> {photo.xpv_asset_id if photo.xpv_asset_id else 'N/A'}</p>
                    <p><strong>Size:</strong> {len(photo.data)} bytes</p>
                </div>
            </div>"""

    html += """
    </div>
    
    <h2>Videos ({0})</h2>
    <div class="container">""".format(len(videos))

    # Add videos
    for video in videos:
            # Use video.location if available, otherwise the first local file
            video_path = video.location if video.location else (video.local_files[0] if video.local_files else "")
            html += f"""
            <div class="media-item">
                <video controls>
                    <source src="{video_path}" type="video/mp4">
                    Your browser does not support the video tag.
                </video>
                <div class="metadata">
                    <p><strong>Asset ID:</strong> {video.xpv_asset_id}</p>
                    <p><strong>Tracks:</strong> {len(video.tracks)} ({', '.join(video.tracks.keys())})</p>
                    <p><strong>Local Files:</strong> {len(video.local_files)}</p>
                    <p><strong>Main File:</strong> {video.location if video.location else 'N/A'}</p>
                </div>
            </div>"""

    html += """
    </div>
</body>
</html>"""
    return html


def _format_structure_data(structure: StructureType) -> str:
    """Helper function to format structure data based on its type"""
    result = "<ul>"

    if hasattr(structure, "caption"):
        result += f"<li><strong>Caption:</strong> {structure.caption}</li>"
    if hasattr(structure, "owner"):
        result += f"<li><strong>Owner:</strong> {structure.owner}</li>"
    if hasattr(structure, "post_id"):
        result += f"<li><strong>Post ID:</strong> {structure.post_id}</li>"
    if hasattr(structure, "timestamp"):
        result += f"<li><strong>Timestamp:</strong> {structure.timestamp}</li>"
    if hasattr(structure, "likes"):
        result += f"<li><strong>Likes:</strong> {structure.likes}</li>"
    if hasattr(structure, "comments"):
        result += f"<li><strong>Comments:</strong> {structure.comments}</li>"
    if hasattr(structure, "url"):
        result += f"<li><strong>URL:</strong> {structure.url}</li>"
    if hasattr(structure, "title"):
        result += f"<li><strong>Title:</strong> {structure.title}</li>"

    result += "</ul>"
    return result
