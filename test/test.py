import argparse
import json
from cl_vx_config.configvars import ConfigVars

cl = ConfigVars()

parser = argparse.ArgumentParser(
    prog='test',
    usage='%(prog)s [config_var]'
)

parser.add_argument(
    'config_var',
    help='name configuration variable',
)

config = parser.parse_args()

method = getattr(cl, config.config_var)
try:
    print(json.dumps(method(), indent=4))
except json.decoder.JSONDecodeError:
    print(method())
except TypeError:
    print(method())
