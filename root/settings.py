import os

from pathlib import Path

from dotenv import load_dotenv

load_dotenv('.env')

BASE_DIR = Path(__file__).resolve().parent.parent

# Telegram token should be loaded from environment variables.
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('BOT_TOKEN')
TELEGRAM_BOT_REDIRECT_URL=os.getenv('TELEGRAM_BOT_REDIRECT_URL')
WEBAPP_URL = 'https://www.shredzville.com'

SECRET_KEY = 'django-insecure-test-key-for-development-12345'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
	'jazzmin',
	'nested_admin',
	
	'django.contrib.admin',
	
	'django.contrib.auth',
	
	'django.contrib.contenttypes',
	
	'django.contrib.sessions',
	
	'django.contrib.messages',
	
	'django.contrib.staticfiles',
	
	'apps',
	
	'rest_framework',
	
	'corsheaders',
	
	'django_filters',
	
	'drf_spectacular',

]

MIDDLEWARE = [
	
	'django.middleware.security.SecurityMiddleware',
	
	'corsheaders.middleware.CorsMiddleware',
	
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.locale.LocaleMiddleware',
	
	'django.middleware.common.CommonMiddleware',
	
	'django.middleware.csrf.CsrfViewMiddleware',
	
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'apps.middleware.TelegramLoginRedirectMiddleware',
	
	'django.contrib.messages.middleware.MessageMiddleware',
	
	'django.middleware.clickjacking.XFrameOptionsMiddleware',

]

ROOT_URLCONF = 'root.urls'

TEMPLATES = [
	
	{
		'BACKEND': 'django.template.backends.django.DjangoTemplates',
		
		'DIRS': [BASE_DIR / 'templates'],
		
		'APP_DIRS': True,
		
		'OPTIONS': {
			
			'context_processors': [
				
				'django.template.context_processors.debug',
				
				'django.template.context_processors.request',
				
				'django.contrib.auth.context_processors.auth',
				
				'django.contrib.messages.context_processors.messages',
			
			],
			
		},
		
	},

]

WSGI_APPLICATION = 'root.wsgi.application'

AUTH_USER_MODEL = 'apps.User'

# Database

DATABASES = {
	
	"default": {
		
		"ENGINE": "django.db.backends.postgresql",
		
		"NAME": 'fitness_db',
		
		"USER": 'postgres',
		
		"PASSWORD": 'JudaKuchliParol123!',
		
		"HOST": '127.0.0.1',
		
		"PORT": '5432',
		
	}
	
}

# Password validation

