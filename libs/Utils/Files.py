import logging
import re
from hashlib import file_digest, sha256

import yaml


def loadYAML(filename: str):
    with open(filename, "r") as file:
        inHash = yaml.safe_load(file)

    return inHash


def saveYAML(data, filename: str):
    with open(filename, "w") as file:
        yaml.safe_dump(data, file, indent=2, sort_keys=True)


def sha256sum(filename):
    with open(filename, 'rb', buffering=0) as f:
        return file_digest(f, 'sha256').hexdigest()


# From: https://stackoverflow.com/a/44873382
# Digest method must be in sync with function shaData
def shaFile(filename):
    with open(filename, 'rb', buffering=0) as f:
        return file_digest(f, 'sha256').hexdigest()


# Digest method must be in sync with function shaFile
def shaData(data):
    result = sha256(data, usedforsecurity=False).hexdigest()

    return result


def extensionFromType(dataType: str):
    if dataType in {'image/png'}:
        return 'png'
    elif dataType in {'image/jpeg'}:
        return 'jpg'
    elif dataType in {'image/gif'}:
        return 'gif'
    logging.error(f"Unknown type {dataType}")
    raise TypeError(f"Unknown type {dataType}")


# From https://stackoverflow.com/a/55101759
def getSaneFilenameStr(inStr: str) -> str:
    validchars = "-_.()"
    out = ""
    for c in inStr.strip():
        if str.isalpha(c) or str.isdigit(c) or (c in validchars):
            out += c
        else:
            out += "_"

    result = re.sub(r'__+', r'_', out).strip('_')

    return result
