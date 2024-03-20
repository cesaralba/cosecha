import logging
import sys
from importlib import import_module
from io import UnsupportedOperation
from os import makedirs

from libs.Utils.Config import globalConfig, runnerConfig
from libs.Utils.Files import loadYAML, saveYAML
from libs.Utils.Misc import createPath
from .ComicPage import ComicPage


class Crawler:
    def __init__(self, runnerCFG: runnerConfig, globalCFG: globalConfig):
        self.runnerCFG = runnerCFG
        self.globalCFG = globalCFG
        self.state = CrawlerState(self.runnerCFG.name, self.globalCFG.stateD()).load()
        self.module = self.RunnerModule(self.runnerCFG.module)
        self.obj: ComicPage = self.module.Page(self.state.lastURL)
        self.results = list()

    def RunnerModule(self, moduleName: str, classLocation: str = "libs.Cosecha.Sites"):
        fullModName = f"{classLocation}.{moduleName}"

        if fullModName not in sys.modules:
            import_module(fullModName, classLocation)

        return sys.modules[fullModName]

    def go(self):
        if self.runnerCFG.mode == "crawler":
            self.crawl()
        elif self.runnerCFG.mode == "poll":
            self.poll()
        else:
            raise TypeError(f"Unknown mode '{self.runnerCFG.mode}'")

    def crawl(self):
        logging.info(f"'{self.runnerCFG.name}' Crawling")
        pass

    def poll(self):
        logging.info(f"'{self.runnerCFG.name}' Polling")
        self.obj.downloadPage()
        if not self.obj.exists(self.globalCFG.imagesD(), self.globalCFG.metadataD()):
            logging.debug(f"'{self.runnerCFG.name}': new image")
            self.obj.downloadMedia()
            self.obj.saveFiles(self.globalCFG.imagesD(), self.globalCFG.metadataD())
            self.results.append(self.obj)
            self.state.update(self)
        else:
            logging.debug(f"'{self.runnerCFG.name}': already downloaded")


class CrawlerState:
    stateElements = {'lastId': 'str', 'lastUpdated': 'timestamp', 'lastURL': 'str', 'lastMedia': 'str'}

    def __init__(self, runnerName: str, storePath: str):
        self.runner = runnerName
        self.storePath = storePath
        self.lastId = None
        self.lastUpdated = None
        self.lastURL = None
        self.lastMedia = None
        self.media = dict()

    def fullFilename(self):
        result = f"{self.runner}.state"
        return result

    def completePath(self):
        result = createPath(self.storePath, self.fullFilename())

        return result

    def update(self, crawler: Crawler):
        self.lastId = crawler.obj.comicId
        self.lastUpdated = crawler.obj.info['timestamp']
        self.lastURL = crawler.obj.URL
        self.lastMedia = crawler.obj.mediaURL

    def load(self):
        try:
            inHash = loadYAML(self.completePath())

            for k, v in inHash.items():
                setattr(self, k, v)
        except FileNotFoundError as exc:
            logging.warning(f"Unable to find {self.completePath()}. Will act as if it is the first time.")
        except UnsupportedOperation as exc:
            logging.warning(f"Problems reading {self.completePath()}. Will act as if it is the first time.", exc)
        return self

    def store(self):
        makedirs(self.storePath, mode=0o755, exist_ok=True)
        outHash = {k: getattr(self, k) for k in self.stateElements}

        saveYAML(outHash, self.completePath())
