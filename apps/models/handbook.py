# handbooks/models.py
from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator

from apps.models.base import CreatedBaseModel


def unique_slugify(instance, base_value, slug_field="slug", scope_q=None, max_len=250):
    """
    base_value -> slugify
    takror bo'lsa: slug, slug-2, slug-3 ...
    scope_q: slug unique bo'ladigan scope (masalan category ichida)
    """
    base_slug = slugify(base_value)[:max_len] or "item"
    slug = base_slug
    Model = instance.__class__

    i = 2
    while True:
        qs = Model.objects.filter(**{slug_field: slug})
        if scope_q is not None:
            qs = qs.filter(scope_q)
        if instance.pk:
            qs = qs.exclude(pk=instance.pk)

        if not qs.exists():
            return slug

        suffix = f"-{i}"
        slug = (base_slug[: max_len - len(suffix)] + suffix)
        i += 1


class HandbookCategory(CreatedBaseModel):
    title = models.CharField(max_length=200, verbose_name=_("Kategoriya nomi"))
    title_uz = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Title (UZ)"))
    title_ru = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Title (RU)"))
    title_en = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Title (EN)"))


    slug = models.SlugField(max_length=250, unique=True, blank=True)
    description = models.TextField(verbose_name=_("Tavsif"), blank=True, null=True)
    description_uz = models.TextField(blank=True, null=True, verbose_name=_("Description (UZ)"))
    description_ru = models.TextField(blank=True, null=True, verbose_name=_("Description (RU)"))


    cover_image = models.ImageField(
        upload_to='handbook/categories/',
        verbose_name=_("Asosiy rasm"),
        blank=True, null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
    )

    icon = models.ImageField(
        upload_to='handbook/categories/icons/',
        verbose_name=_("Ikona"),
        blank=True, null=True
    )

    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'title']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.title, max_len=250)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class HandbookSubCategory(CreatedBaseModel):
    category = models.ForeignKey(
        'apps.HandbookCategory',
        on_delete=models.CASCADE,
        related_name='subcategories'
    )

    title = models.CharField(max_length=200, verbose_name=_("Sub-kategoriya nomi"))
    title_uz = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Title (UZ)"))
    title_ru = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Title (RU)"))
    title_en = models.CharField(max_length=200, blank=True, null=True, verbose_name=_("Title (EN)"))

    slug = models.SlugField(max_length=250, blank=True)

    description = models.TextField(blank=True, null=True)
    description_uz = models.TextField(blank=True, null=True, verbose_name=_("Description (UZ)"))
    description_ru = models.TextField(blank=True, null=True, verbose_name=_("Description (RU)"))

    image = models.ImageField(
        upload_to='handbook/subcategories/',
        blank=True, null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
    )

    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['category', 'order', 'title']
        constraints = [
            models.UniqueConstraint(fields=['category', 'slug'], name='uq_handbook_subcategory_slug_per_category')
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            scope = Q(category_id=self.category_id)
            self.slug = unique_slugify(self, self.title, scope_q=scope, max_len=250)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category.title} - {self.title}"


class HandbookItem(CreatedBaseModel):
    subcategory = models.ForeignKey(
        'apps.HandbookSubCategory',
        on_delete=models.CASCADE,
        related_name='items'
    )

    title = models.CharField(max_length=300, verbose_name=_("Nomi"))
    title_uz = models.CharField(max_length=300, blank=True, null=True, verbose_name=_("Title (UZ)"))
    title_ru = models.CharField(max_length=300, blank=True, null=True, verbose_name=_("Title (RU)"))
    title_en = models.CharField(max_length=300, blank=True, null=True, verbose_name=_("Title (EN)"))

    slug = models.SlugField(max_length=350, blank=True)

    short_description = models.TextField(max_length=500, blank=True, null=True)
    short_description_uz = models.TextField(max_length=500, blank=True, null=True, verbose_name=_("Short description (UZ)"))
    short_description_ru = models.TextField(max_length=500, blank=True, null=True, verbose_name=_("Short description (RU)"))
    short_description_en = models.TextField(max_length=500, blank=True, null=True, verbose_name=_("Short description (EN)"))

    description = models.TextField(help_text=_("HTML bo'lishi mumkin"))
    description_uz = models.TextField(blank=True, null=True, verbose_name=_("Description (UZ)"))
    description_ru = models.TextField(blank=True, null=True, verbose_name=_("Description (RU)"))

    main_image = models.ImageField(
        upload_to='handbook/items/',
        blank=True, null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])],
    )

    additional_info = models.JSONField(blank=True, null=True)
    video = models.FileField(
        upload_to='handbook/items/videos/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['mp4', 'mov', 'webm', 'm4v'])],
    )

    tags = models.CharField(max_length=500, blank=True, null=True)

    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    view_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['subcategory', 'order', 'title']
        constraints = [
            models.UniqueConstraint(fields=['subcategory', 'slug'], name='uq_handbook_item_slug_per_subcategory')
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            scope = Q(subcategory_id=self.subcategory_id)
            self.slug = unique_slugify(self, self.title, scope_q=scope, max_len=350)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.subcategory.title} - {self.title}"
