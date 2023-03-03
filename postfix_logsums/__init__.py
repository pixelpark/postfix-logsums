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

try:
    from collections.abc import MutableMapping, Mapping
except ImportError:
    from collections import MutableMapping, Mapping

__version__ = '0.5.3'
__author__ = 'Frank Brehm <frank@brehm-online.com>'
__copyright__ = '(C) 2023 by Frank Brehm, Berlin'

DEFAULT_TERMINAL_WIDTH = 99
DEFAULT_TERMINAL_HEIGHT = 40
MAX_TERMINAL_WIDTH = 150

UTF8_ENCODING = 'utf-8'
DEFAULT_ENCODING = UTF8_ENCODING
DEFAULT_SYSLOG_NAME = 'postfix'
DEFAULT_MAX_TRIM_LENGTH = 66

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
def encode_or_bust(obj, encoding='utf-8'):
    """Convert given value to a byte string withe the given encoding."""
    if isinstance(obj, str):
        obj = obj.encode(encoding)

    return obj


# =============================================================================
def to_bytes(obj, encoding='utf-8'):
    """Do the same as encode_or_bust()."""
    return encode_or_bust(obj, encoding)


# =============================================================================
def to_utf8(obj):
    """Convert given value to a utf-8 encoded byte string."""
    return encode_or_bust(obj, 'utf-8')


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
class MessageStats(MutableMapping):
    """A class for encapsulating message statistics."""

    valid_keys = ('count', 'size', 'defers', 'delay_avg', 'delay_max')

    # -------------------------------------------------------------------------
    def __init__(self, first_param=None, **kwargs):
        """Constructor."""
        self._count = 0
        self._size = 0
        self._defers = 0
        self._delay_avg = 0
        self._delay_max = 0

        if first_param is not None:

            # LOG.debug("First parameter type {t!r}: {p!r}".format(
            #     t=type(first_param), p=first_param))

            if isinstance(first_param, Mapping):
                self._update_from_mapping(first_param)
            elif first_param.__class__.__name__ == 'zip':
                self._update_from_mapping(dict(first_param))
            else:
                msg = "Object is not a {m} object, but a {w} object instead.".format(
                    m='Mapping', w=first_param.__class__.__qualname__)
                raise PostfixLogsumsError(msg)

        if kwargs:
            self._update_from_mapping(kwargs)

    # -------------------------------------------------------------------------
    def _update_from_mapping(self, mapping):

        for key in mapping.keys():
            if key not in self.valid_keys:
                raise WrongMsgStatsKeyError(key)
            setattr(self, key, mapping[key])

    # -----------------------------------------------------------
    @property
    def count(self):
        """The count of messages."""
        return getattr(self, '_count', 0)

    @count.setter
    def count(self, value):
        v = int(value)
        if v >= 0:
            self._count = v
        else:
            LOG.warning("Wrong count {!r}, must be >= 0".format(value))

    # -----------------------------------------------------------
    @property
    def size(self):
        """The accumulated size of messages."""
        return getattr(self, '_size', 0)

    @size.setter
    def size(self, value):
        v = int(value)
        if v >= 0:
            self._size = v
        else:
            LOG.warning("Wrong size {!r}, must be >= 0".format(value))

    # -----------------------------------------------------------
    @property
    def defers(self):
        """The number of defered messages."""
        return getattr(self, '_defers', 0)

    @defers.setter
    def defers(self, value):
        v = int(value)
        if v >= 0:
            self._defers = v
        else:
            LOG.warning("Wrong defers {!r}, must be >= 0".format(value))

    # -----------------------------------------------------------
    @property
    def delay_avg(self):
        """The total of delays (used for averaging)."""
        return getattr(self, '_delay_avg', 0)

    @delay_avg.setter
    def delay_avg(self, value):
        v = int(value)
        if v >= 0:
            self._delay_avg = v
        else:
            LOG.warning("Wrong delay_avg {!r}, must be >= 0".format(value))

    # -----------------------------------------------------------
    @property
    def delay_max(self):
        """The maximum delay."""
        return getattr(self, '_delay_max', 0)

    @delay_max.setter
    def delay_max(self, value):
        v = int(value)
        if v >= 0:
            self._delay_max = v
        else:
            LOG.warning("Wrong delay_max {!r}, must be >= 0".format(value))

    # -----------------------------------------------------------
    def as_dict(self, pure=False):
        """Transforms the elements of the object into a dict."""

        res = {}
        if not pure:
            res['__class_name__'] = self.__class__.__name__
        res['size'] = self.count
        res['count'] = self.size
        res['defers'] = self.defers
        res['delay_avg'] = self.delay_avg
        res['delay_max'] = self.delay_max

        return res

    # -------------------------------------------------------------------------
    def dict(self):
        """Typecast into a regular dict."""
        return self.as_dict(pure=True)

    # -----------------------------------------------------------
    def __repr__(self):
        """Typecast for reproduction."""
        ret = "{}({{".format(self.__class__.__name__)
        kargs = []
        for pair in self.items():
            arg = "{k!r}: {v!r}".format(k=pair[0], v=pair[1])
            kargs.append(arg)
        ret += ', '.join(kargs)
        ret += '})'

        return ret

    # -------------------------------------------------------------------------
    def __copy__(self):
        """Return a copy of the current set."""
        return self.__class__(self.dict())

    # -------------------------------------------------------------------------
    def copy(self):
        """Return a copy of the current set."""
        return self.__copy__()

    # -------------------------------------------------------------------------
    def _get_item(self, key):
        """Return an arbitrary item by the key."""
        if key not in self.valid_keys:
            raise WrongMsgStatsKeyError(key)

        return getattr(self, key, 0)

    # -------------------------------------------------------------------------
    def get(self, key):
        """Return an arbitrary item by the key."""
        return self._get_item(key)

    # -------------------------------------------------------------------------
    # The next four methods are requirements of the ABC.

    # -------------------------------------------------------------------------
    def __getitem__(self, key):
        """Return an arbitrary item by the key."""
        return self._get_item(key)

    # -------------------------------------------------------------------------
    def __iter__(self):
        """Return an iterator over all keys."""
        for key in self.keys():
            yield key

    # -------------------------------------------------------------------------
    def __len__(self):
        """Return the the nuber of entries (keys) in this dict."""
        return 4

    # -------------------------------------------------------------------------
    def __contains__(self, key):
        """Return, whether the given key exists(the 'in'-operator)."""
        if key in self.valid_keys:
            return True
        return False

    # -------------------------------------------------------------------------
    def keys(self):
        """Return a list with all keys in original notation."""
        return copy.copy(self.valid_keys)

    # -------------------------------------------------------------------------
    def items(self):
        """Return a list of all items of the current dict.

        An item is a tuple, with the key in original notation and the value.
        """
        item_list = []

        for key in sorted(self.keys()):
            value = self.get(key)
            item_list.append((key, value))

        return item_list

    # -------------------------------------------------------------------------
    def values(self):
        """Return a list with all values of the current dict."""
        return list(map(lambda x: self.get(x), self.keys()))

    # -------------------------------------------------------------------------
    def __setitem__(self, key, value):
        """Set the value of the given key."""
        if key not in self.valid_keys:
            raise WrongMsgStatsKeyError(key)

        setattr(self, key, value)

    # -------------------------------------------------------------------------
    def set(self, key, value):
        """Set the value of the given key."""
        self[key] = value

    # -------------------------------------------------------------------------
    def __delitem__(self, key):
        """Should delete the entry on the given key.
        But in real the value if this key set to zero instead."""
        if key not in self.valid_keys:
            raise WrongMsgStatsKeyError(key)

        setattr(self, key, 0)


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
        self.amavis_msgs = 0
        self.lines_total = 0
        self.lines_considered = 0
        self.days_counted = 0
        self.messages_received_total = 0
        self._files_index = None
        self.files = []
        self.messages_per_day = {}
        self.smtpd_per_day = {}
        self.smtpd_per_domain = {}
        self.connections_total = 0
        self.connections_time = 0
        self.received_messages_per_hour = []
        self.rejected_messages_per_hour = []
        self.delivered_messages_per_hour = []
        self.defered_messages_per_hour = []
        self.bounced_messages_per_hour = []
        self.smtpd_messages_per_hour = []
        self.messages = {
            'discard': 0,
            'hold': 0,
            'master': 0,
            'rejected': 0,
            'warning': 0,
        }
        self.rejects = {
            'cleanup': {},
        }
        self.warns = {
            'cleanup': {},
        }
        self.holds = {
            'cleanup': {},
        }
        self.discards = {
            'cleanup': {},
        }
        self.warnings = {}
        self.fatals = {}
        self.panics = {}
        self.master_msgs = {}
        self.message_details = {}
        self.sender_domain_count = 0
        self.sending_domain_data = {}
        self.sending_user_count = 0
        self.sending_user_data = {}
        self.received_size = 0
        self.messages_forwarded = 0
        self.rcpt_domain = {}
        self.rcpt_domain_count = 0
        self.rcpt_user = {}
        self.rcpt_user_count = 0

        for hour in range(0, 24):
            self.received_messages_per_hour.append(0)
            self.rejected_messages_per_hour.append(0)
            self.delivered_messages_per_hour.append(0)
            self.defered_messages_per_hour.append(0)
            self.bounced_messages_per_hour.append(0)
            self.smtpd_messages_per_hour.append([0, 0, 0])

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
    default_max_trim_length = DEFAULT_MAX_TRIM_LENGTH

    # -------------------------------------------------------------------------
    def __init__(
            self, appname=None, verbose=0, day=None, syslog_name=DEFAULT_SYSLOG_NAME,
            zero_fill=False, detail_verbose_msg=False, detail_reject=True,
            detail_smtpd_warning=True, ignore_case=False, rej_add_from=False,
            smtpd_stats=False, extended=False,
            verp_mung=None, compression=None, encoding=DEFAULT_ENCODING):
        """Constructor."""

        self._appname = get_generic_appname()
        self._verbose = 0
        self._initialized = False
        self._compression = None
        self._encoding = self.default_encoding
        self._syslog_name = DEFAULT_SYSLOG_NAME
        self._zero_fill = False
        self._detail_verbose_msg = False
        self._detail_reject = True
        self._detail_smtpd_warning = True
        self._ignore_case = False
        self._extended = False
        self._rej_add_from = False
        self._smtpd_stats = False
        self._verp_mung = None

        self._cur_ts = None
        self._cur_msg = None
        self._cur_pf_command = None
        self._cur_qid = None

        self.last_date = None

        self.re_date_filter = None
        self.re_date_filter_rfc3339 = None
        self.results = PostfixLogSums()

        self._rcvd_msgs_qid = {}
        self._connection_times = {}
        self._message_size = {}

        if day:
            t_diff = datetime.timedelta(days=1)
            used_date = copy.copy(self.today)
            if day == 'yesterday':
                used_date = self.today - t_diff
            elif day != 'today':
                msg = "Wrong day {d!r} given. Valid values are {n}, {y!r} and {t!r}.".format(
                    d=day, n='None', y='yesterday', t='today')
                raise PostfixLogsumsError(msg)
            filter_pattern = r"^{m} {d:02d}\s".format(
                m=self.month_names[used_date.month - 1], d=used_date.day)
            self.re_date_filter = re.compile(filter_pattern, re.IGNORECASE)
            filter_rfc3339_pattern = r"^{y:04d}-{m:02d}-{d:02d}[T\s]".format(
                y=used_date.year, m=used_date.month, d=used_date.day)
            self.re_date_filter_rfc3339 = re.compile(filter_rfc3339_pattern, re.IGNORECASE)

        if appname:
            self.appname = appname
        self.verbose = verbose
        self.compression = compression
        self.syslog_name = syslog_name
        self.zero_fill = zero_fill
        self.detail_verbose_msg = detail_verbose_msg
        self.detail_reject = detail_reject
        self.detail_smtpd_warning = detail_smtpd_warning
        self.extended = extended
        self.ignore_case = ignore_case
        self.rej_add_from = rej_add_from
        self.smtpd_stats = smtpd_stats
        self.verp_mung = verp_mung

        pattern_date = r'^(?P<month_str>...) {1,2}(?P<day>\d{1,2}) '
        pattern_date += r'(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2}) \S+ (?P<msg>.+)$/'
        self.re_date = re.compile(pattern_date)

        pattern_date_rfc3339 = r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})[T\s]'
        pattern_date_rfc3339 += r'(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})'
        pattern_date_rfc3339 += r'(?:\.\d+)?'
        pattern_date_rfc3339 += r'(?:(?P<tz_hours>[\+\-]\d{2}):(?P<tz_mins>\d{2})|Z)'
        pattern_date_rfc3339 += r' \S+ (?P<msg>.+)$'
        self.re_date_rfc3339 = re.compile(pattern_date_rfc3339, re.IGNORECASE)

        self.re_amavis = re.compile(r'^amavis\[\d+\]: ', re.IGNORECASE)

        pattern_pf_command = r'^postfix'
        if self.syslog_name != 'postfix':
            pattern_pf_command = r'^(?:postfix|{})'.format(self.syslog_name)
        pattern_pf_command += r'(?:/(?:smtps|submission))?/(?P<cmd>[^\[:]*).*?: (?P<qid>[^:\s]+)'
        self.re_pf_command = re.compile(pattern_pf_command)

        pattern_pf_script = r'^(?P<cmd>(?:postfix)(?:-script)?)(?:\[\d+\])?: (?P<qid>[^:\s]+)'
        self.re_pf_script = re.compile(pattern_pf_script)

        pattern_cmd_cleanup = r'\/cleanup\[\d+\]: .*?\b(?P<subtype>reject|warning|hold|discard): '
        pattern_cmd_cleanup += r'(?P<part>header|body) (?P<cmd_msg>.*)$'
        self.re_cmd_cleanup = re.compile(pattern_cmd_cleanup)

        self.re_clean_from = re.compile(r'( from \S+?)?; from=<.*$')
        self.re_warning = re.compile(r'^.*warning: ')
        self.re_fatal = re.compile(r'^.*fatal: ')
        self.re_panic = re.compile(r'^.*panic: ')
        self.re_master = re.compile(r'.*master.*: ')

        pat_re_reject = r'^.* \b(?:reject(?:_warning)?|hold|discard): '
        pat_re_reject += r'(?P<type>\S+) from (?P<from>\S+?): (?P<rest>.*)$'
        self.re_reject = re.compile(pat_re_reject)

        self.re_rej_reason1 = re.compile(r'^(\d{3} <).*?(>:)')
        self.re_rej_reason2 = re.compile(r'^(?:.*?[:;] )(?:\[[^\]]+\] )?([^;,]+)[;,].*$')
        self.re_rej_reason3 = re.compile(r'^((?:Sender|Recipient) address rejected: [^:]+):.*$')
        self.re_rej_reason4 = re.compile(r'(Client host|Sender address) .+? blocked')
        self.re_rej_reason5 = re.compile(r'^\d{3} (?:<.+>: )?([^;:]+)[;:]?.*$')
        self.re_rej_reason6 = re.compile(r'^(?:.*[:;] )?([^,]+).*$')

        self.re_rej_smtp_reason1 = re.compile(r'^Sender address rejected:')
        self.re_rej_smtp_reason2 = re.compile(r'^(Recipient address rejected:|User unknown( |$))')
        self.re_rej_smtp_reason3 = re.compile(
            r'^.*?\d{3} (Improper use of SMTP command pipelining);.*$')
        self.re_rej_smtp_reason4 = re.compile(r'^.+? from (\S+?):.*$')
        self.re_rej_smtp_reason5 = re.compile(r'^.*?\d{3} (Message size exceeds fixed limit);.*$')
        self.re_rej_smtp_reason6 = re.compile(
            r'^.*?\d{3} (Server configuration (?:error|problem));.*$')

        self.re_rej_to1 = re.compile(r'to=<([^>]+)>')
        self.re_rej_to2 = re.compile(r'\d{3} <([^>]+)>: User unknown ')
        self.re_rej_to3 = re.compile(r'to=<(.*?)(?:[, ]|$)/')

        pat_verp_mung1 = r'((?:bounce[ds]?|no(?:list|reply|response)|return|sentto|\d+).*?)'
        pat_verp_mung1 += r'(?:[\+_\.\*-]\d+\b)+'
        self.re_verp_mung1 = re.compile(pat_verp_mung1, re.IGNORECASE)
        self.re_verp_mung2 = re.compile(r'[\*-](\d+[\*-])?[^=\*-]+[=\*][^\@]+\@')

        self.re_gdom1 = re.compile(r'^([^\[]+)\[((?:\d{1,3}\.){3}\d{1,3})\]')
        self.re_gdom2 = re.compile(r'^([^\/]+)\/([0-9a-f.:]+)', re.IGNORECASE)
        self.re_gdom3 = re.compile(r'^([^\[\(\/]+)[\[\(\/]([^\]\)]+)[\]\)]?:?\s*$')
        self.re_gdom4 = re.compile(r'^(.*)\.([^\.]+)\.([^\.]{3}|[^\.]{2,3}\.[^\.]{2})$')

        self.re_rej_from = re.compile(r'from=<([^>]+)>')

        self.re_smtpd_client = re.compile(r'\[\d+\]: \w+: client=(.+?)(,|$)/')
        self.re_smtpd_reject = re.compile(r'\[\d+\]: \w+: (reject(?:_warning)?|hold|discard): ')
        self.re_smtpd_connect = re.compile(r': connect from ')
        self.re_smtpd_disconnect = re.compile(r': disconnect from ')
        self.re_smtpd_pid = re.compile(r'\/smtpd\[(\d+)\]: ')
        self.re_smtpd_pid_disconnect = re.compile(r'\/smtpd\[(\d+)\]: disconnect from (.+)$')

        self.re_from_size = re.compile(r'from=<(?P<from>[^>]*)>, size=(?P<size>\d+)')
        self.re_domain = re.compile(r'@(.+)')
        self.re_domain_addr = re.compile(r'^[^@]+\@(.+)$')
        self.re_domain_only = re.compile(r'^[^@]+\@')

        pat_relay = r'to=<(?P<to>[^>]*)>, (?:orig_to=<[^>]*>, )?relay=(?P<relay>[^,]+), '
        pat_relay += r'(?:conn_use=[^,]+, )?delay=(?P<delay>[^,]+), '
        pat_relay += r'(?:delays=[^,]+, )?(?:dsn=[^,]+, )?status=(?P<status>\S+)(?P<rest>.*)$'
        self.re_relay = re.compile(pat_relay)

        self.re_forwarded_as = re.compile(r'forwarded as ')

        if encoding:
            self.encoding = encoding
        else:
            self.encoding = self.default_encoding

        self._initialized = True

    # -------------------------------------------------------------------------
    @classmethod
    def string_trimmer(cls, message, max_len=None, do_not_trim=False):
        """Trimming the given message to the given length inclusive an ellipsis."""
        if not max_len:
            max_len = cls.default_max_trim_length

        trimmed = str(message).strip()
        if do_not_trim:
            return trimmed

        if max_len < 4:
            msg = "Invalid max. length {} of a string, must be >= 4.".format(max_len)
            raise ValueError(msg)

        ml = int(max_len) - 3
        if len(trimmed) > ml:
            trimmed = trimmed[0:ml] + '...'

        return trimmed

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
            LOG.warning("Wrong verbose level {!r}, must be >= 0".format(value))

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
            raise PostfixLogsumsError(msg)
        if v == 'xz':
            self._compression = 'lzma'
        else:
            self._compression = v

    # -------------------------------------------------------------------------
    @property
    def zero_fill(self):
        """'Zero-fill' certain arrays."""
        return self._zero_fill

    @zero_fill.setter
    def zero_fill(self, value):
        self._zero_fill = bool(value)

    # -------------------------------------------------------------------------
    @property
    def detail_verbose_msg(self):
        """Display the full reason rather than a truncated deferral, bounce and reject messages."""
        return self._detail_verbose_msg

    @detail_verbose_msg.setter
    def detail_verbose_msg(self, value):
        self._detail_verbose_msg = bool(value)

    # -------------------------------------------------------------------------
    @property
    def detail_reject(self):
        """Display the full reason rather than a truncated deferral, bounce and reject messages."""
        return self._detail_reject

    @detail_reject.setter
    def detail_reject(self, value):
        if value is None:
            self._detail_reject = True
            return
        self._detail_reject = bool(value)

    # -------------------------------------------------------------------------
    @property
    def detail_smtpd_warning(self):
        """Display the full reason rather than a truncated deferral, bounce and reject messages."""
        return self._detail_smtpd_warning

    @detail_smtpd_warning.setter
    def detail_smtpd_warning(self, value):
        if value is None:
            self._detail_smtpd_warning = True
            return
        self._detail_smtpd_warning = bool(value)

    # -------------------------------------------------------------------------
    @property
    def ignore_case(self):
        """This option causes the entire email address to be lower-cased."""
        return self._ignore_case

    @ignore_case.setter
    def ignore_case(self, value):
        self._ignore_case = bool(value)

    # -------------------------------------------------------------------------
    @property
    def extended(self):
        """Extended detail."""
        return self._extended

    @extended.setter
    def extended(self, value):
        self._extended = bool(value)

    # -------------------------------------------------------------------------
    @property
    def rej_add_from(self):
        """For those reject reports that list IP addresses or host/domain names: append the
        email from address to each listing. (Does not apply to 'Improper use of
        SMTP command pipelining' report.)"""
        return self._rej_add_from

    @rej_add_from.setter
    def rej_add_from(self, value):
        self._rej_add_from = bool(value)

    # -------------------------------------------------------------------------
    @property
    def encoding(self):
        """Return the default encoding used to read config files."""
        return self._encoding

    @encoding.setter
    def encoding(self, value):
        if not isinstance(value, str):
            msg = "Encoding {v!r} must be a {s!r} object, but is a {c!r} object instead.".format(
                v=value, s='str', c=value.__class__.__name__)
            raise TypeError(msg)

        encoder = codecs.lookup(value)
        self._encoding = encoder.name

    # -------------------------------------------------------------------------
    @property
    def smtpd_stats(self):
        """Generate smtpd connection statistics."""
        return self._smtpd_stats

    @smtpd_stats.setter
    def smtpd_stats(self, value):
        self._smtpd_stats = bool(value)

    # -------------------------------------------------------------------------
    @property
    def verp_mung(self):
        """This option causes the entire email address to be lower-cased."""
        return self._verp_mung

    @verp_mung.setter
    def verp_mung(self, value):
        if value is None:
            self._verp_mung = None
            return
        v = int(value)
        if v < 0:
            v = 0
        self._verp_mung = v

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
        res['detail_reject'] = self.detail_reject
        res['detail_verbose_msg'] = self.detail_verbose_msg
        res['encoding'] = self.encoding
        res['extended'] = self.extended
        res['ignore_case'] = self.ignore_case
        res['initialized'] = self.initialized
        res['detail_smtpd_warning'] = self.detail_smtpd_warning
        res['rej_add_from'] = self.rej_add_from
        res['results'] = self.results.as_dict(short=short)
        res['smtpd_stats'] = self.smtpd_stats
        res['syslog_name'] = self.syslog_name
        res['this_month'] = self.this_month
        res['this_year'] = self.this_year
        res['today'] = self.today
        res['verbose'] = self.verbose
        res['verp_mung'] = self.verp_mung
        res['zero_fill'] = self.zero_fill

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
        data = bdata.decode(self.encoding, errors='surrogateescape')

        for line in data.splitlines():
            self.eval_line(line)

    # -------------------------------------------------------------------------
    def read_bzip2(self, cdata):

        bdata = bz2.decompress(cdata)
        data = bdata.decode(self.encoding, errors='surrogateescape')

        for line in data.splitlines():
            self.eval_line(line)

    # -------------------------------------------------------------------------
    def read_lzma(self, cdata):

        bdata = lzma.decompress(cdata)
        data = bdata.decode(self.encoding, errors='surrogateescape')

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

        result = self._eval_msg_ts(line)

        if not result:
            return

        self._cur_ts = result[0]
        self._cur_msg = result[1].strip()

        current_date = self._cur_ts.date()
        if self.last_date is None or self.last_date != current_date:
            self.last_date = current_date
            self.results.days_counted += 1
            if self.zero_fill:
                dt_fmt = self.cur_date_fmt()
                if dt_fmt not in self.results.messages_per_day:
                    self.results.messages_per_day[dt_fmt] = [0, 0, 0, 0, 0]

        if self.re_amavis.match(self._cur_msg):
            self.results.amavis_msgs += 1
            return

        result = self._eval_pf_command(self._cur_msg)
        if result:
            self._cur_pf_command = result[0]
            self._cur_qid = result[1]
        else:
            LOG.debug("Did not found Postfix command and QID from: {}".format(self._cur_msg))
            return
        if self.verbose > 3:
            LOG.debug("Postfix command {cmd!r}, qid {qid!r}, message: {msg}".format(
                cmd=self._cur_pf_command, qid=self._cur_qid, msg=self._cur_msg))

        self.results.incr_lines_considered()

        self.eval_command_msg()

    # -------------------------------------------------------------------------
    def cur_date_fmt(self):
        """Return the formatted day of the current log line."""
        if not self._cur_ts:
            return None
        return self._cur_ts.strftime('%Y-%m-%d')

    # -------------------------------------------------------------------------
    def _eval_msg_ts(self, line):

        result = self._eval_msg_ts_traditional(line)
        if result:
            return result

        return self._eval_msg_ts_rfc3339(line)

    # -------------------------------------------------------------------------
    def _eval_msg_ts_traditional(self, line):

        year = None
        month = None
        day = None
        hour = None
        minute = None
        second = None

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

            return (msg_ts, message)

        return None

    # -------------------------------------------------------------------------
    def _eval_msg_ts_rfc3339(self, line):

        year = None
        month = None
        day = None
        hour = None
        minute = None
        second = None
        tz = None

        msg_ts = None
        message = None

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

            return (msg_ts, message)

        return None

    # -------------------------------------------------------------------------
    def _eval_pf_command(self, message):

        m = self.re_pf_command.match(message)
        if m:
            return(m['cmd'], m['qid'])

        m = self.re_pf_script.match(message)
        if m:
            return(m['cmd'], m['qid'])

        return None

    # -------------------------------------------------------------------------
    def eval_command_msg(self):
        """Further analyzing of the message."""
        if self._cur_pf_command == 'cleanup':
            m = self.re_cmd_cleanup.search(self._cur_msg)
            if m:
                self._eval_cleanup_cmd(subtype=m['subtype'], part=m['part'], cmd_msg=m['cmd_msg'])
                return

        if self._cur_qid == 'warning':
            self._eval_warning_cmd()
            return

        if self._cur_qid == 'fatal':
            self._eval_fatal_cmd()
            return

        if self._cur_qid == 'panic':
            self._eval_panic_cmd()
            return

        if self._cur_qid == 'reject':
            self.proc_smtpd_reject(self.results.messages['rejected'])
            return

        if self._cur_qid == 'reject_warning':
            self.proc_smtpd_reject(self.results.messages['warning'])
            return

        if self._cur_qid == 'hold':
            self.proc_smtpd_reject(self.results.messages['hold'])
            return

        if self._cur_qid == 'discard':
            self.proc_smtpd_reject(self.results.messages['discard'])
            return

        if self._cur_pf_command == 'master':
            mparts = self.re_master.split(self._cur_msg)
            mpart = mparts[1]
            self.results.messages['master'] += 1
            if mpart not in self.results.master_msgs:
                self.results.master_msgs[mpart] = 0
            self.results.master_msgs[mpart] += 1
            return

        if self._cur_pf_command == 'smtpd':
            self.eval_smtpd_msg()
            return

        self.eval_other_msg()

    # -------------------------------------------------------------------------
    def eval_smtpd_msg(self):
        """Analyzing messages from smtpd."""
        if self.verbose > 3:
            LOG.debug("Evaluating 'smtpd' command message.")

        m = self.re_smtpd_client.search(self._cur_msg)
        if m:
            self._incr_smtpd_client_counters(m.group(1))
            return

        m = self.re_smtpd_reject.search(self._cur_msg)
        if m:
            self._eval_smtpd_rejects(m.group(1))
            return

        self._eval_smtpd_connections()

    # -------------------------------------------------------------------------
    def _incr_smtpd_client_counters(self, client):
        hour = self._cur_ts.hour
        self.results.received_messages_per_hour[hour] += 1

        dt_fmt = self.cur_date_fmt()
        self.results.messages_per_day[dt_fmt][4] += 1

        self.results.messages_received_total += 1

        self._rcvd_msgs_qid[self._cur_qid] = self.gimme_domain(client)

    # -------------------------------------------------------------------------
    def _eval_smtpd_rejects(self, sub_type):

        if sub_type == 'reject':
            self.proc_smtpd_reject(self.results.messages['rejected'])
            return

        if sub_type == 'reject_warning':
            self.proc_smtpd_reject(self.results.messages['warning'])
            return

        if sub_type == 'hold':
            self.proc_smtpd_reject(self.results.messages['hold'])
            return

        if sub_type == 'discard':
            self.proc_smtpd_reject(self.results.messages['discard'])
            return

    # -------------------------------------------------------------------------
    def _eval_smtpd_connections(self):
        if not self.smtpd_stats:
            return

        hour = self._cur_ts.hour
        dt_fmt = self.cur_date_fmt()

        if self.re_smtpd_connect.search(self._cur_msg):
            m = self.re_smtpd_pid.search(self._cur_msg)
            if m:
                pid = int(m.group(1))
                self._connection_times[pid] = self._cur_ts
            return

        if self.re_smtpd_disconnect.search(self._cur_msg):
            m = self.re_smtpd_pid_disconnect.search(self._cur_msg)
            if m:
                pid = int(m.group(1))
                host_id = m.group(2)

                if pid not in self._connection_times:
                    return

                host_id = self.gimme_domain(host_id)

                time_diff = self._cur_ts - self._connection_times[pid]
                del self._connection_times[pid]

                seconds = time_diff.total_seconds()

                self.results.smtpd_messages_per_hour[hour][0] += 1
                self.results.smtpd_messages_per_hour[hour][1] += seconds
                if seconds > self.results.smtpd_messages_per_hour[hour][2]:
                    self.results.smtpd_messages_per_hour[hour][2] = seconds

                if dt_fmt not in self.results.smtpd_per_day:
                    self.results.smtpd_per_day[dt_fmt] = [0, 0, 0]
                self.results.smtpd_per_day[dt_fmt][0] += 1
                self.results.smtpd_per_day[dt_fmt][1] += seconds
                if seconds > self.results.smtpd_per_day[dt_fmt][2]:
                    self.results.smtpd_per_day[dt_fmt][2] = seconds

                if host_id not in self.results.smtpd_per_domain:
                    self.results.smtpd_per_domain[host_id] = [0, 0, 0]
                self.results.smtpd_per_domain[host_id][0] += 1
                self.results.smtpd_per_domain[host_id][1] += seconds
                if seconds > self.results.smtpd_per_domain[host_id][2]:
                    self.results.smtpd_per_domain[host_id][2] = seconds

                self.results.connections_total += 1
                self.results.connections_time += seconds

    # -------------------------------------------------------------------------
    def _eval_warning_cmd(self):

        cmd = self._cur_pf_command
        if cmd == 'smtpd' and self.detail_smtpd_warning:
            return

        warn_msg = self.re_warning.sub('', self._cur_msg)
        warn_msg = self.string_trimmer(warn_msg, do_not_trim=self.detail_verbose_msg)

        if cmd not in self.results.warnings:
            self.results.warnings[cmd] = {}
        if warn_msg not in self.results.warnings[cmd]:
            self.results.warnings[cmd][warn_msg] = 0
        self.results.warnings[cmd][warn_msg] += 1

    # -------------------------------------------------------------------------
    def _eval_fatal_cmd(self):

        cmd = self._cur_pf_command

        fatal_msg = self.re_fatal.sub('', self._cur_msg)
        fatal_msg = self.string_trimmer(fatal_msg, do_not_trim=self.detail_verbose_msg)

        if cmd not in self.results.fatals:
            self.results.fatals[cmd] = {}
        if fatal_msg not in self.results.fatals[cmd]:
            self.results.fatals[cmd][fatal_msg] = 0
        self.results.fatals[cmd][fatal_msg] += 1

    # -------------------------------------------------------------------------
    def _eval_panic_cmd(self):

        cmd = self._cur_pf_command

        panic_msg = self.re_panic.sub('', self._cur_msg)
        panic_msg = self.string_trimmer(panic_msg, do_not_trim=self.detail_verbose_msg)

        if cmd not in self.results.panics:
            self.results.panics[cmd] = {}
        if panic_msg not in self.results.panics[cmd]:
            self.results.panics[cmd][panic_msg] = 0
        self.results.panics[cmd][panic_msg] += 1

    # -------------------------------------------------------------------------
    def _eval_cleanup_cmd(self, subtype, part, cmd_msg):
        if self.verbose > 2:
            LOG.debug("Evaluating 'cleanup' command message.")

        if not self.detail_verbose_msg:
            cmd_msg = self.re_clean_from.sub('', cmd_msg)
            cmd_msg = self.string_trimmer(cmd_msg, do_not_trim=self.detail_verbose_msg)

        hour = self._cur_ts.hour
        self.results.rejected_messages_per_hour[hour] += 1

        dt_fmt = self.cur_date_fmt()
        self.results.messages_per_day[dt_fmt][4] += 1

        if subtype == 'reject':
            self.results.messages['rejected'] += 1
            if self.detail_reject:
                if part not in self.results.rejects['cleanup']:
                    self.results.rejects['cleanup'][part] = {}
                if cmd_msg not in self.results.rejects['cleanup'][part]:
                    self.results.rejects['cleanup'][part][cmd_msg] = 0
                self.results.rejects['cleanup'][part][cmd_msg] += 1
            return

        if subtype == 'warning':
            self.results.messages['warning'] += 1
            if self.detail_reject:
                if part not in self.results.warns['cleanup']:
                    self.results.warns['cleanup'][part] = {}
                if cmd_msg not in self.results.warns['cleanup'][part]:
                    self.results.warns['cleanup'][part][cmd_msg] = 0
                self.results.warns['cleanup'][part][cmd_msg] += 1
            return

        if subtype == 'hold':
            self.results.messages['hold'] += 1
            if self.detail_reject:
                if part not in self.results.holds['cleanup']:
                    self.results.holds['cleanup'][part] = {}
                if cmd_msg not in self.results.holds['cleanup'][part]:
                    self.results.holds['cleanup'][part][cmd_msg] = 0
                self.results.holds['cleanup'][part][cmd_msg] += 1
            return

        if subtype == 'discard':
            self.results.messages['discard'] += 1
            if self.detail_reject:
                if part not in self.results.discards['cleanup']:
                    self.results.discards['cleanup'][part] = {}
                if cmd_msg not in self.results.discards['cleanup'][part]:
                    self.results.discards['cleanup'][part][cmd_msg] = 0
                self.results.discards['cleanup'][part][cmd_msg] += 1

    # -------------------------------------------------------------------------
    def do_verp_mung(self, address):

        if self.verp_mung is not None:
            address = self.re_verp_mung1.sub(r'\1-ID', address)
            if self.verp_mung > 1:
                address = self.re_verp_mung2.sub(r'\@', address)

        return address

    # -------------------------------------------------------------------------
    def gimme_domain(self, data):

        domain = None
        ip_address = None

        m = self.re_gdom1.match(data)
        if m:
            domain = m.group(1)
            ip_address = m.group(2)
        else:
            m = self.re_gdom2.match(data)
            if m:
                domain = m.group(1)
                ip_address = m.group(2)
            else:
                m = self.re_gdom3.match(data)
                if not m:
                    return None
                domain = m.group(1)
                ip_address = m.group(2)

        if domain == 'unknown':
            domain = ip_address
        else:
            domain = self.re_gdom4.sub(r'\1.\2', domain).lower()

        return domain

    # -------------------------------------------------------------------------
    def proc_smtpd_reject(self, counter):

        counter += 1

        hour = self._cur_ts.hour
        self.results.rejected_messages_per_hour[hour] += 1

        dt_fmt = self.cur_date_fmt()
        if dt_fmt not in self.results.messages_per_day:
            self.results.messages_per_day[dt_fmt] = [0, 0, 0, 0, 0]
        self.results.messages_per_day[dt_fmt][4] += 1

        if not self.detail_reject:
            return

        reject = self._eval_reject_msg()
        if not reject:
            return

        if self.re_rej_smtp_reason1.match(reject.reason):
            self._incr_reject_counter(reject.type, reject.reason, reject.sender)
        elif self.re_rej_smtp_reason2.match(reject.reason):
            reject_data = reject.to
            if self.rej_add_from:
                reject_data += "  (" + reject.sender + ")"
            self._incr_reject_counter(reject.type, reject.reason, reject_data)
        elif self.re_rej_smtp_reason3.match(reject.reason):
            reject.reason = self.re_rej_smtp_reason3.sub(r'\1', reject.reason)
            if self.re_rej_smtp_reason4.match(self._cur_msg):
                reject_src = self.re_rej_smtp_reason4.match(self._cur_msg).group(1)
                self._incr_reject_counter(reject.type, reject.reason, reject_src)
        elif self.re_rej_smtp_reason5.match(reject.reason):
            reject.reason = self.re_rej_smtp_reason5.sub(r'\1', reject.reason)
            reject_data = self.gimme_domain(reject.sender)
            if reject_data:
                if self.rej_add_from:
                    reject_data += '  (' + reject.sender + ')'
                self._incr_reject_counter(reject.type, reject.reason, reject_data)
        elif self.re_rej_smtp_reason6.match(reject.reason):
            reject.reason = self.re_rej_smtp_reason6.sub(r'(Local) \1', reject.reason)
            reject_data = self.gimme_domain(reject.sender)
            if reject_data:
                if self.rej_add_from:
                    reject_data += '  (' + reject.sender + ')'
                self._incr_reject_counter(reject.type, reject.reason, reject_data)
        else:
            reject_data = self.gimme_domain(reject.sender)
            if reject_data:
                if self.rej_add_from:
                    reject_data += '  (' + reject.sender + ')'
                self._incr_reject_counter(reject.type, reject.reason, reject_data)

    # -------------------------------------------------------------------------
    def _incr_reject_counter(self, rtype, reason, rdata):

        if rtype not in self.results.rejects:
            self.results.rejects[rtype] = {}

        if reason not in self.results.rejects[rtype]:
            self.results.rejects[rtype][reason] = {}

        if rdata not in self.results.rejects[rtype][reason]:
            self.results.rejects[rtype][reason][rdata] = 0

        self.results.rejects[rtype][reason][rdata] += 1

    # -------------------------------------------------------------------------
    def _eval_reject_msg(self):

        class Reject(object):
            pass

        reject = Reject()

        m = self.re_reject.match(self._cur_msg)
        if not m:
            return None

        reject.type = m['type']
        reject.sender = m['from']
        reject.rest = m['rest']
        reject.reason = reject.rest

        if not self.detail_verbose_msg:
            if reject.type in ('RCPT', 'DATA', 'CONNECT'):
                reject.reason = self.re_rej_reason1.sub(r'\1\2', reject.reason)
                reject.reason = self.re_rej_reason2.sub(r'\1', reject.reason)
                reject.reason = self.re_rej_reason3.sub(r'\1', reject.reason)
                reject.reason = self.re_rej_reason4.sub(r'blocked', reject.reason)
            elif reject.type == 'MAIL':
                reject.reason = self.re_rej_reason5.sub(r'\1', reject.reason)
            else:
                reject.reason = self.re_rej_reason6.sub(r'\1', reject.reason)

        reject.to = '<>'
        m = self.re_rej_to1.search(reject.rest)
        if m:
            reject.to = m.group(1)
        else:
            m = self.re_rej_to2.search(reject.rest)
            if m:
                reject.to = m.group(1)
            else:
                m = self.re_rej_to3.search(reject.rest)
                if m:
                    reject.to = m.group(1)
        if self.ignore_case:
            reject.to = reject.to.lower()

        reject.sender = '<>'
        m = self.re_rej_from.search(reject.rest)
        if m:
            reject.sender = self.do_verp_mung(m.group(1))
            if self.ignore_case:
                reject.sender = reject.sender.lower()

        return reject

    # -------------------------------------------------------------------------
    def eval_other_msg(self):
        """Analyzing other messages."""
        if self.verbose > 3:
            LOG.debug("Evaluating other message.")

        m = self.re_from_size.search(self._cur_msg)
        if m:
            self._eval_message_size(sender=m['from'], size=int(m['size']))
            return

        m = self.re_relay.search(self._cur_msg)
        if m:
            self._eval_relayed_msg(
                addr=m['to'], relay=m['relay'], delay=float(m['delay']),
                status=m['status'], rest=m['rest'])

    # -------------------------------------------------------------------------
    def _eval_message_size(self, sender, size):
        qid = self._cur_qid
        if qid in self._message_size:
            return

        if sender:
            if self.ignore_case:
                sender = sender.lower()
            else:
                m = self.re_domain.search(sender)
                if m:
                    domain = m.group(1).lower()
                    sender = self.re_domain.sub('@' + domain, sender)
        else:
            sender = "from=<>"

        self._message_size[qid] = size
        if self.extended:
            if qid not in self.results.message_details:
                self.results.message_details[qid] = []
            self.results.message_details[qid].append(sender)

        if qid in self._rcvd_msgs_qid:

            dom_addr = self.re_domain_addr.sub(r'\1', sender)
            if dom_addr == sender:
                if self._rcvd_msgs_qid[qid] != "pickup":
                    dom_addr = self._rcvd_msgs_qid[qid]
            if dom_addr not in self.results.sending_domain_data:
                self.results.sending_domain_data[dom_addr] = MessageStats()
            if not self.results.sending_domain_data[dom_addr].count:
                self.results.sender_domain_count += 1
            self.results.sending_domain_data[dom_addr].count += 1
            self.results.sending_domain_data[dom_addr].size += size

            if sender not in self.results.sending_user_data:
                self.results.sending_user_data[sender] = MessageStats()
            if not self.results.sending_user_data[sender].count:
                self.sending_user_count += 1
            self.results.sending_user_data[sender].count += 1
            self.results.sending_user_data[sender].size += size
            self.results.received_size += size

            del self._rcvd_msgs_qid[qid]

    # -------------------------------------------------------------------------
    def _eval_relayed_msg(self, addr, relay, delay, status, rest):
        if self.ignore_case:
            addr = addr.lower()
            relay = relay.lower()
        else:
            m = self.re_domain.search(addr)
            if m:
                domain = m.group(1).lower()
                addr = self.re_domain.sub('@' + domain, addr)

        domain = self.re_domain_only.sub('', addr)

        if self.verbose > 2:
            data = {
                'addr': addr, 'domain': domain, 'relay': relay, 'delay': delay,
                'status': status, 'rest': rest, }
            LOG.debug("Processing relaying message:\n" + pp(data))

        if status == 'sent':
            self._eval_relay_sent_msg(addr, domain, relay, delay, rest)
            return

    # -------------------------------------------------------------------------
    def _eval_relay_sent_msg(self, addr, domain, relay, delay, rest):
        if self.re_forwarded_as.search(rest):
            self.results.messages_forwarded += 1
            return

        if domain not in self.results.rcpt_domain:
            self.results.rcpt_domain[domain] = MessageStats()
            self.results.rcpt_domain_count += 1
        self.results.rcpt_domain[domain].count += 1
        self.results.rcpt_domain[domain].delay_avg += delay
        if delay > self.results.rcpt_domain[domain].delay_max:
            self.results.rcpt_domain[domain].delay_max = delay

        if addr not in self.results.rcpt_user:
            self.results.rcpt_user[addr] = MessageStats()
            self.results.rcpt_user_count += 1
        self.results.rcpt_user[addr].count += 1


# =============================================================================

if __name__ == "__main__":

    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
