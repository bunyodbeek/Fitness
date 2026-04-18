# /var/www/fitness/apps/admin/handbook.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count

from apps.models.handbook import HandbookCategory, HandbookSubCategory, HandbookItem


@admin.register(HandbookCategory)
class HandbookCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "cover_preview", "subcategories_count", "order", "is_active", "created_at")
    list_display_links = ("id", "title")
    list_filter = ("is_active", "created_at")
    search_fields = (
        "title", "title_uz", "title_ru", "title_en",
        "description", "description_uz", "description_ru"
    )
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("order", "is_active")
    readonly_fields = ("created_at", "updated_at", "cover_big_preview")

    fieldsets = (
        ("Main", {"fields": ("title", "slug", "order", "is_active")}),
        ("Titles (multi-language)", {"fields": ("title_uz", "title_ru", "title_en"), "classes": ("collapse",)}),
        ("Descriptions (multi-language)", {"fields": ("description", "description_uz", "description_ru"), "classes": ("collapse",)}),
        ("Images", {"fields": ("cover_image", "cover_big_preview", "icon")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" style="height:40px;border-radius:6px;" />', obj.cover_image.url)
        return "-"

    cover_preview.short_description = "Cover"

    def cover_big_preview(self, obj):
        if obj.cover_image:
            return format_html('<img src="{}" style="max-width:420px;border-radius:10px;" />', obj.cover_image.url)
        return "-"

    cover_big_preview.short_description = "Preview"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_sub_count=Count("subcategories"))

    def subcategories_count(self, obj):
        # annotate bo‘lsa tezroq bo‘ladi
        count = getattr(obj, "_sub_count", None)
        if count is None:
            count = obj.subcategories.count()
        return count

    subcategories_count.short_description = "Subcategories"


@admin.register(HandbookSubCategory)
class HandbookSubCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "category", "image_preview", "items_count", "order", "is_active", "created_at")
    list_display_links = ("id", "title")
    list_filter = ("category", "is_active", "created_at")
    search_fields = (
        "title", "title_uz", "title_ru", "title_en",
        "description", "description_uz", "description_ru",
        "category__title"
    )
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("order", "is_active")
    readonly_fields = ("created_at", "updated_at", "image_big_preview")
    autocomplete_fields = ("category",)

    fieldsets = (
        ("Main", {"fields": ("category", "title", "slug", "order", "is_active")}),
        ("Titles (multi-language)", {"fields": ("title_uz", "title_ru", "title_en"), "classes": ("collapse",)}),
        ("Descriptions (multi-language)", {"fields": ("description", "description_uz", "description_ru"), "classes": ("collapse",)}),
        ("Image", {"fields": ("image", "image_big_preview")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:40px;border-radius:6px;" />', obj.image.url)
        return "-"

    image_preview.short_description = "Image"

    def image_big_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width:420px;border-radius:10px;" />', obj.image.url)
        return "-"

    image_big_preview.short_description = "Preview"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("category").annotate(_items_count=Count("items"))

    def items_count(self, obj):
        count = getattr(obj, "_items_count", None)
        if count is None:
            count = obj.items.count()
        return count

    items_count.short_description = "Items"


@admin.register(HandbookItem)
class HandbookItemAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "subcategory", "category_name", "main_image_preview", "view_count", "is_active", "created_at")
    list_display_links = ("id", "title")
    list_filter = ("subcategory__category", "subcategory", "is_active", "created_at")
    search_fields = (
        "title", "title_uz", "title_ru", "title_en",
        "description", "description_uz", "description_ru",
        "tags"
    )
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_active",)
    readonly_fields = ("created_at", "updated_at", "view_count", "main_image_big_preview")
    autocomplete_fields = ("subcategory",)

    fieldsets = (
        ("Main", {"fields": ("subcategory", "title", "slug", "order", "is_active")}),
        ("Titles (multi-language)", {"fields": ("title_uz", "title_ru", "title_en"), "classes": ("collapse",)}),
        ("Description (multi-language)", {"fields": ("description", "description_uz", "description_ru"), "classes": ("collapse",)}),
        ("Media", {"fields": ("main_image", "main_image_big_preview", "video")}),
        ("Extra", {"fields": ("tags", "additional_info"), "classes": ("collapse",)}),
        ("Stats", {"fields": ("view_count", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def category_name(self, obj):
        return obj.subcategory.category.title

    category_name.short_description = "Category"
    category_name.admin_order_field = "subcategory__category__title"

    def main_image_preview(self, obj):
        if obj.main_image:
            return format_html('<img src="{}" style="height:40px;border-radius:6px;" />', obj.main_image.url)
        return "-"

    main_image_preview.short_description = "Image"

    def main_image_big_preview(self, obj):
        if obj.main_image:
            return format_html('<img src="{}" style="max-width:420px;border-radius:10px;" />', obj.main_image.url)
        return "-"

    main_image_big_preview.short_description = "Preview"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("subcategory", "subcategory__category")
