import json
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

import bs4

from libs.Cosecha.ComicPage import ComicPage
from libs.Utils.Web import DownloadPage, MergeURL,DownloadRawPage

URLBASE = "https://phdcomics.com/"
KEY = "PhD"


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
        RawPage=DownloadRawPage(self.URL)
        self.timestamp = RawPage.timestamp

        mendedPage=RawPage.data.replace(b'--!>',b'-->').replace(b'\t',b' ').replace(b'\n',b' ')
        pagBase=bs4.BeautifulSoup(mendedPage, 'html.parser')

        metadata = findMetas(pagBase)

        self.linkNext = metadata.get('next')
        self.linkPrev = metadata.get('prev')
        self.linkFirst = metadata.get('first')
        self.linkLast = metadata.get('last')


        print(metadata)
        return

        for k in ['url', 'author', 'publisher', 'about', 'image', 'datePublished']:
            self.info[k] = metadata[k]
        self.info['title'] = metadata['name'].lstrip('Saturday Morning Breakfast Cereal - ')
        self.URL = metadata['url']
        self.mediaURL = metadata['image']
        self.comicDate = metadata['datePublished']
        self.comicId = self.info['id'] = extractId(self.comicDate)

        links = findComicLinks(pagBase.data, here=self.URL)

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

"{self.info['comment']}" (_by {self.info['author']}_)
"""

        return text

    def URLfromId(self,comicId:str):
        pass

###############################
def findMetas(webContent: bs4.BeautifulSoup):
    result = dict()

    imgMeta = webContent.head.find('meta', attrs={'property': "og:image"})
    if imgMeta:
        result['urlImg'] = imgMeta['content']
    metaTitle = webContent.head.find('meta', attrs={'name': "twitter:title"})
    if metaTitle:
        result['title'] = metaTitle['content']

    linkPrint = parentOf(webContent, 'img', attrs={'src': 'http://phdcomics.com/comics/images/printit_button.gif'})
    if linkPrint:
        urlPrint = linkPrint['href']
        comicId = extractId(urlPrint)
        if comicId is not None:
            result['id'] = comicId
        else:
            raise ValueError(f'Unable to find Comic ID in {urlPrint}')
    else:
        raise ValueError(f'Unable to find URL for print')

    INFOLINKS = [('prev',  'http://phdcomics.com/comics/images/prev_button.gif'),
                 ('first', 'http://phdcomics.com/comics/images/first_button.gif'),
                 ('next',  'http://phdcomics.com/comics/images/next_button.gif')]

    for label, iconLink in INFOLINKS:
        parent=parentOf(webContent,'img',attrs={'src': iconLink})
        if parent:
            destLnk=parent['href']
            result[label]=destLnk


    for i in webContent.find_all('img'):
        print(f" ---> {i['src']}")
    print(result)

    return result


def parentOf(webContent: bs4.BeautifulSoup, *kargs, **kwargs):
    son = webContent.find(*kargs, **kwargs)
    print(f"{kwargs} -> {son}")
    if son:
        return son.parent

    return None


def extractId(url: str):
    urlparts = urlparse(url)
    qparams = parse_qs(urlparts.query)
    if 'comicid' in qparams:
        return qparams['comicid'][0]
    return None


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
