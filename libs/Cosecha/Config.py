import logging
import os.path
from argparse import Namespace, REMAINDER
from configparser import ConfigParser
from dataclasses import dataclass, Field, field
from datetime import datetime
from glob import glob
from os import makedirs, path
from typing import Dict, List, Optional

import validators
from configargparse import ArgParser

RUNNERFILEEXTENSION = "conf"

RUNNERVALIDMODES = {'poll', 'crawler'}
RUNNERVALIDINITIALS = {'*first', '*last'}
RUNNERBATCHMODES = {'crawler'}
RUNNERVALIDPOLLINTERVALS = {'none', 'daily', 'weekly', 'biweekly', 'monthly', 'bimonthly', 'quarterly'}

DEFAULTRUNNERMODE = "poll"
DEFAULTRUNNERBATCHSIZE = 7
DEFAULTPOLLINTERVAL = 'daily'

STOREVALIDBACKENDS = {'Pony','None'}

GMTIMEFORMATFORMAIL = "%Y/%m/%d-%H:%M %z"
TIMESTAMPFORMAT = "%Y%m%d-%H%M%S %z"
TIMESTAMPFORMATORM = "%Y-%m-%d %H:%M:%S%z" #2024-04-04 06:31:07+00:00

@dataclass
class storeConfig:
    backend: str
    backendData: Optional[dict] = None
    verbose:bool = False
    filename: Optional[str] = None
    parser: Optional[ConfigParser] = None

    @classmethod
    def createFromParse(cls, parser: ConfigParser, filename: str):
        auxData = dict()
        auxData['filename'] = filename
        auxData['parser'] = parser

        auxData.update(mergeConfFileIntoDataClass(cls, parser, 'STORE'))

        fileKeys = set(auxData.keys())
        requiredClassFields = {k for k, v in cls.__dataclass_fields__.items() if
                               not isinstance(v.default, (type(None), str, bool, int))}
        missingKeys = requiredClassFields.difference(fileKeys)

        if (missingKeys):
            logging.error(f"{filename}: missing required fields: {missingKeys}")
            raise KeyError(f"{filename}: missing required fields: {missingKeys}")

        if auxData.get('backend',None).lower() == 'none':
            return None

        if 'DB' not in parser:
            logging.error(f"{filename}: Backend requested {auxData['backend']} but no 'DB' section provided")
            raise ValueError(f"{filename}: Backend requested {auxData['backend']} but no 'DB' section provided")

        auxData['backendData'] = {k:v.strip('"').strip("'") for k,v in dict(parser['DB']).items()}

        result = cls(**auxData)

        return result

    def __post_init__(self):
        if not self.check():
            raise ValueError(f"storeConfig: '{self.filename}' provided configuration for STORE is not valid")

    def check(self):
        problems = list()

        if self.backend not in STOREVALIDBACKENDS:
            problems.append(f"{self.filename}: Backend '{self.backend}' unknown. Known ones are {STOREVALIDBACKENDS}")

        for msg in problems:
            logging.error(msg)

        return len(problems) == 0


@dataclass
class mailConfig:
    subject: str = "Cosecha. Files downloaded on {timestamp}"
    SMTPHOST: str = "localhost"
    SMTPPORT: int = 25
    mailMaxSize: int = 1000000
    sender: str = "root@localhost"
    to: List[str] = field(default_factory=list)

    @classmethod
    def createFromParse(cls, parser: ConfigParser, filename: str):
        auxData = dict()

        auxData.update(mergeConfFileIntoDataClass(cls, parser, 'MAIL'))

        auxData['to'] = [d for d in auxData['to'].split('\n') if validators.email(d)]

        fileKeys = set(auxData.keys())
        requiredClassFields = {k for k, v in cls.__dataclass_fields__.items() if
                               not isinstance(v.default, (type(None), str, bool, int))}
        missingKeys = requiredClassFields.difference(fileKeys)

        if (missingKeys):
            logging.error(f"{filename}: missing required fields: {missingKeys}")
            raise KeyError(f"{filename}: missing required fields: {missingKeys}")

        result = cls(**auxData)

        return result


