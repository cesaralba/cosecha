
from time import gmtime
from os import makedirs, path
import logging
from abc import ABCMeta, abstractmethod
import json
logger = logging.getLogger()


class ComicPage(metaclass=ABCMeta):

    def __init__(self, key: str, URL: str=None):
        self.URL = URL
        self.key = key
        self.timestamp = gmtime()
        self.date = None  # Date from page (if nay)
        self.comicId = None  # Any identifier related to page (if any)
        self.mediaURL = None
        self.data = None  # Actual image
        self.mediaHash = None
        self.info = {'key':key}  # Dict containing metadata related to page (alt text, title...)
        self.saveFilePath = None
        self.saveMetadataPath = None

        # Navigational links on page (if any)
        self.linkNext = None
        self.linkPrev = None
        self.linkFirst = None
        self.linkLast = None

    @abstractmethod
    def downloadPage(self,downloadFile=True):
        """Downloads the page of the object and fills in fields"""
        raise NotImplementedError

    @abstractmethod
    def updateInfo(self):
        """Builds a dataFilename for the image"""
        raise NotImplementedError

    @abstractmethod
    def dataFilename(self):
        """Builds a dataFilename for the image"""
        raise NotImplementedError

    @abstractmethod
    def metadataFilename(self):
        """Builds a dataFilename for the image"""
        raise NotImplementedError

    @abstractmethod
    def dataPath(self):
        """Builds a path for the image"""
        raise NotImplementedError

    @abstractmethod
    def metadataPath(self):
        """Builds a path for the image"""
        raise NotImplementedError

    def saveFiles(self, rootFolder: str = "output"):
        if self.data is None:
            raise ValueError("saveFile: empty file")

        dataFullPath = path.join(rootFolder, self.dataPath())
        makedirs(dataFullPath,mode=0o755,exist_ok=True)
        dataFilename = path.join(dataFullPath, self.dataFilename())

        with open(dataFilename, "wb") as bin_file:
            bin_file.write(self.data)
        self.saveFilePath = dataFilename

        self.updateInfo()
        metaFullPath = path.join(rootFolder, self.metadataPath())
        makedirs(metaFullPath,mode=0o755,exist_ok=True)
        metadataFilename = path.join(metaFullPath, self.metadataFilename())

        with open(metadataFilename, "w") as metadata_file:
            json.dump(self.info,metadata_file,indent=2,sort_keys=True)
            metadata_file.write('\n')

        self.saveMetadataPath = metadataFilename

    #TODO: updateDB
    #TODO: mailContent