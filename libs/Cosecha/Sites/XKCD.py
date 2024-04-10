import re
from typing import List, Optional

import bs4

from libs.Cosecha.ComicPage import ComicPage
from libs.Cosecha.Config import IDPATHDIVIDER
from libs.Utils.Web import DownloadPage, MergeURL

URLBASE = "https://xkcd.com/"
KEY = "xkcd"


class Page(ComicPage):

    def __init__(self, **kwargs):
        auxKey = kwargs.pop('key', None) or KEY
        auxURL = kwargs.pop('URL', None) or URLBASE

        super().__init__(key=auxKey, URL=auxURL, **kwargs)

    def __str__(self):
        dataStr = f"[{self.size()}b]" if self.data else "No data"
        idStr = f"{self.comicId}"
        result = f"Comic '{self.key}' [{idStr}] {self.URL} -> {self.info['title']} {dataStr}"

        return result

    def downloadPage(self):
        reqMetas = {'title', 'url'}
        self.info = dict()

        pagBase = DownloadPage(self.URL)
        metas = findInterestingMetas(pagBase.data)

        if reqMetas.difference(set(metas.keys())):
            metas = findInterestingMetasTheHardWay(pagBase.data, currMetas=metas)

        self.info['title'] = metas['title']
        self.URL = self.info['url'] = metas['url']
        self.comicId = self.info['id'] = extractId(metas['url'])

        links = findComicLinks(pagBase.data, here=self.URL, thisPage=self.info.get('url', None))
        self.linkNext = links.get('next')
        self.linkPrev = links.get('prev')
        self.linkFirst = links.get('first')
        self.linkLast = links.get('last')

        infoImg = findComicImg(pagBase.data, title=metas['title'], here=self.URL)
        self.info['comment'] = infoImg['comment']
        self.info['titleStr'] = infoImg['titleStr']
        self.mediaURL = infoImg['urlImg']
        self.timestamp = pagBase.timestamp

    def updateOtherInfo(self):
        # Will do if need arises
        pass

    def sharedPath(self) -> List[str]:
        """
        Produces a path for files
        :return: a list with elements that will be added to the path to store elements (metadata & images for now)
        """
        idGrouper = (int(self.comicId) // IDPATHDIVIDER) * IDPATHDIVIDER
        pathList = [self.key, f"{idGrouper:04}"]

        return pathList

    dataPath = sharedPath
    metadataPath = sharedPath

    def dataFilename(self):
        ext = self.fileExtension()
        intId = int(self.comicId)
        title = self.info['titleStr']

        result = f"{self.key}.{intId:05}-{title}.{ext}"

        return result

    def metadataFilename(self):
        ext = 'yml'
        intId = int(self.comicId)

        result = f"{self.key}.{intId:05}.{ext}"
        return result

    def mailBodyFragment(self, indent=1, imgSeq: int = 0, imgTot: int = 0, **kwargs):
        title = self.info['title']
        text = f"""{indent * "#"} ({imgSeq}/{imgTot}) {self.key} #{self.comicId} [{title}]({self.URL})
![{self.mediaURL}](cid:{self.mediaAttId})

"{self.info['comment']}"
"""

        return text


def findInterestingMetas(webContent: bs4.BeautifulSoup):
    """
    Metadata for page (meta's) contain all the interesting info (if present)
    :param webContent:
    :return:
    """
    labs2extract = {'title', 'url'}
    result = dict()

    for entry in webContent.findAll('meta'):
        if 'property' not in entry.attrs:
            continue
        label = entry.attrs['property'].removeprefix('og:')
        if label not in labs2extract:
            continue
        result[label] = entry.attrs['content']

    return result


def findInterestingMetasTheHardWay(webContent: bs4.BeautifulSoup, currMetas: dict):
    """
    If we couldn't extract information from meta tags on the head block, let's find info one by one
    :param webContent:
    :param currMetas:
    :return:
    """
    result = currMetas.copy()
    if 'title' not in currMetas:
        auxTitle = webContent.head.find('title').text.lstrip('xkcd:').strip()
        result['title'] = auxTitle
    if 'url' not in currMetas:
        auxText = webContent.find(string=re.compile('Permanent link to this comic: '))
        auxLink = auxText.find_next('a')
        result['url'] = auxLink.text.strip()

    return result


def findComicLinks(webContent: bs4.BeautifulSoup, here: Optional[str] = None, thisPage: Optional[str] = None):
    result = dict()

    barNav = webContent.find('ul', {"class": "comicNav"})
    for item in barNav.findAll('a'):
        text = item.text
        label = ''
        dest = item.attrs['href']
        if (text == '|<'):
            label = 'first'
        elif (text == '< Prev'):
            label = 'prev'
        elif (text == 'Random'):
            continue
        elif (text == 'Next >'):
            label = 'next'
        elif (text == '>|'):
            label = 'last'
        else:
            raise ValueError(f"{item} '{text}' It shouldn't have reached here")

        if dest in {'#'}:
            if thisPage:
                dest = thisPage
            else:
                continue  # / is the last page, # is self
        elif dest in {'/'}:
            continue

        destURL = MergeURL(here, dest)

        if destURL == here:
            continue
        result[label] = destURL

    return result


def extractId(url):
    pat = r'/(?P<id>\d+)/$'

    match = re.search(pat, url)

    if match:
        return match['id']

    raise ValueError(f"extractId: '{url}' doesn't match pattern '{pat}'")


def findComicImg(webContent: bs4.BeautifulSoup, title: Optional[str], here: Optional[str] = None):
    result = dict()

    imgLink = webContent.find('img', {'alt': title})
    result['comment'] = imgLink.attrs['title']
    dest = imgLink.attrs['src']
    result['urlImg'] = MergeURL(here, dest)

    pat = r'/(?P<titleStr>[^./]+)\.\w+$'
    match = re.search(pat, dest)
    if match:
        result['titleStr'] = match['titleStr']
    else:
        raise ValueError(f"findComicImg: '{dest}' doesn't match pattern '{pat}'")

    return result
