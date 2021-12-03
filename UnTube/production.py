from .settings import *
import os

SECRET_KEY = SECRETS['SECRET_KEY']

# configure the domain name using the environment variable found on pythonanywhere
ALLOWED_HOSTS = ['bakaabu.pythonanywhere.com', '127.0.0.1', 'untube.it'] if 'UNTUBE' in os.environ else ['bakaabu.pythonanywhere.com', 'untube.it']
SITE_ID = 9

DEBUG = False
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

# WhiteNoise configuration
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # Add whitenoise middleware after the security middleware
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# DBHOST is only the server name
hostname = os.environ['DBHOST']

# Configure MySQL database on pythonanywhere
# See https://django-mysql.readthedocs.io/en/latest/checks.html for options
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': f'{os.environ["DBUSER"]}${os.environ["DBNAME"]}',
        'USER': f'{os.environ["DBUSER"]}',
        'PASSWORD': f'{os.environ["DBPASS"]}',
        'HOST': hostname,
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES', innodb_strict_mode=1",
            'charset': 'utf8mb4',
            "autocommit": True,
        }
    }
}
