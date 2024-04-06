import logging
from calendar import timegm
from datetime import datetime
from io import UnsupportedOperation
from os import makedirs
from time import localtime, mktime, strptime, struct_time
from typing import Optional

import validators

from libs.Utils.Files import loadYAML, saveYAML
from libs.Utils.Misc import createPath
from .ComicPage import ComicPage
from .Config import globalConfig, runnerConfig, RUNNERVALIDPOLLINTERVALS, TIMESTAMPFORMAT
from ..Utils.Python import RunnerModule


class Crawler:
    def __init__(self, runnerCFG: runnerConfig, globalCFG: globalConfig):
        self.runnerCFG = runnerCFG
        self.globalCFG = globalCFG
        self.name = self.runnerCFG.name
        self.state = CrawlerState(self.name, self.globalCFG.stateD()).load()
        self.module = RunnerModule(self.runnerCFG.module)
        self.obj: ComicPage = self.module.Page(URL=self.state.lastURL, **dict(self.runnerCFG.data['RUNNER']))
        self.key: str = self.obj.key
        self.results = list()

        if self.state.lastUpdated is None:
            # Either it is a new Crawler (ever) or it hasn't downloaded anything. It does not matter the poll interval
            self.runnerCFG.pollInterval = None

    def __str__(self):
        result = (f"[Crawler: '{self.name}' [{self.key},{self.runnerCFG.module},{self.runnerCFG.mode}] Results: "
                  f"{len(self.results)}")
        return result

    __repr__ = __str__

    def title(self):
        if self.runnerCFG.title is not None:
            return self.runnerCFG.title
        return self.name

    def go(self):
        if self.runnerCFG.mode == "crawler":
            self.crawl()
        elif self.runnerCFG.mode == "poll":
            self.poll()
        else:
            raise TypeError(f"Unknown mode '{self.runnerCFG.mode}'")

    def crawl(self):
        remainingImgs = min(self.runnerCFG.batchSize, self.globalCFG.maxBatchSize)
        logging.debug(f"Crawler '{self.name}: batchSize: from global {self.globalCFG.maxBatchSize} from conf "
                      f"{self.runnerCFG.batchSize} -> {remainingImgs}")
        logging.info(f"Runner: '{self.name}'[{self.runnerCFG.module}] Crawling")
        downloadedOnce = False
        while remainingImgs > 0:
            try:
                if (self.state.lastURL is None) and not downloadedOnce:
                    self.obj.downloadPage()
                    initialLink = self.runnerCFG.initial.lower()
                    if initialLink == '*first':
                        self.obj = self.module.Page(key=self.key, URL=self.obj.linkFirst)
                    elif initialLink == '*last':
                        # We should already be on last edited picture but just in case
                        if self.obj.linkLast and self.obj.linkLast != self.obj.URL:
                            self.obj = self.module.Page(key=self.key, URL=self.obj.linkLast)
                    elif validators.url(self.runnerCFG.initial):
                        self.obj = self.module.Page(key=self.key, URL=self.runnerCFG.initial)
                    else:
                        raise ValueError(f"Runner: '{self.name}' {self.runnerCFG.filename}:Unknown initial value:'"
                                         f"{self.runnerCFG.initial}'")
                self.obj.downloadPage()
                downloadedOnce = True
                if not self.obj.exists(self.globalCFG.imagesD(), self.globalCFG.metadataD()):
                    logging.debug(f"'{self.name}': downloading new image")
                    self.obj.downloadMedia()
                    self.results.append(self.obj)
                    remainingImgs -= 1
                    self.state.update(self.obj)
                else:
                    logging.debug(f"'{self.name}' {self.obj.URL}: already downloaded")
                if self.obj.linkNext and self.obj.linkNext != self.obj.URL:
                    self.obj = self.module.Page(key=self.key, URL=self.obj.linkNext)
                else:
                    break
            except Exception as exc:
                logging.error(f"Crawler(crawl)'{self.name}': problem:{type(exc)} {exc}")
                logging.exception(exc, stack_info=True)
                break

    def poll(self):
        logging.info(f"Runner: '{self.name}'[{self.runnerCFG.module}] Polling")
        try:
            self.obj.downloadPage()
            logging.debug(f"'{self.name}': downloading new image {self.obj.URL} -> {self.obj.mediaURL}")
            if self.obj.linkLast and self.obj.linkLast != self.obj.URL:
                self.obj = self.module.Page(key=self.key, URL=self.obj.linkLast)
                self.obj.downloadPage()
            elif self.obj.linkNext and self.obj.linkNext != self.obj.URL:
                while (self.obj.linkNext and self.obj.linkNext != self.obj.URL):
                    self.obj = self.module.Page(key=self.key, URL=self.obj.linkNext)
                    self.obj.downloadPage()
            if not self.obj.exists(self.globalCFG.imagesD(), self.globalCFG.metadataD()):
                logging.debug(f"'{self.name}': downloading new image {self.obj.URL} -> {self.obj.mediaURL}")
                self.obj.downloadMedia()
                self.results.append(self.obj)
            else:
                logging.debug(f"'{self.name}': already downloaded")
        except Exception as exc:
            logging.error(f"Crawler(poll)'{self.name}': problem:{type(exc)} {exc}")
            logging.exception(exc, stack_info=True)

    def checkPollSlot(self, now: struct_time) -> bool:
        """
        Checks if now is in a different poll spot than last successful one

        :param now: struct_time with now (localtime)
        :return: false -> can't poll ; true (not same period) -> can poll (info extracted for DoY or Month)
        """
        mode = self.runnerCFG.pollInterval
        if not ((mode is None) or (mode.lower() in RUNNERVALIDPOLLINTERVALS)):
            raise KeyError(
                    f"Provided mode '{mode}'not valid. Valid modes are None or any of {RUNNERVALIDPOLLINTERVALS}")

        if mode is None:
            return True

        if mode.lower() in {'weekly', 'biweekly'}:
            weekPoll = datetime.fromtimestamp(mktime(self.state.lastPoll)).isocalendar().week
            weekNow = datetime.fromtimestamp(mktime(now)).isocalendar().week

        match mode.lower():
            case 'none':
                return True
            case 'daily':
                return self.state.lastPoll.tm_yday != now.tm_yday
            case 'weekly':
                return weekPoll != weekNow
            case 'biweekly':
                return (weekPoll // 2) != (weekNow // 2)
            case 'monthly':
                return self.state.lastPoll.tm_mon != now.tm_mon
            case 'bimonthly':
                return (self.state.lastPoll.tm_mon // 2) != (now.tm_mon // 2)
            case 'quarterly':
                return (self.state.lastPoll.tm_mon // 3) != (now.tm_mon // 3)

        raise KeyError("It shouldn't have got here")


class CrawlerState:
    stateElements = {'lastId': 'str', 'lastUpdated': 'timestamp', 'lastURL': 'str', 'lastMediaURL': 'str'}

    def __init__(self, runnerName: str, storePath: str):
        self.runnerName = runnerName
        self.storePath = storePath
        self.lastId = None
        self.lastUpdated = None
        self.lastURL = None
        self.lastMediaURL = None
        self.media = dict()
        self.lastPoll: Optional[struct_time] = None

    def fullFilename(self):
        result = f"{self.runnerName}.state"
        return result

    def completePath(self):
        result = createPath(self.storePath, self.fullFilename())

        return result

    def update(self, state: ComicPage):
        self.lastId = state.comicId
        self.lastUpdated = state.info['timestamp']
        self.lastURL = state.URL
        self.lastMediaURL = state.mediaURL

    def load(self):
        try:
            inHash = loadYAML(self.completePath())

            for k, v in inHash.items():
                setattr(self, k, v)
        except FileNotFoundError as exc:
            logging.warning(f"Unable to find {self.completePath()}. Will act as if it is the first time.")
        except UnsupportedOperation as exc:
            logging.warning(f"Problems reading {self.completePath()}. Will act as if it is the first time.", exc)

        if self.lastUpdated:
            self.lastPoll = localtime(timegm(strptime(self.lastUpdated, TIMESTAMPFORMAT)))  # It compares times in local

        return self

    def store(self):
        makedirs(self.storePath, mode=0o755, exist_ok=True)
        outHash = {k: getattr(self, k) for k in self.stateElements}

        saveYAML(outHash, self.completePath())
