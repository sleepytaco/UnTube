import yaml
from django.conf import settings


def yaml_coerce(value):
    """
    Pass in a string dictionary and convert it into proper python dictionary
    """
    if isinstance(value, str):
        # create a tiny snippet of YAML, with key=dummy, and val=value, then load the YAML into
        # a pure Pythonic dictionary. Then, we read off the dummy key from the coversion to get our
        # final result
        return yaml.load(f'dummy: {value}', Loader=yaml.SafeLoader)['dummy']

    return value


def print_(*args, **kwargs):
    if settings.ENABLE_PRINT_STATEMENTS:
        print(*args, **kwargs)
