from django.http import Http404
from django.shortcuts import redirect
from django.utils.translation import get_language


class PremiumRequiredMixin:
	"""Premium obyekt ochilsa va user premium bo'lmasa -> premium page'ga yo'naltiradi."""

	def _user_is_premium(self):
		profile = getattr(self.request.user, "profile", None)
		return bool(profile and profile.is_premium)

	def is_object_premium(self, obj):
		return getattr(obj, "is_premium", False)

	def get(self, request, *args, **kwargs):
		try:
			self.object = self.get_object()
		except Http404:
			raise Http404(self.premium_not_found_message(kwargs))

		if self.is_object_premium(self.object) and not self._user_is_premium():
			lang = get_language() or "en"
			return redirect(f"/{lang}/premium/")

		context = self.get_context_data(object=self.object)
		return self.render_to_response(context)

	def premium_not_found_message(self, kwargs):
		return "Object not found."