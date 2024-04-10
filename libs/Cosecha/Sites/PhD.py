import logging
import os.path
import re
from typing import List
from urllib.parse import parse_qs, urlencode, urlparse

import bs4
from markdownify import markdownify

from libs.Cosecha.ComicPage import ComicPage
from libs.Cosecha.Config import IDPATHDIVIDER
from libs.Utils.Files import getSaneFilenameStr
from libs.Utils.Web import DownloadPage

URLBASE = "https://phdcomics.com/"
KEY = "PhD"


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
        self.info = dict()

        pagBase = DownloadPage(self.URL, sanitizer=sanitizer)
        self.timestamp = pagBase.timestamp
        metadata = findMetas(pagBase.data)
        for k in ['urlImg', 'title', 'id', 'url']:
            if k in metadata:
                self.info[k] = metadata[k]

        self.URL = metadata['url']
        self.mediaURL = metadata['urlImg']
        self.comicId = self.info['id']

        self.linkNext = metadata.get('next')
        self.linkPrev = metadata.get('prev')
        self.linkFirst = metadata.get('first')
        self.linkLast = metadata.get('last')

        self.info['titleStr'] = getSaneFilenameStr(self.info['title'])

        comments = findFootNotes(webContent=pagBase.data, urlIMG=self.mediaURL)
        self.info['comments'] = comments

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

        result = f"{self.key}.{intId:04}-{title}.{ext}"

        return result

    def metadataFilename(self):
        ext = 'yml'
        intId = int(self.comicId)

        result = f"{self.key}.{intId:04}.{ext}"
        return result

    def mailBodyFragment(self, indent=1, imgSeq: int = 0, imgTot: int = 0, **kwargs):
        title = self.info['title']
        commentsStr = ""
        if 'comments' in self.info:
            commentsStr = "\n".join(map(lambda c: f"* {c}", self.info['comments']))

        text = f"""{indent * "#"} ({imgSeq}/{imgTot}) {self.key} #{self.comicId} [{title}]({self.URL})
![{self.mediaURL}](cid:{self.mediaAttId})

{commentsStr}
"""

        return text


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
            result['url'] = URLfromId(result['id'])
        else:
            raise ValueError(f'Unable to find Comic ID in {urlPrint}')
    else:
        raise ValueError(f'Unable to find URL for print')

    INFOLINKS = [('prev', 'http://phdcomics.com/comics/images/prev_button.gif'),
                 ('first', 'http://phdcomics.com/comics/images/first_button.gif'),
                 ('next', 'http://phdcomics.com/comics/images/next_button.gif')]

    for label, iconLink in INFOLINKS:
        parent = parentOf(webContent, 'img', attrs={'src': iconLink})
        if parent:
            destLnk = parent['href']
            result[label] = destLnk

    return result


def parentOf(webContent: bs4.BeautifulSoup, *kargs, **kwargs):
    son = webContent.find(*kargs, **kwargs)

    if son:
        return son.parent

    return None


def extractId(url: str):
    urlparts = urlparse(url)
    qparams = parse_qs(urlparts.query)
    if 'comicid' in qparams:
        return qparams['comicid'][0]
    return None


def sanitizer(raw: (bytes, str)) -> bytes:
    """
    Applies some changes to the page so it can be parsed. Let's say the HTML is 'legacy'
    :param raw:
    :return:
    """
    if isinstance(raw, bytes):
        result = raw.replace(b'--!>', b'-->').replace(b'\t', b' ').replace(b'\n', b' ')
        result2 = re.sub(rb'\s+', rb' ', result)
    elif isinstance(raw, str):
        result = raw.replace('--!>', '-->').replace('\t', ' ').replace('\n', ' ')
        result2 = re.sub(r'\s+', r' ', result)
    else:
        raise TypeError(f"sanitizer: don't know what to do with type {type(raw)}")

    return result2


def URLfromId(comicId: str):
    """
    Builds the PhD URL for a specific ID
    :param comicId:
    :return:
    """
    refURL = 'https://phdcomics.com/comics/archive.php?comicid=2002'

    parsedURL = urlparse(refURL)
    queryStr = parse_qs(parsedURL.query)
    queryStr['comicid'] = comicId
    newParsedURL = parsedURL._replace(query=urlencode(queryStr))
    result = newParsedURL.geturl()

    return result


def findFootNotes(webContent: bs4.BeautifulSoup, urlIMG: str):
    result = []

    def imgNameWithoutExt(path: str):
        fullFname = os.path.basename(path)
        result = re.sub(r'\.[^.]*$', '', fullFname)
        return result

    def imgMatch(t: bs4.Tag, reqfname: str):
        if t.name != 'img':
            return False

        if 'src' not in t.attrs:
            return False
        provPath = urlparse(t['src']).path
        provFname = imgNameWithoutExt(provPath)
        result = (provFname == reqfname)
        return result

    reqPath = urlparse(urlIMG).path
    reqFName = imgNameWithoutExt(reqPath)

    imgElem = webContent.find(lambda t: imgMatch(t, reqFName))
    if imgElem is None:

        for i in webContent.find_all('img'):
            logging.debug(f"Found img: '{i}")
        raise ValueError("Unable to find Image element with picture")
    divFootNotes = imgElem.fetchNextSiblings('div')
    for div in divFootNotes:
        tabElems = div.find_all('table')
        if not tabElems:
            continue
        for tab in tabElems:
            auxSubstrs = []
            for td in tab.find_all('td'):
                for child in td.find_all('i'):
                    oldText = child.text
                    newText = oldText.replace('**', '').strip()
                    if oldText != newText:
                        child.string.replace_with(newText)
                auxSubstrs.append(markdownify(td.prettify(), strip=['td']).replace('\n', ' ').strip())

            result.extend(auxSubstrs)
    return result
