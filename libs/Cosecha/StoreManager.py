from abc import ABCMeta, abstractmethod

from .Config import globalConfig,storeConfig
from ..Utils.Python import LoadModule

commit = None
session_manager = None

class DBStorageBackendBase(metaclass=ABCMeta):
    def __init__(self, **kwargs):
        auxGlobalCFG = kwargs.get('globalCFG', None)
        if not auxGlobalCFG:
            raise KeyError("Missing 'globalCFG' parameter")

        self.globalCFG:globalConfig=auxGlobalCFG
        self.storeCFG:storeConfig=self.globalCFG.storeCFG
        self.verbose=self.globalCFG.verbose

    @abstractmethod
    def connect(self,**kwargs):
        """Prepares the connection to the actual database"""
        raise NotImplementedError

    @abstractmethod
    def validateBackendData(self):
        """Checks that the parameters passed for the backend are valid"""
        raise NotImplementedError

    session_manager = None
    commit = None
    CrawlerState = None
    ImageMetadata = None
    RowNotFound = None


class DBStorage:
    def __init__(self, globalCFG:globalConfig):
        self.globalCFG:globalConfig = globalCFG
        self.storeCFG:storeConfig = globalCFG.storeCFG
        self.fullModuleName, self.module = LoadModule(moduleName=self.storeCFG.backend,classLocation="libs.Cosecha.Backends")
        self.obj = self.module.CosechaStore(globalCFG=self.globalCFG)

    def prepare(self):
        self.obj.connect(initial=self.globalCFG.initializeStoreDB)
