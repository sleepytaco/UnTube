if IN_PYTHONANYWHERE:  # type: ignore # noqa: F821
    # to use env variables on pythonanywhere
    # from dotenv import load_dotenv
    # project_folder = os.path.expanduser('/home/bakaabu')
    # load_dotenv(os.path.join(project_folder, '.env'))
    GOOGLE_OAUTH_URI = os.environ['GOOGLE_OAUTH_URI']  # type: ignore # noqa: F821 #  "bakaabu.pythonanywhere.com"
    SECRET_KEY = os.environ['SECRET_KEY']  # type: ignore # noqa: F821
    YOUTUBE_V3_API_KEY = os.environ['YOUTUBE_V3_API_KEY']  # type: ignore # noqa: F821

    # WhiteNoise configuration
    assert MIDDLEWARE[:1] == [  # type: ignore # noqa: F821
        'django.middleware.security.SecurityMiddleware'
    ] and not IN_DOCKER  # type: ignore # noqa: F821 # PA does not support dockerized apps
    # Add whitenoise middleware after the security middleware
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')  # type: ignore # noqa: F821 # noqa: F821

    # configure the domain name using the environment variable found on pythonanywhere
    ALLOWED_HOSTS = ['bakaabu.pythonanywhere.com', '127.0.0.1', 'untube.it']
    SITE_ID = 10

    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True

    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')  # type: ignore # noqa: F821

    # DBHOST is only the server name
    hostname = os.environ['DBHOST']  # type: ignore # noqa: F821

    # Configure MySQL database on pythonanywhere
    # See https://django-mysql.readthedocs.io/en/latest/checks.html for options
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': f'{os.environ["DBUSER"]}${os.environ["DBNAME"]}',  # type: ignore # noqa: F821
            'USER': f'{os.environ["DBUSER"]}',  # type: ignore # noqa: F821
            'PASSWORD': f'{os.environ["DBPASS"]}',  # type: ignore # noqa: F821
            'HOST': hostname,
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES', innodb_strict_mode=1",
                'charset': 'utf8mb4',
                'autocommit': True,
            }
        }
    }

    print('Using Pythonanywhere settings...')
