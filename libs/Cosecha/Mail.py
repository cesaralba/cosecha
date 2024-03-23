# https://dev.to/aahnik/compose-email-with-markdown-and-send-it-with-a-python-script-9d

from typing import Dict, List

from .ComicPage import ComicPage
from .Crawler import Crawler


class MailBundle:
    def __init__(self, crawler: Crawler = None):
        self.name = crawler.name
        self.bid: int = 0  # Order number of bundle for the specific crawler
        self.bcnt: int = 0  # Total number of bundles of the specific crawler
        self.crawler = crawler
        self.images: List[ComicPage] = []
        self.size: int = 0

    def __str__(self):

        seqStr = "" if self.bcnt == 1 else f"({self.bid}/{self.bcnt})"
        result = f"Bundle: name: '{self.name}' {seqStr} size: {self.size} #imgs: {len(self.images)}"
        return result

    def len(self):
        return len(self.images)

    def setId(self, bid: int = 0):
        self.bid = bid

    def setCnt(self, cnt: int = 0):
        self.bcnt = cnt

    def addImage(self, image: ComicPage):
        self.images.append(image)
        self.size += image.size()


class MailMessage:
    def __init__(self, mid: int = 0):
        self.mid: int = mid
        self.mcnt: int = 0
        self.size: int = 0
        self.bundles: Dict[str, MailBundle] = dict()

    def __str__(self):
        bundleStr = ",".join([f"{b}" for b in self.bundles])
        result = f"Message: [{self.mid}] size: {self.size} #bundles: {len(self.bundles)} bundles: [{bundleStr}]"
        return result

    def len(self):
        return len(self.bundles)

    def setCnt(self, cnt: int = 0):
        self.mcnt = cnt

    def addImage(self, crawler: Crawler, image: ComicPage):
        cName = crawler.name
        if cName not in self.bundles:
            self.bundles[cName] = MailBundle(crawler)

        self.bundles[cName].addImage(image)
        self.size += image.size()


