"""Reusable staff-only CRUD base views for the panel.

Subclasses get a consistent black+gold list/form/delete UI for free. Used by the
Users / Subscriptions / Tracking / Payments / Admins sections (Phase 3 & 5) and
the simpler content sections.
"""
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.panel.mixins import StaffRequiredMixin
from apps.panel.views.base import PanelContextMixin


class PanelListView(StaffRequiredMixin, PanelContextMixin, ListView):
    template_name = "panel/list.html"
    paginate_by = 25
    context_object_name = "objects"

    # Subclass config
    columns = []                 # list of column header labels
    search_fields = []           # model fields to OR-search with ?q=
    create_url_name = None       # e.g. "panel:user_add"
    edit_url_name = None
    delete_url_name = None
    open_url_name = None          # optional drill-down detail link
    create_label = None

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q and self.search_fields:
            cond = Q()
            for field in self.search_fields:
                cond |= Q(**{f"{field}__icontains": q})
            qs = qs.filter(cond)
        return qs

    def get_row_cells(self, obj):
        """Return a list of cell values (str or SafeString) for one row."""
        raise NotImplementedError

    def _url(self, name, obj):
        return reverse(name, args=[obj.pk]) if name else None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = []
        for obj in context["objects"]:
            rows.append({
                "cells": self.get_row_cells(obj),
                "open_url": self._url(self.open_url_name, obj),
                "edit_url": self._url(self.edit_url_name, obj),
                "delete_url": self._url(self.delete_url_name, obj),
            })
        context["columns"] = self.columns
        context["rows"] = rows
        context["create_url"] = reverse(self.create_url_name) if self.create_url_name else None
        context["create_label"] = self.create_label
        context["search_q"] = self.request.GET.get("q", "")
        context["searchable"] = bool(self.search_fields)
        return context


class PanelFormViewMixin(StaffRequiredMixin, PanelContextMixin):
    template_name = "panel/form.html"

    def get_cancel_url(self):
        # Use success_url directly: on a CreateView GET self.object is None, so
        # get_success_url() (which formats with object.__dict__) would fail.
        return self.success_url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = self.get_cancel_url()
        return context


class PanelCreateView(PanelFormViewMixin, CreateView):
    success_message = None

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.success_message:
            messages.success(self.request, self.success_message)
        return response

    def get_page_title(self):
        return self.page_title


class PanelUpdateView(PanelFormViewMixin, UpdateView):
    def get_page_title(self):
        return self.page_title


class PanelDeleteView(StaffRequiredMixin, PanelContextMixin, DeleteView):
    template_name = "panel/confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = self.get_success_url()
        return context
