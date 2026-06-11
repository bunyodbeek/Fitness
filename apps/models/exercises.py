import io
import os
import subprocess
import threading

from apps.models.base import CreatedBaseModel
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import (
    CASCADE,
    CharField,
    FileField,
    ForeignKey,
    ImageField,
    IntegerField,
    Model,
    FloatField,
    TextChoices,
    TextField,
)
from django.utils.translation import gettext_lazy as _, get_language
from PIL import Image


class MuscleGroup(TextChoices):
    SHOULDERS  = "shoulders",  _("Shoulders")
    CHEST      = "chest",      _("Chest")
    BICEPS     = "biceps",     _("Biceps")
    FOREARM    = "forearm",    _("Forearm")
    ABS        = "abs",        _("Abs")
    OBLIQUES   = "obliques",   _("Obliques")
    QUADS      = "quads",      _("Quads")
    ADDUCTORS  = "adductors",  _("Adductors")
    ABDUCTORS  = "abductors",  _("Abductors")
    TRAPS      = "traps",      _("Traps")
    TRICEPS    = "triceps",    _("Triceps")
    LATS       = "lats",       _("Lats")
    LOWER_BACK = "lower_back", _("Lower back")
    GLUTES     = "glutes",     _("Glutes")
    HAMSTRINGS = "hamstrings", _("Hamstrings")
    CALVES     = "calves",     _("Calves")
    CARDIO     = "cardio",     _("Cardio")

class Exercise(CreatedBaseModel):
    class WorkoutType(TextChoices):
        GYM = 'gym', _('Gym')
        HOME = 'home', _('Home')

    name = CharField(_("Name"), max_length=200)
    name_ru = CharField(_("Russian Name"), max_length=200, blank=True)
    name_uz = CharField(_("Uzbek Name"), max_length=200, blank=True)
    description = TextField(_("Description"), blank=True)
    description_ru = TextField(_("Russian Description"), blank=True)
    description_uz = TextField(_("Uzbek Description"), blank=True)
    primary_body_part = CharField(_("Muscle Group"), choices=MuscleGroup.choices, default=MuscleGroup.SHOULDERS)
    thumbnail = ImageField(_("Image"), upload_to='exercises/thumbnails/')
    video = FileField(upload_to='exercises/videos/')
    calory = IntegerField(_("Calories"), default=0)
    duration = IntegerField(_("Duration"), default=0)
    recommended_weight = FloatField(_("Recommended weight (W1)"), default=0)
    workout_type = CharField(_("Workout type"), max_length=10, choices=WorkoutType.choices, default=WorkoutType.GYM)

    class Meta:
        ordering = ['id']
        verbose_name = _("Exercise")
        verbose_name_plural = _("Exercises")

    def _convert_video_in_background(self, input_path, final_name):
        try:
            base, _ = os.path.splitext(input_path)
            tmp_output = base + "_conv.mp4"

            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-vcodec", "libx264", "-acodec", "aac",
                tmp_output
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if os.path.exists(tmp_output):
                with open(tmp_output, "rb") as f:
                    storage_name = f"exercises/videos/{final_name}"

                    default_storage.save(storage_name, File(f))

                if os.path.exists(input_path):
                    try:
                        os.remove(input_path)
                    except Exception:
                        pass
                try:
                    os.remove(tmp_output)
                except Exception:
                    pass

                from django.apps import apps
                ExerciseModel = apps.get_model(self._meta.app_label, self.__class__.__name__)

                ExerciseModel.objects.filter(pk=self.pk).update(video=storage_name)

        except Exception as e:

            print("Video convert error:", e)

    def save(self, *args, **kwargs):

        try:
            if self.thumbnail and hasattr(self.thumbnail, 'file.txt') and isinstance(self.thumbnail.file,
                                                                                     InMemoryUploadedFile):
                img = Image.open(self.thumbnail)
                if img.mode != "RGB":
                    img = img.convert("RGB")

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                buffer.seek(0)

                new_name = os.path.splitext(self.thumbnail.name)[0] + ".jpg"
                self.thumbnail = InMemoryUploadedFile(
                    buffer,
                    field_name='thumbnail',
                    name=new_name,
                    content_type='image/jpeg',
                    size=buffer.getbuffer().nbytes,
                    charset=None
                )
        except Exception as e:
            print("Image convert error:", e)

        super().save(*args, **kwargs)

        try:
            if self.video and not self.video.name.lower().endswith(".mp4"):
                input_path = self.video.path

                final_basename = f"exercise_{self.pk}.mp4"

                t = threading.Thread(target=self._convert_video_in_background, args=(input_path, final_basename))
                t.daemon = True
                t.start()
        except Exception as e:
            print("Start video convert error:", e)

    @property
    def display_name(self):
        lang = (get_language() or "en").split("-")[0]
        if lang == "uz" and self.name_uz:
            return self.name_uz
        if lang == "ru" and self.name_ru:
            return self.name_ru
        return self.name

    @property
    def display_description(self):
        lang = (get_language() or "en").split("-")[0]
        if lang == "uz" and self.description_uz:
            return self.description_uz
        if lang == "ru" and self.description_ru:
            return self.description_ru
        return self.description

    def __str__(self):
        return self.name or f"Exercise #{self.pk}"


class ExerciseInstruction(Model):
    exercise = ForeignKey('apps.Exercise', CASCADE, related_name='instructions', verbose_name=_("Exercise"))
    step_number = IntegerField(_("Stem Number"), default=1)
    text = TextField(_("Text"), blank=True)
    text_uz = TextField(_("Uzbek Text"), blank=True)

    class Meta:
        ordering = ['step_number']
        unique_together = ('exercise', 'step_number')
        verbose_name = _("ExerciseInstruction")
        verbose_name_plural = _("ExerciseInstructions")

    def __str__(self):
        return f"{self.exercise.name} - Qadam {self.step_number}"
