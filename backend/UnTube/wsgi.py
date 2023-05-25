"""
WSGI config for UnTube project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

settings_module = 'backend.UnTube.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

# to use env variables on pythonanywhere
# from dotenv import load_dotenv
# project_folder = os.path.expanduser('/home/bakaabu')
# load_dotenv(os.path.join(project_folder, '.env'))

application = get_wsgi_application()
