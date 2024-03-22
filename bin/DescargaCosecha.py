#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from configargparse import ArgParser

from libs.Cosecha.Crawler import Crawler
from libs.Cosecha.Harvest import Harvest
from libs.Cosecha.Config import globalConfig, readRunnerConfigs
from libs.Utils.Logging import prepareLogger

logger = logging.getLogger()


def parse_arguments():
    descriptionTXT = "Configuration to retrieve comics"

    parser = ArgParser(description=descriptionTXT)

    parser.add_argument('-v', dest='verbose', action="count", env_var='CS_VERBOSE', required=False, help='Verbose mode (warning)', default=0)
    parser.add_argument('-d', dest='debug', action="store_true", env_var='CS_DEBUG', required=False, help='Debug mode (debug)',
                        default=False)

    parser.add_argument('--ignore-enabled', dest='ignoreEnabled', action="store_true", env_var='CS_DEBUG', required=False, help='Ignores if the runner is disabled', default=False)

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


def main(config: globalConfig):
    #TODO: sacar el home directory
    cosecha = Harvest(config=config,homeDirectory='.')

    cosecha.go()

    cosecha.print()

    print(config.data['MAIL'])
    print(type(config.data))

if __name__ == '__main__':
    config = parse_arguments()
    main(config)
