"""Server-side validation + thumbnail generation for Help-chat image uploads.

The client MIME type is NOT trusted — the bytes are opened and verified with
Pillow, and only genuine JPEG/PNG/WEBP/GIF files under the size cap are accepted.
Returns Django file objects ready to assign to the model's ImageFields."""
import io
import uuid

from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils.translation import gettext as _

MAX_BYTES = 5 * 1024 * 1024          # 5 MB
THUMB_SIZE = (480, 480)              # bounding box, aspect preserved
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
_EXT = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}


def process_chat_image(uploaded):
    """Validate an uploaded image and build (original, thumbnail) files.

    Returns ``(image_content, image_name, thumb_content, thumb_name)`` or raises
    ``ValidationError`` with a translated, user-safe message."""
    if uploaded.size > MAX_BYTES:
        raise ValidationError(_("Image is too large (max 5 MB)."))

    data = uploaded.read()

    # Verify the file really is an image of an allowed type (don't trust MIME).
    try:
        probe = Image.open(io.BytesIO(data))
        probe.verify()
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError(_("Unsupported or invalid image."))

    fmt = (probe.format or "").upper()
    if fmt not in ALLOWED_FORMATS:
        raise ValidationError(_("Only JPEG, PNG, WEBP or GIF images are allowed."))

    # Reopen for processing (verify() leaves the image unusable).
    img = Image.open(io.BytesIO(data))
    thumb = img.convert("RGBA") if img.mode in ("P", "LA") else img.copy()
    thumb.thumbnail(THUMB_SIZE)

    buf = io.BytesIO()
    if thumb.mode in ("RGBA", "LA", "P"):
        thumb.save(buf, format="PNG")
        thumb_ext = "png"
    else:
        thumb.convert("RGB").save(buf, format="JPEG", quality=85)
        thumb_ext = "jpg"

    base = uuid.uuid4().hex
    return (
        ContentFile(data), f"{base}.{_EXT[fmt]}",
        ContentFile(buf.getvalue()), f"{base}_thumb.{thumb_ext}",
    )
