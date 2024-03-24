import logging
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from time import gmtime, strftime
from typing import List, Optional

from .Config import globalConfig, readRunnerConfigs, runnerConfig
from .Crawler import Crawler
from .Mail import MailMessage


class Harvest:
    def __init__(self, config: globalConfig, homeDirectory: str, ignoreEnabled: bool = False):

        # Configuration items
        self.globalCFG: globalConfig = config
        self.runnerCFGs: List[runnerConfig] = []
        self.homeDirectory = homeDirectory

        # Execution parameters
        self.ignoreEnabled: bool = ignoreEnabled

        # Working objects
        self.crawlers: List[Crawler] = []

    def go(self):
        self.prepare()
        self.download()

        if not self.globalCFG.dryRun:
            if not self.globalCFG.dontSave:
                self.save()

            if not self.globalCFG.dontSendEmails:
                self.email()

    def prepare(self):
        """
        Creates Crawler objects from configuration files
        :return:
        """
        self.runnerCFGs: List[runnerConfig] = readRunnerConfigs(self.globalCFG.runnersCFG, self.homeDirectory)

        for cfgData in self.runnerCFGs:
            if not (self.ignoreEnabled or cfgData.enabled):
                continue
            try:
                newCrawler = Crawler(runnerCFG=cfgData, globalCFG=self.globalCFG)
                self.crawlers.append(newCrawler)
                logging.debug(f"Created Crowler '{newCrawler.name}'")
            except Exception as exc:
                logging.error(f"Problems creating Crawler '{cfgData.filename}'  {type(exc)}:{exc}", stack_info=True)

        if not (self.crawlers):
            logging.warning("No crawlers to execute")
            sys.exit(1)

    def download(self):
        for crawler in self.crawlers:
            crawler.go()

    def save(self):
        for crawler in self.crawlers:
            savedFiles = []
            if crawler.results:
                for res in crawler.results:
                    try:
                        res.saveFiles(self.globalCFG.imagesD(), self.globalCFG.metadataD())
                        crawler.state.update(res)
                        crawler.state.store()
                        savedFiles.append(res)
                    except Exception as exc:
                        logging.error(f"Crawler '{crawler.name}': problem saving results:{type(exc)} {exc}")
                        break
                if len(savedFiles) != len(crawler.results):
                    crawler.results = savedFiles

    def print(self):
        lines: List[str] = []

        for i, crawler in enumerate(sorted(self.crawlers, key=lambda c: c.name), start=1):
            if crawler.results:
                lines.append(f"[{i}] Crawler: '{crawler.name}' ({crawler.runnerCFG.mode}@{crawler.runnerCFG.filename})")
                numImgs = len(crawler.results)
                for k, image in enumerate(crawler.results, start=1):
                    lines.append(f"     [{k}/{numImgs}] {image}")

            lines.append("")

        print("\n".join(lines))

    def email(self):
        mailDelivery = MailDelivery(self)

        mailDelivery.print()

        mailDelivery.prepareCargo()
        mailDelivery.sendCargo()


class MailDelivery:
    def __init__(self, harvest: Harvest):
        self.mailConfig = harvest.globalCFG.mailCFG
        self.mailMaxSize = harvest.globalCFG.mailCFG.mailMaxSize
        self.messages: List[MailMessage] = []
        self.currMessage: Optional[MailMessage] = None
        self.timestamp = strftime("%Y/%m/%d-%H:%M %z", gmtime())
        self.cargo: List[MIMEMultipart] = []
        self.prepareDelivery(harvest)

    def prepareDelivery(self, harvest: Harvest):

        for crawler in sorted(harvest.crawlers, key=lambda c: c.name):
            crawlerMessages: List[MailMessage] = []
            if not crawler.results:
                continue

            for image in crawler.results:
                if self.currMessage is None:
                    self.addMessage()
                    crawlerMessages.append(self.currMessage)

                if (self.currMessage.size + image.size()) <= self.mailMaxSize:
                    self.currMessage.addImage(crawler, image)
                else:
                    self.addMessage()
                    crawlerMessages.append(self.currMessage)
                    if (self.currMessage.size + image.size()) > self.mailMaxSize:
                        logging.warning(
                                f"Image size ({image.size()}) exceeds maximum allowed limit ({self.mailMaxSize}). "
                                f"Sending "
                                f"anyway but it may not reach destination")
                    self.currMessage.addImage(crawler, image)

            for bid, msg in enumerate(crawlerMessages, start=1):
                msg.bundles[crawler.name].setId(bid)
                msg.bundles[crawler.name].setCnt(len(crawlerMessages))

        for msg in self.messages:
            msg.setCnt(len(self.messages))

    def addMessage(self):
        result = MailMessage(len(self.messages) + 1)
        self.messages.append(result)
        self.currMessage = result

        return result

    def print(self):
        lines: List[str] = []

        lines.append(f" Mails to deliver: {len(self.messages)}")
        for i, msg in enumerate(self.messages, start=1):
            lines.append(msg.print(i, 0))

        print("\n".join(lines))

    def prepareCargo(self):
        subject = f"{self.mailConfig.subject} {self.timestamp}"
        self.cargo = [msg.compose(config=self.mailConfig, subject=subject) for msg in self.messages]

    def sendCargo(self):
        if not self.cargo:
            return

        try:
            server = smtplib.SMTP(self.mailConfig.SMTPHOST, self.mailConfig.SMTPPORT)
            server.ehlo()  # Can be omitted

            for msg in self.cargo:
                server.sendmail(self.mailConfig.sender, self.mailConfig.to, msg.as_string())
        except Exception as e:
            # Print any error messages to stdout
            logging.error(e)
        finally:
            server.quit()
