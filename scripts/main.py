from core import GetConfigVars
from utilities import Utilities
import argparse


getconfigvars = GetConfigVars()
utils = Utilities()


def arg_parse():
    parser = argparse.ArgumentParser(
        description='Generate ansible variables'
                    )
    parser.add_argument(
        "vars",
        help='Name of the variable to generate.'
        )

    args = parser.parse_args()

    return args.vars


def main():
    data = {}
    method = getattr(getconfigvars, arg_parse())
    data = method()

    print(data)


if __name__ == '__main__':
    main()
