"""
Python specific functions
"""
from importlib import import_module

import sys


def LoadModule(moduleName: str, classLocation: str):
    fullModName = f"{classLocation}.{moduleName}"

    if fullModName not in sys.modules:
        import_module(fullModName, classLocation)

    return fullModName,sys.modules[fullModName]
