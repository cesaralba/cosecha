import logging
from abc import ABCMeta, abstractmethod
from os import makedirs, path
from time import gmtime, strftime
from urllib.parse import urlsplit

import magic

from libs.Utils.Files import extensionFromType, loadYAML, saveYAML, shaData, shaFile
from libs.Utils.Web import DownloadRawPage

logger = logging.getLogger()


class ComicPage(metaclass=ABCMeta):

    def __init__(self, key: str, URL: str = None):
        self.URL = URL
        self.key = key
        self.timestamp = gmtime()
        self.date = None  # Date from page (if nay)
        self.comicId = None  # Any identifier related to page (if any)
        self.mediaURL = None
        self.data = None  # Actual image
        self.mediaHash = None
        self.info = {'key': key}  # Dict containing metadata related to page (alt text, title...)
        self.saveFilePath = None
        self.saveMetadataPath = None

        # Navigational links on page (if any)
        self.linkNext = None
        self.linkPrev = None
        self.linkFirst = None
        self.linkLast = None

    @abstractmethod
    def downloadPage(self):
        """Downloads the page of the object and fills in fields"""
        raise NotImplementedError

    def downloadMedia(self):
        if self.mediaURL is None:
            self.downloadPage()

        if self.mediaURL is None:
            raise ValueError(f"Unable to find media {self.URL}")

        img = DownloadRawPage(self.mediaURL, here=self.URL, allow_redirects=True)
        self.timestamp = self.info['timestamp'] = strftime("%Y%m%d-%H%M%S %z", img.timestamp)
        self.data = img.data
        self.info['mediaURL'] = self.mediaURL = img.source
        self.info['mediaHash'] = self.mediaHash = shaData(img.data)
        self.info['mimeType'] = magic.detect_from_content(self.data).mime_type

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

    def saveFiles(self, imgFolder: str, metadataFolder: str):
        if self.data is None:
            raise ValueError("saveFile: empty file")

        dataFullPath = path.join(imgFolder, self.dataPath())
        makedirs(dataFullPath, mode=0o755, exist_ok=True)
        dataFilename = path.join(dataFullPath, self.dataFilename())

        with open(dataFilename, "wb") as bin_file:
            bin_file.write(self.data)
        self.saveFilePath = dataFilename

        self.updateInfo()
        metaFullPath = path.join(metadataFolder, self.metadataPath())
        makedirs(metaFullPath, mode=0o755, exist_ok=True)
        metadataFilename = path.join(metaFullPath, self.metadataFilename())
        saveYAML(self.info, metadataFilename)

        self.saveMetadataPath = metadataFilename

    def exists(self, imgFolder: str, metadataFolder: str) -> bool:
        metadataFilename = path.join(metadataFolder, self.metadataPath(), self.metadataFilename())
        dataFilename = path.join(imgFolder, self.dataPath(), self.dataFilename())

        return comicPageExists(dataFilename, metadataFilename)

    def fileExtension(self):
        if self.data is None:  # Not downloaded, get the info from URL
            urlpath = urlsplit(self.mediaURL).path
            ext = path.splitext(urlpath)[1].lstrip('.').lower()
        else:
            mimeType = magic.detect_from_content(self.data).mime_type
            ext = extensionFromType(mimeType).lower()
        return ext

    # TODO: updateDB  # TODO: mailContent


def comicPageExists(dataFilename: str, metadataFilename: str) -> bool:
    if not (path.exists(metadataFilename) and path.exists(dataFilename)):
        return False

    metadata = loadYAML(metadataFilename)
    hashData = shaFile(dataFilename)

    if metadata['mediaHash'] != hashData:
        return False

    return True
