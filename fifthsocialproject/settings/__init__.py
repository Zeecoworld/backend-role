"""
Django settings module initialization.

This file determines which settings configuration to load based on the
DJANGO_SETTINGS_MODULE environment variable or defaults to development.
"""

import os
from django.core.exceptions import ImproperlyConfigured

# Get the environment from DJANGO_SETTINGS_MODULE or default to development
settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', '')

if 'production' in settings_module:
    from .production import *
elif 'development' in settings_module:
    from .development import *
else:
    # Default to development if no specific settings module is specified
    from .development import *
    print("No specific settings module found, defaulting to development settings")