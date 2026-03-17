#!/bin/env python3
# -*- coding: utf-8 -*-
"""
@summary: a module for all error (exception) classes used in this package

@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 by Frank Brehm, Berlin
"""

from .xlate import XLATOR

__version__ = '0.5.0'
__author__ = 'Frank Brehm <frank@brehm-online.com>'
__copyright__ = '(C) 2023 by Frank Brehm, Berlin'

_ = XLATOR.gettext


# =============================================================================
class PostfixLogsumsError(Exception):
    """Base error class for all exceptions in this package."""

    pass


# =============================================================================
class StatsError(PostfixLogsumsError):
    """Base error class for all exceptions the statistics module."""

    pass


# =============================================================================
class WrongDateKeyError(StatsError, ValueError):
    """Error class for a wrong date key for a DailyStatsDict."""

    # -------------------------------------------------------------------------
    def __init__(self, key, err_msg=None):
        """Initialise a WrongDateKeyError exception."""
        self.key = key
        self.err_msg = err_msg
        super(WrongDateKeyError, self).__init__()

    # -------------------------------------------------------------------------
    def __str__(self):
        """Typecast into str."""
        if self.err_msg:
            msg = _("Invalid key {k!r} for a {what}, must be valid date: {e}")
        else:
            msg = _("Invalid key {k!r} for a {what}, must be valid date.")
        return msg.format(k=self.key, what='DailyStatsDict', e=self.err_msg)

# =============================================================================
class WrongDailyKeyError(StatsError, KeyError):
    """Error class for a invalid key for a DailyStatsDict."""

    # -------------------------------------------------------------------------
    def __init__(self, key, err_msg=None):
        """Initialise a WrongDailyKeyError exception."""
        self.key = key
        self.err_msg = err_msg
        super(WrongDailyKeyError, self).__init__()

    # -------------------------------------------------------------------------
    def __str__(self):
        """Typecast into str."""
        if self.err_msg:
            msg = _("Key error for key {k!r} for a {what}: {e}")
        else:
            msg = _("Key error for {k!r} for a {what}.")
        return msg.format(k=self.key, what='DailyStatsDict', e=self.err_msg)

# =============================================================================
class WrongMsgStatsAttributeError(StatsError, AttributeError):
    """Error class for a wrong attribute in a MessageStats object."""

    # -------------------------------------------------------------------------
    def __init__(self, attribute, class_name):
        """Initialise a WrongMsgStatsAttributeError exception."""
        self.attribute = attribute
        self.class_name = class_name
        super(WrongMsgStatsAttributeError, self).__init__()

    # -------------------------------------------------------------------------
    def __str__(self):
        """Typecast into str."""
        msg = _("Invalid attribute {attr!r} for a {w} object.")
        return msg.format(attr=self.attribute, w=self.class_name)


# =============================================================================
class WrongMsgStatsValueError(StatsError, ValueError):
    """Error class for a wrong value for a MessageStats value."""

    pass


# =============================================================================
class WrongMsgStatsKeyError(StatsError, KeyError):
    """Error class for a wrong key for the MessageStats object."""

    # -------------------------------------------------------------------------
    def __init__(self, key, obj_type='MessageStats'):
        """Initialise a WrongMsgStatsKeyError exception."""

        self.key = key
        self.obj_type = obj_type
        super(WrongMsgStatsKeyError, self).__init__()

    # -------------------------------------------------------------------------
    def __str__(self):
        """Typecast into str."""
        msg = _("Invalid key {k!r} for a {w} object.")
        return msg.format(k=self.key, w=self.obj_type)


# =============================================================================
class WrongMsgPerDayKeyError(StatsError, KeyError):
    """Error class for a wrong key for the MessageStatsPerDay object."""

    # -------------------------------------------------------------------------
    def __init__(self, key, obj_type='MessageStatsPerDay'):
        """Initialise a WrongMsgPerDayKeyError exception."""

        self.key = key
        self.obj_type = obj_type
        super(WrongMsgPerDayKeyError, self).__init__()

    # -------------------------------------------------------------------------
    def __str__(self):
        """Typecast into str."""
        msg = _("Invalid key {k!r} for a {w} object.")
        return msg.format(k=self.key, w=self.obj_type)


# =============================================================================
class WrongMsgStatsHourError(StatsError, KeyError):
    """Error class for a wrong hour for the HourlyStats object."""

    # -------------------------------------------------------------------------
    def __init__(self, hour, obj_type='HourlyStats'):
        """Initialise a WrongMsgStatsHourError exception."""

        self.hour = hour
        self.obj_type = obj_type
        super(WrongMsgStatsHourError, self).__init__()

    # -------------------------------------------------------------------------
    def __str__(self):
        """Typecast into str."""
        msg = _("Invalid hour {h!r} for a {w} object.")
        return msg.format(h=self.hour, w=self.obj_type)


# =============================================================================
class MsgStatsHourValNotfoundError(StatsError, ValueError):
    """Error class for a value not found error in the HourlyStats class."""

    # -------------------------------------------------------------------------
    def __init__(self, value, obj_type='HourlyStats'):
        """Initialise a MsgStatsHourValNotfoundError exception."""

        self.value = value
        self.obj_type = obj_type
        super(MsgStatsHourValNotfoundError, self).__init__()

    # -------------------------------------------------------------------------
    def __str__(self):
        """Typecast into str."""
        msg = _("Value {v!r} not found in the {w} object.")
        return msg.format(v=self.value, w=self.obj_type)


# =============================================================================
class MsgStatsHourInvalidMethodError(StatsError, RuntimeError):
    """Error class for an invalid method used with a HourlyStats class object."""

    # -------------------------------------------------------------------------
    def __init__(self, method, obj_type='HourlyStats'):
        """Initialise a MsgStatsHourInvalidMethodError exception."""

        self.method = method
        self.obj_type = obj_type
        super(MsgStatsHourInvalidMethodError, self).__init__()

    # -------------------------------------------------------------------------
    def __str__(self):
        """Typecast into str."""
        msg = _("Invalid method {m}() for a {w} object.")
        return msg.format(m=self.method, w=self.obj_type)


# =============================================================================

if __name__ == "__main__":

    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
