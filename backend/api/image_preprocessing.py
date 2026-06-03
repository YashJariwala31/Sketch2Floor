from pathlib import Path

from django.conf import settings
from PIL import Image, ImageOps


def normalize_uploaded_image(job, max_side: int | None = None) -> bool:
    image_field = getattr(job, 'original_image', None)
    if not image_field:
        return False

    try:
        image_path = Path(image_field.path)
    except (NotImplementedError, ValueError):
        return False

    if not image_path.exists():
        return False

    max_side = int(max_side or getattr(settings, 'PIPELINE_MAX_IMAGE_SIDE', 1800))
    if max_side <= 0:
        return False

    original_path = image_path

    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img)
        width, height = img.size
        if max(width, height) <= max_side:
            return False

        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')

        if image_path.suffix.lower() not in {'.jpg', '.jpeg'}:
            image_path = image_path.with_suffix('.jpg')
            image_field.name = str(Path(image_field.name).with_suffix('.jpg')).replace('\\', '/')

        image_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(image_path, format='JPEG', quality=90, optimize=True)
        processed_size = [img.width, img.height]

    if original_path != image_path and original_path.exists():
        original_path.unlink(missing_ok=True)

    job.metadata = {
        **(job.metadata or {}),
        'normalized_image': {
            'max_side': max_side,
            'original_size': [width, height],
            'processed_size': processed_size,
        },
    }
    job.save(update_fields=['original_image', 'metadata', 'updated_at'])
    return True
