#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from configargparse import ArgParser

from libs.Cosecha.Crawler import Crawler
from libs.Utils.Config import globalConfig, readRunnerConfigs
from libs.Utils.Logging import prepareLogger

logger = logging.getLogger()


def parse_arguments():
    descriptionTXT = "Configuration to retrieve comics"

    parser = ArgParser(description=descriptionTXT)

    parser.add_argument('-v', dest='verbose', action="count", env_var='CS_VERBOSE', required=False, help='', default=0)
    parser.add_argument('-d', dest='debug', action="store_true", env_var='CS_DEBUG', required=False, help='',
                        default=False)

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
    runnerCFGs = readRunnerConfigs(config.runnersCFG, '.')

    crawlers = {runner.name: Crawler(runnerCFG=runner, globalCFG=config) for runner in runnerCFGs}

    for crawler, obj in crawlers.items():
        if not obj.runnerCFG.enabled:
            continue
        obj.go()
        obj.state.store()

    for crawlerN, crawler in crawlers.items():
        print(f"{crawlerN} -> {crawler.runnerCFG}")
        if crawler.results:
            for res in crawler.results:
                print(f"{crawlerN} -> {res}")


if __name__ == '__main__':
    config = parse_arguments()
    main(config)
