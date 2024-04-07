import logging
from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from datetime import datetime
from email.mime.image import MIMEImage
from email.utils import make_msgid
from os import makedirs, path
from time import strftime
from typing import Dict, List, Optional
from urllib.parse import urlsplit

import magic
import validators

from libs.Cosecha.Config import TIMESTAMPFORMAT
from libs.Utils.Files import extensionFromType, loadYAML, saveYAML, shaData, shaFile
from libs.Utils.Misc import getUTC, stripPubDate
from libs.Utils.Web import DownloadRawPage

logger = logging.getLogger()


class ComicPage(metaclass=ABCMeta):

    def __init__(self, **kwargs):
        auxKey = kwargs.get('key', None)
        if not auxKey:
            raise KeyError("Missing key parameter")
        auxURL = kwargs.get('URL', None)
        if not auxURL or not validators.url(auxURL):
            raise KeyError(f"Missing or invalid URL parameter {auxURL}")

        self.URL: str = auxURL
        self.key: str = auxKey
        self.timestamp: datetime = getUTC()
        self.comicDate: Optional[str] = None  # Date from page (if nay)
        self.comicId: Optional[str] = None  # Any identifier related to page (if any)
        self.mediaURL: Optional[str] = None
        self.data: Optional[bytes] = None  # Actual image
        self.mediaHash: Optional[str] = None
        self.mediaAttId: Optional[str] = None
        self.mimeType: Optional[str] = None
        self.info: dict = {'key': self.key}  # Dict containing metadata related to page (alt text, title...)
        self.otherInfo: dict = {}
        self.saveFilePath: Optional[str] = None
        self.saveMetadataPath: Optional[str] = None

        # Navigational links on page (if any)
        self.linkNext: Optional[str] = None
        self.linkPrev: Optional[str] = None
        self.linkFirst: Optional[str] = None
        self.linkLast: Optional[str] = None

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
        # If there is no URL for media, tries to download the page (again)
        if self.mediaURL is None:
            self.downloadPage()
        # No, there is no way to find media. We give up
        if self.mediaURL is None:
            raise ValueError(f"Unable to find media {self.URL}")

        img = DownloadRawPage(self.mediaURL, here=self.URL, allow_redirects=True)
        self.timestamp = img.timestamp
        self.info['timestamp'] = strftime(TIMESTAMPFORMAT, img.timestamp)
        self.data = img.data
        self.info['mediaURL'] = self.mediaURL = img.source
        self.info['mediaHash'] = self.mediaHash = shaData(img.data)
        self.mediaAttId = make_msgid(domain=self.key)[1:-1]
        self.info['mimeType'] = self.mimeType = magic.detect_from_content(self.data).mime_type

    def getRaw(self, sanitizer: Optional[Callable[[bytes], bytes]] = None):
        """ Commodity function for development. Returns the page as-is (without parsing nor preprocessing)"""
        result = DownloadRawPage(self.URL, sanitizer=sanitizer)
        return result

    def updateLinksFromDict(self, links: Dict[str, str]):
        self.linkNext = links.get('next')
        self.linkPrev = links.get('prev')
        self.linkFirst = links.get('first')
        self.linkLast = links.get('last')

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

    def sharedPath(self) -> List[str]:
        """
        Produces a path for files
        :return: a list with elements that will be added to the path to store elements (metadata & images for now)
        """
        pathList = [self.key]

        return pathList

    dataPath = sharedPath
    metadataPath = sharedPath

    def sharedPathWithDate(self) -> List[str]:
        """
        Produces a path for files that takes into account the date (year, actually) of publication.
        This prevents a lot of files storing in the same dir
        IMPORTANT: Field DATEFORMAT must be defined in the class or an exception will raise
        :return: a list with elements that will be added to the path to store elements (metadata & images for now)
        """
        year, _, _, _, _, _ = stripPubDate(self.comicDate, self.DATEFORMAT)
        pathList = [self.key, year]

        return pathList

    def saveFiles(self, imgFolder: str, metadataFolder: str):
        if self.data is None:
            raise ValueError("saveFile: empty file")

        dataFullPath = path.join(imgFolder, *(self.dataPath()))
        makedirs(dataFullPath, mode=0o755, exist_ok=True)
        dataFilename = path.join(dataFullPath, self.dataFilename())
        self.info['filename'] = self.dataFilename()
        self.info['fullFilename'] = dataFilename

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
        dataPath = path.join(imgFolder, *(self.dataPath()))

        if not path.exists(metadataFilename):
            return False

        metadata = loadYAML(metadataFilename)

        if 'fullFilename' in metadata and path.exists(metadata['fullFilename']):  # We have file locations in metadata
            result = shaFile(metadata['fullFilename']) == metadata.get('mediaHash')
            expectedPath = path.dirname(metadata['fullFilename'])
            if path.realpath(expectedPath) != path.realpath(dataPath):
                logging.warning(f"File {metadata['fullFilename']} location {expectedPath} is not where it was expected "
                                f"{dataPath}")
            return result
        elif 'filename' in metadata and path.exists(path.join(dataPath, metadata['filename'])):  # Id
            wrkFileName = path.join(dataPath, metadata['filename'])
            result = shaFile(wrkFileName) == metadata.get('mediaHash')
            return result
        else:  # We have to compose name
            dataFilename = self.dataFilename()
            if not dataFilename:
                logging.warning(f"{self.key}: Unable to calculate comic filename for '{self.comicId}' with existing "
                                f"information")
                return False
        fullFilename = path.join(dataPath, self.dataFilename())

        if not path.exists(fullFilename):
            return False
        hashData = shaFile(fullFilename)

        if metadata['mediaHash'] != hashData:
            return False

        return True

    def fileExtension(self):
        if self.data is None:  # Not downloaded, get the info from URL
            if not self.mediaURL:
                raise ValueError(f"Called function with mediaURL set")
            urlpath = urlsplit(self.mediaURL).path
            ext = path.splitext(urlpath)[1].lstrip('.').lower()
            if ext == '':
                raise ValueError(f"Impossible to deduct extension from URL '{self.mediaURL}'")
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

    # TODO: updateDB
