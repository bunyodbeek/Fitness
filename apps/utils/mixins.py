from django.http import Http404
from django.shortcuts import redirect
from django.utils.translation import get_language

from apps.models.workouts import Program


def paywall_redirect():
	"""The single paywall redirect used across the app (same target the
	program/plan premium gate has always used)."""
	lang = get_language() or "en"
	return redirect(f"/{lang}/premium/")


def week_paywall_redirect(request, week):
	"""Return a paywall redirect when ``week`` is premium-locked for the request
	user, else ``None``.

	The structural rule ("first plan's week 1 is free, everything else premium")
	lives entirely in ``Week.is_locked_for`` / ``Week.is_free_preview``; this
	only wires it to the HTTP layer. One-time programs are exempt — they keep
	their legacy per-object ``is_premium`` behaviour and never reach the
	hierarchy paywall."""
	if week is None:
		return None
	program = week.plan.program
	if getattr(program, "is_one_time", False):
		return None
	# Custom (user-cloned) programs are the user's own content — importing
	# already required premium (share flow). Never paywall them.
	if program.type == Program.ProgramType.CUSTOM:
		return None
	profile = getattr(request.user, "profile", None)
	if week.is_locked_for(profile):
		return paywall_redirect()
	return None


class PremiumRequiredMixin:
	"""Program/plan-level premium gate.

	For hierarchy programs (``is_one_time=False``) the program-detail and
	plan-week list pages are ALWAYS browsable — the paywall moved down to the
	week level (see ``week_paywall_redirect``). Only one-time programs still
	honour the per-object ``is_premium`` checkbox here."""

	def _user_is_premium(self):
		profile = getattr(self.request.user, "profile", None)
		return bool(profile and profile.is_premium)

	def is_object_premium(self, obj):
		# Resolve the owning program whether obj is a Program or a Plan.
		program = obj if isinstance(obj, Program) else getattr(obj, "program", None)
		# One-time programs (no hierarchy) keep the manual is_premium checkbox.
		if program is not None and getattr(program, "is_one_time", False):
			return bool(getattr(program, "is_premium", False))
		# Hierarchy programs: lists / detail pages never block. The gate lives
		# at week level (first plan's week 1 is the free preview).
		return False

	def get(self, request, *args, **kwargs):
		try:
			self.object = self.get_object()
		except Http404:
			raise Http404(self.premium_not_found_message(kwargs))

		if self.is_object_premium(self.object) and not self._user_is_premium():
			return paywall_redirect()

		context = self.get_context_data(object=self.object)
		return self.render_to_response(context)

	def premium_not_found_message(self, kwargs):
		return "Object not found."


class WeekPaywallDetailMixin:
	"""DetailView mixin: redirect to the paywall before rendering when the
	resolved week is premium-locked for the current user.

	Subclasses override ``paywall_week()`` to point at the Week being served
	(``self.object`` for a WeekDetailView, ``self.object.week`` for a
	WorkoutDetailView)."""

	def paywall_week(self):
		return self.object

	def get(self, request, *args, **kwargs):
		self.object = self.get_object()
		blocked = week_paywall_redirect(request, self.paywall_week())
		if blocked:
			return blocked
		context = self.get_context_data(object=self.object)
		return self.render_to_response(context)
