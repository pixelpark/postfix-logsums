#!/bin/env python3
# -*- coding: utf-8 -*-
"""
@summary: A log analyzer/summarizer for the Postfix MTA.

@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 by Frank Brehm, Berlin
"""

import pprint
import shutil
import sys
import os
import re
import datetime
import copy
import codecs
import gzip
import bz2
import lzma
import logging

__version__ = '0.3.2'
__author__ = 'Frank Brehm <frank@brehm-online.com>'
__copyright__ = '(C) 2023 by Frank Brehm, Berlin'

DEFAULT_TERMINAL_WIDTH = 99
DEFAULT_TERMINAL_HEIGHT = 40
MAX_TERMINAL_WIDTH = 150

UTF8_ENCODING = 'utf-8'
DEFAULT_ENCODING = UTF8_ENCODING
DEFAULT_SYSLOG_NAME = 'postfix'

LOG = logging.getLogger(__name__)


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
class PostfixLogsumError(Exception):
    """Base exception class for all exceptions in this package."""

    pass


# =============================================================================
def get_generic_appname(appname=None):
    """Evaluate the current application name."""
    if appname:
        v = str(appname).strip()
        if v:
            return v
    aname = sys.argv[0]
    aname = re.sub(r'\.py$', '', aname, flags=re.IGNORECASE)
    return os.path.basename(aname)


# =============================================================================
class PostfixLogSums(object):
    """A class for the results of parsing of postfix logfiles."""

    # -------------------------------------------------------------------------
    def __init__(self):
        """Constructor."""
        self.reset()

    # -------------------------------------------------------------------------
    def reset(self):
        """Resetting all counters and result structs."""
        self.lines_total = 0
        self.lines_considered = 0
        self._files_index = None
        self.files = []

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
    def as_dict(self, short=True):
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
            res[key] = self.__dict__[key]

        res['__class_name__'] = self.__class__.__name__

        return res

