"""
Settings specific to this application only (no Django or third party settings)
"""

IN_PYTHONANYWHERE = False  # PA has PYTHONANYWHERE_SITE in its env
IN_DOCKER = False
STOKEN_EXPIRATION_SECONDS = 10
USE_ON_COMMIT_HOOK = True