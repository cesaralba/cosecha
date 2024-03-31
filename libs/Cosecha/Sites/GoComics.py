import re
from os import path
from time import strftime, struct_time
from typing import Optional
from urllib.parse import urljoin

import bs4

from libs.Cosecha.ComicPage import ComicPage
from libs.Utils.Misc import datePub2Id
from libs.Utils.Web import DownloadPage, findObjectsWithAttributes

URLBASE = 'https://www.gocomics.com'


class Page(ComicPage):
    DATEFORMAT = '%Y-%m-%d'
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
        result = f"Comic '{self.key}' [{idStr}] {self.URL} -> {self.info['title']} {dataStr}"

        return result

    def downloadPage(self):
        self.info = dict()

        pagBase = DownloadPage(self.URL)
        self.timestamp = pagBase.timestamp

        divNav = pagBase.data.find('nav', attrs={'class': 'content-section-padded-sm'})
        if divNav is None:
            raise ValueError(f"Unable to find nav bar in {self.URL}")
        comicLink = divNav.find('a', attrs={'data-link': 'comics'})
        comicPageURL = urljoin(self.URL, comicLink['href'])
        if 'active' not in comicLink.attrs['class']:
            pagBase = DownloadPage(comicPageURL)
            self.URL = comicPageURL

        metadata = findMetadata(pagBase.data)
        self.info.update(metadata)
        self.comicDate = metadata['datePublished']

        self.comicId = self.info['id'] = datePub2Id(self.comicDate, self.DATEFORMAT, self.IDFROMDATE)
        self.mediaURL = self.info['mediaURL']
        self.info['about'] = re.sub(r' \| GoComics.com', r'', self.info['about']).strip()

        links = findComicLinks(pagBase.data, here=self.URL)

        self.updateLinksFromDict(links)

    def updateOtherInfo(self):
        # Will do if need arises
        pass

    dataPath = ComicPage.sharedPathWithDate
    metadataPath = ComicPage.sharedPathWithDate

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

    def mailBodyFragment(self, indent=1):
        title = self.info['about']
        text = f"""{(indent) * "#"} {self.key} #{self.comicId} [{title}]({self.URL})
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


def findMetadata(webContent: bs4.BeautifulSoup):
    targetInfo = [('url', 'property', "og:url"), ('title', 'name', "twitter:description"),
                  ('author', 'property', "article:author"), ('datePublished', 'property', "article:published_time"),
                  ('mediaURL', 'property', "og:image"), ('about', 'name', "twitter:title"), ]
    result = dict()

    interestingMetas = findObjectsWithAttributes(webContent.find('head'), 'meta', targetInfo)

    for label, tag in interestingMetas.items():
        result[label] = tag['content']

    return result


def findComicLinks(webContent: bs4.BeautifulSoup, here: Optional[str] = None):
    result = dict()

    targetInfo = [('last', 'class', "fa-forward"), ('next', 'class', "fa-caret-right"),
                  ('prev', 'class', "fa-caret-left"), ('first', 'class', "fa-backward"), ]

    auxButtons = findObjectsWithAttributes(webContent, 'a', targetInfo)

    for label, tag in auxButtons.items():
        destLink = urljoin(here, tag['href'])
        result[label] = destLink

    return result

###############################
