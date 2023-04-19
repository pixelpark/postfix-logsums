#!/bin/env python3
# -*- coding: utf-8 -*-
"""
@summary: A log analyzer/summarizer for the Postfix MTA.

@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 by Frank Brehm, Berlin
"""
from __future__ import absolute_import

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

# Own modules
from .errors import PostfixLogsumsError

from .results import PostfixLogSums

from .stats import MessageStats, MessageStatsPerDay, SmtpdStats

from .xlate import XLATOR

__version__ = '0.9.1'
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
def get_smh(seconds):
    """Get seconds, minutes and hours from seconds."""
    hours = int(seconds / 3600)
    seconds -= hours * 3600
    minutes = int(seconds / 60)
    seconds -= minutes * 60

    return (seconds, minutes, hours)

# =============================================================================
class PostfixLogParser(object):
    """The underlaying class for parsing Postfix logfiles."""

    # Class variables as constants

    div_by_one_kb_at = 512 * 1024
    div_by_one_mb_at = 512 * 1024 * 1024
    div_by_one_gb_at = 512 * 1024 * 1024 * 1024
    one_kb = 1024
    one_mb = 1024 * 1024
    one_gb = 1024 * 1024 * 1024

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

    re_said = re.compile(r'^.* said: ')
    re_said1 = re.compile(r'^.*: *')

    utc = datetime.timezone(datetime.timedelta(0), 'UTC')

    default_encoding = DEFAULT_ENCODING
    default_max_trim_length = DEFAULT_MAX_TRIM_LENGTH

    min_max_len = 4

    # -------------------------------------------------------------------------
    def __init__(
            self, appname=None, verbose=0, day=None, syslog_name=DEFAULT_SYSLOG_NAME,
            zero_fill=False, detail_verbose_msg=False, detail_reject=True,
            detail_deferral=False, detail_bounce=False, detail_smtp=True,
            detail_smtpd_warning=True, ignore_case=False, rej_add_from=False,
            smtpd_stats=False, extended=False, no_no_message_size=False,
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
        self._detail_deferral = True
        self._detail_bounce = True
        self._detail_smtp = True
        self._detail_smtpd_warning = True
        self._ignore_case = False
        self._extended = False
        self._rej_add_from = False
        self._smtpd_stats = False
        self._no_no_message_size = False
        self._verp_mung = None

        self._cur_ts = None
        self._cur_msg = None
        self._cur_pf_command = None
        self._cur_qid = None

        self.last_date = None

        self.re_date_filter = None
        self.re_date_filter_rfc3339 = None

        self._rcvd_msgs_qid = {}
        self._connection_times = {}
        self._message_size = {}
        self._message_deferred_qid = {}
        self.date_str = None

        if day:

            if isinstance(day, datetime.datetime):
                used_date = day.date()
            elif isinstance(day, datetime.date):
                used_date = day
            elif day.lower() == 'yesterday':
                t_diff = datetime.timedelta(days=1)
                used_date = self.today - t_diff
            elif day.lower() == 'today':
                used_date = copy.copy(self.today)
            else:
                msg = _(
                    "Wrong day {d!r} given. Valid values are {n}, {y!r} and {t!r} or a valid "
                    "{dt} or {dd} object.").format(
                        d=day, n='None', y='yesterday', t='today',
                        dt='datetime.datetime', dd='datetime.date')
                raise PostfixLogsumsError(msg)
            self.date_str = used_date.isoformat()
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
        self.detail_deferral = detail_deferral
        self.detail_bounce = detail_bounce
        self.detail_smtp = detail_smtp
        self.detail_smtpd_warning = detail_smtpd_warning
        self.extended = extended
        self.ignore_case = ignore_case
        self.rej_add_from = rej_add_from
        self.no_no_message_size = no_no_message_size
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
        self.re_pf_message = re.compile(r'^.*postfix\[\d+\]:\s+(\S.*)')

        pattern_cmd_cleanup = r'\/cleanup\[\d+\]: .*?\b(?P<subtype>reject|warning|hold|discard): '
        pattern_cmd_cleanup += r'(?P<part>header|body) (?P<cmd_msg>.*)$'
        self.re_cmd_cleanup = re.compile(pattern_cmd_cleanup)

        self.re_removed = re.compile(r' removed(\b|$)')
        self.re_skipped = re.compile(r' skipped(\b|$)')

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

        self.re_smtpd_client = re.compile(r'\[\d+\]: \w+: client=(.+?)(,|$)')
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

        self.re_defer_reason = re.compile(r', status=deferred \(([^\)]+)')
        self.re_bounce_reason = re.compile(r', status=bounced \((.+)\)')

        self.re_three_digits_at_start = re.compile(r'^\d{3} ')
        self.re_connect_to = re.compile(r'^connect to ')

        self.re_sender_uid = re.compile(r': (sender|uid)=')

        self.re_connected_to_addr = re.compile(
            r'.* connect to (\S+?): ([^;]+); address \S+ port.*$')
        self.re_connected_to_port = re.compile(
            r'.* connect to ([^[]+)\[\S+?\]: (.+?) \(port \d+\)$')
        self.re_smtp_connect_to = re.compile(r'.* connect to (\S+?): (.+)')
        self.re_smtp_connect_to_trusted = re.compile(
            r'.* Trusted TLS connection established to (\S+?): (.+)', re.IGNORECASE)
        self.re_smtp_connect_to_untrusted = re.compile(
            r'.* Untrusted TLS connection established to (\S+?): (.+)', re.IGNORECASE)

        if encoding:
            self.encoding = encoding
        else:
            self.encoding = self.default_encoding

        self.results = PostfixLogSums(smtpd_stats=self.smtpd_stats)

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

        if max_len < cls.min_max_len:
            msg = _("Invalid max. length {max} of a string, must be >= {min}.").format(
                max=max_len, min=cls.min_max_len)
            raise ValueError(msg)

        ml = int(max_len) - 3
        if len(trimmed) > ml:
            trimmed = trimmed[0:ml] + '...'

        return trimmed

    # -------------------------------------------------------------------------
    @classmethod
    def said_string_trimmer(cls, message, max_len=None):
        """Trim a "said:" string, if necessary.  Add elipses to show it."""

        if not max_len:
            max_len = cls.default_max_trim_length

        while len(message) > max_len:
            if cls.re_said.match(message):
                message = cls.re_said.sub('', message)
            elif cls.re_said1.match(message):
                message = cls.re_said1.sub('', message)
            else:
                ml = max_len - 3
                message = message[0:ml] + '...'
                break

        return message

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
            msg = _("The syslog name must not be {}.").format('None')
            raise TypeError(msg)
        v = str(value).strip()
        if v == '':
            msg = _("The syslog name must not be empty.")
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
            msg = _("Invalid compression {!r} given.").format(value)
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
    def detail_bounce(self):
        """Limit detailed bounce reports."""
        return self._detail_bounce

    @detail_bounce.setter
    def detail_bounce(self, value):
        if value is None:
            self._detail_bounce = True
            return
        self._detail_bounce = bool(value)

    # -------------------------------------------------------------------------
    @property
    def detail_smtp(self):
        """Limit detailed smtp delivery reports."""
        return self._detail_smtp

    @detail_smtp.setter
    def detail_smtp(self, value):
        if value is None:
            self._detail_smtp = True
            return
        self._detail_smtp = bool(value)

    # -------------------------------------------------------------------------
    @property
    def detail_deferral(self):
        """Limit detailed deferral reports."""
        return self._detail_deferral

    @detail_deferral.setter
    def detail_deferral(self, value):
        if value is None:
            self._detail_deferral = True
            return
        self._detail_deferral = bool(value)

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
            msg = _(
                "Encoding {v!r} must be a {s!r} object, but is a {c!r} object instead.").format(
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
    def no_no_message_size(self):
        """Don't report messages without a message size."""
        return self._no_no_message_size

    @no_no_message_size.setter
    def no_no_message_size(self, value):
        self._no_no_message_size = bool(value)

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
        res['detail_bounce'] = self.detail_bounce
        res['detail_deferral'] = self.detail_deferral
        res['detail_reject'] = self.detail_reject
        res['detail_smtp'] = self.detail_smtp
        res['detail_smtpd_warning'] = self.detail_smtpd_warning
        res['detail_verbose_msg'] = self.detail_verbose_msg
        res['encoding'] = self.encoding
        res['extended'] = self.extended
        res['ignore_case'] = self.ignore_case
        res['initialized'] = self.initialized
        res['no_no_message_size'] = self.no_no_message_size
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
            LOG.debug(_("Parsing from {} ...").format('STDIN'))
            self.results.start_logfile('STDIN')
            return self.parse_fh(sys.stdin, 'STDIN', self.compression)

        for logfile in files:
            LOG.debug(_("Parsing logfile {!r} ...").format(str(logfile)))
            self.results.start_logfile(logfile)
            if not self.parse_file(logfile):
                return False

        if self.date_str:
            LOG.debug(_("Filtering log messages for date {} ...").format(self.date_str))

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
            LOG.debug(_("Reading uncompressed file {!r} ...").format(filename))
            line = fh.readline()
            while line:
                self.eval_line(line)
                line = fh.readline()
            return True

        cdata = fh.read()

        if compression == 'gzip':
            LOG.debug(_("Reading {w} compressed file {f!r} ...").format(
                w='GZIP', f=filename))
            self.read_gzip(cdata)
            return True

        if compression == 'bzip2':
            LOG.debug(_("Reading {w} compressed file {f!r} ...").format(
                w='BZIP2', f=filename))
            self.read_bzip2(cdata)
            return True

        if compression == 'lzma':
            LOG.debug(_("Reading {w} compressed file {f!r} ...").format(
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

        if not self._eval_msg_ts(line):
            return

        current_date = self._cur_ts.date()
        if self.last_date is None or self.last_date != current_date:
            self.last_date = current_date
            self.results.days_counted += 1
            if self.zero_fill:
                self.incr_msgs_per_day()

        if self.re_amavis.match(self._cur_msg):
            self.results.amavis_msgs += 1
            return

        result = self._eval_pf_command(self._cur_msg)
        if result:
            self._cur_pf_command = result[0]
            self._cur_qid = result[1]
        else:
            if self.verbose > 1:
                LOG.debug(_("Did not found Postfix command and QID from: {}").format(
                    self._cur_msg))
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
    def incr_msgs_per_day(self, index=None):

        cur_date = self._cur_ts.date()
        if cur_date not in self.results.messages_per_day:
            self.results.messages_per_day[cur_date] = MessageStatsPerDay()

        if index is None:
            return

        self.results.messages_per_day[cur_date][index] += 1

    # -------------------------------------------------------------------------
    def _eval_msg_ts(self, line):

        result = self._eval_msg_ts_traditional(line)
        if not result:
            result = self._eval_msg_ts_rfc3339(line)

        if not result:
            return None

        self._cur_ts = result[0]
        self._cur_msg = result[1].strip()

        if self.results.logdate_oldest is None or self._cur_ts < self.results.logdate_oldest:
            self.results.logdate_oldest = copy.copy(self._cur_ts)

        if self.results.logdate_latest is None or self._cur_ts > self.results.logdate_latest:
            self.results.logdate_latest = copy.copy(self._cur_ts)

        return True

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
            return (m['cmd'], m['qid'])

        m = self.re_pf_script.match(message)
        if m:
            return (m['cmd'], m['qid'])

        return None

    # -------------------------------------------------------------------------
    def eval_command_msg(self):
        """Further analyzing of the message."""
        if self._cur_pf_command == 'cleanup':
            m = self.re_cmd_cleanup.search(self._cur_msg)
            if m:
                self._eval_cleanup_cmd(subtype=m['subtype'], part=m['part'], cmd_msg=m['cmd_msg'])
            return

        if self._cur_pf_command == 'qmgr':
            if self.re_removed.search(self._cur_msg) or self.re_skipped.search(self._cur_msg):
                return

        if self._cur_pf_command == 'postfix-script':
            self._eval_postfix_script()
            return

        if self._cur_pf_command == 'postfix':
            self._eval_postfix_message()
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
            self.proc_smtpd_reject('rejected')
            return

        if self._cur_qid == 'reject_warning':
            self.proc_smtpd_reject('reject_warning')
            return

        if self._cur_qid == 'hold':
            self.proc_smtpd_reject('held')
            return

        if self._cur_qid == 'discard':
            self.proc_smtpd_reject('discarded')
            return

        if self._cur_pf_command == 'master':
            mparts = self.re_master.split(self._cur_msg)
            mpart = mparts[1]
            self.results.msgs_total.master += 1
            if mpart not in self.results.master_msgs:
                self.results.master_msgs[mpart] = 0
            self.results.master_msgs[mpart] += 1
            return

        if self._cur_pf_command == 'smtpd':
            self.eval_smtpd_msg()
            return

        self.eval_other_msg()

    # -------------------------------------------------------------------------
    def _eval_postfix_script(self):
        qid = self._cur_qid

        if qid not in self.results.postfix_script:
            self.results.postfix_script[qid] = 0
        self.results.postfix_script[qid] += 1

    # -------------------------------------------------------------------------
    def _eval_postfix_message(self):

        m = self.re_pf_message.search(self._cur_msg)
        if m:
            msg = m.group(1)
            if msg not in self.results.postfix_messages:
                self.results.postfix_messages[msg] = 0
            self.results.postfix_messages[msg] += 1

    # -------------------------------------------------------------------------
    def eval_smtpd_msg(self):
        """Analyzing messages from smtpd."""
        if self.verbose > 3:
            LOG.debug("Evaluating 'smtpd' command message: " + self._cur_msg)

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

        qid = self._cur_qid
        domain = self.gimme_domain(client)
        hour = self._cur_ts.hour
        if self.verbose > 2:
            msg = (
                "Increasing smtpd_client_counters for client {c!r}, domain {d!r} and "
                "qid {q!r}.").format(c=client, d=domain, q=qid)
            LOG.debug(msg)

        self.results.received_messages_per_hour[hour] += 1
        self.incr_msgs_per_day('received')
        self.results.msgs_total.received += 1
        self._rcvd_msgs_qid[qid] = domain

    # -------------------------------------------------------------------------
    def _eval_smtpd_rejects(self, sub_type):

        if sub_type == 'reject':
            self.proc_smtpd_reject('rejected')
            return

        if sub_type == 'reject_warning':
            self.proc_smtpd_reject('reject_warning')
            return

        if sub_type == 'hold':
            self.proc_smtpd_reject('held')
            return

        if sub_type == 'discard':
            self.proc_smtpd_reject('discarded')
            return

    # -------------------------------------------------------------------------
    def _eval_smtpd_connections(self):
        if not self.smtpd_stats:
            return

        hour = self._cur_ts.hour

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

                self.results.smtpd_messages_per_hour[hour].count += 1
                self.results.smtpd_messages_per_hour[hour].time_total += seconds
                if seconds > self.results.smtpd_messages_per_hour[hour].time_max:
                    self.results.smtpd_messages_per_hour[hour].time_max = seconds

                cur_date = self._cur_ts.date()
                if cur_date not in self.results.smtpd_per_day:
                    self.results.smtpd_per_day[cur_date] = SmtpdStats()
                self.results.smtpd_per_day[cur_date].connections += 1
                self.results.smtpd_per_day[cur_date].connect_time_total += seconds
                if seconds > self.results.smtpd_per_day[cur_date].connect_time_max:
                    self.results.smtpd_per_day[cur_date].connect_time_max = seconds

                if host_id not in self.results.smtpd_per_domain:
                    self.results.smtpd_per_domain[host_id] = SmtpdStats()
                self.results.smtpd_per_domain[host_id].connections += 1
                self.results.smtpd_per_domain[host_id].connect_time_total += seconds
                if seconds > self.results.smtpd_per_domain[host_id].connect_time_max:
                    self.results.smtpd_per_domain[host_id].connect_time_max = seconds

                self.results.msgs_total.connections += 1
                self.results.connections_time += seconds

    # -------------------------------------------------------------------------
    def _eval_warning_cmd(self):

        cmd = self._cur_pf_command
        if cmd == 'smtpd' and self.detail_smtpd_warning == 0:
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
    def _incr_cleanup_msg(self, counter_name, part, cmd_msg, cmd='cleanup'):

        if not hasattr(self.results, counter_name):
            setattr(self.results, counter_name, {})
        counter = getattr(self.results, counter_name)

        if cmd not in counter:
            counter[cmd] = {}
        if part not in counter[cmd]:
            counter[cmd][part] = {}
        if cmd_msg not in counter[cmd][part]:
            counter[cmd][part][cmd_msg] = 0
        counter[cmd][part][cmd_msg] += 1

    # -------------------------------------------------------------------------
    def _eval_cleanup_cmd(self, subtype, part, cmd_msg):
        if self.verbose > 2:
            LOG.debug(_("Evaluating {!r} command message.").format('cleanup'))

        if not self.detail_verbose_msg:
            cmd_msg = self.re_clean_from.sub('', cmd_msg)
            cmd_msg = self.string_trimmer(cmd_msg, do_not_trim=self.detail_verbose_msg)

        hour = self._cur_ts.hour
        self.results.rejected_messages_per_hour[hour] += 1

        self.incr_msgs_per_day('rejected')

        if subtype == 'reject':
            self.results.msgs_total.rejected += 1
            if self.detail_reject:
                self._incr_cleanup_msg('rejects', part, cmd_msg)
            return

        if subtype == 'warning':
            self.results.msgs_total.reject_warning += 1
            if self.detail_reject:
                self._incr_cleanup_msg('cleanup_warnings', part, cmd_msg)
            return

        if subtype == 'hold':
            self.results.msgs_total.held += 1
            if self.detail_reject:
                self._incr_cleanup_msg('holds', part, cmd_msg)
            return

        if subtype == 'discard':
            self.results.msgs_total.discarded += 1
            if self.detail_reject:
                self._incr_cleanup_msg('discards', part, cmd_msg)

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
                    return ''
                domain = m.group(1)
                ip_address = m.group(2)

        if domain == 'unknown':
            domain = ip_address
        else:
            domain = self.re_gdom4.sub(r'\1.\2', domain).lower()

        return domain

    # -------------------------------------------------------------------------
    def proc_smtpd_reject(self, counter):

        self.results.msgs_total[counter] += 1
        # counter += 1

        hour = self._cur_ts.hour
        self.results.rejected_messages_per_hour[hour] += 1

        self.incr_msgs_per_day('rejected')

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
            self._eval_message_size(addr=m['from'], size=int(m['size']))
            return

        m = self.re_relay.search(self._cur_msg)
        if m:
            self._eval_relayed_msg(
                addr=m['to'], relay=m['relay'], delay=float(m['delay']),
                status=m['status'], rest=m['rest'])
            return

        if self._cur_pf_command == 'pickup' and self.re_sender_uid.search(self._cur_msg):
            self._eval_pickup_msgs()
            return

        if self._cur_pf_command == 'smtp':
            self._eval_smtp()
            return

        if self.verbose > 2:
            msg = "Unhandled message: {msg!r}\n    Command: {cmd!r}, Qid: {q!r}.".format(
                msg=self._cur_msg, cmd=self._cur_pf_command, q=self._cur_qid)
            LOG.debug(msg)

    # -------------------------------------------------------------------------
    def _add_ext_msg_detail(self, qid, addr):

        if not self.extended:
            return

        if qid not in self.results.message_details:
            self.results.message_details[qid] = []
        self.results.message_details[qid].append(addr)

    # -------------------------------------------------------------------------
    def _eval_message_size(self, addr, size):
        qid = self._cur_qid
        if qid in self._message_size:
            return

        if addr:
            if self.ignore_case:
                addr = addr.lower()
            else:
                m = self.re_domain.search(addr)
                if m:
                    domain = m.group(1).lower()
                    addr = self.re_domain.sub('@' + domain, addr)
            addr = self.do_verp_mung(addr)
        else:
            addr = "from=<>"

        self._message_size[qid] = size
        self._add_ext_msg_detail(qid, addr)

        if self.verbose > 2:
            LOG.debug("Eval message size: qid: {q!r}, addr: {a!r}, size: {s!r}.".format(
                q=qid, a=addr, s=size))

        if qid in self._rcvd_msgs_qid:

            if self.verbose > 2:
                LOG.debug("Bla: {!r}".format(self._rcvd_msgs_qid[qid]))

            dom_addr = self.re_domain_addr.sub(r'\1', addr)
            if dom_addr == addr:
                if self._rcvd_msgs_qid[qid] != "pickup":
                    dom_addr = self._rcvd_msgs_qid[qid]
            if dom_addr not in self.results.sending_domain_data:
                self.results.sending_domain_data[dom_addr] = MessageStats()
            if not self.results.sending_domain_data[dom_addr].count:
                self.results.msgs_total.sending_domains += 1
            self.results.sending_domain_data[dom_addr].count += 1
            self.results.sending_domain_data[dom_addr].size += size

            if addr not in self.results.sending_user_data:
                self.results.sending_user_data[addr] = MessageStats()
            if not self.results.sending_user_data[addr].count:
                self.results.msgs_total.sending_users += 1
            self.results.sending_user_data[addr].count += 1
            self.results.sending_user_data[addr].size += size
            self.results.msgs_total.bytes_received += size

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
            if self.verbose > 2:
                LOG.debug("Processing relaying message:\n" + pp(data))

        if status == 'sent':
            self._eval_relay_sent_msg(addr, domain, relay, delay, rest)
            return

        if status == 'deferred':
            self._eval_deferred_msg(addr, domain, relay, delay, rest)
            return

        if status == 'bounced':
            self._eval_bounced_msg(addr, domain, relay, delay, rest)
            return

        if self.verbose > 2:
            msg = (
                "Unhandled message: addr={a!r}, relay={r!r}, delay={d!r}, status={s!r}, "
                "rest={rst!r}.").format(a=addr, r=relay, d=delay, s=status, rst=rest)
            LOG.debug(msg)

    # -------------------------------------------------------------------------
    def _inc_deferred(self, cmd, reason):

        if cmd not in self.results.deferred:
            self.results.deferred[cmd] = {}
        if reason not in self.results.deferred[cmd]:
            self.results.deferred[cmd][reason] = 0
        self.results.deferred[cmd][reason] += 1

    # -------------------------------------------------------------------------
    def _eval_deferred_msg(self, addr, domain, relay, delay, rest):

        qid = self._cur_qid
        hour = self._cur_ts.hour

        if self.detail_deferral:
            m = self.re_defer_reason.search(self._cur_msg)
            if m:
                reason = m.group(1)
                if not self.detail_verbose_msg:
                    reason = self.said_string_trimmer(reason)
                    reason = self.re_three_digits_at_start.sub('', reason)
                    reason = self.re_connect_to.sub('', reason)
                self._inc_deferred(self._cur_pf_command, reason)

        self.results.deferred_messages_per_hour[hour] += 1
        self.incr_msgs_per_day('deferred')
        self.results.msgs_total.deferrals += 1

        if qid not in self._message_deferred_qid:
            self.results.msgs_total.deferred += 1
            self._message_deferred_qid[qid] = 1

        if domain not in self.results.rcpt_domain:
            self.results.rcpt_domain[domain] = MessageStats()
        self.results.rcpt_domain[domain].defers += 1
        if delay > self.results.rcpt_domain[domain].delay_max:
            self.results.rcpt_domain[domain].delay_max = delay

    # -------------------------------------------------------------------------
    def _inc_bounced(self, relay, reason):

        if relay not in self.results.bounced:
            self.results.bounced[relay] = {}
        if reason not in self.results.bounced[relay]:
            self.results.bounced[relay][reason] = 0
        self.results.bounced[relay][reason] += 1

    # -------------------------------------------------------------------------
    def _eval_bounced_msg(self, addr, domain, relay, delay, rest):

        hour = self._cur_ts.hour

        if self.detail_bounce:
            m = self.re_bounce_reason.search(self._cur_msg)
            if m:
                reason = m.group(1)
                if not self.detail_verbose_msg:
                    reason = self.said_string_trimmer(reason)
                    reason = self.re_three_digits_at_start.sub('', reason)
                self._inc_bounced(relay, reason)

        self.results.bounced_messages_per_hour[hour] += 1
        self.incr_msgs_per_day('bounced')
        self.results.msgs_total.bounced += 1

    # -------------------------------------------------------------------------
    def _eval_relay_sent_msg(self, addr, domain, relay, delay, rest):
        if self.re_forwarded_as.search(rest):
            self.results.msgs_total.forwarded += 1
            return

        if domain not in self.results.rcpt_domain:
            self.results.rcpt_domain[domain] = MessageStats()
            # self.results.rcpt_domain_count += 1
            self.results.msgs_total.rcpt_domains += 1
        self.results.rcpt_domain[domain].count += 1
        self.results.rcpt_domain[domain].delay_avg += delay
        if delay > self.results.rcpt_domain[domain].delay_max:
            self.results.rcpt_domain[domain].delay_max = delay

        if addr not in self.results.rcpt_user:
            self.results.rcpt_user[addr] = MessageStats()
            # self.results.rcpt_user_count += 1
            self.results.msgs_total.rcpt_users += 1
        self.results.rcpt_user[addr].count += 1

        hour = self._cur_ts.hour
        self.results.delivered_messages_per_hour[hour] += 1
        self.incr_msgs_per_day('sent')
        self.results.msgs_total.delivered += 1

        qid = self._cur_qid
        if qid in self._message_size:
            size = self._message_size[qid]
            self.results.rcpt_domain[domain].size += size
            self.results.rcpt_user[addr].size += size
            self.results.msgs_total.bytes_delivered += size
        else:
            self.results.rcpt_domain[domain].size += 0
            self.results.rcpt_user[addr].size += 0
            if not self.no_no_message_size:
                self.results.no_message_size[qid] = addr
            self._add_ext_msg_detail(qid, '({})'.format('sender not in log'))

        self._add_ext_msg_detail(qid, addr)

    # -------------------------------------------------------------------------
    def _eval_pickup_msgs(self):
        hour = self._cur_ts.hour
        qid = self._cur_qid

        self.results.received_messages_per_hour[hour] += 1
        self.incr_msgs_per_day('received')
        self.results.msgs_total.received += 1
        self._rcvd_msgs_qid[qid] = 'pickup'

    # -------------------------------------------------------------------------
    def _eval_smtp(self):

        smtp_target = None
        smtp_msg = None

        m = self.re_smtp_connect_to_trusted.search(self._cur_msg)
        if m:
            smtp_target = m.group(1).lower()
            smtp_msg = m.group(2)
            self.results.smtp_connections['total'] += 1
            self.results.smtp_connections['trusted'] += 1
            if self.detail_smtp:
                if smtp_target not in self.results.smtp_connection_details['trusted']:
                    self.results.smtp_connection_details['trusted'][smtp_target] = {}
                if smtp_msg not in self.results.smtp_connection_details['trusted'][smtp_target]:
                    self.results.smtp_connection_details['trusted'][smtp_target][smtp_msg] = 0
                self.results.smtp_connection_details['trusted'][smtp_target][smtp_msg] += 1
            return

        m = self.re_smtp_connect_to_untrusted.search(self._cur_msg)
        if m:
            smtp_target = m.group(1).lower()
            smtp_msg = m.group(2)
            self.results.smtp_connections['total'] += 1
            self.results.smtp_connections['untrusted'] += 1
            if self.detail_smtp:
                if smtp_target not in self.results.smtp_connection_details['untrusted']:
                    self.results.smtp_connection_details['untrusted'][smtp_target] = {}
                if smtp_msg not in self.results.smtp_connection_details['untrusted'][smtp_target]:
                    self.results.smtp_connection_details['untrusted'][smtp_target][smtp_msg] = 0
                self.results.smtp_connection_details['untrusted'][smtp_target][smtp_msg] += 1
            return

        m = self.re_smtp_connect_to.search(self._cur_msg)
        if m:
            smtp_target = m.group(1).lower()
            smtp_msg = m.group(2)
            self.results.smtp_connections['other'] += 1
            if self.detail_smtp:
                if smtp_target not in self.results.smtp_connection_details['other']:
                    self.results.smtp_connection_details['other'][smtp_target] = {}
                if smtp_msg not in self.results.smtp_connection_details['other'][smtp_target]:
                    self.results.smtp_connection_details['other'][smtp_target][smtp_msg] = 0
                self.results.smtp_connection_details['other'][smtp_target][smtp_msg] += 1
            return

        if not self.detail_smtp:
            return

        m = self.re_connected_to_addr.search(self._cur_msg)
        if m:
            smtp_target = m.group(1).lower()
            smtp_msg = m.group(2)

        else:
            m = self.re_connected_to_port.search(self._cur_msg)
            if m:
                smtp_target = m.group(1).lower()
                smtp_msg = m.group(2)

        if not smtp_target:
            if self.verbose > 1:
                msg = _("Unhandled SMTP message: {msg!r}").format(msg=self._cur_msg)
                LOG.debug(msg)
            return

        if smtp_target not in self.results.smtp_messages:
            self.results.smtp_messages[smtp_target] = {}
        if smtp_msg not in self.results.smtp_messages[smtp_target]:
            self.results.smtp_messages[smtp_target] = 0
        self.results.smtp_messages[smtp_target] += 1


# =============================================================================

if __name__ == "__main__":

    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