AUTH_PASSWORD_VALIDATORS = [
	
	{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
	
	{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
	
	{'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
	
	{'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},

]

LANGUAGE_CODE = 'en'

TIME_ZONE = 'Asia/Tashkent'

USE_I18N = True

USE_L10N = False

USE_TZ = True

LANGUAGES = [
	
	('uz', 'O‘zbekcha'),
	
	('ru', 'Русский'),
	
	('en', 'English'),

]

LOCALE_PATHS = [
	
	BASE_DIR / 'locale',

]

LOGIN_URL = 'onboarding'

LOGIN_REDIRECT_URL = 'program_list'

LOGOUT_REDIRECT_URL = '/'

STATIC_URL = '/static/'

STATICFILES_DIRS = [
	os.path.join(BASE_DIR, 'static'),
]

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework

# CSRF_TRUSTED_ORIGINS = [
#
# 	'https://*.ngrok-free.app',
#
# 	'https://*.ngrok-free.dev',
#
# 	'https://educated-luana-shroudlike.ngrok-free.dev',
#
# ]

# CORS Settings

CORS_ALLOW_ALL_ORIGINS = True

# Telegram Bot Settings

TELEGRAM_BOT_TOKEN = BOT_TOKEN

TELEGRAM_WEBHOOK_URL = os.getenv('TELEGRAM_WEBHOOK_URL', default=WEBAPP_URL)
TELEGRAM_BOT_REDIRECT_URL = os.getenv('TELEGRAM_BOT_REDIRECT_URL', default=f'{WEBAPP_URL}/uz/miniapp/questionnaire/')

ADMIN_ID = '7946709135'
#
# JAZZMIN_SETTINGS = {
#
# 	# title of the window (Will default to current_admin_site.site_title if absent or None)
#
# 	"site_title": "Library Admin",
#
# 	# Title on the login screen (19 chars max) (defaults to current_admin_site.site_header if absent or None)
#
# 	"site_header": "Library",
#
# 	# Title on the brand (19 chars max) (defaults to current_admin_site.site_header if absent or None)
#
# 	"site_brand": "Library",
#
# 	# Logo to use for your site, must be present in static files, used for brand on top left
#
# 	"site_logo": "vendor/adminlte/img/AdminLTELogo.png",
#
# 	# Logo to use for your site, must be present in static files, used for login form logo (defaults to site_logo)
#
# 	"login_logo": None,
#
# 	# Logo to use for login form in dark themes (defaults to login_logo)
#
# 	"login_logo_dark": None,
#
# 	# CSS classes that are applied to the logo above
#
# 	"site_logo_classes": "img-circle",
#
# 	# Relative path to a favicon for your site, will default to site_logo if absent (ideally 32x32 px)
#
# 	"site_icon": None,
#
# 	# Welcome text on the login screen
#
# 	"welcome_sign": "Welcome to the library",
#
# 	# Copyright on the footer
#
# 	"copyright": "Acme Library Ltd",
#
# 	# List of model admins to search from the search bar, search bar omitted if excluded
#
#
# 	"search_model": ["auth.User", "auth.Group"],
#
# 	# Field name on user model that contains avatar ImageField/URLField/Charfield or a callable that receives the user
#
# 	"user_avatar": None,
#
# 	############
#
# 	# Top Menu #
#
# 	############
#
# 	# Links to put along the top menu
#
# 	"topmenu_links": [
#
# 		# Url that gets reversed (Permissions can be added)
#
# 		{"name": "Home", "url": "admin:index"},
#
# 		# external url that opens in a new window (Permissions can be added)
#
# 		{"model": "apps.Program"},
# 		{"model": "apps.Exercise"},
#
# 	],
#
# 	#############
#
# 	# User Menu #
#
# 	#############
#
# 	# Additional links to include in the user menu on the top right ("app" url type is not allowed)
#
# 	"usermenu_links": [
# 		{"model": "auth.user"}
#
# 	],
#
# 	#############
#
# 	# Side Menu #
#
# 	#############
#
# 	# Whether to display the side menu
#
# 	"show_sidebar": True,
#
# 	# Whether to aut expand the menu
#
# 	"navigation_expanded": True,
#
# 	# Hide these apps when generating side menu e.g (auth)
#
# 	"hide_apps": ["auth"],
#
#
# 	"hide_models": [
# 		"apps.favorite",
# 		"apps.favoritecollection",
# 		"apps.gymplan",
# 		"apps.homeplan",
# 		"apps.gymworkout",
# 		"apps.homeworkout",
# 		"apps.workoutprogress",
# 		"apps.userworkoutprogress",
# 		"apps.workoutexerciseplan",
# 		"apps.progressionprofile",
# 		"apps.programtemplate",
# 		"apps.userprogram",
# 		"apps.workoutday",
# 		"apps.userprogramexercise",
# 				"apps.subscription",
# 		"apps.subscriptionplan",
# 		"apps.useractivity",
# 	],
#
# 	# List of apps (and/or models) to base side menu ordering off of (does not need to contain all apps/models)
#
# 	"order_with_respect_to": ["auth", "apps", "apps.program", "apps.exercise", "apps.userprofile", "apps.handbookcategory", "apps.handbooksubcategory", "apps.handbookitem"],
#
# 	# Custom links to append to app groups, keyed on app name
#
# 	"custom_links": {},
#
# 	# for the full list of 5.13.0 free icon classes
#
# 	"icons": {
#
# 		"auth": "fas fa-users-cog",
#
# 		"auth.user": "fas fa-user",
#
# 		"auth.Group": "fas fa-users",
#
# 	},
#
# 	# Icons that are used when one is not manually specified
#
# 	"default_icon_parents": "fas fa-chevron-circle-right",
#
# 	"default_icon_children": "fas fa-circle",
#
# 	#################
#
# 	# Related Modal #
#
# 	#################
#
# 	# Use modals instead of popups
#
# 	"related_modal_active": False,
#
# 	#############
#
# 	# UI Tweaks #
#
# 	#############
#
# 	# Relative paths to custom CSS/JS scripts (must be present in static files)
#
# 	"custom_css": None,
#
# 	"custom_js": None,
#
#
# 	"use_google_fonts_cdn": True,
#
# 	# Whether to show the UI customizer on the sidebar
#
# 	"show_ui_builder": False,
#
# 	###############
#
# 	# Change view #
#
# 	###############
#
# 	# Render out the change view as a single form, or in tabs, current options are
#
# 	# - single
#
# 	# - horizontal_tabs (default)
#
# 	# - vertical_tabs
#
# 	# - collapsible
#
# 	# - carousel
#
# 	"changeform_format": "horizontal_tabs",
#
# 	# override change forms on a per modeladmin basis
#
# 	"changeform_format_overrides": {"auth.user": "collapsible", "auth.group": "vertical_tabs"},
#
# 	# Add a language dropdown into the admin
#
# 	"language_chooser": True,
#
# }
#
# REST_FRAMEWORK = {
#
# 	'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
#
# }
APPEND_SLASH = True
JAZZMIN_SETTINGS = {
	"site_title": "Fitness App Admin",
	"site_header": "Fitness Admin",
	"welcome_sign": "Xush kelibsiz, Admin",
	"search_model": ["apps.Exercise", "apps.Plan"],
	"topmenu_links": [
		{"name": "Home", "url": "admin:index", "permissions": ["auth.view_user"]},
	],
	"show_sidebar": True,
	"navigation_expanded": True,
	"theme": "darkly",
	"show_ui_builder": True,
	# TO'Q RANG (Dark theme)
}

JAZZMIN_UI_CONFIG = {
	"navbar_variant": "navbar-dark",
	"theme": "darkly",  # Bu ko'kroq/to'q fon beradi
	"accent": "accent-primary",
}
