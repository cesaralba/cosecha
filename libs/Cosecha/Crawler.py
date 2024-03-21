import logging
import sys
from importlib import import_module
from io import UnsupportedOperation
from os import makedirs

import validators

from libs.Utils.Config import globalConfig, runnerConfig
from libs.Utils.Files import loadYAML, saveYAML
from libs.Utils.Misc import createPath
from .ComicPage import ComicPage


class Crawler:
    def __init__(self, runnerCFG: runnerConfig, globalCFG: globalConfig):
        self.runnerCFG = runnerCFG
        self.globalCFG = globalCFG
        self.name = self.runnerCFG.name
        self.state = CrawlerState(self.name, self.globalCFG.stateD()).load()
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
        logging.info(f"Runner: '{self.name}' Crawling")
        remainingImgs = int(self.runnerCFG.batchSize)
        while remainingImgs > 0:
            try:
                if self.state.lastURL is None:
                    self.obj.downloadPage()
                    initialLink = self.runnerCFG.initial.lower()
                    if (initialLink == '*first'):
                        self.obj = self.module.Page(self.obj.linkFirst)
                    elif (initialLink == '*last'):
                        # We are already on last edited picture
                        pass
                    elif validators.url(self.runnerCFG.initial):
                        self.obj = self.module.Page(self.runnerCFG.initial)
                    else:
                        raise ValueError(f"Runner: '{self.name}' {self.runnerCFG.filename}:Unknown initial value:'"
                                         f"{self.runnerCFG.initial}'")
                self.obj.downloadPage()
                if not self.obj.exists(self.globalCFG.imagesD(), self.globalCFG.metadataD()):
                    logging.debug(f"'{self.name}': downloading new image")
                    self.obj.downloadMedia()
                    self.obj.saveFiles(self.globalCFG.imagesD(), self.globalCFG.metadataD())
                    self.results.append(self.obj)
                    self.state.update(self)
                    remainingImgs -= 1
                else:
                    logging.debug(f"'{self.name}' {self.obj.URL}: already downloaded")
                self.obj = self.obj = self.module.Page(self.obj.linkNext)
            except Exception as exc:
                logging.error(f"Crawler(crawl)'{self.name}': problem:{type(exc)} {exc}")
                break

    def poll(self):
        logging.info(f"'{self.name}' Polling")
        try:
            self.obj.downloadPage()
            if not self.obj.exists(self.globalCFG.imagesD(), self.globalCFG.metadataD()):
                logging.debug(f"'{self.name}': downloading new image {self.obj.URL} -> {self.obj.mediaURL}")
                self.obj.downloadMedia()
                self.obj.saveFiles(self.globalCFG.imagesD(), self.globalCFG.metadataD())
                self.results.append(self.obj)
                self.state.update(self)
            else:
                logging.debug(f"'{self.name}': already downloaded")
        except Exception as exc:
            logging.error(f"Crawler(poll)'{self.name}': problem:{type(exc)} {exc}")


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
