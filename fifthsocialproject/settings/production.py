from .base import *
import dj_database_url
import cloudinary
from datetime import timedelta
import os

DATABASES = {}

DEBUG = False

FRONTEND_URL = os.getenv('FRONTEND_URL')
print(f"Raw FRONTEND_URL: '{FRONTEND_URL}'")
print(f"FRONTEND_URL type: {type(FRONTEND_URL)}")
print(f"FRONTEND_URL repr: {repr(FRONTEND_URL)}")

if FRONTEND_URL:
    FRONTEND_URL = FRONTEND_URL.strip()
    print(f"Cleaned FRONTEND_URL: '{FRONTEND_URL}'")


ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',') if os.getenv('ALLOWED_HOSTS') else []

# Override with production database if DATABASE_URL is provided
raw_database_url = os.getenv('DATABASE_URL')
if raw_database_url:
    if isinstance(raw_database_url, bytes):
        database_url_str = raw_database_url.decode('utf-8')
    else:
        database_url_str = raw_database_url
        
    try:
        DATABASES['default'] = dj_database_url.parse(database_url_str, conn_max_age=600)
        print(f"Using production database: {DATABASES['default']['ENGINE']}")
    except Exception as e:
        print(f"Error parsing DATABASE_URL: {e}")
        print("Falling back to SQLite")
        # Fallback to SQLite if DATABASE_URL parsing fails
        DATABASES['default'] = {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
else:
    # Default SQLite configuration if no DATABASE_URL is provided
    print("No DATABASE_URL found, using SQLite")
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }

# CORS Settings for Production with proper validation
if FRONTEND_URL and FRONTEND_URL.strip():
    # Ensure proper format
    cleaned_url = FRONTEND_URL.strip()
    
    # Validate the URL format
    if cleaned_url.startswith(('http://', 'https://')):
        CORS_ALLOWED_ORIGINS = [cleaned_url]
        print(f"CORS_ALLOWED_ORIGINS set to: {CORS_ALLOWED_ORIGINS}")
    else:
        # If missing scheme, add it based on content
        if 'localhost' in cleaned_url or '127.0.0.1' in cleaned_url:
            CORS_ALLOWED_ORIGINS = [f'http://{cleaned_url}']
        else:
            CORS_ALLOWED_ORIGINS = [f'https://{cleaned_url}']
        print(f"Added scheme, CORS_ALLOWED_ORIGINS: {CORS_ALLOWED_ORIGINS}")
else:
    CORS_ALLOWED_ORIGINS = []
    print("No FRONTEND_URL provided, CORS_ALLOWED_ORIGINS is empty")

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Configure cloudinary for production
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

# Use Cloudinary for media files
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Static Files Storage for production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security settings for production
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_FRAME_DENY = True

# Session security
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# Production JWT settings
SIMPLE_JWT.update({
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),  # Shorter for security
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
})

# Email backend for production (you might want to configure a proper email backend)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Production logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'ERROR',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'ERROR',
            'propagate': True,
        },
        'fifthsocialproject': {
            'handlers': ['file', 'console'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}

# Ensure logs directory exists
logs_dir = BASE_DIR / 'logs'
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

print("Production settings loaded")