"""
Settings specific to this application only (no Django or third party settings)
"""

YOUTUBE_V3_API_KEY = NotImplemented
GOOGLE_OAUTH_URI = NotImplemented
GOOGLE_OAUTH_CLIENT_ID = NotImplemented
GOOGLE_OAUTH_CLIENT_SECRET = NotImplemented
CRISPY_TEMPLATE_PACK = 'bootstrap4'

# hosting environments
IN_PYTHONANYWHERE = False  # PA has PYTHONANYWHERE_SITE in its env
IN_DOCKER = False

STOKEN_EXPIRATION_SECONDS = 10
USE_ON_COMMIT_HOOK = True
