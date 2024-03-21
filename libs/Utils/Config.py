import logging
from configparser import ConfigParser
from dataclasses import dataclass
from glob import glob
from os import makedirs, path
from typing import Optional

import validators
from configargparse import ArgumentParser

RUNNERFILEEXTENSION = "conf"


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

    @classmethod
    def createFromArgs(cls, args: ArgumentParser):
        #TODO:
        pass

    def imagesD(self) -> str:
        return path.join(self.saveDirectory, self.imagesDirectory)

    def metadataD(self) -> str:
        return path.join(self.saveDirectory, self.metadataDirectory)

    def stateD(self) -> str:
        return path.join(self.saveDirectory, self.stateDirectory)

    @classmethod
    def createStorePath(cls, field: str):
        makedirs(field, mode=0o755, exist_ok=True)


RUNNERVALIDMODES = {'poll', 'crawler'}
RUNNERVALIDINITIALS = {'*first', '*last'}
RUNNERBATCHMODES = {'crawler'}


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

        parser = ConfigParser()
        parser.read(filename)

        auxData['data'] = parser

        for field in cls.__dataclass_fields__:
            if field in parser['RUNNER']:
                auxData[field] = parser.get('RUNNER', field).strip('"').strip("'")

        fileKeys = set(auxData.keys())
        requiredClassFields = {k for k, v in cls.__dataclass_fields__.items() if
                               not isinstance(v.default, (type(None), str, bool, int))}
        missingKeys = requiredClassFields.difference(fileKeys)

        if (missingKeys):
            logging.error(f"{filename}: missing required fields: {missingKeys}")
            raise KeyError(f"{filename}: missing required fields: {missingKeys}")

        result = cls(**auxData)

        return result


def readConfig(filename: str):
    parser = ConfigParser()

    parser.read(filename)


def runnerConfFName2Name(filename):
    fname = path.basename(filename)
    result = fname.rstrip(f".{RUNNERFILEEXTENSION}")

    return result


def readRunnerConfig(filename: str) -> runnerConfig:
    auxResult = dict()
    auxResult['filename'] = filename
    auxResult['name'] = runnerConfFName2Name(filename)

    parser = ConfigParser()
    parser.read(filename)

    for field in runnerConfig._fields:
        if field in parser['RUNNER']:
            auxResult[field] = parser.get('RUNNER', field).strip('"').strip("'")

    result = runnerConfig(**auxResult)

    return result


def readRunnerConfigs(confGlob: str, baseDir: Optional[str] = None) -> list[runnerConfig]:
    result = []
    confList = glob(confGlob, root_dir=baseDir)
    for f in confList:
        try:
            newConfig = runnerConfig.createFromFile(f)
            result.append(newConfig)
        except Exception as exc:
            logging.error(f"Problems reading '{f}'. Ignoring.", exc_info=exc)

    return result
