import os
from pathlib import Path
from split_settings.tools import include, optional

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Namespacing our own custom environment variables
ENVVAR_SETTINGS_PREFIX = 'UNTUBE_SETTINGS_'

LOCAL_SETTINGS_PATH = os.getenv(f'{ENVVAR_SETTINGS_PREFIX}LOCAL_SETTINGS_PATH')

# if local settings not specified in the environment
if not LOCAL_SETTINGS_PATH:  # default to development mode - use local dev settings
    LOCAL_SETTINGS_PATH = 'local/settings.dev.py'

if not os.path.isabs(LOCAL_SETTINGS_PATH):  # always make sure to have the absolute path
    LOCAL_SETTINGS_PATH = str(BASE_DIR / LOCAL_SETTINGS_PATH)

include(
    'base.py',
    'logging.py',
    # 'rest_framework.py',
    # 'channels.py',
    # 'aws.py',
    'custom.py',
    'allauth.py',
    optional(LOCAL_SETTINGS_PATH),  # `optional` means the file may or may not exist - it is fine if it does not
    'envvars.py',
    'docker.py',
    'pythonanywhere.py',
)
