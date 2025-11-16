import datetime
import json
import re
from os import path
from pprint import pp
from time import strftime, struct_time
from typing import Optional, Dict
from urllib.parse import urljoin

import bs4
import dateparser
from CAPcore.Misc import datePub2Id
from CAPcore.Web import downloadPage, findObjectsWithAttributes, DownloadedPage

from libs.Cosecha.ComicPage import ComicPage
from libs.Cosecha.Config import GOCOMICSDATE

URLBASE = 'https://www.gocomics.com'


class Page(ComicPage):
    DATEFORMAT = GOCOMICSDATE
    IDFROMDATE = '%Y%m%d'

    def __init__(self, **kwargs):
        auxKey = kwargs.get('key', None)
        if not auxKey:
            raise KeyError("Missing key parameter")
        auxURL = kwargs.pop('URL', buildURL(auxKey)) or buildURL(auxKey)

        super().__init__(URL=auxURL, **kwargs)

    def __str__(self):
        dataStr = f"[{self.size()}b]" if self.data else "No data"
        idStr = f"{self.comicId}"
        dateStr = f" ({self.dayWeek()})" if self.datePub() else ""

        result = f"Comic '{self.key}' [{idStr}] {self.URL} -> {self.info['title']} {dataStr}{dateStr}"

        return result

    __repr__ = __str__

    def downloadPage(self):
        detectedIssues = []
        self.info = dict()

        pagBase = downloadPage(self.URL)
        print(f"CAP: downloading {self.URL}")
        self.timestamp = pagBase.timestamp

        links = findComicLinks(pagBase, here=self.URL)
        self.updateLinksFromDict(links)

        metadata = findMetadata(pagBase)
        metadata.update(traverseScripts(pagBase,targetURL=self.info.get('mediaURL'),targetDate=extractDateFromURL(self.URL)))

        self.info.update(metadata)
        self.info['about'] = re.sub(r' \| GoComics.com', r'', self.info['about']).strip()

        if 'here' in links:
            self.URL = links['here']
        else:
            detectedIssues.append(f"Unable to find own link in page {pagBase.source}")

        self.comicDate = metadata['datePublished']

        self.comicId = self.info['id'] = datePub2Id(self.comicDate, self.DATEFORMAT, self.IDFROMDATE)
        self.mediaURL = self.info['mediaURL']

    def updateOtherInfo(self):
        # Will do if need arises
        pass

    dataPath = ComicPage.sharedPathWithDate
    metadataPath = ComicPage.sharedPathWithDate
    debugPath = ComicPage.sharedPathWithDate

    def dataFilename(self):
        ext = self.fileExtension()
        intId = self.comicId

        result = f"{self.key}.{intId}.{ext}"

        return result

    def metadataFilename(self):
        ext = 'yml'
        intId = self.comicId

        result = f"{self.key}.{intId}.{ext}"
        return result

    def mailBodyFragment(self, indent=1, imgSeq: int = 0, imgTot: int = 0, **kwargs):
        title = self.info['about']
        dateStr = f" ({self.dayWeek()})" if self.datePub() else ""

        text = f"""{indent * "#"} ({imgSeq}/{imgTot}) {self.key} #{self.comicId}{dateStr} [{title}]({self.URL})
![{self.mediaURL}](cid:{self.mediaAttId})
"""

        return text


def buildURL(key: str, dateOpt: Optional[struct_time] = None):
    """
    Builds a URL to retrieve things from GoComics
    :param key: key for desired comic
    :param dateOpt: Optional date.
    :return: new URL
    """

    extraFields = [key]
    if dateOpt:
        dateStr = strftime("%Y/%m/%d")
        extraFields.append(dateStr)

    extraURL = path.join(*extraFields)
    result = urljoin(URLBASE, extraURL)

    return result


def findMetadata(pagBase: DownloadedPage):
    webContent: bs4.BeautifulSoup = pagBase.data

    targetInfo = [('url', 'property', "og:url"), ('title', 'name', "twitter:description"),
                  ('author', 'property', "article:author"), ('datePublished', 'property', "article:published_time"),
                  ('mediaURL', 'property', "og:image"), ('about', 'name', "twitter:title"), ]
    result = dict()

    interestingMetas = findObjectsWithAttributes(webContent.find('head'), 'meta', targetInfo)

    for label, tag in interestingMetas.items():
        if label == 'mediaURL':
            if 'staging-assets' in tag['content']:
                continue
        result[label] = tag['content']

    return result


reComicViewer = re.compile(r'^ShowComicViewer_.*', re.IGNORECASE)
reComicViewerButton = re.compile(r'^ComicNavigation_controls__button.*', re.IGNORECASE)


def findComicLinks(pagBase: DownloadedPage, here: str):
    result = {}

    webContent: bs4.BeautifulSoup = pagBase.data
    divNav: bs4.element.Tag = webContent.find('section', {'class': reComicViewer})
    if divNav is None:
        raise ValueError(f"Unable to find nav bar in {pagBase.source}")

    for aB in divNav.find_all('a', {'class': reComicViewerButton}):
        if aB.get('aria-disabled', 'XXX') == "true":
            continue
        if any(['button_previous_' in x for x in aB['class']]):
            result['prev'] = urljoin(here, aB['href'])
            if aB.get('data-analytics-location'):
                result['here'] = urljoin(here, aB['data-analytics-location'])
            continue
        if any(['button_next_' in x for x in aB['class']]):
            result['next'] = urljoin(here, aB['href'])
            if aB.get('data-analytics-location'):
                result['here'] = urljoin(here, aB['data-analytics-location'])
            continue
        print(f"Link Type Unknown {aB}")

    return result


def traverseScripts(pagBase: DownloadedPage, targetURL: Optional[str] = None, targetDate: Optional[str] = None):
    webContent: bs4.BeautifulSoup = pagBase.data
    auxResult = {}

    def subData2data(data: Dict[str, str]) -> str:
        return data.get('name', "WTF!")

    for scriptJSON in webContent.find_all('script', {'type': "application/ld+json"}):
        auxData = {}
        dataJSON = json.loads((scriptJSON.getText()))
        if not dataJSON.get('representativeOfPage', False):
            continue
        auxData['author'] = subData2data(dataJSON['author'])
        auxData['title'] = dataJSON['datePublished']
        auxData['auxTime']: datetime.datetime = dateparser.parse(dataJSON['datePublished'])
        auxData['datePublished'] = auxData['auxTime'].strftime(GOCOMICSDATE)
        if 'url' in dataJSON:
            auxData['mediaURL'] = dataJSON['url']
        if 'contentUrl' in dataJSON:
            auxData['mediaURL'] = dataJSON['contentUrl']

        if targetURL and targetURL == auxData['mediaURL']:
            return auxData
        if targetDate and targetDate == auxData['datePublished']:
            return auxData

        auxResult[auxData['datePublished']] = auxData

    if targetDate is None:
        keysRes = sorted(auxResult.keys(),reverse=True)
        return auxResult[keysRes[0]]


def extractDateFromURL(url:str) -> Optional[str]:
    patDate=r"^.*/(?P<year>\d{4})/(?P<month>\d{4})/(?P<day>\d{2})$"

    reDate= re.match(patDate,url)
    if reDate:
        return f"{reDate.group('year')}-{reDate.group('month')}-{reDate.group('day')}"
    else:
        return None

###############################
