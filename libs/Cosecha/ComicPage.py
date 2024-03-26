import logging
from abc import ABCMeta, abstractmethod
from email.mime.image import MIMEImage
from email.utils import make_msgid
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
        self.comicDate = None  # Date from page (if nay)
        self.comicId = None  # Any identifier related to page (if any)
        self.mediaURL = None
        self.data = None  # Actual image
        self.mediaHash = None
        self.mediaAttId = None
        self.mimeType = None
        self.info = {'key': key}  # Dict containing metadata related to page (alt text, title...)
        self.saveFilePath = None
        self.saveMetadataPath = None

        # Navigational links on page (if any)
        self.linkNext = None
        self.linkPrev = None
        self.linkFirst = None
        self.linkLast = None

    def __str__(self):
        dataStr = f"[{self.size()}b]" if self.data else "No data"
        idStr = f"{self.comicId}"
        result = f"Comic '{self.key}' [{idStr}] {self.URL} -> {self.mediaURL} {dataStr}"

        return result

    __repr__ = __str__

    def size(self):
        if self.data is None:
            return None
        return len(self.data)

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
        self.mediaAttId = make_msgid(domain=self.key)[1:-1]
        self.info['mimeType'] = self.mimeType = magic.detect_from_content(self.data).mime_type

    def updateInfoLinks(self):
        if self.linkNext:
            self.info['next'] = self.linkNext
        if self.linkPrev:
            self.info['prev'] = self.linkPrev
        if self.linkFirst:
            self.info['first'] = self.linkFirst
        if self.linkLast:
            self.info['last'] = self.linkLast

    @abstractmethod
    def updateOtherInfo(self):
        raise NotImplementedError

    @abstractmethod
    def dataFilename(self):
        """Builds a dataFilename for the image"""
        raise NotImplementedError

    @abstractmethod
    def metadataFilename(self):
        """Builds a dataFilename for the image"""
        raise NotImplementedError

    def dataPath(self):
        pathList = [self.key]
        return pathList

    def metadataPath(self):
        pathList = [self.key]
        return pathList

    def saveFiles(self, imgFolder: str, metadataFolder: str):
        if self.data is None:
            raise ValueError("saveFile: empty file")

        dataFullPath = path.join(imgFolder, *(self.dataPath()))
        makedirs(dataFullPath, mode=0o755, exist_ok=True)
        dataFilename = path.join(dataFullPath, self.dataFilename())

        with open(dataFilename, "wb") as bin_file:
            bin_file.write(self.data)
        self.saveFilePath = dataFilename

        self.updateInfoLinks()
        self.updateOtherInfo()
        metaFullPath = path.join(metadataFolder, *(self.metadataPath()))
        makedirs(metaFullPath, mode=0o755, exist_ok=True)
        metadataFilename = path.join(metaFullPath, self.metadataFilename())
        saveYAML(self.info, metadataFilename)

        self.saveMetadataPath = metadataFilename

    def exists(self, imgFolder: str, metadataFolder: str) -> bool:
        metadataFilename = path.join(metadataFolder, *(self.metadataPath()), self.metadataFilename())
        dataFilename = path.join(imgFolder, *(self.dataPath()), self.dataFilename())

        return comicPageExists(dataFilename, metadataFilename)

    def fileExtension(self):
        if self.data is None:  # Not downloaded, get the info from URL
            urlpath = urlsplit(self.mediaURL).path
            ext = path.splitext(urlpath)[1].lstrip('.').lower()
        else:
            ext = extensionFromType(self.mimeType).lower()
        return ext

    def mailBodyFragment(self, indent=1):
        text = f"""{(indent) * "#"} [{self.key} {self.comicId}]({self.URL})
![{self.mediaURL}](cid:{self.mediaAttId})"""

        return text

    def prepareAttachment(self):
        if self.data is None:
            raise ValueError("Trying to attach non existent data")

        filename = self.dataFilename()
        part = MIMEImage(self.data, name=filename)
        part.add_header("Content-Disposition", f"inline; filename=\"{filename}\"")
        part.add_header("X-Attachment-Id", self.mediaAttId)
        part.add_header("Content-ID", f"<{self.mediaAttId}>")

        return part

    # TODO: updateDB  # TODO: mailContent


def comicPageExists(dataFilename: str, metadataFilename: str) -> bool:
    if not (path.exists(metadataFilename) and path.exists(dataFilename)):
        return False

    metadata = loadYAML(metadataFilename)
    hashData = shaFile(dataFilename)

    if metadata['mediaHash'] != hashData:
        return False

    return True
