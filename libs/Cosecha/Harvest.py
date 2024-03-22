import logging
from operator import itemgetter
import sys

from .Crawler import Crawler
from .Config import globalConfig,runnerConfig,readRunnerConfigs


class Harvest:
    def __init__(self, config:globalConfig, homeDirectory:str, sendEmails:bool=True, ignoreEnabled:bool=False):

        #Configuration items
        self.globalCFG: globalConfig = config
        self.runnerCFGs:list[runnerConfig] = []
        self.homeDirectory = homeDirectory

        #Execution parameters
        self.sendEmails:bool = sendEmails
        self.ignoreEnabled:bool = ignoreEnabled

        #Working objects
        self.crawlers:list[Crawler] = []


    def go(self):
        self.prepare()
        self.download()

        if not self.globalCFG.dryRun:
            self.save()

    def prepare(self):
        """
        Creates Crawler objects from configuration files
        :return:
        """
        self.runnerCFGs: list[runnerConfig] = readRunnerConfigs(self.globalCFG.runnersCFG, self.homeDirectory)

        for cfgData in self.runnerCFGs:
            if not(self.ignoreEnabled or cfgData.enabled):
                continue
            try:
                newCrawler = Crawler(runnerCFG=cfgData, globalCFG=self.globalCFG)
                self.crawlers.append(newCrawler)
                logging.debug(f"Created Crowler '{newCrawler.name}'")
            except Exception as exc:
                logging.error(f"Problems creating Crawler '{cfgData.filename}'  {type(exc)}:{exc}",stack_info=True)

        if not(self.crawlers):
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
        for crawler in sorted(self.crawlers,key=lambda c:c.name):
            if crawler.results:
                print(f"{crawler.name} -> {crawler.runnerCFG.mode}@{crawler.runnerCFG.filename}")

            for res in crawler.results:
                    print(f"{crawler.name} -> {res}")



    def email(self):
        pass
