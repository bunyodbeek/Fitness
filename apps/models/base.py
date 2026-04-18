import uuid

from django.db.models import DateTimeField, Model, SlugField, UUIDField


class CreatedBaseModel(Model):
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SlugBaseModel(Model):
    slug = SlugField(max_length=255, unique=True, editable=False)

    class Meta:
        abstract = True


class UUIDBaseModel(Model):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True
