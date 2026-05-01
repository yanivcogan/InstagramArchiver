import sys
from pathlib import Path

from archiver.summarizers.har_summary_generator import summarize_nested_entities
from extractors.structures_from_wacz import scan_wacz
from extractors.structures_to_entities import har_data_to_entities, nest_entities_from_archive_session


def generate_wacz_summary(archive_path: Path, metadata: dict = None) -> Path:
    """
    Extract entities from a WACZ archive and write entities_summary.html to output_dir.
    Media files are saved under output_dir/videos/ and output_dir/photos/.
    Returns the path to the generated HTML file.
    """
    if metadata is None:
        metadata = {"wacz_file": str(archive_path)}

    archive_dir = archive_path.parent

    print(f"Scanning WACZ: {archive_path}")
    structures, videos, photos = scan_wacz(archive_path, archive_dir)

    flattened = har_data_to_entities(
        archive_path,
        structures, videos, photos,
    )
    print(f"Entities — accounts: {len(flattened.accounts)}, "
          f"posts: {len(flattened.posts)}, media: {len(flattened.media)}")

    nested = nest_entities_from_archive_session(flattened)
    html = summarize_nested_entities(nested, metadata)

    # Replace absolute output_dir paths with relative "." so the HTML is portable
    html = html.replace(archive_dir.as_posix(), ".")

    out_path = archive_dir / "entities_summary.html"
    out_path.write_text(html, encoding='utf-8')
    print(f"Written: {out_path}")
    return out_path


if __name__ == "__main__":
    wacz_path = Path(input("Input path to WACZ file: ").strip().strip('"').strip("'"))
    if not wacz_path.exists():
        print(f"File not found: {wacz_path}")
        sys.exit(1)

    generate_wacz_summary(wacz_path)
