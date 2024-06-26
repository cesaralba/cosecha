import logging
from datetime import datetime, timezone
from io import UnsupportedOperation
from os import makedirs
from time import struct_time
from typing import Callable, Dict, List, Optional

import validators
from requests import HTTPError

from libs.Utils.Files import loadYAML, saveYAML
from libs.Utils.Misc import createPath, getUTC, UTC2local
from .ComicPage import ComicPage
from .Config import globalConfig, parseDatatime, runnerConfig, RUNNERVALIDPOLLINTERVALS
from .StoreManager import DBStorage
from ..Utils.Python import LoadModule

commit: Optional[Callable] = None


class Crawler:
    def __init__(self, runnerCFG: runnerConfig, globalCFG: globalConfig, dbStore: Optional[DBStorage] = None):
        self.runnerCFG: runnerConfig = runnerCFG
        self.globalCFG: globalConfig = globalCFG
        self.dataStore: DBStorage = dbStore
        self.name = self.runnerCFG.name
        self.state: CrawlerState = CrawlerState(runnerName=self.name, storePath=self.globalCFG.stateD(),
                                                dbstore=self.dataStore, storeJSON=self.globalCFG.storeJSON).load()
        self.fullModuleName, self.module = LoadModule(moduleName=self.runnerCFG.module,
                                                      classLocation="libs.Cosecha.Sites")
        self.obj: ComicPage = self.module.Page(URL=self.state.lastURL, **dict(self.runnerCFG.data['RUNNER']))
        self.key: str = self.obj.key
        self.results: List[ComicPage] = list()

        logging.debug(f"CrawlerState: {self.state}")
        global commit
        if commit is None:
            commit = self.dataStore.module.commit

        if self.state.lastUpdated is None:
            # Either it is a new Crawler (ever) or it hasn't downloaded anything, it does not matter the poll interval
            self.runnerCFG.pollInterval = None

    def __str__(self):
        result = (f"[Crawler: '{self.name}' [{self.key},{self.runnerCFG.module},{self.runnerCFG.mode}] Results: "
                  f"{len(self.results)}")
        return result

    __repr__ = __str__

    def __len__(self):
        return len(self.results)

    def size(self):
        return sum([img.size() for img in self.results])

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
                    self.state.updateFromImage(self.obj)
                else:
                    logging.debug(f"'{self.name}' {self.obj.URL}: already downloaded")
                if self.obj.linkNext and self.obj.linkNext != self.obj.URL:
                    self.obj = self.module.Page(key=self.key, URL=self.obj.linkNext)
                else:
                    break
            except HTTPError as exc:
                logging.error(
                        f"Crawler(crawl) '{self.name}': Problems downloading media {self.obj.URL}: {self.obj.mediaURL} "
                        f"{exc}")
                break
            except Exception as exc:
                logging.error(f"Crawler(crawl) '{self.name}': problem:{type(exc)} {exc}")
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
        except HTTPError as exc:
            logging.error(
                    f"Crawler(poll) '{self.name}': Problems downloading media {self.obj.URL}: {self.obj.mediaURL} "
                    f"{exc}")
        except Exception as exc:
            logging.error(f"Crawler(poll) '{self.name}': problem:{type(exc)} {exc}")
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
        if self.state.lastUpdated is None:
            return True

        DATEpoll = UTC2local(self.state.lastUpdated)
        DATEnow = UTC2local(getUTC())
        logging.debug(f"checkPollSlot: Mode: {mode} Poll: {DATEpoll} Now: {DATEnow}")
        if mode.lower() in {'weekly', 'biweekly'}:
            weekPoll = DATEpoll.isocalendar().week
            weekNow = DATEnow.isocalendar().week

            match mode.lower():
                case 'weekly':
                    return weekPoll != weekNow
                case 'biweekly':
                    return (weekPoll // 2) != (weekNow // 2)

        match mode.lower():
            case 'none':
                return True
            case 'daily':
                return DATEpoll.timetuple().tm_yday != DATEnow.timetuple().tm_yday
            case 'monthly':
                return DATEpoll.month != DATEnow.month
            case 'bimonthly':
                return (DATEpoll.month // 2) != (DATEnow.month // 2)
            case 'quarterly':
                return (DATEpoll.month // 3) != (DATEnow.month // 3)

        raise KeyError("It shouldn't have got here")


class CrawlerState:
    stateElements = {'lastId', 'lastUpdated', 'lastURL', 'lastMediaURL'}
    keyTranslations = {'lastMedia': 'lastMediaURL'}

    def __init__(self, runnerName: str, storePath: Optional[str] = None, dbstore: Optional[DBStorage] = None,
                 storeJSON: bool = True
                 ):
        self.runnerName: str = runnerName
        self.storePath: str = storePath
        self.DBstore: DBStorage = dbstore
        self.storeJSON: bool = storeJSON
        self.lastId: Optional[str] = None
        self.lastUpdated: Optional[datetime] = None
        self.lastURL: Optional[str] = None
        self.lastMediaURL: Optional[str] = None
        self.media: Dict = dict()
        self.record = None

        if self.DBstore is None and self.storePath is None:
            raise ValueError("No storage provided, at least storePath or DBstore must be provided")

        if self.storeJSON and not self.storePath:
            raise ValueError("Storage of State files requested but no storePath be provided")

    def __str__(self):
        result = "CrawlerState" + " ".join([f"{k}={getattr(self, k)} [{type(getattr(self, k))}]" for k in
                                            (["runnerName"] + list(self.stateElements))])

        return result

    __repr__ = __str__

    def fullFilename(self):
        result = f"{self.runnerName}.state"
        return result

    def completePath(self):
        result = createPath(self.storePath, self.fullFilename())

        return result

    def updateFromImage(self, image: ComicPage):
        """
        Updates the fields with the latest image downloaded in channel
        :param image:
        :return:
        """
        self.lastId = image.comicId
        self.lastUpdated = image.timestamp
        self.lastURL = image.URL
        self.lastMediaURL = image.mediaURL

    def load(self):
        missingState = False
        if self.DBstore is not None:
            try:
                dbData = self.DBstore.obj.CrawlerState[self.runnerName]
                self.record = dbData
                auxData = dbData.to_dict().copy()
                auxData['lastUpdated'] = auxData['lastUpdated'].replace(tzinfo=timezone.utc)
                self.updateStateFromReadData(auxData)
            except self.DBstore.obj.RowNotFound as exc:
                missingState = True
            except Exception as exc:
                logging.exception(exc, exc_info=True)
                raise KeyError(f"Key {self.runnerName} not found on states DB. Ignoring crawler")
            if not missingState:
                return self
        if self.storeJSON:
            try:
                inHash = loadYAML(self.completePath())
                self.updateStateFromReadData(inHash)

            except FileNotFoundError as exc:
                logging.warning(f"Unable to find state for {self.runnerName}. Will act as if it were the first time.")
            except UnsupportedOperation as exc:
                logging.warning(
                    f"Problems reading state for {self.runnerName}. Will act as if it were the first time. {exc}")

        return self

    def store(self):

        if self.DBstore:
            self.updateDBrecord()
        if self.storeJSON:
            makedirs(self.storePath, mode=0o755, exist_ok=True)
            outHash = {k: getattr(self, k) for k in self.stateElements}
            saveYAML(outHash, self.completePath())

    def updateStateFromReadData(self, newData: dict):
        for k, v in newData.items():
            if k == 'lastUpdated':
                setattr(self, k, parseDatatime(v))
            elif k in self.stateElements:
                setattr(self, k, v)
            elif k in self.keyTranslations:
                setattr(self, self.keyTranslations[k], v)

    def createDBrecord(self):
        newData = {k: getattr(self, k) for k in self.stateElements}
        newData['runnerName'] = self.runnerName

        dbData = self.DBstore.obj.CrawlerState(**newData)
        commit()

        return dbData

    def updateDBrecord(self):
        try:
            currRecord = self.DBstore.obj.CrawlerState[self.runnerName]
            newElems = {k: getattr(self, k) for k in self.stateElements if getattr(self, k) != getattr(currRecord, k)}
            currRecord.set(**newElems)
            result = self.DBstore.obj.CrawlerState[self.runnerName]
            commit()
            return result
        except self.DBstore.obj.RowNotFound as exc:
            newRecord = self.createDBrecord()
            return newRecord