@dataclass
class runnerConfig:
    module: str
    data: object
    enabled: bool = True
    filename: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    mode: str = DEFAULTRUNNERMODE
    initial: Optional[str] = '*last'
    batchSize: int = DEFAULTRUNNERBATCHSIZE
    pollInterval: Optional[str] = DEFAULTPOLLINTERVAL

    def __post_init__(self):
        if not isinstance(self.batchSize, int):
            self.batchSize = int(self.batchSize)
        if self.name is None:
            self.name = runnerConfFName2Name(self.filename)
        if self.title is None:
            self.title = self.name

        if not self.check():
            raise ValueError(f"runnerConfig: '{self.filename}' not valid")

    def check(self):
        problems = list()

        if self.mode not in RUNNERVALIDMODES:
            problems.append(
                    f"{self.__class__}:{self.filename} 'mode' has not a valid value '{self.mode}'. Valid modes are "
                    f"{RUNNERVALIDMODES}")

        if not ((self.initial in RUNNERVALIDINITIALS) or (self.initial is None) or validators.url(self.initial)):
            problems.append(f"{self.__class__}:{self.filename} 'initial' has not a valid value '{self.initial}'. "
                            f"Initial value may be any of {RUNNERVALIDINITIALS} or a valid URL or None")
        if (self.mode in RUNNERBATCHMODES) and (self.batchSize <= 0):
            problems.append(f"{self.__class__}:{self.filename} 'batchSize' value '{self.batchSize}' "
                            f"must be a positive integer for mode '{self.mode}'.")
        if not ((self.pollInterval is None) or (self.pollInterval.lower() in RUNNERVALIDPOLLINTERVALS)):
            problems.append(f"Provided mode '{self.pollInterval}'not valid. Valid modes are None or any of "
                            f"{RUNNERVALIDPOLLINTERVALS}")

        # TOTHINK: Check module exists?
        for msg in problems:
            logging.error(msg)

        return len(problems) == 0

    @classmethod
    def createFromFile(cls, filename: str):
        auxData = dict()
        auxData['filename'] = filename
        auxData['name'] = runnerConfFName2Name(filename)

        logging.debug(f" Reading runner config file: {filename}")
        auxData['data'] = parser = readConfigFile(filename)
        auxData.update(mergeConfFileIntoDataClass(cls, parser, 'RUNNER'))

        fileKeys = set(auxData.keys())
        requiredClassFields = {k for k, v in cls.__dataclass_fields__.items() if
                               not isinstance(v.default, (type(None), str, bool, int))}
        missingKeys = requiredClassFields.difference(fileKeys)

        if (missingKeys):
            logging.error(f"{filename}: missing required fields: {missingKeys}")
            raise KeyError(f"{filename}: missing required fields: {missingKeys}")

        result = cls(**auxData)

        return result


@dataclass
class globalConfig:
    filename: Optional[str] = None
    data: object = None
    saveDirectory: str = '.'
    imagesDirectory: str = 'images'
    metadataDirectory: str = 'metadata'
    stateDirectory: str = 'state'
    databaseDirectory:str = 'db'
    runnersCFG: str = 'etc/runners.d/*.conf'
    dryRun: bool = False
    dontSendEmails: bool = False
    dontSave: bool = False
    ignorePollInterval: bool = False
    mailCFG: Optional[mailConfig] = None
    runnersData: List[runnerConfig] = field(default_factory=list)
    requiredRunners: List[str] = field(default_factory=list)
    maxBatchSize: int = 7
    defaultPollInterval: Optional[str] = DEFAULTPOLLINTERVAL
    storeCFG:Optional[storeConfig] = None
    storeStateFiles:bool = True
    initializeStoreDB:bool = False
    verbose:bool = False

    @classmethod
    def createFromArgs(cls, args: Namespace):
        fielsAddedLater = {'runnersData'}
        auxData = dict()

        if 'config' in args:
            auxData['filename'] = args.config
            logging.debug(f" Reading global config file: {args.config}")
            auxData['data'] = parser = readConfigFile(args.config)

            auxData.update(mergeConfFileIntoDataClass(cls, parser, "GENERAL"))

            auxData['mailCFG'] = mailConfig.createFromParse(parser, args.config) if 'MAIL' in parser else None
            auxData['storeCFG'] = storeConfig.createFromParse(parser, args.config) if 'STORE' in parser else None

        if not args.requiredRunners:
            auxData['requiredRunners'] = []
        for field in cls.__dataclass_fields__:
            if field in args and args.__dict__[field]:

                auxArgValue = args.__dict__[field]
                argValue = auxArgValue.strip('"').strip("'") if isinstance(auxArgValue, str) else auxArgValue
                targetField = cls.__dataclass_fields__[field]

                auxData[field] = convertToDataClassField(argValue, targetField)
                if auxData.get('data', None) is not None:
                    auxData['data'].set('GENERAL', field, str(auxData[field]))

        fileKeys = set(auxData.keys())
        requiredClassFields = {k for k, v in cls.__dataclass_fields__.items() if
                               not isinstance(v.default, (type(None), str, bool, int))}
        missingKeys = requiredClassFields.difference(fileKeys).difference(fielsAddedLater)

        if (missingKeys):
            logging.error(f"{args.config}: missing required fields: {missingKeys}")
            raise KeyError(f"{args.config}: missing required fields: {missingKeys}")

        result = cls(**auxData)

        if args.debug:
            result.verbose = True

        result.runnersData = readRunnerConfigs(result.runnersCFG, result.homeDirectory())

        if not result.requiredRunners:
            result.requiredRunners = list(result.allRunners().keys())

        return result

    @classmethod
    def addSpecificParams(cls, parser: ArgParser):
        parser.add_argument('requiredRunners', nargs=REMAINDER)
        parser.add_argument('-c', '--config', dest='config', action="store", env_var='CS_CONFIG', required=False,
                            help='Fichero de configuración',
                            default="etc/cosecha.cfg")  # TODO: Quitar ese valor por defect

        parser.add_argument('-o', '--saveDir', dest='saveDirectory', type=str, env_var='CS_DATADIR',
                            help='Root directory to store things', required=False)
        parser.add_argument('-i', '--imageDir', dest='imagesDirectory', type=str, env_var='CS_DESTDIRIMG',
                            help='Location to store images (supersedes ${CS_DATADIR}/images', required=False)
        parser.add_argument('-m', '--metadataDir', dest='metadataDirectory', type=str, env_var='CS_DESTDIRMETA',
                            help='Location to store metadata files (supersedes ${CS_DATADIR}/metadata', required=False)
        parser.add_argument('-s', '--stateDir', dest='stateDirectory', type=str, env_var='CS_DESTDIRSTATE',
                            help='Location to store state files (supersedes ${CS_DATADIR}/state', required=False)
        parser.add_argument('-b', '--stateDatabase', dest='databaseDirectory', type=str, env_var='CS_DESTDIRDB',
                            help='Location to store database files (supersedes ${CS_DATADIR}/db', required=False)

        parser.add_argument('-r', '--runnersGlob', dest='runnersCFG', type=str, env_var='CS_RUNNERSCFG',
                            help='Glob for configuration files of runners', required=False)

        parser.add_argument('-n', '--dry-run', dest='dryRun', action="store_true", env_var='CS_DRYRUN',
                            help="Don't save or send emails", required=False)
        parser.add_argument('--ignore-poll-interval', dest='ignorePollInterval', action="store_true",
                            env_var='CS_NOSAVE', help="Don't check poll intervals", required=False)
        parser.add_argument('--no-emails', dest='dontSendEmails', action="store_true", env_var='CS_NOEMAILS',
                            help="Don't send emails", required=False)
        parser.add_argument('--no-save', dest='dontSave', action="store_true", env_var='CS_NOSAVE',
                            help="Don't save images", required=False)

        parser.add_argument('-x', '--maxBatchSize', dest='maxBatchSize', type=int,
                            help='Maximum number of images to download for a crawler', required=False)

        parser.add_argument('--initialize-db', dest='initializeStoreDB', action="store_true",
                            help="Create DB objects", required=False)


    def homeDirectory(self):
        return os.path.dirname(self.filename) if self.filename else '.'

    def imagesD(self) -> str:
        return path.join(self.saveDirectory, self.imagesDirectory)

    def metadataD(self) -> str:
        return path.join(self.saveDirectory, self.metadataDirectory)

    def stateD(self) -> str:
        return path.join(self.saveDirectory, self.stateDirectory)

    def databaseD(self) -> str:
        return path.join(self.saveDirectory, self.databaseDirectory)

    @classmethod
    def createStorePath(cls, field: str):
        makedirs(field, mode=0o755, exist_ok=True)

    def allRunners(self):
        dictRunners: Dict[str, runnerConfig] = {r.name: r for r in self.runnersData}

        return dictRunners


