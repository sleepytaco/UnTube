from backend.general.utils.collections import deep_update
from backend.general.utils.settings import get_settings_from_environment
"""
This takes env variables with a matching prefix (set by you), strips out the prefix, and adds it to globals

Eg.
export UNTUBE_SETTINGS_IN_DOCKER=true (environment variable)

could be then referenced in the globals() dictionary as
IN_DOCKER (where the value will be set to Pythonic True)
"""
# globals() is a dictionary of global variables
deep_update(globals(), get_settings_from_environment(ENVVAR_SETTINGS_PREFIX))  # type: ignore  # noqa: F821
