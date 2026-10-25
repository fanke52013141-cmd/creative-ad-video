"""Decode media and verify file identity; visual review remains independent."""
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from .contracts import FlowError, require
from .storage import inside, digest


def inspect_image(run, row):
    path = inside(run, row['file'], True)
    require(digest(path) == row['sha256'], 'media file hash mismatch')
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
            width, height, fmt = image.width, image.height, image.format.lower()
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        raise FlowError(f'invalid image {row["file"]}: {exc}') from exc
    require(Path(path).suffix.lower() == '.png' and fmt == 'png', 'media must be a decoded PNG')
    require(width > 0 and height > 0, 'media dimensions must be positive')
    return {'width': width, 'height': height, 'format': fmt}
