#!/bin/env python3
# -*- coding: utf-8 -*-
"""
@summary: a module for all error (exception) classes used in this package

@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 by Frank Brehm, Berlin
"""

__version__ = '0.1.1'
__author__ = 'Frank Brehm <frank@brehm-online.com>'
__copyright__ = '(C) 2023 by Frank Brehm, Berlin'


# =============================================================================
class PostfixLogsumsError(Exception):
    """Base error class for all exceptions in this package."""

    pass


# =============================================================================
class WrongMsgStatsKeyError(PostfixLogsumsError, KeyError):
    """Error class for a wrong key for the MessageStats object."""

    # -------------------------------------------------------------------------
    def __init__(self, key):
        """Initialise a WrongMsgStatsKeyError exception."""

        self.key = key
        super(WrongMsgStatsKeyError, self).__init__()

    # -------------------------------------------------------------------------
    def __str__(self):
        """Typecast into str."""
        msg = "Invalid key {k!r} for a {w} object."
        return msg.format(k=self.key, w='MessageStats')


# =============================================================================

if __name__ == "__main__":

    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
