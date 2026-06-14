# Django's default admin has been removed in favour of the custom panel
# (apps.panel, mounted at /manage/). All ModelAdmin registrations that used to
# live in this package are intentionally disabled — nothing is imported here so
# none of them register. The legacy module files are kept for reference only and
# are never imported at runtime.
