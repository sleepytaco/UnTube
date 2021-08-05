from .settings import *
import os

DEBUG = False
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

# Configure the domain name using the environment variable
# that Azure automatically creates for us.
# ALLOWED_HOSTS = [os.environ['WEBSITE_HOSTNAME'], '127.0.0.1'] if 'WEBSITE_HOSTNAME' in os.environ else []

# configure the domain name using the environment variable found on pythonanywhere
ALLOWED_HOSTS = ['bakaabu.pythonanywhere.com', '127.0.0.1'] if 'PYTHONANYWHERE_SITE' in os.environ else []
SITE_ID = 8

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

# DBHOST is only the server name, not the full URL (azure)
hostname = os.environ['DBHOST']

# Configure Postgres database; the full username is username@servername,
# which we construct using the DBHOST value.
# DATABASES = {
#    'default': {
#        'ENGINE': 'django.db.backends.postgresql',
#        'NAME': os.environ['DBNAME'],
#        'HOST': hostname + ".postgres.database.azure.com",
#        'USER': os.environ['DBUSER'] + "@" + hostname,
#        'PASSWORD': os.environ['DBPASS']
#    }
# }

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
