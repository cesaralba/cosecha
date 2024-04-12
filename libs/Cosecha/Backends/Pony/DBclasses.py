import datetime

from pony.orm import Json, Optional, PrimaryKey, Required

# https://docs.ponyorm.org/firststeps.html
from .DBstore import DB


class ImageMetadataDB(DB.Entity):
    timestamp = Required(datetime.datetime)
    key = Required(str)
    comicId = Required(str)
    comicDate = Optional(str)
    URL = Required(str)
    mediaURL = Required(str)
    mediaHash = Required(str, index=True)
    mediaSize = Required(int, size=24, unsigned=True)
    fname = Optional(str)
    info = Optional(Json)
    PrimaryKey(key, comicId)


class ChannelStateDB(DB.Entity):
    runnerName = PrimaryKey(str)
    lastId = Required(str)
    lastUpdated = Required(datetime.datetime, sql_type='TIMESTAMP WITH TIME ZONE')
    lastURL = Required(str)
    lastMediaURL = Optional(str)
