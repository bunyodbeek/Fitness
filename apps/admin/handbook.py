from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count
from apps.models.handbook import HandbookCategory, HandbookSubCategory, HandbookItem


class HandbookItemInline(admin.StackedInline):
    model = HandbookItem
    extra = 0
    fk_name = 'subcategory'  # ← SubCategory admin uchun
    fields = ('title', 'slug', 'main_image', 'description', 'order', 'is_active')
    prepopulated_fields = {"slug": ("title",)}
    show_change_link = True
    classes = ('collapse',)
class HandbookDirectItemInline(admin.StackedInline):
    model = HandbookItem
    extra = 0
    fk_name = 'category'  # ← Category admin uchun
    fields = ('title', 'slug', 'main_image', 'description', 'order', 'is_active')
    prepopulated_fields = {"slug": ("title",)}
    show_change_link = True
    classes = ('collapse',)
    verbose_name = "Direct Item"
    verbose_name_plural = "Direct Items (subcategorysiz)"
class HandbookSubCategoryInline(admin.StackedInline):
    model = HandbookSubCategory
    extra = 0
    fields = ('title', 'slug', 'image', 'order', 'is_active')
    prepopulated_fields = {"slug": ("title",)}
    show_change_link = True
    inlines = [HandbookItemInline]
    classes = ('collapse',)


@admin.register(HandbookCategory)
class HandbookCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "cover_preview", "subcategories_count", "direct_items_count", "order", "is_active")
    list_display_links = ("id", "title")
    list_filter = ("is_active",)
    search_fields = ("title", "title_uz", "title_ru", "title_en")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("order", "is_active")
    readonly_fields = ("created_at", "updated_at", "cover_big_preview")
    inlines = [HandbookSubCategoryInline, HandbookDirectItemInline]
    
    fieldsets = (
        ("Main", {"fields": ("title", "slug", "order", "is_active")}),
        ("Titles", {"fields": ("title_uz", "title_ru", "title_en"), "classes": ("collapse",)}),
        ("Descriptions", {"fields": ("description", "description_uz", "description_ru"), "classes": ("collapse",)}),
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
        return super().get_queryset(request).annotate(
            _sub_count=Count("subcategories", distinct=True),
            _items_count=Count("direct_items", distinct=True)
        )

    def subcategories_count(self, obj):
        return getattr(obj, "_sub_count", 0)
    subcategories_count.short_description = "Subcategories"

    def direct_items_count(self, obj):
        return getattr(obj, "_items_count", 0)
    direct_items_count.short_description = "Direct Items"


@admin.register(HandbookSubCategory)
class HandbookSubCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "category", "image_preview", "items_count", "order", "is_active")
    list_display_links = ("id", "title")
    list_filter = ("category", "is_active")
    search_fields = ("title", "title_uz", "title_ru", "category__title")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("order", "is_active")
    readonly_fields = ("created_at", "updated_at", "image_big_preview")
    autocomplete_fields = ("category",)
    inlines = [HandbookItemInline]

    fieldsets = (
        ("Main", {"fields": ("category", "title", "slug", "order", "is_active")}),
        ("Titles", {"fields": ("title_uz", "title_ru", "title_en"), "classes": ("collapse",)}),
        ("Descriptions", {"fields": ("description", "description_uz", "description_ru"), "classes": ("collapse",)}),
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
        return super().get_queryset(request).select_related("category").annotate(
            _items_count=Count("items")
        )

    def items_count(self, obj):
        return getattr(obj, "_items_count", 0)
    items_count.short_description = "Items"


@admin.register(HandbookItem)
class HandbookItemAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "get_category", "subcategory", "main_image_preview", "view_count", "is_active")
    list_display_links = ("id", "title")
    list_filter = ("is_active",)
    search_fields = ("title", "title_uz", "title_ru", "tags")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_active",)
    readonly_fields = ("created_at", "updated_at", "view_count", "main_image_big_preview")
    autocomplete_fields = ("subcategory", "category")

    fieldsets = (
        ("Main", {"fields": ("category", "subcategory", "title", "slug", "order", "is_active")}),
        ("Titles", {"fields": ("title_uz", "title_ru", "title_en"), "classes": ("collapse",)}),
        ("Description", {"fields": ("description", "description_uz", "description_ru"), "classes": ("collapse",)}),
        ("Media", {"fields": ("main_image", "main_image_big_preview", "video")}),
        ("Extra", {"fields": ("tags", "additional_info"), "classes": ("collapse",)}),
        ("Stats", {"fields": ("view_count", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_category(self, obj):
        if obj.category:
            return obj.category.title
        if obj.subcategory:
            return obj.subcategory.category.title
        return "-"
    get_category.short_description = "Category"

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
        return super().get_queryset(request).select_related(
            "category", "subcategory", "subcategory__category"
        )