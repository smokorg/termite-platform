import argparse

from configparser import ConfigParser
import logging
from termite import metadata
from termite.platform import Platform

__author__ = 'pavle'


PROG_NAME='platfromctl'
DESCRIPTION='''
Run Nano Plugin Platform
'''


def create_arg_parser(prog_name):
    arg_parser = argparse.ArgumentParser(
        prog=prog_name,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=DESCRIPTION)

    arg_parser.add_argument(
        '-v', '--version',
        action='version',
        version='{0} {1}'.format(prog_name, metadata.version))

    arg_parser.add_argument(
        '-c', '--config-file',
        default='conf/platform.ini',
        dest='config_file',
        help='Platform configuration file.'
    )

    arg_parser.add_argument(
        '-V', '--verbose',
        dest='verbose',
        action='store_true'
    )

    arg_parser.add_argument(
        '-d', '--plugins-directory',
        default='plugins',
        help='Plugins directory'
    )

    return arg_parser

def create_platform_instance(args):
    config = read_config(args.config_file)
    config.set('platform','plugins-dir', args.plugins_directory)
    return Platform(config)


def read_config(config_file):
    parser = ConfigParser()
    parser.read(config_file)
    return parser

def ctl_main():
    parser = create_arg_parser(PROG_NAME)
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format='[%(levelname)7s] %(asctime)s - %(name)s: %(message)s')
    logging.info(metadata.logo_ascii)
    platform = create_platform_instance(args)
    platform.start()
    platform.shutdown()

if __name__ == '__main__':
    ctl_main()
