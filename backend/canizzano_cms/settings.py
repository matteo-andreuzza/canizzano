"""
Impostazioni Django per il CMS di canizzano.it.

Il CMS gira solo in locale (rete Docker privata): serve a redigere i
contenuti dinamici — eventi di sagra, Pro Loco, parrocchia, Grest — che
Astro consuma in fase di build per produrre il sito statico.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Sicurezza -------------------------------------------------------------

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "insecure-solo-per-sviluppo-locale")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,backend,[::1]")
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
)

# --- Applicazioni ----------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "eventi",
    "assistente",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "canizzano_cms.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "canizzano_cms.wsgi.application"

# --- Database --------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "canizzano"),
        "USER": os.environ.get("POSTGRES_USER", "canizzano"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "canizzano"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Localizzazione --------------------------------------------------------

LANGUAGE_CODE = "it-it"
TIME_ZONE = os.environ.get("TZ", "Europe/Rome")
USE_I18N = True
USE_TZ = True

# --- File statici e media --------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# MEDIA_ROOT e' un volume condiviso col container di build di Astro: le
# immagini caricate in admin finiscono cosi' dentro al sito statico.
MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

# --- API -------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": None,
    "DATETIME_FORMAT": "iso-8601",
}

# Il consumatore delle API e' il builder Astro sulla rete Docker locale.
CORS_ALLOW_ALL_ORIGINS = True

# --- Assistente AI (server MCP su /mcp/) -----------------------------------

# Un agente puo' caricare la locandina di un evento dentro alla chiamata,
# codificata in base64: il tetto di Django (2,5 MB) la taglierebbe a meta'.
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("MCP_MAX_CORPO_MB", "32")) * 1024 * 1024

# --- Sito ------------------------------------------------------------------

SITE_NAME = os.environ.get("SITE_NAME", "Canizzano")
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://canizzano.it")
