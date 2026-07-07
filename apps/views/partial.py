"""Shared mixin that lets a tab view render a bare fragment for the tab router.

A GET with ``?partial=1`` swaps the base template for ``partial_base.html`` (only
the content/CSS/JS blocks, no shell) and marks the response ``no-store`` so no
intermediate cache ever serves a fragment as a full page or vice versa.

Templates opt in with ``{% extends base_template|default:'base.html' %}``.
"""


class PartialTabMixin:
    def _is_partial(self):
        return self.request.GET.get("partial") == "1"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["base_template"] = "partial_base.html" if self._is_partial() else "base.html"
        return ctx

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        if self._is_partial():
            response["Cache-Control"] = "no-store"
            response["Vary"] = "X-Requested-With"
        return response
