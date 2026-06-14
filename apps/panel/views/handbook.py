"""Handbook section — categories → subcategories → items (drill-down CRUD)."""
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView

from apps.models.handbook import HandbookCategory, HandbookItem, HandbookSubCategory
from apps.panel.forms import HandbookCategoryForm, HandbookItemForm, HandbookSubCategoryForm
from apps.panel.mixins import StaffRequiredMixin
from apps.panel.views.base import PanelContextMixin
from apps.panel.views.crud import PanelCreateView, PanelDeleteView, PanelListView, PanelUpdateView


def _yesno(flag):
    if flag:
        return format_html('<span class="badge badge-green">{}</span>', _("Yes"))
    return format_html('<span class="badge badge-free">{}</span>', _("No"))


# ───────────────────────── Categories ─────────────────────────

class HandbookListView(PanelListView):
    model = HandbookCategory
    nav_active = "handbook"
    page_title = _("Handbook")
    columns = [_("Title"), _("Subcategories"), _("Items"), _("Active")]
    search_fields = ["title"]
    create_url_name = "panel:category_add"
    open_url_name = "panel:category_detail"
    delete_url_name = "panel:category_delete"
    create_label = _("Add category")

    def get_row_cells(self, obj):
        return [
            obj.title,
            obj.subcategories.count(),
            obj.direct_items.count(),
            _yesno(obj.is_active),
        ]


class CategoryCreateView(PanelCreateView):
    model = HandbookCategory
    form_class = HandbookCategoryForm
    nav_active = "handbook"
    page_title = _("Add category")
    success_url = reverse_lazy("panel:handbook")
    success_message = _("Category created.")

    def get_success_url(self):
        return reverse("panel:category_detail", args=[self.object.pk])


