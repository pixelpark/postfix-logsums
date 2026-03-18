#!/bin/env python3
# -*- coding: utf-8 -*-
"""
@summary: A log analyzer/summarizer for the Postfix MTA.

@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 - 2026 by Frank Brehm, Berlin
"""

from __future__ import absolute_import

import logging

__version__ = "0.9.9"
__author__ = "Frank Brehm <frank@brehm-online.com>"
__copyright__ = "(C) 2023 - 2026 by Frank Brehm, Berlin"

DEFAULT_TERMINAL_WIDTH = 99
DEFAULT_TERMINAL_HEIGHT = 40
MAX_TERMINAL_WIDTH = 150

UTF8_ENCODING = "utf-8"
DEFAULT_ENCODING = UTF8_ENCODING
DEFAULT_SYSLOG_NAME = "postfix"
DEFAULT_MAX_TRIM_LENGTH = 66

# Own modules
from .parser import PostfixLogParser
from .xlate import XLATOR

LOG = logging.getLogger(__name__)

_ = XLATOR.gettext

__all__ = ['PostfixLogParser']


# =============================================================================

if __name__ == "__main__":
    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
