from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List

import markdown

from .ComicPage import ComicPage
from .Config import mailConfig
from .Crawler import Crawler
from ..Utils.Misc import listize


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

    def print(self, indent=2):
        result = []
        result.append(((indent) * " ") + f"[{self.bid}/{self.bcnt}] {self}")
        for k, image in enumerate(self.images, start=1):
            result.append((indent + 3) * " " + f"[{k}] {image}")
        return "\n".join(result)

    def compose(self, indent=1):
        resultPlain = []
        attachList = []

        textHeader = f"""
{indent * "#"} {self.crawler.title()} ({self.bid}/{self.bcnt}) 
"""
        resultPlain.append(textHeader)

        for image in self.images:
            imgPlain = image.mailBodyFragment(indent + 1)
            resultPlain.append(imgPlain)
            attachList.append(image.prepareAttachment())

        return resultPlain, attachList


# https://dev.to/aahnik/compose-email-with-markdown-and-send-it-with-a-python-script-9d
# https://realpython.com/python-send-email/

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

    def print(self, i, indent=0):
        result = []
        result.append(((indent) * " ") + f"[{self.mid}/{self.mcnt}] {self}")

        for j, bundleN in enumerate(sorted(self.bundles), start=1):
            bundle = self.bundles[bundleN]
            result.append(bundle.print(indent + 3))

        return "\n".join(result)

    def compose(self, config: mailConfig, subject="Cosecha"):
        resultPlain = []
        attachments = []

        for j, bundleN in enumerate(sorted(self.bundles), start=1):
            bundle = self.bundles[bundleN]
            listPlain, listAttachments = bundle.compose()
            resultPlain.extend(listPlain)
            attachments.extend(listAttachments)

        finalPlain = "\n".join(resultPlain)
        finalHTML = markdown.markdown("CAP\n" + finalPlain)

        fullSubject = f"{subject} {self.mid}/{self.mcnt}"

        main_msg = MIMEMultipart("related")

        main_msg["Subject"] = fullSubject.splitlines()[0]
        main_msg["From"] = config.sender
        # https://stackoverflow.com/a/54478485
        main_msg["To"] = ", ".join(listize(config.to))

        alternate_msg = MIMEMultipart("alternative")
        part1 = MIMEText(finalPlain, "plain")
        part2 = MIMEText(finalHTML, "html")

        alternate_msg.attach(part1)
        alternate_msg.attach(part2)

        main_msg.attach(alternate_msg)

        for attach in attachments:
            main_msg.attach(attach)

        return main_msg