class CategoryUpdateView(PanelUpdateView):
    model = HandbookCategory
    form_class = HandbookCategoryForm
    nav_active = "handbook"
    page_title = _("Edit category")

    def get_success_url(self):
        return reverse("panel:category_detail", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("panel:category_detail", args=[self.object.pk])


class CategoryDeleteView(PanelDeleteView):
    model = HandbookCategory
    nav_active = "handbook"
    page_title = _("Delete category")
    success_url = reverse_lazy("panel:handbook")


class CategoryDetailView(StaffRequiredMixin, PanelContextMixin, DetailView):
    model = HandbookCategory
    template_name = "panel/detail.html"
    nav_active = "handbook"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        c = self.object
        ctx["page_title"] = c.title
        ctx["obj_title"] = c.title
        ctx["obj_edit_url"] = reverse("panel:category_edit", args=[c.pk])
        ctx["back_url"] = reverse("panel:handbook")
        ctx["breadcrumbs"] = [
            {"label": _("Handbook"), "url": reverse("panel:handbook")},
            {"label": c.title},
        ]
        # Child 1: subcategories
        ctx["child_title"] = _("Subcategories")
        ctx["child_add_url"] = reverse("panel:subcat_add", args=[c.pk])
        ctx["child_add_label"] = _("Add subcategory")
        ctx["child_columns"] = [_("Title"), _("Items"), _("Active")]
        ctx["child_rows"] = [
            {
                "cells": [s.title, s.items.count(), _yesno(s.is_active)],
                "open_url": reverse("panel:subcat_detail", args=[s.pk]),
                "edit_url": reverse("panel:subcat_edit", args=[s.pk]),
                "delete_url": reverse("panel:subcat_delete", args=[s.pk]),
            }
            for s in c.subcategories.all()
        ]
        # Child 2: direct items (no subcategory)
        ctx["child2_title"] = _("Direct items")
        ctx["child2_add_url"] = reverse("panel:item_add") + f"?category={c.pk}"
        ctx["child2_add_label"] = _("Add item")
        ctx["child2_columns"] = [_("Title"), _("Active")]
        ctx["child2_rows"] = [
            {
                "cells": [it.title, _yesno(it.is_active)],
                "edit_url": reverse("panel:item_edit", args=[it.pk]),
                "delete_url": reverse("panel:item_delete", args=[it.pk]),
            }
            for it in c.direct_items.all()
        ]
        return ctx


# ───────────────────────── Subcategories ─────────────────────────

class SubCategoryCreateView(PanelCreateView):
    model = HandbookSubCategory
    form_class = HandbookSubCategoryForm
    nav_active = "handbook"
    page_title = _("Add subcategory")
    success_message = _("Subcategory created.")

    def form_valid(self, form):
        form.instance.category = get_object_or_404(HandbookCategory, pk=self.kwargs["category_pk"])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("panel:subcat_detail", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("panel:category_detail", args=[self.kwargs["category_pk"]])


class SubCategoryUpdateView(PanelUpdateView):
    model = HandbookSubCategory
    form_class = HandbookSubCategoryForm
    nav_active = "handbook"
    page_title = _("Edit subcategory")

    def get_success_url(self):
        return reverse("panel:subcat_detail", args=[self.object.pk])

    def get_cancel_url(self):
        return reverse("panel:subcat_detail", args=[self.object.pk])


class SubCategoryDeleteView(PanelDeleteView):
    model = HandbookSubCategory
    nav_active = "handbook"
    page_title = _("Delete subcategory")

    def get_success_url(self):
        return reverse("panel:category_detail", args=[self.object.category_id])


class SubCategoryDetailView(StaffRequiredMixin, PanelContextMixin, DetailView):
    model = HandbookSubCategory
    template_name = "panel/detail.html"
    nav_active = "handbook"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        s = self.object
        ctx["page_title"] = s.title
        ctx["obj_title"] = f"{s.category.title} · {s.title}"
        ctx["obj_edit_url"] = reverse("panel:subcat_edit", args=[s.pk])
        ctx["back_url"] = reverse("panel:category_detail", args=[s.category_id])
        ctx["breadcrumbs"] = [
            {"label": _("Handbook"), "url": reverse("panel:handbook")},
            {"label": s.category.title, "url": reverse("panel:category_detail", args=[s.category_id])},
            {"label": s.title},
        ]
        ctx["child_title"] = _("Items")
        ctx["child_add_url"] = reverse("panel:item_add") + f"?subcategory={s.pk}"
        ctx["child_add_label"] = _("Add item")
        ctx["child_columns"] = [_("Title"), _("Active")]
        ctx["child_rows"] = [
            {
                "cells": [it.title, _yesno(it.is_active)],
                "edit_url": reverse("panel:item_edit", args=[it.pk]),
                "delete_url": reverse("panel:item_delete", args=[it.pk]),
            }
            for it in s.items.all()
        ]
        return ctx


# ───────────────────────── Items ─────────────────────────

class ItemCreateView(PanelCreateView):
    model = HandbookItem
    form_class = HandbookItemForm
    nav_active = "handbook"
    page_title = _("Add item")
    success_message = _("Item created.")

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("category"):
            initial["category"] = self.request.GET["category"]
        if self.request.GET.get("subcategory"):
            initial["subcategory"] = self.request.GET["subcategory"]
        return initial

    def _back_url(self):
        obj = getattr(self, "object", None)
        if obj and obj.subcategory_id:
            return reverse("panel:subcat_detail", args=[obj.subcategory_id])
        if obj and obj.category_id:
            return reverse("panel:category_detail", args=[obj.category_id])
        return reverse("panel:handbook")

    def get_success_url(self):
        return self._back_url()

    def get_cancel_url(self):
        if self.request.GET.get("subcategory"):
            return reverse("panel:subcat_detail", args=[self.request.GET["subcategory"]])
        if self.request.GET.get("category"):
            return reverse("panel:category_detail", args=[self.request.GET["category"]])
        return reverse("panel:handbook")


class ItemUpdateView(PanelUpdateView):
    model = HandbookItem
    form_class = HandbookItemForm
    nav_active = "handbook"
    page_title = _("Edit item")

    def get_success_url(self):
        if self.object.subcategory_id:
            return reverse("panel:subcat_detail", args=[self.object.subcategory_id])
        return reverse("panel:category_detail", args=[self.object.category_id])

    def get_cancel_url(self):
        return self.get_success_url()


class ItemDeleteView(PanelDeleteView):
    model = HandbookItem
    nav_active = "handbook"
    page_title = _("Delete item")

    def get_success_url(self):
        if self.object.subcategory_id:
            return reverse("panel:subcat_detail", args=[self.object.subcategory_id])
        if self.object.category_id:
            return reverse("panel:category_detail", args=[self.object.category_id])
        return reverse("panel:handbook")
