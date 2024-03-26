import json
import re
from datetime import datetime
from typing import Optional

import bs4

from libs.Cosecha.ComicPage import ComicPage
from libs.Utils.Web import DownloadPage, MergeURL

URLBASE = "https://www.smbc-comics.com/"
KEY = "smbc"


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
        self.timestamp = pagBase.timestamp
        metadata = findMetadataStruct(pagBase.data)
        print(metadata)

        for k in ['url', 'author', 'publisher', 'about', 'image', 'datePublished']:
            self.info[k] = metadata[k]
        self.info['title'] = metadata['name'].lstrip('Saturday Morning Breakfast Cereal - ')
        self.URL = metadata['url']
        self.mediaURL = metadata['image']
        self.comicDate = metadata['datePublished']
        self.comicId = self.info['id'] = extractId(self.comicDate)

        links = findComicLinks(pagBase.data, here=self.URL)
        self.linkNext = links.get('next')
        self.linkPrev = links.get('prev')
        self.linkFirst = links.get('first')
        self.linkLast = links.get('last')

        infoImg = findComicImg(pagBase.data, url=self.mediaURL, here=self.URL)
        self.info['comment'] = infoImg['comment']
        self.mediaURL = infoImg['urlImg']
        self.info['titleStr'] = findURLstr(self.info['url'])

    def updateOtherInfo(self):
        # Will do if need arises
        pass

    def dataFilename(self):
        ext = self.fileExtension()
        intId = self.comicId
        title = self.info['titleStr']

        result = f"{self.key}.{intId}-{title}.{ext}"

        return result

    def metadataFilename(self):
        ext = 'yml'
        intId = self.comicId

        result = f"{self.key}.{intId}.{ext}"
        return result

    def mailBodyFragment(self, indent=1):
        title = self.info['title']
        text = f"""{(indent) * "#"} {self.key} #{self.comicId} [{title}]({self.URL})
![{self.mediaURL}](cid:{self.mediaAttId})

"{self.info['comment']}"
"""

        return text


###############################
def findMetadataStruct(webContent: bs4.BeautifulSoup):
    scrInfo = webContent.find('script', attrs={'type': 'application/ld+json'}, recursive=True)

    if not scrInfo:
        raise ValueError("Unable to find metadata struct")
    metaInfo = json.loads(scrInfo.text)

    result = {k: v for k, v in metaInfo.items() if not k.startswith('@')}

    return result


def extractId(datePublished):
    # 'datePublished': '2024-03-26T08:14:46-04:00'
    datePub = datetime.strptime(datePublished, '%Y-%m-%dT%H:%M:%S%z')
    result = datePub.strftime('%Y%m%dT%H%M')

    return result


def findComicLinks(webContent: bs4.BeautifulSoup, here: Optional[str] = None):
    result = dict()

    barNav = webContent.find('nav', {"class": "cc-nav", "role": "navigation"})
    for item in barNav.findAll('a'):
        text = item.text
        if 'rel' not in item.attrs:
            continue
        rel = item.attrs['rel'][0]
        dest = item.attrs['href']
        if rel not in {'first', 'prev', 'next', 'last'}:
            raise ValueError(f"{item} '{rel}' It shouldn't have reached here")
        destURL = MergeURL(here, dest)

        if destURL == here:
            continue
        result[rel] = destURL

    return result


def findComicImg(webContent: bs4.BeautifulSoup, url: Optional[str], here: Optional[str] = None):
    attrs = {'id': 'cc-comic'}
    if url:
        attrs['src'] = url

    result = dict()

    imgLink = webContent.find('img', attrs=attrs)

    result['comment'] = imgLink.attrs['title']
    dest = imgLink.attrs['src']
    result['urlImg'] = MergeURL(here, dest)

    return result


def findURLstr(url: str):
    pat = r'/(?P<titleStr>[^./]+)$'
    match = re.search(pat, url)
    if match:
        result = match['titleStr']
    else:
        raise ValueError(f"findComicImg: '{url}' doesn't match pattern '{pat}'")

    return result
