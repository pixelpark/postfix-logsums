#!/bin/env python3
# -*- coding: utf-8 -*-
"""
@summary: A module for all result classesin this package

@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 by Frank Brehm, Berlin
"""
from __future__ import absolute_import

import logging

from .stats import HourlyStats, MessageStatsTotals, HourlyStatsSmtpd
from .stats import DailyStatsDict, MessageStatsPerDay, SmtpdStats
from .stats import CommonStatsDict

__version__ = '0.5.5'
__author__ = 'Frank Brehm <frank@brehm-online.com>'
__copyright__ = '(C) 2023 by Frank Brehm, Berlin'

LOG = logging.getLogger(__name__)


# =============================================================================
class PostfixLogSums(object):
    """A class for encaplsulating the results of parsing of postfix logfiles."""

    # -------------------------------------------------------------------------
    def __init__(self, smtpd_stats=False):
        """Constructor."""
        self._smtpd_stats = False
        self.smtpd_stats = smtpd_stats

        self.reset()

    # -------------------------------------------------------------------------
    @property
    def smtpd_stats(self):
        """Generate smtpd connection statistics."""
        return self._smtpd_stats

    @smtpd_stats.setter
    def smtpd_stats(self, value):
        self._smtpd_stats = bool(value)

    # -------------------------------------------------------------------------
    def reset(self):
        """Resetting all counters and result structs."""
        self._files_index = None
        self.amavis_msgs = 0
        self.bounced = {}
        self.bounced_messages_per_hour = HourlyStats()
        self.cleanup_warnings = {}
        self.connections_time = 0
        self.connections_total = 0
        self.days_counted = 0
        self.deferred = {}
        self.deferred_messages_per_hour = HourlyStats()
        self.delivered_messages_per_hour = HourlyStats()
        self.discards = {}
        self.fatals = {}
        self.files = []
        self.holds = {}
        self.lines_considered = 0
        self.lines_total = 0
        self.logdate_oldest = None
        self.logdate_latest = None
        self.master_msgs = {}
        self.message_details = {}
        self.messages_per_day = DailyStatsDict(stats_class=MessageStatsPerDay)
        self.msgs_total = MessageStatsTotals()
        self.no_message_size = {}
        self.panics = {}
        self.postfix_messages = {}
        self.postfix_script = {}
        self.rcpt_domain = CommonStatsDict()
        self.rcpt_user = CommonStatsDict()
        self.received_messages_per_hour = HourlyStats()
        self.rejected_messages_per_hour = HourlyStats()
        self.rejects = {}
        self.sending_domain_data = CommonStatsDict()
        self.sending_user_data = CommonStatsDict()
        self.smtp_messages = {}
        self.smtp_connection_details = {
            'other': {},
            'trusted': {},
            'untrusted': {},
        }
        self.smtp_connections = {
            'other': 0,
            'total': 0,
            'trusted': 0,
            'untrusted': 0,
        }
        self.smtpd_per_day = DailyStatsDict(stats_class=SmtpdStats)
        self.smtpd_per_domain = CommonStatsDict()
        self.smtpd_messages_per_hour = None
        if self.smtpd_stats:
            self.smtpd_messages_per_hour = HourlyStatsSmtpd()
        self.warnings = {}

    # -------------------------------------------------------------------------
    def start_logfile(self, logfile):
        """Creates an entry for a new logfile in self.files and sets self.files_index
        to the index of the new created entry."""
        entry = {
            'file': logfile,
            'lines_total': 0,
            'lines_considered': 0,
        }

        self.files.append(entry)
        self._files_index = len(self.files) - 1

    # -------------------------------------------------------------------------
    def incr_lines_total(self, increment=1):
        """Increment all counters for all evaluated lines."""
        self.lines_total += increment
        if self._files_index is not None:
            self.files[self._files_index]['lines_total'] += increment

    # -------------------------------------------------------------------------
    def incr_lines_considered(self, increment=1):
        """Increment all counters for all considered lines."""
        self.lines_considered += increment
        if self._files_index is not None:
            self.files[self._files_index]['lines_considered'] += increment

    # -------------------------------------------------------------------------
    def as_dict(self, short=True, pure=False):
        """
        Transforms the elements of the object into a dict

        @param short: don't include local properties in resulting dict.
        @type short: bool

        @return: structure as dict
        @rtype:  dict
        """

        res = {}
        for key in self.__dict__:
            if short and key.startswith('_') and not key.startswith('__'):
                continue
            # LOG.debug("Typecasting {!r} ...".format(key))
            if key in ('msgs_total', 'messages_per_day', 'smtpd_per_day'):
                res[key] = getattr(self, key).dict()
            elif isinstance(getattr(self, key), CommonStatsDict):
                res[key] = getattr(self, key).as_dict(pure=pure)
            elif key == 'files':
                if pure:
                    res[key] = []
                    for f in self.files:
                        fs = {
                            'file': str(f['file']),
                            'lines_considered': f['lines_considered'],
                            'lines_total': f['lines_total'],
                        }
                        res[key].append(fs)
                else:
                    res[key] = self.__dict__[key]
            elif key == 'smtpd_messages_per_hour':
                # LOG.debug("Typecasting smtpd_messages_per_hour into a list ...")
                if self.smtpd_messages_per_hour is None:
                    res[key] = None
                else:
                    res[key] = self.smtpd_messages_per_hour.as_list(pure=pure)
            elif key in (
                    'bounced_messages_per_hour', 'deferred_messages_per_hour',
                    'delivered_messages_per_hour', 'received_messages_per_hour',
                    'rejected_messages_per_hour'):
                if pure:
                    res[key] = getattr(self, key).as_list()
                else:
                    res[key] = self.__dict__[key]
            elif key in ('logdate_latest', 'logdate_oldest'):
                if pure:
                    dt = getattr(self, key, None)
                    if dt:
                        dt = dt.isoformat(' ')
                    res[key] = dt
                else:
                    res[key] = self.__dict__[key]
            elif key in ('messages_per_day', ):
                if pure:
                    stats_dict = getattr(self, key)
                    if isinstance(stats_dict, dict):
                        res[key] = {}
                        for day in getattr(self, key).keys():
                            stats = stats_dict[day].dict()
                            res[key][day] = stats
                    else:
                        res[key] = None
            else:
                res[key] = self.__dict__[key]

        if not pure:
            res['__class_name__'] = self.__class__.__name__

        return res

    # -------------------------------------------------------------------------
    def dict(self):
        """Typecast into a regular dict."""
        return self.as_dict(pure=True)


# =============================================================================

if __name__ == "__main__":

    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
