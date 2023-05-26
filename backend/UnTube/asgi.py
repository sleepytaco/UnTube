"""
ASGI config for UnTube project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/asgi/
"""

import os
# from dotenv import load_dotenv
from django.core.asgi import get_asgi_application

settings_module = 'backend.UnTube.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

# to use env variables on pythonanywhere
# project_folder = os.path.expanduser('/home/bakaabu')
# load_dotenv(os.path.join(project_folder, '.env'))

application = get_asgi_application()
