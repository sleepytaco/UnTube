DEBUG = True
SECRET_KEY = 'django-insecure-ycs22y+20sq67y(6dm6ynqw=dlhg!)%vuqpd@$p6rf3!#1h$u='

GOOGLE_OAUTH_URI = '127.0.0.1:8000'  # this is the URI you will use when creating your OAuth Creds
SITE_ID = 1  # increment/decrement site ID as necessary

# please fill these in with your own Google OAuth credentials for the app to run properly!
GOOGLE_OAUTH_CLIENT_ID = NotImplemented
GOOGLE_OAUTH_CLIENT_SECRET = NotImplemented

# update logger to display DEBUG level or higher logs (+ color the logs using the colorlog package)
LOGGING['formatters']['colored'] = {  # type: ignore
    '()': 'colorlog.ColoredFormatter',
    'format': '%(log_color)s%(asctime)s %(levelname)s %(name)s %(bold_white)s%(message)s',
}
LOGGING['loggers']['backend']['level'] = 'DEBUG'  # type: ignore
LOGGING['handlers']['console']['level'] = 'DEBUG'  # type: ignore
LOGGING['handlers']['console']['formatter'] = 'colored'  # type: ignore
