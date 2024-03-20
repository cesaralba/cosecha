#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from configargparse import ArgumentParser
from configparser import ConfigParser
from libs.Utils.Logging import prepareLogger
import logging
from os import getenv
from libs.Utils.Config import globalConfig, readRunnerConfigs
from os import path
from libs.Cosecha.Crawler import Crawler
import sys
from locale import LC_ALL, setlocale

logger = logging.getLogger()


def parse_arguments():
    descriptionTXT = "Configuration to retrieve comics"

    parser = ArgumentParser(description=descriptionTXT)

    parser.add('-v', dest='verbose', action="count", env_var='CS_VERBOSE', required=False, help='', default=0)
    parser.add('-d', dest='debug', action="store_true", env_var='CS_DEBUG', required=False, help='', default=False)

    parser.add('-c', '--config', dest='config', action="store", env_var='CS_CONFIG', required=False,
               help='Fichero de configuración', default="etc/cosecha.cfg")

    parser.add('-j', dest='justone', action="store_true", env_var='CS_JUSTONE', required=False,
               help='Just downloads one vignette', default=False)

    parser.add('-o', dest='destdir', type=str, env_var='CS_DESTDIR', help='Root directory to store things',
               required=False)
    parser.add('-i', dest='destimgs', type=str, env_var='CS_DESTDIRIMG',
               help='Location to store images (supersedes ${CS_DESTDIR}/images', required=False)
    parser.add('-m', dest='destmeta', type=str, env_var='CS_DESTDIRMETA',
               help='Location to store metadata files (supersedes ${CS_DESTDIR}/metadata', required=False)
    parser.add('-s', dest='deststate', type=str, env_var='CS_DESTDIRSTATE',
               help='Location to store state files (supersedes ${CS_DESTDIR}/state', required=False)

    # parser.add('-f', dest='saveanyway', action="store_true", env_var='SM_SAVEANYWAY', required=False,
    #            help='Graba el fichero aunque no haya habido cambios', default=False)
    #
    # parser.add('-e', dest='edicion', action="store", env_var='SM_EDICION', required=False,
    #            help=('Año de la temporada (para 2015-2016 sería 2016). La ACB empieza en 1983. '
    #                  'La copa se referencia por el año menor '),
    #            default=None)
    # parser.add('-u', dest='url', action="store", env_var='SM_URLCAL', help='', required=False)
    # parser.add('-b', dest='procesaBio', action="store_true", env_var='SM_STOREBIO',
    #            help='Descarga los datos biográficos de los jugadores', required=False, default=False)
    # parser.add('-p', dest='procesaPlantilla', action="store_true", env_var='SM_STOREPLANT',
    #            help='Descarga las plantillas de los equipos', required=False, default=False)
    #
    # parser.add('-i', dest='infile', type=str, env_var='SM_INFILE', help='Fichero de entrada', required=False)
    #
    # parser.add_argument("-t", "--acbfile", dest="acbfile", action="store", required=True, env_var="ACB_FILE",
    #                     help="Nombre del ficheros de temporada", )
    # parser.add_argument("-l", "--listaequipos", dest='listaEquipos', action="store_true", required=False,
    #                     help="Lista siglas para equipos", )
    # parser.add_argument("-q", "--quiet", dest='quiet', action="store_true", required=False,
    #                     help="En combinación con -l saca lista siglas sin nombres", )
    #
    # parser.add_argument("-e", "--equipo", dest="equipo", action="store", required=False,
    #                     help="Abreviatura del equipo deseado (usar -l para obtener lista)", )
    # parser.add_argument("-o", "--outfile", dest="outfile", action="store", help="Fichero PDF generado",
    #                     required=False, )
    #
    # parser.add_argument("-c", "--cachedir", dest="cachedir", action="store", required=False, env_var="ACB_CACHEDIR",
    #                     help="Ubicación de caché de ficheros", )
    # parser.add_argument("--locale", dest="locale", action="store", required=False, default='es_ES', help="Locale", )

    args = parser.parse_args()

    logLevel = logging.WARNING
    if args.debug:
        logLevel = logging.DEBUG
    elif args.verbose:
        logLevel = logging.INFO

    prepareLogger(logger=logger, level=logLevel)

    # result = readConfig(args)

    configFile = globalConfig(saveDirectory='/tmp/Cosecha', runnersCFG='etc/runners.d/*.conf', batchSize='3')

    if args.destdir:
        configFile.saveDirectory = args.destdir

    if args.destimgs:
        configFile.imagesDirectory = args.destimgs

    if args.destmeta:
        configFile.metadataDirectory = args.destmeta

    if args.deststate:
        configFile.stateDirectory = args.deststate

    return configFile


def main(config: globalConfig):
    runnerCFGs = readRunnerConfigs(config.runnersCFG, '.')

    crawlers = {runner.name: Crawler(runnerCFG=runner, globalCFG=config) for runner in runnerCFGs}

    for crawler, obj in crawlers.items():
        obj.go()
        obj.state.store()


if __name__ == '__main__':
    config = parse_arguments()
    main(config)
