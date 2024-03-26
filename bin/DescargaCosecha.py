#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import sys

from configargparse import ArgParser

logger = logging.getLogger()


def parse_arguments():
    from libs.Utils.Logging import prepareLogger
    from libs.Cosecha.Config import globalConfig

    descriptionTXT = "Configuration to retrieve comics"

    parser = ArgParser(description=descriptionTXT)

    parser.add_argument('-v', dest='verbose', action="count", env_var='CS_VERBOSE', required=False,
                        help='Verbose mode (info)', default=0)
    parser.add_argument('-d', dest='debug', action="store_true", env_var='CS_DEBUG', required=False,
                        help='Debug mode (debug)', default=False)

    parser.add_argument('--ignore-enabled', dest='ignoreEnabled', action="store_true", env_var='CS_DEBUG',
                        required=False, help='Ignores if the runner is disabled', default=False)

    globalConfig.addSpecificParams(parser)

    args = parser.parse_args()

    logLevel = logging.WARNING
    if args.debug:
        logLevel = logging.DEBUG
    elif args.verbose:
        logLevel = logging.INFO

    prepareLogger(logger=logger, level=logLevel)

    configFile = globalConfig.createFromArgs(args)

    return configFile


def main(config):
    from libs.Cosecha.Harvest import Harvest

    cosecha = Harvest(config=config)

    cosecha.go()

    cosecha.print()


if __name__ == '__main__':

    sys.run_local = os.path.abspath(__file__)
    base = os.path.dirname(sys.run_local)
    src = os.path.dirname(base)

    if src not in sys.path:
        sys.path.insert(0, src)

    config = parse_arguments()
    main(config)