def readConfigFile(filename: str) -> ConfigParser:
    parser = ConfigParser()
    parser.read(filename)

    return parser


def mergeConfFileIntoDataClass(cls, parser: ConfigParser, sectionN: str) -> dict:
    result = dict()
    for field in cls.__dataclass_fields__:
        if field in parser[sectionN]:
            value2add = parser.get(sectionN, field).strip('"').strip("'")
            targetField = cls.__dataclass_fields__[field]

            result[field] = convertToDataClassField(value2add, targetField)
    return result


def runnerConfFName2Name(filename):
    fname = path.basename(filename)
    result = fname.rstrip(f".{RUNNERFILEEXTENSION}")

    return result


def readRunnerConfigs(confGlob: str, baseDir: Optional[str] = None) -> List[runnerConfig]:
    logging.debug(f"Searching runner conf files: baseDir: {baseDir} glob: {confGlob}")
    result = []

    confList = glob(confGlob, root_dir=baseDir)
    for f in confList:
        realFile = os.path.join(baseDir, f)

        try:
            newConfig = runnerConfig.createFromFile(realFile)
            result.append(newConfig)
        except Exception as exc:
            logging.error(f"Problems reading '{realFile}'. Ignoring. {exc}")

    return result


def convertToDataClassField(value, field: Field):
    if not isinstance(field.default, (str, bool, int)):
        return value  # Either is _MISSINGFIELD (or None) or a type we don't know about- There is nothing we can do

    if not isinstance(value, field.type):
        return field.type(value)

    return value


def parseDatatime(v):
    if isinstance(v, str):
        try:
            newV = datetime.strptime(v, TIMESTAMPFORMAT)
        except ValueError as exc:
            newV = datetime.strptime(v, TIMESTAMPFORMATORM)
        return newV
    elif isinstance(v, datetime):
        return v
    else:
        raise TypeError(f"Unable to process '{v}': don't know how to process it ({type(v)}")