# =============================================================================
class PostfixLogParser(object):
    """The underlaying class for parsing Postfix logfiles."""

    # Class variables as constants

    div_by_one_k_at = 512 * 1024
    div_by_one_mb_at = 512 * 1024 * 1024
    one_k = 1024
    one_mb = 1024 * 1024

    month_names = (
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
    month_nums = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12, }

    today = datetime.date.today()
    this_month = today.month
    this_year = today.year

    valid_compressions = ('gzip', 'bzip2', 'xz', 'lzma')

    re_gzip = re.compile(r'\.gz$', re.IGNORECASE)
    re_bzip2 = re.compile(r'\.(bz2?|bzip2?)$', re.IGNORECASE)
    re_lzma = re.compile(r'\.(xz|lzma)$', re.IGNORECASE)

    utc = datetime.timezone(datetime.timedelta(0), 'UTC')

    default_encoding = DEFAULT_ENCODING

    # -------------------------------------------------------------------------
    def __init__(
            self, appname=None, verbose=0, day=None, syslog_name=DEFAULT_SYSLOG_NAME,
            compression=None, encoding=DEFAULT_ENCODING):
        """Constructor."""

        self._appname = get_generic_appname()
        self._verbose = 0
        self._initialized = False
        self._compression = None
        self._encoding = self.default_encoding
        self._syslog_name = DEFAULT_SYSLOG_NAME

        self.re_date_filter = None
        self.re_date_filter_rfc3339 = None
        self.results = PostfixLogSums()

        if day:
            t_diff = datetime.timedelta(days=1)
            used_date = copy.copy(self.today)
            if day == 'yesterday':
                used_date = self.today - t_diff
            elif day != 'today':
                msg = "Wrong day {d!r} given. Valid values are {n}, {y!r} and {t!r}.".format(
                        d=day, n='None', y='yesterday', t='today')
                raise PostfixLogsumError(msg)
            filter_pattern = "^{m} {d:02d}\s".format(
                m=self.month_names[used_date.month - 1], d=used_date.day)
            self.re_date_filter = re.compile(filter_pattern, re.IGNORECASE)
            filter_rfc3339_pattern = "^{y:04d}-{m:02d}-{d:02d}[T\s]".format(
                y=used_date.year, m=used_date.month, d=used_date.day)
            self.re_date_filter_rfc3339 = re.compile(filter_rfc3339_pattern, re.IGNORECASE)

        if appname:
            self.appname = appname
        self.verbose = verbose
        self.compression = compression
        self.syslog_name = syslog_name

        pattern_date = r'^(?P<month_str>...) {1,2}(?P<day>\d{1,2}) '
        pattern_date += r'(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2}) \S+ (?P<msg>.+)$/'
        self.re_date = re.compile(pattern_date)

        pattern_date_rfc3339 = r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})[T\s]'
        pattern_date_rfc3339 += r'(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})'
        pattern_date_rfc3339 += r'(?:\.\d+)?'
        pattern_date_rfc3339 += r'(?:(?P<tz_hours>[\+\-]\d{2}):(?P<tz_mins>\d{2})|Z)'
        pattern_date_rfc3339 += r' \S+ (?P<msg>.+)$'
        self.re_date_rfc3339 = re.compile(pattern_date_rfc3339, re.IGNORECASE)

        pattern_pf_command = r'^postfix'
        if self.syslog_name != 'postfix':
            pattern_pf_command = r'^(?:postfix|{})'.format(self.syslog_name)
        pattern_pf_command += r'(?:/(?:smtps|submission))?/([^\[:]*).*?: ([^:\s]+)'
        self.re_pf_command = re.compile(pattern_pf_command)

        pattern_pf_script = r'^((?:postfix)(?:-script)?)(?:\[\d+\])?: ([^:\s]+)'
        self.re_pf_script = re.compile(pattern_pf_script)

        if encoding:
            self.encoding = encoding
        else:
            self.encoding = self.default_encoding

        self._initialized = True

    # -----------------------------------------------------------
    @property
    def appname(self):
        """The name of the current running application."""
        if hasattr(self, '_appname'):
            return self._appname
        return os.path.basename(sys.argv[0])

    @appname.setter
    def appname(self, value):
        if value:
            v = str(value).strip()
            if v:
                self._appname = v

    # -----------------------------------------------------------
    @property
    def verbose(self):
        """The verbosity level."""
        return getattr(self, '_verbose', 0)

    @verbose.setter
    def verbose(self, value):
        v = int(value)
        if v >= 0:
            self._verbose = v
        else:
            LOG.warning(_("Wrong verbose level {!r}, must be >= 0").format(value))

    # -----------------------------------------------------------
    @property
    def initialized(self):
        """The initialisation of this object is complete."""
        return getattr(self, '_initialized', False)

    # -----------------------------------------------------------
    @property
    def syslog_name(self):
        """The name, which is used by syslog for entries in logfiles."""
        return self._syslog_name

    @syslog_name.setter
    def syslog_name(self, value):
        if value is None:
            msg = "The syslog name must not be None."
            raise TypeError(msg)
        v = str(value).strip()
        if v == '':
            msg = "The syslog name must not be empty."
            raise ValueError(msg)
        self._syslog_name = v

    # -----------------------------------------------------------
    @property
    def compression(self):
        """The compression explicitely to use for all logfiles and the input stream."""
        return self._compression

    @compression.setter
    def compression(self, value):
        if value is None:
            self._compression = None
            return
        v = str(value).strip().lower()
        if v not in self.valid_compressions:
            msg = "Invalid compression {!r} given.".format(value)
            raise PostfixLogsumError(msg)
        if v == 'xz':
            self._compression = 'lzma'
        else:
            self._compression = v

    # -------------------------------------------------------------------------
    @property
    def encoding(self):
        """Return the default encoding used to read config files."""
        return self._encoding

    @encoding.setter
    def encoding(self, value):
        if not isinstance(value, str):
            msg = _(
                "Encoding {v!r} must be a {s!r} object, "
                "but is a {c!r} object instead.").format(
                v=value, s='str', c=value.__class__.__name__)
            raise TypeError(msg)

        encoder = codecs.lookup(value)
        self._encoding = encoder.name

    # -------------------------------------------------------------------------
    def __str__(self):
        """
        Typecasting function for translating object structure
        into a string

        @return: structure as string
        @rtype:  str
        """

        return pp(self.as_dict(short=True))

    # -------------------------------------------------------------------------
    def as_dict(self, short=True):
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
            res[key] = self.__dict__[key]

        res['__class_name__'] = self.__class__.__name__
        res['appname'] = self.appname
        res['compression'] = self.compression
        res['encoding'] = self.encoding
        res['initialized'] = self.initialized
        res['results'] = self.results.as_dict(short=short)
        res['syslog_name'] = self.syslog_name
        res['this_month'] = self.this_month
        res['this_year'] = self.this_year
        res['today'] = self.today
        res['verbose'] = self.verbose

        return res

    # -------------------------------------------------------------------------
    def parse(self, *files):
        """Main entry point of this class."""

        self.results.reset()

        if not files:
            LOG.info("Parsing from STDIN ...")
            self.results.start_logfile('STDIN')
            return self.parse_fh(sys.stdin, 'STDIN', self.compression)

        for logfile in files:
            LOG.info("Parsing logfile {!r} ...".format(str(logfile)))
            self.results.start_logfile(logfile)
            if not self.parse_file(logfile):
                return False

        return True

    # -------------------------------------------------------------------------
    def parse_file(self, logfile):
        """Parsing a particular logfile."""

        open_opts = {
            'encoding': self.encoding,
            'errors': 'surrogateescape',
        }

        compression = None

        if self.compression:
            compression = self.compression
        else:
            if self.re_gzip.search(logfile.name):
                compression = 'gzip'
            elif self.re_bzip2.search(logfile.name):
                compression = 'bzip2'
            elif self.re_lzma.search(logfile.name):
                compression = 'lzma'

        if compression:
            with logfile.open('rb') as fh:
                return self.parse_fh(fh, filename=str(logfile), compression=compression)
        else:
            with logfile.open('r', **open_opts) as fh:
                return self.parse_fh(fh, filename=str(logfile))

    # -------------------------------------------------------------------------
    def parse_fh(self, fh, filename, compression=None):

        line = None

        if not compression:
            LOG.debug("Reading uncompressed file {!r} ...".format(filename))
            line = fh.readline()
            while line:
                self.eval_line(line)
                line = fh.readline()
            return True

        cdata = fh.read()

        if compression == 'gzip':
            LOG.debug("Reading {w} compressed file {f!r} ...".format(
                w='GZIP', f=filename))
            self.read_gzip(cdata)
            return True

        if compression == 'bzip2':
            LOG.debug("Reading {w} compressed file {f!r} ...".format(
                w='BZIP2', f=filename))
            self.read_bzip2(cdata)
            return True

        if compression == 'lzma':
            LOG.debug("Reading {w} compressed file {f!r} ...".format(
                w='LZMA', f=filename))
            self.read_lzma(cdata)
            return True

    # -------------------------------------------------------------------------
    def read_gzip(self, cdata):

        bdata = gzip.decompress(cdata)
        data = bdata.decode(self.encoding)

        for line in data.splitlines():
            self.eval_line(line)

    # -------------------------------------------------------------------------
    def read_bzip2(self, cdata):

        bdata = bz2.decompress(cdata)
        data = bdata.decode(self.encoding)

        for line in data.splitlines():
            self.eval_line(line)

    # -------------------------------------------------------------------------
    def read_lzma(self, cdata):

        bdata = lzma.decompress(cdata)
        data = bdata.decode(self.encoding)

        for line in data.splitlines():
            self.eval_line(line)

    # -------------------------------------------------------------------------
    def eval_line(self, line):

        self.results.incr_lines_total()

        if self.re_date_filter:
            matched = False
            if self.re_date_filter.match(line):
                matched = True
            elif self.re_date_filter_rfc3339.match(line):
                matched = True
            if not matched:
                return

        year = None
        month = None
        day = None
        hour = None
        minute = None
        second = None
        tz = None

        msg_ts = None
        message = None

        m = self.re_date.match(line)
        if m:
            month_str = m['month_str']
            month = self.month_nums[month_str]
            day = int(m['day'])
            hour = int(m['hour'])
            minute = int(m['minute'])
            second = int(m['second'])
            year = self.this_year
            if month > self.this_month:
                year -= 1

            msg_ts = datetime.datetime(year, month, day, hour, minute, second, tzinfo=self.utc)
            message = m['msg']
        else:
            m = self.re_date_rfc3339.match(line)
            if m:
                year = int(m['year'])
                month = int(m['month'])
                day = int(m['day'])
                hour = int(m['hour'])
                minute = int(m['minute'])
                second = int(m['second'])

                tz = self.utc
                tz_hours = m['tz_hours']
                tz_mins = m['tz_mins']
                if tz_hours is not None and tz_mins is not None:
                    tz_hours = int(tz_hours)
                    tz_mins = int(tz_mins)
                    delta = datetime.timedelta(hours=tz_hours, minutes=tz_mins)
                    tz = datetime.timezone(delta, 'Local_TZ')

                msg_ts = datetime.datetime(year, month, day, hour, minute, second, tzinfo=tz)
                message = m['msg']

        if not msg_ts:
            return

        if self.verbose > 4:
            LOG.debug("Found message: {ts}: {msg}".format(ts=msg_ts.isoformat(' '), msg=message))

        self.results.incr_lines_considered()


# =============================================================================

if __name__ == "__main__":

    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
