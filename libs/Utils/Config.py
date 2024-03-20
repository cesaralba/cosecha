from collections import namedtuple
from configparser import ConfigParser
from dataclasses import dataclass
from glob import glob
from os import makedirs, path
from typing import Optional

RUNNERFILEEXTENSION = "conf"

runnerConfig = namedtuple('runnerConfig', ['filename', 'name', 'module', 'mode', 'initial', 'batchSize'],
                          defaults=('poll', '*last', '7'))


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

    def imagesD(self) -> str:
        return path.join(self.saveDirectory, self.imagesDirectory)

    def metadataD(self) -> str:
        return path.join(self.saveDirectory, self.metadataDirectory)

    def stateD(self) -> str:
        return path.join(self.saveDirectory, self.stateDirectory)

    @classmethod
    def createStorePath(cls, field: str):
        makedirs(field, mode=0o755, exist_ok=True)


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
    confList = glob(confGlob, root_dir=baseDir)
    result = [readRunnerConfig(f) for f in confList]

    return result
