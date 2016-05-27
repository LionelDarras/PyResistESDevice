# -*- coding: utf-8 -*-
'''
    pyresistesdevice
    ----------------

    The public API and command-line interface to PyResistESDevice package.

    :copyright: Copyright 2015 Lionel Darras and contributors, see AUTHORS.
    :license: GNU GPL v3.

'''
# Make sure the logger is configured early:
from .logger import LOGGER, active_logger
from .device import ResistESDevice

VERSION = '0.13'
__version__ = VERSION
