"""
Django AllAuth package related settings
"""

SITE_ID = 10  # increment/decrement site ID as necessary

SOCIALACCOUNT_PROVIDERS = {
    'google': {
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