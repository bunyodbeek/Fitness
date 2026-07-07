"""WebP conversion helpers for cover images (programs page LCP).

Plain Pillow — no extra dependencies. Two variants are produced from one source:

  • hero  — up to ~1000px wide, used as the recommended-program LCP cover.
  • thumb — up to ~400px wide, saved next to the hero as ``<stem>_thumb.webp``
            and used for the small grid/list cards.

Aspect ratio is preserved and images are never upscaled. Used by both the
``convert_images_to_webp`` backfill command and ``Program.save()`` so new uploads
never regress.
"""

import os
from io import BytesIO

from PIL import Image, ImageOps
from django.core.files.base import ContentFile

HERO_MAX_W = 1000
THUMB_MAX_W = 400
QUALITY = 80
THUMB_SUFFIX = "_thumb"
CONVERTIBLE_EXTS = {".png", ".jpg", ".jpeg"}

# Every static PNG/JPEG cover ImageField we optimise to WebP. Consumed by both the
# ``convert_images_to_webp`` backfill (default targets) and the upload-time signal
# in ``apps/signals.py``. FileFields (e.g. exercise/handbook videos) are excluded.
WEBP_TARGETS = [
	("apps", "Program", "image"),
	("apps", "Exercise", "thumbnail"),
	("apps", "HandbookCategory", "cover_image"),
	("apps", "HandbookCategory", "icon"),
	("apps", "HandbookSubCategory", "image"),
	("apps", "HandbookItem", "main_image"),
]


def ext_of(name: str) -> str:
    return os.path.splitext(name or "")[1].lower()


def is_convertible(name: str) -> bool:
    """True for a PNG/JPEG we should convert (skips webp/gif/anything else)."""
    return ext_of(name) in CONVERTIBLE_EXTS


def thumb_name_for(name: str) -> str:
    """``programs/x.webp`` -> ``programs/x_thumb.webp``."""
    stem, _ = os.path.splitext(name)
    return f"{stem}{THUMB_SUFFIX}.webp"


def _prepare(img: Image.Image, max_w: int) -> Image.Image:
    """Respect EXIF orientation, downscale to ``max_w`` (never up), pick a WebP-safe mode."""
    img = ImageOps.exif_transpose(img)
    if img.width > max_w:
        ratio = max_w / float(img.width)
        img = img.resize((max_w, max(1, round(img.height * ratio))), Image.LANCZOS)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")   # keep transparency (WebP supports alpha)
    else:
        img = img.convert("RGB")
    return img


def encode_webp(img: Image.Image, max_w: int, *, quality: int = QUALITY, method: int = 6) -> bytes:
    out = BytesIO()
    _prepare(img, max_w).save(out, format="WEBP", quality=quality, method=method)
    return out.getvalue()


def _open(fieldfile) -> Image.Image:
    fieldfile.open("rb")
    try:
        img = Image.open(fieldfile)
        img.load()
        return img
    finally:
        fieldfile.close()


def replace_fieldfile_with_hero_webp(fieldfile, *, max_w: int = HERO_MAX_W, quality: int = QUALITY,
                                     method: int = 6) -> None:
    """Rewrite an ImageField's file to the hero WebP **in memory** (``save=False``).

    Only updates the field's ``name``/content — the caller is responsible for
    persisting the model. No-op if the file is already a ``.webp``.
    """
    if not fieldfile or ext_of(fieldfile.name) == ".webp":
        return
    data = encode_webp(_open(fieldfile), max_w, quality=quality, method=method)
    # Pass only the basename: FieldFile.save() runs it through generate_filename(),
    # which re-applies the field's upload_to. Passing the full path would double-nest
    # it (e.g. programs/programs/x.webp).
    base = os.path.splitext(os.path.basename(fieldfile.name))[0]
    fieldfile.save(f"{base}.webp", ContentFile(data), save=False)


def ensure_thumb(fieldfile, *, max_w: int = THUMB_MAX_W, quality: int = QUALITY, method: int = 6) -> str | None:
    """Write the ``<stem>_thumb.webp`` sibling to storage if it's missing.

    Returns the thumb name if it was created, else ``None`` (already existed / no image).
    Idempotent.
    """
    if not fieldfile or not fieldfile.name:
        return None
    storage = fieldfile.storage
    thumb = thumb_name_for(fieldfile.name)
    if storage.exists(thumb):
        return None
    data = encode_webp(_open(fieldfile), max_w, quality=quality, method=method)
    return storage.save(thumb, ContentFile(data))
