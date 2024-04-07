from pony.orm import PrimaryKey,Required,Json,Optional
import datetime

#https://docs.ponyorm.org/firststeps.html
from .DBstore import DB

class ImageMetadataDB(DB.Entity):
    timestamp = Required(datetime.datetime)
    key = Required(str)
    comicID = Required(str)
    comicDate = Required(str)
    URL = Required(str)
    URLmedia = Required(str)
    crawlerName = Required(str)
    hash = Required(str,index=True)
    size = Required(int,size=24,unsigned=True)
    fname = Optional(str)
    info = Required(Json)
    PrimaryKey(key,comicID)


class ChannelStateDB(DB.Entity):
    runnerName = PrimaryKey(str)
    lastId = Required(str)
    lastUpdated = Required(datetime.datetime,volatile=True, sql_type='TIMESTAMP WITH TIME ZONE')
    lastURL = Required(str)
    lastMediaURL = Optional(str)