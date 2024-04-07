from os import makedirs, path

from pony.orm import db_session, ObjectNotFound, set_sql_debug, commit

from libs.Cosecha.StoreManager import DBStorageBackendBase
from .DBstore import DB
from .ImageDB import ChannelStateDB, ImageMetadataDB

# https://docs.ponyorm.org/api_reference.html#sqlite

VALIDPROVIDERS = {'sqlite'}
SQLITENONPATHPROVIDERS = {':memory:', ':sharedmemory:'}

session_manager = db_session
XXXX = commit # To save it from import clean up

class CosechaStore(DBStorageBackendBase):
    def __init__(self, **kwargs):
        auxGlobalCFG = kwargs.pop('globalCFG', None)
        auxStoreCFG = kwargs.pop('storeCFG', None)

        super().__init__(globalCFG=auxGlobalCFG, storeCFG=auxStoreCFG, **kwargs)

        self.db = DB

        self.validateBackendData()

    def connect(self, **kwargs):
        initial = kwargs.get('initial', False)
        finalBindParams = self.tunedParamsBind(initial=initial)

        set_sql_debug(debug=self.verbose, show_values=self.verbose)
        self.db.bind(**finalBindParams)
        self.db.generate_mapping(check_tables=True, create_tables=initial)

    def validateBackendData(self):
        requiredKeys = {'provider'}
        requiredKeysPerProvider = {'sqlite': {'filename'}
                                   }

        backendData = self.storeCFG.backendData

        missingBaseKeys = requiredKeys.difference(set(backendData.keys()))

        if missingBaseKeys:
            raise KeyError(f"Missing keys: {missingBaseKeys}. Required keys: {requiredKeys}")

        provider = backendData['provider']

        reqProvKeys = requiredKeys.union(requiredKeysPerProvider[provider])
        missingProvKeys = reqProvKeys.difference(set(backendData.keys()))

        if missingProvKeys:
            raise KeyError(f"Missing keys: {missingProvKeys}. Required keys: {reqProvKeys}")

    def tunedParamsBind(self, initial: bool = False) -> dict:

        backendData = self.storeCFG.backendData
        result = backendData.copy()
        provider = backendData['provider']

        extraParams = dict()
        if provider == 'sqlite':
            filename = backendData['filename']
            if filename not in {':sharedmemory:', ':memory:'}:
                dbFullPath = path.realpath(self.globalCFG.databaseD())
                makedirs(dbFullPath, mode=0o755, exist_ok=True)
                dbFilename = path.join(dbFullPath, filename)
                extraParams['filename'] = dbFilename
        else:
            raise ValueError(f"We shouldn't have reached here. Provider: '{provider}'")

        if initial:
            extraParams['create_db'] = initial

        result.update(extraParams)

        return result

    CrawlerState = ChannelStateDB
    ImageMetadata = ImageMetadataDB
    RowNotFound = ObjectNotFound
