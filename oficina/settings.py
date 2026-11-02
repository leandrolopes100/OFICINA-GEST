from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

_env_path = BASE_DIR / '.env'
if _env_path.exists():
    for _line in _env_path.read_text(encoding='utf-8').splitlines():
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _, _v = _line.partition('=')
            os.environ.setdefault(_k.strip(), _v.strip())

SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'

_raw_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(',') if h.strip()]

_raw_origins = os.environ.get(
    'DJANGO_CSRF_TRUSTED_ORIGINS',
    'https://oficinagest.com.br,https://www.oficinagest.com.br',
)
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _raw_origins.split(',') if o.strip()]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if os.environ.get('DJANGO_HTTPS_ENABLED', 'False') == 'True':
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # Third party
    'crispy_forms',
    'crispy_bootstrap5',

    # Local
    'core',
    'accounts',
    'clientes',
    'veiculos',
    'orcamentos',
    'ordens_servico',
    'estoque',
    'financeiro',
    'relatorios',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'oficina.urls'

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

WSGI_APPLICATION = 'oficina.wsgi.application'

_db_engine = os.environ.get('DB_ENGINE', 'sqlite')

if _db_engine == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE':       'django.db.backends.postgresql',
            'NAME':         os.environ.get('DB_NAME', 'oficina_dev'),
            'USER':         os.environ.get('DB_USER', 'postgres'),
            'PASSWORD':     os.environ.get('DB_PASSWORD', ''),
            'HOST':         os.environ.get('DB_HOST', 'localhost'),
            'PORT':         os.environ.get('DB_PORT', '5432'),
            'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', '0')),
            'OPTIONS': {
                'client_encoding': 'UTF8',
            },
        }
    }
else:

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME':   BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'oficina-cache',
        'TIMEOUT': 300,
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'padrao': {'format': '{asctime} {levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'padrao'},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'WARNING'), 'propagate': False},
    },
}

AUTH_USER_MODEL = 'accounts.CustomUser'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ── E-mail ────────────────────────────────────────────────────────────────────
# Padrão: console — imprime o e-mail no terminal do servidor (sem SMTP).
# O administrador copia o link e repassa ao usuário (WhatsApp, presencialmente).
# Para ativar envio real: defina DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# e configure as variáveis SMTP no .env.
EMAIL_BACKEND       = os.environ.get(
    'DJANGO_EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST          = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT          = int(os.environ.get('EMAIL_PORT', '25'))
EMAIL_HOST_USER     = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS       = os.environ.get('EMAIL_USE_TLS', 'False') == 'True'
DEFAULT_FROM_EMAIL  = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    'Oficina-Gest <noreply@oficina-gest.com.br>',
)
# Token de reset válido por 3 dias (padrão Django = 3 dias)
PASSWORD_RESET_TIMEOUT = int(os.environ.get('PASSWORD_RESET_TIMEOUT', str(60 * 60 * 24 * 3)))
