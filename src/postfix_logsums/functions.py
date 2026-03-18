#!/bin/env python3
# -*- coding: utf-8 -*-
"""
@summary: A log analyzer/summarizer for the Postfix MTA.

This module contains common used functions in this package.

@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 - 2026 by Frank Brehm, Berlin
"""

from __future__ import absolute_import

import logging
import os
import pprint
import re
import shutil
import sys

# Own modules
from . import DEFAULT_TERMINAL_HEIGHT
from . import DEFAULT_TERMINAL_WIDTH
from .xlate import XLATOR

__version__ = "0.1.0"
__author__ = "Frank Brehm <frank@brehm-online.com>"
__copyright__ = "(C) 2023 - 2026 by Frank Brehm, Berlin"

LOG = logging.getLogger(__name__)

_ = XLATOR.gettext


# =============================================================================
def pp(value, indent=4, width=None, depth=None):
    """
    Return a pretty print string of the given value.

    @return: pretty print string
    @rtype: str
    """
    if not width:
        term_size = shutil.get_terminal_size((DEFAULT_TERMINAL_WIDTH, DEFAULT_TERMINAL_HEIGHT))
        width = term_size.columns

    pretty_printer = pprint.PrettyPrinter(indent=indent, width=width, depth=depth)
    return pretty_printer.pformat(value)


# =============================================================================
def encode_or_bust(obj, encoding="utf-8"):
    """Convert given value to a byte string withe the given encoding."""
    if isinstance(obj, str):
        obj = obj.encode(encoding)

    return obj


# =============================================================================
def to_bytes(obj, encoding="utf-8"):
    """Do the same as encode_or_bust()."""
    return encode_or_bust(obj, encoding)


# =============================================================================
def to_utf8(obj):
    """Convert given value to a utf-8 encoded byte string."""
    return encode_or_bust(obj, "utf-8")


# =============================================================================
def get_generic_appname(appname=None):
    """Evaluate the current application name."""
    if appname:
        v = str(appname).strip()
        if v:
            return v
    aname = sys.argv[0]
    aname = re.sub(r"\.py$", "", aname, flags=re.IGNORECASE)
    return os.path.basename(aname)


# =============================================================================
def get_smh(seconds):
    """Get seconds, minutes and hours from seconds."""
    hours = int(seconds / 3600)
    seconds -= hours * 3600
    minutes = int(seconds / 60)
    seconds -= minutes * 60

    return (seconds, minutes, hours)


# =============================================================================

if __name__ == "__main__":

    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
