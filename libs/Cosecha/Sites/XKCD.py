import re
from typing import Optional

import bs4

from libs.Cosecha.ComicPage import ComicPage
from libs.Utils.Misc import createPath
from libs.Utils.Web import DownloadPage, MergeURL

URLBASE = "https://xkcd.com/"
KEY = "xkcd"


class Page(ComicPage):

    def __init__(self, URL: str = None):
        auxURL = URL or URLBASE
        super().__init__(key=KEY, URL=auxURL)


    def __str__(self):
        dataStr = f"[{self.size()}b]" if self.data else "No data"
        idStr = f"{self.comicId}"
        result = f"Comic '{self.key}' [{idStr}] {self.URL} -> {self.info['title']} {dataStr}"

        return result
    def downloadPage(self):
        self.info = dict()

        pagBase = DownloadPage(self.URL)
        metas = findInterestingMetas(pagBase.data)
        self.info['title'] = metas['title']
        self.info['url'] = metas['url']
        self.comicId = self.info['id'] = extractId(metas['url'])

        links = findComicLinks(pagBase.data, here=self.URL)
        self.linkNext = links.get('next')
        self.linkPrev = links.get('prev')
        self.linkFirst = links.get('first')
        self.linkLast = links.get('last')

        infoImg = findComicImg(pagBase.data, title=metas['title'], here=self.URL)
        self.info['comment'] = infoImg['comment']
        self.info['titleStr'] = infoImg['titleStr']
        self.mediaURL = infoImg['urlImg']
        self.timestamp = pagBase.timestamp

    def updateInfo(self):
        if self.linkNext:
            self.info['next'] = self.linkNext
        if self.linkPrev:
            self.info['prev'] = self.linkPrev
        if self.linkFirst:
            self.info['first'] = self.linkFirst
        if self.linkLast:
            self.info['last'] = self.linkLast

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

    def dataPath(self):
        pathList = [self.key]
        return createPath(*pathList)

    def metadataPath(self):
        pathList = [self.key]
        return createPath(*pathList)


def findInterestingMetas(webContent: bs4.BeautifulSoup):
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


def findComicLinks(webContent: bs4.BeautifulSoup, here: Optional[str] = None):
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

        if dest in {'/', '#'}:
            continue  # / is the last page, # is self

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
