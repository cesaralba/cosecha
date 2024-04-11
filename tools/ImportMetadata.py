import logging
import os
import sys
from collections import defaultdict, OrderedDict
from datetime import datetime
from typing import Callable, Optional

import dateutil.parser as dateparse
from configargparse import ArgParser

from libs.Cosecha.ComicPage import ComicPage
from libs.Cosecha.Harvest import Harvest
from libs.Cosecha.StoreManager import DBStorage
from libs.Utils.Files import loadYAML
from libs.Utils.Misc import prepareBuilderPayloadDict

logger = logging.getLogger()

commit: Optional[Callable] = None


def parse_arguments():
    from libs.Utils.Logging import prepareLogger
    from libs.Cosecha.Config import globalConfig

    descriptionTXT = "Configuration to retrieve comics"

    parser = ArgParser(description=descriptionTXT)

    parser.add_argument('-v', dest='verbose', action="count", env_var='CS_VERBOSE', required=False,
                        help='Verbose mode (info)', default=0)
    parser.add_argument('-d', dest='debug', action="store_true", env_var='CS_DEBUG', required=False,
                        help='Debug mode (debug)', default=False)

    parser.add_argument('--ignore-enabled', dest='ignoreEnabled', action="store_true", required=False,
                        help='Ignores if the runner is disabled', default=False)

    parser.add_argument('-l', '--list-runners', dest='listRunners', action="store_true", required=False,
                        help='List all runners', default=False)

    globalConfig.addSpecificParams(parser)

    args = parser.parse_args()

    logLevel = logging.WARNING
    if args.verbose:
        logLevel = logging.INFO
    elif args.debug:
        logLevel = logging.DEBUG

    prepareLogger(logger=logger, level=logLevel)

    configGlobal = globalConfig.createFromArgs(args)

    if (args.listRunners):
        for k, runner in OrderedDict(sorted(configGlobal.allRunners().items(), key=lambda i: i[0].lower())).items():
            print(f"* {k:12} '{runner.title}' (module:{runner.module},enabled:{runner.enabled},mode:{runner.mode},"
                  f"batch:{runner.batchSize})")
        sys.exit(0)

    return configGlobal


from os import path

KEYS2IGNORE = {'fullFilename', 'saveMetadataPath', 'image'}
KEYTRANSLATOR = {'id': 'comicId', 'url': 'URL', 'filename': 'fname', 'urlImg': 'mediaURL', 'datePublished': 'comicDate',
                 }


def set2hashKey(s: set) -> str:
    return ",".join(sorted(s))


def parseDates(d: str) -> datetime:
    res = dateparse.parse(d)
    return res


def createDBmetadataRecord(data, dbStore: DBStorage):
    newData = prepareBuilderPayloadDict(source=data, dest=dbStore.obj.ImageMetadata)

    for k in newData:
        newData['info'].pop(k, None)
    dbData = dbStore.obj.ImageMetadata(**newData)
    commit()

    return dbData


def updateDBmetadataRecord(data, dbStore: DBStorage):
    try:
        currRecord = dbStore.obj.ImageMetadata[data['key'], data['comicId']]

        getChanges = lambda k: (k == 'info') or (data.get(k, None) != getattr(currRecord, k))

        newElems = prepareBuilderPayloadDict(source=data, dest=dbStore.obj.ImageMetadata, condition=getChanges)
        for k in newElems:
            newElems['info'].pop(k, None)

        currRecord.set(**newElems)
        commit()

        result = dbStore.obj.ImageMetadata[data['key'], data['comicId']]
        return result

    except dbStore.obj.RowNotFound as exc:
        newRecord = createDBmetadataRecord(data, dbStore=dbStore)
        return newRecord


KEYTRANSLATORFUNC = {'timestamp': parseDates}


def main(config):
    global commit

    config.ignorePollInterval = True
    cosecha = Harvest(config=config)
    cosecha.prepareStorage()

    session_manager = cosecha.dataStore.module.session_manager
    commit = cosecha.dataStore.module.commit

    with session_manager(immediate=True, optimistic=False, serializable=True, sql_debug=cosecha.globalCFG.verbose,
                         show_values=cosecha.globalCFG.verbose):
        cosecha.prepare()

        key2crawler = {crwl.key: crwl for crwl in cosecha.crawlers}
        print("CAP", key2crawler)
        metadataBase = cosecha.globalCFG.metadataD()

        metadataClass = cosecha.dataStore.obj.ImageMetadata
        fieldNames = {att.name for att in metadataClass._attrs_}

        for key in os.listdir(metadataBase):
            print(f"Key: {key}")
            fullPath = path.join(metadataBase, key)
            if not (path.exists(fullPath) and path.isdir(fullPath)):
                continue

            for root, dirs, files in os.walk(fullPath):
                if not files:
                    continue
                for file in files:

                    fullFile = path.join(root, file)
                    metadata: dict = loadYAML(fullFile)

                    newHash = {'key': key, 'info': dict()}

                    for k, v in metadata.items():
                        if k in KEYTRANSLATORFUNC:
                            v = KEYTRANSLATORFUNC[k](v)

                        if k in KEYS2IGNORE:
                            continue
                        elif k in fieldNames:
                            newHash[k] = v
                        elif k in KEYTRANSLATOR:
                            newHash[KEYTRANSLATOR[k]] = v
                        else:
                            newHash['info'][k] = v
                            if k == 'image':
                                print(file, key, k, v)

                    missingKeys = fieldNames.difference(newHash.keys())
                    if missingKeys:
                        imgDownloader: ComicPage = key2crawler[key].module.Page(**newHash)
                        imgDownloader.downloadMedia()
                        if 'mediaSize' in missingKeys:
                            newHash['mediaSize'] = imgDownloader.size()
                        if 'fname' in missingKeys:
                            newHash['fname'] = imgDownloader.dataFilename()

                        updateDBmetadataRecord(newHash, cosecha.dataStore)

                    print(f"Processed: {fullPath} -> {newHash['key']},{newHash['comicId']}")

if __name__ == '__main__':

    sys.run_local = os.path.abspath(__file__)
    base = os.path.dirname(sys.run_local)
    src = os.path.dirname(base)

    if src not in sys.path:
        sys.path.insert(0, src)

    config = parse_arguments()
    main(config)
