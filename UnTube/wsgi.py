"""
WSGI config for UnTube project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/3.2/howto/deployment/wsgi/
"""

import os
from dotenv import load_dotenv
from django.core.wsgi import get_wsgi_application

settings_module = "UnTube.production" if 'UNTUBE' in os.environ else 'UnTube.settings'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

# to use env variables on pythonanywhere
project_folder = os.path.expanduser('/home/bakaabu')
load_dotenv(os.path.join(project_folder, '.env'))

application = get_wsgi_application()
