import logging
from argparse import Namespace
from configparser import ConfigParser
from dataclasses import dataclass, Field, field
from glob import glob
from os import makedirs, path
from typing import List, Optional

import validators
from configargparse import ArgParser

RUNNERFILEEXTENSION = "conf"

RUNNERVALIDMODES = {'poll', 'crawler'}
RUNNERVALIDINITIALS = {'*first', '*last'}
RUNNERBATCHMODES = {'crawler'}


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
class globalConfig:
    filename: Optional[str] = None
    data: object = None
    saveDirectory: str = '.'
    imagesDirectory: str = 'images'
    metadataDirectory: str = 'metadata'
    stateDirectory: str = 'state'
    defaultMode: str = 'poll'
    runnersCFG: str = 'etc/runners.d/*.conf'
    batchSize: int = 7
    dryRun: bool = False
    dontSendEmails: bool = False
    dontSave: bool = False
    mailCFG: mailConfig = None

    @classmethod
    def createFromArgs(cls, args: Namespace):

        auxData = dict()

        if 'config' in args:
            auxData['filename'] = args.config

            auxData['data'] = parser = readConfigFile(args.config)

            auxData.update(mergeConfFileIntoDataClass(cls, parser, "GENERAL"))

            auxData['mailCFG'] = mailConfig.createFromParse(parser, args.config)

        for field in cls.__dataclass_fields__:
            if field in args and args.__dict__[field]:

                argValue = args.__dict__[field].strip('"').strip("'")
                targetField = cls.__dataclass_fields__[field]

                auxData[field] = convertToDataClassField(argValue, targetField)
                if auxData.get('data', None) is not None:
                    auxData['data'].set('GENERAL', field, auxData[field])

        fileKeys = set(auxData.keys())
        requiredClassFields = {k for k, v in cls.__dataclass_fields__.items() if
                               not isinstance(v.default, (type(None), str, bool, int))}
        missingKeys = requiredClassFields.difference(fileKeys)

        if (missingKeys):
            logging.error(f"{args.config}: missing required fields: {missingKeys}")
            raise KeyError(f"{args.config}: missing required fields: {missingKeys}")

        result = cls(**auxData)

        return result

    @classmethod
    def addSpecificParams(cls, parser: ArgParser):
        parser.add_argument('-c', '--config', dest='config', action="store", env_var='CS_CONFIG', required=False,
                            help='Fichero de configuración',
                            default="etc/cosecha.cfg")  # TODO: Quitar ese valor por defect

        parser.add_argument('-o', dest='saveDirectory', type=str, env_var='CS_DATADIR',
                            help='Root directory to store things', required=False)
        parser.add_argument('-i', dest='imagesDirectory', type=str, env_var='CS_DESTDIRIMG',
                            help='Location to store images (supersedes ${CS_DATADIR}/images', required=False)
        parser.add_argument('-m', dest='metadataDirectory', type=str, env_var='CS_DESTDIRMETA',
                            help='Location to store metadata files (supersedes ${CS_DATADIR}/metadata', required=False)
        parser.add_argument('-s', dest='stateDirectory', type=str, env_var='CS_DESTDIRSTATE',
                            help='Location to store state files (supersedes ${CS_DATADIR}/state', required=False)

        parser.add_argument('-r', dest='runnersCFG', type=str, env_var='CS_RUNNERSCFG',
                            help='Glob for configuration files of runners', required=False)

        parser.add_argument('-n', '--dry-run', dest='dryRun', action="store_true", env_var='CS_DRYRUN',
                            help="Don't save or send emails", required=False)
        parser.add_argument('--no-emails', dest='dontSendEmails', action="store_true", env_var='CS_DRYRUN',
                            help="Don't send emails", required=False)
        parser.add_argument('--no-save', dest='dontSave', action="store_true", env_var='CS_DRYRUN',
                            help="Don't save images", required=False)

    def imagesD(self) -> str:
        return path.join(self.saveDirectory, self.imagesDirectory)

    def metadataD(self) -> str:
        return path.join(self.saveDirectory, self.metadataDirectory)

    def stateD(self) -> str:
        return path.join(self.saveDirectory, self.stateDirectory)

    @classmethod
    def createStorePath(cls, field: str):
        makedirs(field, mode=0o755, exist_ok=True)


@dataclass
class runnerConfig:
    module: str
    data: object
    enabled: bool = True
    filename: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    mode: str = globalConfig.__dataclass_fields__['defaultMode'].default
    initial: Optional[str] = '*last'
    batchSize: int = globalConfig.__dataclass_fields__['batchSize'].default

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
        # TOTHINK: Check module exists?
        for msg in problems:
            logging.error(msg)

        return (len(problems) == 0)

    @classmethod
    def createFromFile(cls, filename: str):
        auxData = dict()
        auxData['filename'] = filename
        auxData['name'] = runnerConfFName2Name(filename)

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
    result = []
    confList = glob(confGlob, root_dir=baseDir)
    for f in confList:
        try:
            newConfig = runnerConfig.createFromFile(f)
            result.append(newConfig)
        except Exception as exc:
            logging.error(f"Problems reading '{f}'. Ignoring.", exc_info=exc)

    return result


def convertToDataClassField(value, field: Field):
    if not isinstance(field.default, (str, bool, int)):
        return value  # Either is _MISSINGFIELD (or None) or a type we don't know about- There is nothing we can do

    if not isinstance(value, field.type):
        return field.type(value)

    return value
