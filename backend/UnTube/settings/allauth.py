"""
Django AllAuth package related settings
"""

LOGIN_REDIRECT_URL = '/home/'
LOGOUT_REDIRECT_URL = '/'

# Additional configuration settings
# ACCOUNT_LOGOUT_ON_GET= True
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_STORE_TOKENS = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_REQUIRED = True

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        # 'APP': {
        #     'client_id': GOOGLE_OAUTH_CLIENT_ID,  # type: ignore
        #     'secret': GOOGLE_OAUTH_CLIENT_SECRET,  # type: ignore
        #     'key': ''
        # },
        # 'OAUTH_PKCE_ENABLED': True,  # valid in allauth ver > 0.47.0
        'SCOPE': [
            'profile',
            'email',
            'https://www.googleapis.com/auth/youtube',
        ],
        'AUTH_PARAMS': {
            # To refresh authentication in the background, set AUTH_PARAMS['access_type'] to offline.
            'access_type': 'offline',
        }
    }
}
