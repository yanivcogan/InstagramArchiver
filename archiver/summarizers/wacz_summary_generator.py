import sys
from pathlib import Path

from archiver.summarizers.entities_summary_generator import summarize_nested_entities
from extractors.structures_from_wacz import scan_wacz
from extractors.structures_to_entities import har_data_to_entities, nest_entities_from_archive_session


def generate_wacz_summary(wacz_path: Path, output_dir: Path, metadata: dict = None) -> Path:
    """
    Extract entities from a WACZ archive and write entities_summary.html to output_dir.
    Media files are saved under output_dir/videos/ and output_dir/photos/.
    Returns the path to the generated HTML file.
    """
    if metadata is None:
        metadata = {"wacz_file": str(wacz_path)}

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Scanning WACZ: {wacz_path}")
    structures, videos, photos = scan_wacz(wacz_path, output_dir)

    flattened = har_data_to_entities(
        output_dir / wacz_path.name,
        structures, videos, photos,
    )
    print(f"Entities — accounts: {len(flattened.accounts)}, "
          f"posts: {len(flattened.posts)}, media: {len(flattened.media)}")

    nested = nest_entities_from_archive_session(flattened)
    html = summarize_nested_entities(nested, metadata)

    # Replace absolute output_dir paths with relative "." so the HTML is portable
    html = html.replace(output_dir.as_posix(), ".")

    out_path = output_dir / "entities_summary.html"
    out_path.write_text(html, encoding='utf-8')
    print(f"Written: {out_path}")
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run archiver/summarizers/wacz_summary_generator.py <path_to.wacz> [output_dir]")
        sys.exit(1)

    wacz_path = Path(sys.argv[1])
    if not wacz_path.exists():
        print(f"File not found: {wacz_path}")
        sys.exit(1)

    if len(sys.argv) >= 3:
        output_dir = Path(sys.argv[2])
    else:
        output_dir = wacz_path.parent / f"{wacz_path.stem}_summary"

    generate_wacz_summary(wacz_path, output_dir)
