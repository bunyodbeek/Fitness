"""One-off backfill: convert existing PNG/JPEG cover images to WebP.

For every targeted ImageField it writes a hero (~1000px) WebP in place, a thumb
(~400px) sibling, repoints the DB field to the WebP, and moves the original into
an ``_originals/`` backup folder (never deleted). Idempotent — re-running skips
files that are already WebP (only filling in a missing thumb).

    python manage.py convert_images_to_webp                 # Program.image
    python manage.py convert_images_to_webp --dry-run       # report only, no writes
    python manage.py convert_images_to_webp --models apps.Exercise.thumbnail
"""

import os

from django.apps import apps as django_apps
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from apps.services import image_optim

DEFAULT_TARGETS = image_optim.WEBP_TARGETS
BACKUP_DIR = "_originals"


def _fmt(n):
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1048576:.2f} MB"


class Command(BaseCommand):
    help = "Convert existing PNG/JPEG cover ImageFields to WebP (hero + thumb). Idempotent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--models", nargs="*", default=[], metavar="app.Model.field",
            help="Extra ImageFields to convert (default: apps.Program.image).",
        )
        parser.add_argument("--dry-run", action="store_true",
                            help="Report projected savings without writing anything.")
        parser.add_argument("--quality", type=int, default=image_optim.QUALITY)

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        quality = opts["quality"]

        targets = list(DEFAULT_TARGETS)
        for spec in opts["models"]:
            parts = spec.split(".")
            if len(parts) < 3:
                raise CommandError(f"Bad --models spec {spec!r}; use app.Model.field")
            targets.append((".".join(parts[:-2]), parts[-2], parts[-1]))

        if dry:
            self.stdout.write(self.style.WARNING("DRY RUN — no files will be written\n"))

        grand_old = grand_new = 0
        converted = skipped = errors = 0

        for app_label, model_name, field in targets:
            try:
                model = django_apps.get_model(app_label, model_name)
            except LookupError:
                raise CommandError(f"Unknown model {app_label}.{model_name}")

            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n{app_label}.{model_name}.{field}"))

            qs = model.objects.exclude(**{field: ""}).exclude(**{f"{field}__isnull": True})
            for obj in qs.iterator():
                ff = getattr(obj, field)
                if not ff or not ff.name:
                    continue
                try:
                    result = self._process(obj, field, ff, dry=dry, quality=quality)
                except Exception as exc:  # keep going on a single bad file
                    errors += 1
                    self.stdout.write(self.style.ERROR(f"  ✗ {ff.name}: {exc}"))
                    continue

                if result is None:
                    skipped += 1
                    continue
                converted += 1
                grand_old += result["old"]
                grand_new += result["new"]
                pct = (1 - result["new"] / result["old"]) * 100 if result["old"] else 0
                self.stdout.write(
                    f"  ✓ {result['old_name']}  {_fmt(result['old'])} "
                    f"→ {_fmt(result['new'])} (hero+thumb, -{pct:.0f}%)"
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Converted {converted}, skipped {skipped}, errors {errors}"))
        if grand_old:
            pct = (1 - grand_new / grand_old) * 100
            verb = "would drop" if dry else "dropped"
            self.stdout.write(self.style.SUCCESS(
                f"Total {verb}: {_fmt(grand_old)} → {_fmt(grand_new)} (-{pct:.0f}%)"))

    def _process(self, obj, field, ff, *, dry, quality):
        """Convert one ImageField. Returns a size dict, or None if skipped."""
        storage = ff.storage
        name = ff.name

        # Already WebP → just make sure the thumb exists, then skip.
        if image_optim.ext_of(name) == ".webp":
            if not dry:
                image_optim.ensure_thumb(ff, quality=quality)
            return None
        if not image_optim.is_convertible(name):
            return None  # gif / other — out of scope

        old_size = storage.size(name)

        if dry:
            # Encode in memory to report a realistic projected size (no writes).
            img = image_optim._open(ff)
            hero = len(image_optim.encode_webp(img, image_optim.HERO_MAX_W, quality=quality))
            thumb = len(image_optim.encode_webp(img, image_optim.THUMB_MAX_W, quality=quality))
            return {"old_name": name, "old": old_size, "new": hero + thumb}

        # Read the original bytes before we repoint/overwrite anything.
        ff.open("rb")
        try:
            original_bytes = ff.read()
        finally:
            ff.close()

        # Trigger the same conversion path used at upload time: hero WebP + thumb.
        image_optim.replace_fieldfile_with_hero_webp(ff, quality=quality)
        obj.save(update_fields=[field])
        image_optim.ensure_thumb(ff, quality=quality)

        # Back up the now-orphaned original, then remove it from its old location.
        backup_name = os.path.join(os.path.dirname(name), BACKUP_DIR, os.path.basename(name))
        if not storage.exists(backup_name):
            storage.save(backup_name, ContentFile(original_bytes))
        if storage.exists(name):
            storage.delete(name)

        new_size = storage.size(ff.name)
        thumb_name = image_optim.thumb_name_for(ff.name)
        if storage.exists(thumb_name):
            new_size += storage.size(thumb_name)
        return {"old_name": name, "old": old_size, "new": new_size}
