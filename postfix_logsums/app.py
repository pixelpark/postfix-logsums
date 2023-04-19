#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Author: Frank Brehm <frank@brehm-online.com
#         Berlin, Germany, 2022
# Date:   2022-02-17
#
# Refactored from Perl script 'pflogsumm' from James S. Seymour, Release 1.1.5
#

from __future__ import absolute_import, print_function

import sys
import os
import logging
import argparse
import traceback
import datetime
import copy
import re
import textwrap
import shutil
import locale
import json

HAS_YAML = False
try:
    import yaml
    HAS_YAML = True
except ImportError:
    pass

# from argparse import RawDescriptionHelpFormatter
from argparse import RawTextHelpFormatter

from pathlib import Path

from functools import cmp_to_key

from locale import strcoll, format_string

from operator import itemgetter

LOG = logging.getLogger(__name__)

from . import __version__ as GLOBAL_VERSION
from . import pp, to_bytes, MAX_TERMINAL_WIDTH
from . import DEFAULT_TERMINAL_WIDTH, DEFAULT_TERMINAL_HEIGHT
from . import get_generic_appname, get_smh
from . import PostfixLogParser

from .xlate import XLATOR, format_list

from .stats import HOURS_PER_DAY

__version__ = '0.8.4'
_ = XLATOR.gettext
ngettext = XLATOR.ngettext


# =============================================================================
class NonNegativeItegerOptionAction(argparse.Action):

    # -------------------------------------------------------------------------
    def __call__(self, parser, namespace, value, option_string=None):

        try:
            val = int(value)
        except Exception as e:
            msg = _("Got a {c} for converting {v!r} into an integer value: {e}").format(
                c=e.__class__.__name__, v=value, e=e)
            raise argparse.ArgumentError(self, msg)

        if val < 0:
            msg = _("The option must not be negative (given: {}).").format(value)
            raise argparse.ArgumentError(self, msg)

        setattr(namespace, self.dest, val)


# =============================================================================
class FilterDayOptionAction(argparse.Action):

    # -------------------------------------------------------------------------
    def __init__(self, option_strings, *args, **kwargs):
        """Initialise a FilterDayOptionAction object."""
        super(FilterDayOptionAction, self).__init__(
            option_strings=option_strings, *args, **kwargs)

    # -------------------------------------------------------------------------
    def __call__(self, parser, namespace, value, option_string=None):

        val = str(value)
        used_day = None
        if val.lower() == 'today':
            used_day = datetime.date.today()
        elif val.lower() == 'yesterday':
            t_diff = datetime.timedelta(days=1)
            used_day = datetime.date.today() - t_diff
        else:
            pattern = r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$'
            m = re.match(pattern, val)
            if m:
                try:
                    used_day = datetime.date(int(m['year']), int(m['month']), int(m['day']))
                except Exception as e:
                    msg = _("Invalid date as day {!r} given").format(value)
                    msg += ': ' + str(e)
                    raise argparse.ArgumentError(self, msg)
            else:
                msg = _("Invalid date as day {!r} given").format(value) + '.'
                raise argparse.ArgumentError(self, msg)

        setattr(namespace, self.dest, used_day)


# =============================================================================
class LogFilesOptionAction(argparse.Action):
    """An argparse action for logfiles."""

    # -------------------------------------------------------------------------
    def __init__(self, option_strings, *args, **kwargs):
        """Initialise a LogFilesOptionAction object."""
        super(LogFilesOptionAction, self).__init__(
            option_strings=option_strings, *args, **kwargs)

    # -------------------------------------------------------------------------
    def __call__(self, parser, namespace, values, option_string=None):
        """Parse the logfile option."""
        if values is None or values == []:
            setattr(namespace, self.dest, [])
            return

        if isinstance(values, list):
            all_files = values
        else:
            all_files = [values]

        logfiles = []
        for logfile in all_files:

            path = Path(logfile)
            if not path.exists():
                msg = _("Logfile {!r} does not exists.").format(logfile)
                raise argparse.ArgumentError(self, msg)

            if not path.is_file():
                msg = _("File {!r} is not a regular file.").format(logfile)
                raise argparse.ArgumentError(self, msg)

            if not os.access(str(path), os.R_OK):
                msg = _("File {!r} is not readable.").format(logfile)
                raise argparse.ArgumentError(self, msg)

            logfiles.append(path.resolve())

        setattr(namespace, self.dest, logfiles)

# =============================================================================
def adj_int_units(value):

    val = value
    unit = ' '
    if value > PostfixLogParser.div_by_one_gb_at:
        val = value / PostfixLogParser.one_gb
        unit = 'G'
    elif value > PostfixLogParser.div_by_one_mb_at:
        val = value / PostfixLogParser.one_mb
        unit = 'M'
    elif value > PostfixLogParser.div_by_one_kb_at:
        val = value / PostfixLogParser.one_kb
        unit = 'K'
    elif not value:
        val = 0

    return {'value': val, 'unit': unit}


# =============================================================================
def ci_cmp(one, two):
    """Comparing two strings case insensitive."""
    if one.lower() < two.lower():
        return -1
    if one.lower() > two.lower():
        return 1
    if one < two:
        return -1
    if one > two:
        return 1
    return 0

# =============================================================================
def adj_int_units_localized(value, digits=1, dec_digits=0, no_unit=False):
    """Generating a string with localized value."""
    val = value
    unit = ' '
    if not value:
        val = 0
    if not no_unit:
        if value > PostfixLogParser.div_by_one_gb_at:
            val = value / PostfixLogParser.one_gb
            unit = 'G'
        elif value > PostfixLogParser.div_by_one_mb_at:
            val = value / PostfixLogParser.one_mb
            unit = 'M'
        elif value > PostfixLogParser.div_by_one_kb_at:
            val = value / PostfixLogParser.one_kb
            unit = 'K'

    tpl = '%{}.0f'.format(digits)
    if dec_digits:
        tpl = '%{dig}.{dec}f'.format(dig=digits, dec=dec_digits)
    ret = format_string(tpl, val, grouping=True)
    ret += unit

    return ret


# =============================================================================
def adj_time_units(seconds, digits=1, dec_digits=1):
    """Return (value + unit) for time"""

    val = seconds
    unit = 's'
    if seconds > 3600 * 1.5:
        val = seconds / 3600
        unit = 'h'
    elif seconds > 90:
        val = seconds / 60
        unit = 'm'

    tpl = '%{}.0f'.format(digits)
    if dec_digits:
        tpl = '%{dig}.{dec}f'.format(dig=digits, dec=dec_digits)
    ret = format_string(tpl, val, grouping=True)
    ret += unit

    return ret


# =============================================================================
class PostfixLogsumsApp(object):

    term_size = shutil.get_terminal_size((DEFAULT_TERMINAL_WIDTH, DEFAULT_TERMINAL_HEIGHT))
    max_width = term_size.columns
    if max_width > MAX_TERMINAL_WIDTH:
        max_width = MAX_TERMINAL_WIDTH

    re_first_letter = re.compile(r'^(.)(.*)')
    pat_ipv4_tuple = r'(\d|[1-9]\d|1\d\d|2(?:[04]\d|5[0-5]))'
    pat_ipv4 = r'^' + r'.'.join(pat_ipv4_tuple) + r'$'
    re_ipv4 = re.compile(pat_ipv4)

    re_mailsplit = re.compile(r'@')
    re_maildomain = re.compile(r'^(.*)\.([^\.]+)\.([^\.]{3}|[^\.]{2,3}\.[^\.]{2})$')
    re_bang_path = re.compile(r'^.*!')

    hours_per_day = HOURS_PER_DAY

    output_formats = ['txt', 'json']
    if HAS_YAML:
        output_formats.append('yaml')

    # -------------------------------------------------------------------------
    @classmethod
    def sorted_keys_by_count_and_key(cls, data):
        """Returns all keys of tha data dict sorted."""
        sorted_keys = []

        # ---------------------------------------------
        def sort_by_count_and_key(key_one, key_two):
            val_one = data[key_one]
            val_two = data[key_two]
            if val_one != val_two:
                if val_one < val_two:
                    return 1
                else:
                    return -1
            lkey_one = key_one.lower()
            lkey_two = key_two.lower()
            m_one = cls.re_ipv4.match(key_one)
            m_two = cls.re_ipv4.match(key_two)
            if m_one and m_two:
                lkey_one = ''.join(map(lambda x: chr(int(x)), m_one.groups()))
                lkey_two = ''.join(map(lambda x: chr(int(x)), m_two.groups()))
            return strcoll(lkey_one, lkey_two)

        for key in sorted(data.keys(), key=cmp_to_key(sort_by_count_and_key)):
            sorted_keys.append(key)

        return sorted_keys

    # -------------------------------------------------------------------------
    @classmethod
    def sorted_keys_of_msg_stats(cls, data):
        """Returns all keys of tha data dict sorted."""
        sorted_keys = []

        # ---------------------------------------------
        def by_count_then_size(key_one, key_two):
            stats_one = data[key_one]
            stats_two = data[key_two]

            if stats_one.count != stats_two.count:
                if stats_one.count > stats_two.count:
                    return -1
                else:
                    return 1

            if stats_one.size > stats_two.size:
                return -1
            if stats_one.size < stats_two.size:
                return 1
            return 0

        for key in sorted(data.keys(), key=cmp_to_key(by_count_then_size)):
            sorted_keys.append(key)

        return sorted_keys

    # -------------------------------------------------------------------------
    @classmethod
    def sorted_keys_of_smtpd_stats(cls, data):
        """Returns all keys of tha data dict sorted."""
        sorted_keys = []

        # ---------------------------------------------
        def by_count_then_time(key_one, key_two):
            stats_one = data[key_one]
            stats_two = data[key_two]

            if stats_one.connections != stats_two.connections:
                if stats_one.connections > stats_two.connections:
                    return -1
                else:
                    return 1

            if stats_one.connect_time_total > stats_two.connect_time_total:
                return -1
            if stats_one.connect_time_total < stats_two.connect_time_total:
                return 1
            return 0

        for key in sorted(data.keys(), key=cmp_to_key(by_count_then_time)):
            sorted_keys.append(key)

        return sorted_keys

    # -------------------------------------------------------------------------
    @classmethod
    def wrap_msg(cls, message, width=None):
        """Wrap the given message to the max terminal width ..."""
        if width is None:
            width = cls.max_width
        return textwrap.fill(message, width)

    # -------------------------------------------------------------------------
    def __init__(self):
        """The constructor method."""
        self._appname = get_generic_appname()
        self._version = __version__
        self._verbose = 0
        self._quiet = False
        self._initialized = False
        self.parser = None

        self.init_arg_parser()
        self.perform_arg_parser()
        self.init_logging()

        self.nr_days = 0

        compression = None
        if self.args.gzip:
            compression = 'gzip'
        elif self.args.bzip2:
            compression = 'bzip2'
        elif self.args.xz:
            compression = 'lzma'

        self.parser = PostfixLogParser(
            appname=self.appname, verbose=self.verbose, day=self.args.day,
            compression=compression, zero_fill=self.args.zero_fill, detail_smtp=self.detail_smtp,
            detail_reject=self.detail_reject, detail_smtpd_warning=self.detail_smtpd_warning,
            detail_bounce=self.detail_bounce, detail_deferral=self.detail_deferral,
            ignore_case=self.args.ignore_case, rej_add_from=self.args.rej_add_from,
            smtpd_stats=self.args.smtpd_stats, extended=self.args.extended,
            verp_mung=self.args.verp_mung, detail_verbose_msg=self.detail_verbose_msg)

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
    def appname_capitalized(self):
        """The name of the current running application withe first character
        as a capital."""
        match = self.re_first_letter.match(self.appname)
        if match:
            return match.group(1).upper() + match.group(2)
        return self.appname

    # -----------------------------------------------------------
    @property
    def version(self):
        """The version string of the current object or application."""
        return getattr(self, '_version', __version__)

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
    def quiet(self):
        """Don't print headings for empty reports."""
        return self._quiet

    @quiet.setter
    def quiet(self, value):
        self._quiet = bool(value)

    # -----------------------------------------------------------
    @property
    def initialized(self):
        """The initialisation of this object is complete."""
        return getattr(self, '_initialized', False)

    @initialized.setter
    def initialized(self, value):
        self._initialized = bool(value)

    # -----------------------------------------------------------
    @property
    def detail(self):
        """Sets all --*-detail, -h and -u. Is over-ridden by individual settings."""
        if not hasattr(self, 'args'):
            return 1
        if not self.args:
            return 1
        return getattr(self.args, 'detail', 1)

    # -----------------------------------------------------------
    @property
    def detail_bounce(self):
        """Limit detailed bounce reports."""
        if not hasattr(self, 'args'):
            return None
        if not self.args:
            return None
        det = getattr(self.args, 'detail_bounce', None)
        if det is None:
            return self.detail
        return det

    # -----------------------------------------------------------
    @property
    def detail_deferral(self):
        """Limit detailed deferral reports."""
        if not hasattr(self, 'args'):
            return None
        if not self.args:
            return None
        det = getattr(self.args, 'detail_deferral', None)
        if det is None:
            return self.detail
        return det

    # -----------------------------------------------------------
    @property
    def detail_host(self):
        """Limit detailed host reports."""
        if not hasattr(self, 'args'):
            return None
        if not self.args:
            return None
        det = getattr(self.args, 'detail_host', None)
        if det is None:
            return self.detail
        return det

    # -----------------------------------------------------------
    @property
    def detail_reject(self):
        """Limit detailed reject reports."""
        if not hasattr(self, 'args'):
            return None
        if not self.args:
            return None
        det = getattr(self.args, 'detail_reject', None)
        if det is None:
            return self.detail
        return det

    # -----------------------------------------------------------
    @property
    def detail_smtp(self):
        """Limit detailed smtp reports."""
        if not hasattr(self, 'args'):
            return None
        if not self.args:
            return None
        det = getattr(self.args, 'detail_smtp', None)
        if det is None:
            return self.detail
        return det

    # -----------------------------------------------------------
    @property
    def detail_smtpd_warning(self):
        """Limit detailed smtpd warnings reports."""
        if not hasattr(self, 'args'):
            return None
        if not self.args:
            return None
        det = getattr(self.args, 'detail_smtpd_warning', None)
        if det is None:
            return self.detail
        return det

    # -----------------------------------------------------------
    @property
    def detail_user(self):
        """Limit detailed user reports."""
        if not hasattr(self, 'args'):
            return None
        if not self.args:
            return None
        det = getattr(self.args, 'detail_user', None)
        if det is None:
            return self.detail
        return det

    # -----------------------------------------------------------
    @property
    def detail_verbose_msg(self):
        """Limit detailed verbose message reports."""
        if not hasattr(self, 'args'):
            return None
        if not self.args:
            return None
        return getattr(self.args, 'detail_verbose_msg', False)

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
        res['appname_capitalized'] = self.appname_capitalized
        res['args'] = copy.copy(self.args.__dict__)
        res['initialized'] = self.initialized
        res['detail'] = self.detail
        res['detail_bounce'] = self.detail_bounce
        res['detail_deferral'] = self.detail_deferral
        res['detail_host'] = self.detail_host
        res['detail_reject'] = self.detail_reject
        res['detail_smtp'] = self.detail_smtp
        res['detail_smtpd_warning'] = self.detail_smtpd_warning
        res['detail_user'] = self.detail_user
        res['detail_verbose_msg'] = self.detail_verbose_msg
        if self.parser:
            res['parser'] = self.parser.as_dict(short=short)
        res['quiet'] = self.quiet
        res['version'] = self.version
        res['verbose'] = self.verbose

        return res

    # -------------------------------------------------------------------------
    def init_arg_parser(self):
        """
        Local called method to initiate the argument parser.

        @raise PBApplicationError: on some errors

        """

        appname = self.appname_capitalized
        arg_width = self.max_width - 24

        desc = []
        desc.append(_('{} is a log analyzer/summarizer for the Postfix MTA.').format(appname))
        desc.append(_(
            'It is designed to provide an over-view of Postfix activity, with just enough '
            'detail to give the administrator a "heads up" for potential trouble spots.'))
        desc.append(_(
            '{} generates summaries and, in some cases, detailed reports of mail server traffic '
            'volumes, rejected and bounced email, and server warnings, '
            'errors and panics.').format(appname))

        description = ''
        for des in desc:
            des = self.wrap_msg(des)
            if description:
                description += '\n\n'
            description += des

        self.arg_parser = argparse.ArgumentParser(
            prog=self.appname,
            description=description,
            formatter_class=RawTextHelpFormatter,
            add_help=False,
        )

        logfile_group = self.arg_parser.add_argument_group(_(
            'Options for scanning Postfix logfiles'))

        # --day
        desc = self.wrap_msg(_(
            'Generate report for just today, yesterday or a date in ISO format (YYY-mm-dd).'))
        desc = self.wrap_msg(desc, arg_width)
        logfile_group.add_argument(
            '-d', '--day', metavar=_('DAY'), dest='day',
            action=FilterDayOptionAction, help=desc)

        # --extended
        desc = _('Extended (extreme? excessive?) detail.') + '\n'
        desc += self.wrap_msg(_(
            'At present, this includes only a per-message report, sorted by sender domain, '
            'then user-in-domain, then by queue i.d.'), arg_width) + '\n'
        desc += self.wrap_msg(_(
            'WARNING: the data built to generate this report can quickly consume very large '
            'amounts of memory if a lot of log entries are processed!'), arg_width)
        logfile_group.add_argument(
            '-e', '--extended', dest='extended', action="store_true", help=desc)

        # --ignore-case
        desc = self.wrap_msg(_(
            'Handle complete email address in a case-insensitive manner.'), arg_width)
        desc += '\n'
        desc += self.wrap_msg(_(
            'Normally {} lower-cases only the host and domain parts, leaving the user part alone. '
            'This option causes the entire email address to be lower-cased.').format(appname),
            arg_width)
        logfile_group.add_argument(
            '-i', '--ignore-case', dest='ignore_case', action="store_true", help=desc)

        # --no-no-msg-size
        desc = self.wrap_msg(_('Do not emit report on "Messages with no size data".'), arg_width)
        desc += '\n'
        desc += self.wrap_msg(_(
            'Message size is reported only by the queue manager. The message may be delivered '
            'long-enough after the (last) qmgr log entry that the information is not in '
            'the log(s) processed by a particular run of {a}. This throws off "Recipients by '
            'message size" and the total for "bytes delivered." These are normally reported by '
            '{a} as "Messages with nosize data".').format(a=appname), arg_width)
        logfile_group.add_argument(
            '--no-no-msg-size', dest='nono_msgsize', action="store_true", help=desc)

        # --rej-add-from
        desc = self.wrap_msg(_(
            'For those reject reports that list IP addresses or host/domain names: append the '
            'email from address to each listing. (Does not apply to "Improper use of '
            'SMTP command pipelining" report.)'), arg_width)
        logfile_group.add_argument(
            '--rej-add-from', dest='rej_add_from', action="store_true", help=desc)

        # --smtpd-stats
        desc = self.wrap_msg(_('Generate smtpd connection statistics.'), arg_width) + '\n'
        desc += self.wrap_msg(_(
            'The "per-day" report is not generated for single-day reports. For multiple-day '
            'reports: "per-hour" numbers are daily averages (reflected in the report '
            'heading).'), arg_width)
        logfile_group.add_argument(
            '--smtpd-stats', dest='smtpd_stats', action="store_true", help=desc)

        # --verp-mung
        desc = self.wrap_msg(_(
            'Do "VERP" generated address (?) munging. Convert sender addresses of the form '
            '"list-return-NN-someuser=some.dom@host.sender.dom" to '
            '"list-return-ID-someuser=some.dom@host.sender.dom".'), arg_width) + '\n'
        desc += self.wrap_msg(_(
            'In other words: replace the numeric value with "ID".'), arg_width) + '\n'
        desc += self.wrap_msg(_(
            'By specifying the optional "=2" (second form), the munging is more "aggressive", '
            'converting the address to something like: "list-return@host.sender.dom".'),
            arg_width) + '\n'
        desc += self.wrap_msg(_(
            'Actually: specifying anything less than 2 does the "simple" munging and anything '
            'greater than 1 results in the more "aggressive" hack being applied.'), arg_width)
        logfile_group.add_argument(
            '--verp-mung', type=int, metavar='1|2', const=0, dest='verp_mung', nargs='?',
            action=NonNegativeItegerOptionAction, help=desc)

        #######
        # Select compression
        compression_section = self.arg_parser.add_argument_group(_('Logfile compression options'))

        compression_group = compression_section.add_mutually_exclusive_group()

        # --gzip
        desc = self.wrap_msg(_(
            'Assume, that stdin stream or the given files are gzip compressed.'), arg_width) + '\n'
        desc += self.wrap_msg(_(
            'If not given, filenames with the extension ".gz" are assumed to be compressed with '
            'the gzip compression.'), arg_width)
        compression_group.add_argument(
            '-z', '--gzip', dest='gzip', action="store_true", help=desc)

        # --bzip2
        desc = self.wrap_msg(_(
            'Assume, that stdin stream or the given files are bzip2 '
            'compressed.'), arg_width) + '\n'
        desc += self.wrap_msg(_(
            'If not given, filenames with the extensions ".bz2" or ".bzip2" are assumed to be '
            'compressed with the bzip2 compression.'), arg_width)
        compression_group.add_argument(
            '-j', '--bzip2', dest='bzip2', action="store_true", help=desc)

        # --xz
        desc = self.wrap_msg(_(
            'Assume, that stdin stream or the given files are xz or lzma compressed.'),
            arg_width) + '\n'
        desc += self.wrap_msg(_(
            'If not given, filenames with the extensions ".xz" or ".lzma" are assumed to be '
            'compressed with the xz or lzma compression.'), arg_width)
        compression_group.add_argument(
            '-J', '--xz', '--lzma', dest='xz', action="store_true", help=desc)

        # last parse option
        desc = _('The logfile(s) to analyze. If no file(s) specified, reads from stdin.')
        desc = self.wrap_msg(desc, arg_width)
        logfile_group.add_argument(
            'logfiles', metavar=_('FILE'), nargs='*', action=LogFilesOptionAction, help=desc)

        #######
        # Output
        output_options = self.arg_parser.add_argument_group(_('Output options'))

        desc = _('Output format. Valid options are:') + ' ' + format_list(
            self.output_formats, True) + '. '
        desc += _("Default: '{}'.").format('txt')
        desc = self.wrap_msg(desc, arg_width)
        output_options.add_argument(
            '-O', '--output-format', choices=self.output_formats, metavar=_('FORMAT'),
            dest='output_format', help=desc)

        # --detail
        desc = self.wrap_msg(_(
            'Sets all --*-detail, -h and -u to COUNT. Is over-ridden by '
            'individual settings.'), arg_width) + '\n'
        desc += self.wrap_msg(_('--detail 0 suppresses *all* detail.'), arg_width)
        output_options.add_argument(
            '-D', '--detail', type=int, metavar=_('COUNT'), dest='detail',
            action=NonNegativeItegerOptionAction, help=desc)

        # --bounce-detail
        desc = self.wrap_msg(_(
            'Limit detailed bounce reports to the top {}.').format(_('COUNT')), arg_width) + '\n'
        desc += self.wrap_msg(_('0 to suppress entirely.'), arg_width)
        output_options.add_argument(
            '--bounce-detail', type=int, metavar=_('COUNT'), dest='detail_bounce',
            action=NonNegativeItegerOptionAction, help=desc)

        # --deferral-detail
        desc = self.wrap_msg(_(
            'Limit detailed deferral reports to the top {}.').format(_('COUNT')), arg_width) + '\n'
        desc += self.wrap_msg(_('0 to suppress entirely.'), arg_width)
        output_options.add_argument(
            '--deferral-detail', type=int, metavar=_('COUNT'), dest='detail_deferral',
            action=NonNegativeItegerOptionAction, help=desc)

        # --reject-detail
        desc = self.wrap_msg(_(
            'Limit detailed smtpd reject, warn, hold and discard reports to the '
            'top {}.').format(_('COUNT')), arg_width) + '\n'
        desc += self.wrap_msg(_('0 to suppress entirely.'), arg_width)
        output_options.add_argument(
            '--reject-detail', type=int, metavar=_('COUNT'), dest='detail_reject',
            action=NonNegativeItegerOptionAction, help=desc)

        # --smtp-detail
        desc = self.wrap_msg(_(
            'Limit detailed smtp delivery reports to the '
            'top {}.').format(_('COUNT')), arg_width) + '\n'
        desc += self.wrap_msg(_('0 to suppress entirely.'), arg_width)
        output_options.add_argument(
            '--smtp-detail', type=int, metavar=_('COUNT'), dest='detail_smtp',
            action=NonNegativeItegerOptionAction, help=desc)

        # --smtpd-warning-detail
        desc = self.wrap_msg(_(
            'Limit detailed smtpd warnings reports to the '
            'top {}.').format(_('COUNT')), arg_width) + '\n'
        desc += self.wrap_msg(_('0 to suppress entirely.'), arg_width)
        output_options.add_argument(
            '--smtpd-warning-detail', type=int, metavar=_('COUNT'), dest='detail_smtpd_warning',
            action=NonNegativeItegerOptionAction, help=desc)

        # --host
        desc = self.wrap_msg(_(
            'Top {} to display in host/domain reports.').format(_('COUNT')), arg_width)
        desc += '\n0 = {}.\n'.format(_('none'))
        desc += self.wrap_msg(_(
            'See also: "-u" and "--*-detail" options for further report-limiting options.'),
            arg_width)
        output_options.add_argument(
            '-h', '--host', type=int, metavar=_('COUNT'), dest='detail_host',
            action=NonNegativeItegerOptionAction, help=desc)

        # --user
        desc = self.wrap_msg(_(
            'Top {} to display in user reports.').format(_('COUNT')), arg_width) + '\n'
        desc += '0 = {}.'.format(_('none'))
        output_options.add_argument(
            '-u', '--user', type=int, metavar=_('COUNT'), dest='detail_user',
            action=NonNegativeItegerOptionAction, help=desc)

        # --problems-first
        desc = self.wrap_msg(_(
            'Emit "problems" reports (bounces, defers, warnings, etc.) before "normal" stats.'),
            arg_width)
        output_options.add_argument(
            '--pf', '--problems-first', dest='problems_first', action="store_true", help=desc)

        # --iso-date-time
        desc = self.wrap_msg(_(
            'For summaries that contain date or time information, use ISO 8601 standard formats '
            '(CCYY-MM-DD and HH:MM), rather than "Mon DD CCYY" and "HHMM".'), arg_width)
        output_options.add_argument(
            '--iso-date-time', dest='iso_date', action="store_true", help=desc)

        # --verbose-msg-detail
        desc = self.wrap_msg(_(
            'For the message deferral, bounce and reject summaries: display the full "reason", '
            'rather than a truncated one.'), arg_width) + '\n'
        desc += self.wrap_msg(_(
            'NOTE: this can result in quite long lines in the report.'), arg_width)
        output_options.add_argument(
            '--verbose-msg-detail', dest='detail_verbose_msg', action="store_true", help=desc)

        # --zero-fill
        desc = self.wrap_msg(_(
            '"Zero-fill" certain arrays so reports come out with data in columns that might '
            'otherwise be blank.'), arg_width)
        output_options.add_argument(
            '--zero-fill', dest='zero_fill', action="store_true", help=desc)

        #######
        # General stuff
        general_group = self.arg_parser.add_argument_group(_('General options'))

        verbose_group = general_group.add_mutually_exclusive_group()

        desc = self.wrap_msg(_(
            'Enabling debug messages and increase their verbosity level if used multiple times.'))
        verbose_group.add_argument(
            "-v", "--verbose", action="count", dest='verbose', help=desc)

        # --quiet
        desc = self.wrap_msg(_("quiet - don't print headings for empty reports."), arg_width)
        desc += '\n'
        desc += self.wrap_msg(_(
            'NOTE: headings for warning, fatal, and "master" messages will always be '
            'printed.'), arg_width)
        verbose_group.add_argument(
            '-q', '--quiet', dest='quiet', action="store_true", help=desc)

        general_group.add_argument(
            "--help", action='help', dest='help',
            help=_('Show this help message and exit.')
        )

        general_group.add_argument(
            "--usage", action='store_true', dest='usage',
            help=_("Display brief usage message and exit.")
        )

        v_msg = _("Version of %(prog)s: {}").format(GLOBAL_VERSION)
        general_group.add_argument(
            "-V", '--version', action='version', version=v_msg,
            help=_("Show program's version number and exit.")
        )

    # -------------------------------------------------------------------------
    def perform_arg_parser(self):

        self.args = self.arg_parser.parse_args()

        if self.args.usage:
            self.arg_parser.print_usage(sys.stdout)
            self.exit(0)

        if self.args.verbose is not None and self.args.verbose > self.verbose:
            self.verbose = self.args.verbose
        elif self.args.quiet:
            self.quiet = True

    # -------------------------------------------------------------------------
    def init_logging(self):
        """
        Initialize the logger object.
        It creates a colored loghandler with all output to STDERR.
        Maybe overridden in descendant classes.

        @return: None
        """

        log_level = logging.INFO
        if self.verbose:
            log_level = logging.DEBUG

        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # create formatter
        format_str = ''
        if self.verbose:
            format_str = '[%(asctime)s]: '
        format_str += self.appname + ': '
        if self.verbose:
            if self.verbose > 1:
                format_str += '%(name)s(%(lineno)d) %(funcName)s() '
            else:
                format_str += '%(name)s '
        format_str += '%(levelname)s - %(message)s'
        formatter = logging.Formatter(format_str)

        # create log handler for console output
        lh_console = logging.StreamHandler(sys.stderr)
        lh_console.setLevel(log_level)
        lh_console.setFormatter(formatter)

        root_logger.addHandler(lh_console)

        return

    # -------------------------------------------------------------------------
    def handle_error(
            self, error_message=None, exception_name=None, do_traceback=False):

        msg = str(error_message).strip()
        if not msg:
            msg = _('undefined error.')
        title = None

        if isinstance(error_message, Exception):
            title = error_message.__class__.__name__
        else:
            if exception_name is not None:
                title = exception_name.strip()
            else:
                title = _('Exception happened')
        msg = title + ': ' + msg

        root_log = logging.getLogger()
        has_handlers = False
        if root_log.handlers:
            has_handlers = True

        if has_handlers:
            LOG.error(msg)
            if do_traceback:
                LOG.error(traceback.format_exc())
        else:
            curdate = datetime.datetime.now()
            curdate_str = "[" + curdate.isoformat(' ') + "]: "
            msg = curdate_str + msg + "\n"
            if hasattr(sys.stderr, 'buffer'):
                sys.stderr.buffer.write(to_bytes(msg))
            else:
                sys.stderr.write(msg)
            if do_traceback:
                traceback.print_exc()

        return

    # -------------------------------------------------------------------------
    def __call__(self):
        return self.run()

    # -------------------------------------------------------------------------
    def run(self):

        LOG.debug(_("And here wo go ..."))

        locale.setlocale(locale.LC_ALL, '')

        self.parser.parse(*self.args.logfiles)
        self.results = self.parser.results
        self.nr_days = len(self.results.messages_per_day.keys())

        if self.verbose > 2:
            LOG.info(_('Result of parsing:') + '\n' + pp(self.results.as_dict()))
        elif self.verbose > 1:
            LOG.info(_('Result of parsing:') + '\n' + pp(self.results.dict()))

        if self.args.output_format == 'json':
            print(json.dumps(self.results.dict(), indent=4, sort_keys=True))
            return
        elif self.args.output_format == 'yaml':
            print(yaml.safe_dump(
                self.results.dict(), allow_unicode=True, explicit_start=True, canonical=False,
                sort_keys=True, indent=4, width=self.max_width, default_style=None))
            return

        print()
        if self.parser.date_str:
            msg = _("Postfix log summaries for {}").format(self.parser.date_str)
        else:
            msg = _("Postfix log summaries")
        print(msg)
        print('=' * len(msg))

        self.print_grand_totals()

        if self.args.smtpd_stats:
            self.print_smtpd_stats()

        if self.args.problems_first:
            self.print_problems_reports()

        if self.nr_days > 1:
            self.print_per_day_summary()
        self.print_per_hour_summary()
        self.print_recip_domain_summary()
        self.print_sending_domain_summary()

        if self.args.smtpd_stats:
            if self.nr_days > 1:
                self.print_per_day_smtpd()
            self.print_per_hour_smtpd()
            self.print_domain_smtpd_summary()

        self.print_user_data(
            self.results.sending_user_data, _("Senders by message count"), 'count')
        self.print_user_data(self.results.rcpt_user, _("Recipients by message count"), 'count')
        self.print_user_data(self.results.sending_user_data, _("Senders by message size"), 'size')
        self.print_user_data(self.results.rcpt_user, _("Recipients by message size"), 'size')

        self.print_hash_by_key(
            self.results.no_message_size, _('Messages with no size data'), self.detail)

        if not self.args.problems_first:
            self.print_problems_reports()

        if self.args.extended:
            self.print_detailed_msg_data()

        print()

    # -------------------------------------------------------------------------
    def print_grand_totals(self):
        """Printing the grand total numbers and data."""
        self.print_subsect_title(_('Grand Totals'))

        if self.results.logdate_oldest or self.results.logdate_latest:
            lbl_oldest = _('Date of oldest log entry:')
            lbl_latest = _('Date of latest log entry:')
            max_len = len(lbl_oldest)
            if len(lbl_latest) > max_len:
                max_len = len(lbl_latest)
            print()
            if self.results.logdate_oldest:
                dt = self.results.logdate_oldest.isoformat(' ')
                print("{m:<{lng}}  {dt}".format(m=lbl_oldest, lng=max_len, dt=dt))
            if self.results.logdate_latest:
                dt = self.results.logdate_latest.isoformat(' ')
                print("{m:<{lng}}  {dt}".format(m=lbl_latest, lng=max_len, dt=dt))

        print()
        print(_('Messages:'))
        print()

        # Variable renamings:
        #  - self.results.bounced_total => self.results.msgs_total.bounced
        #  - self.results.deferrals_total => self.results.msgs_total.deferrals
        #  - self.results.deferred_messages_total => self.results.msgs_total.deferred
        #  - self.results.messages_delivered => self.results.msgs_total.delivered
        #  - self.results.messages_forwarded => self.results.msgs_total.forwarded
        #  - self.results.messages_received_total => self.results.msgs_total.received
        #  - self.results.messages['rejected'] => self.results.msgs_total.rejected
        #  - self.results.messages['warning'] => self.results.msgs_total.reject_warning
        #  - self.results.messages['hold'] => self.results.msgs_total.held
        #  - self.results.messages['discard'] => self.results.msgs_total.discarded

        tpl_loc = ' {val:>8}  {lbl}'

        msgs_received = self.results.msgs_total.received
        msgs_delivered = self.results.msgs_total.delivered
        msgs_rejected = self.results.msgs_total.rejected
        msgs_discarded = self.results.msgs_total.discarded
        msgs_total = msgs_delivered + msgs_rejected + msgs_discarded

        msgs_rejected_pct = 0.0
        msgs_discarded_pct = 0.0
        if msgs_total:
            msgs_rejected_pct = msgs_rejected / msgs_total * 100
            msgs_discarded_pct = msgs_discarded / msgs_total * 100

        nr = adj_int_units_localized(msgs_received)
        print(tpl_loc.format(val=nr, lbl=_('received')))
        nr = adj_int_units_localized(msgs_delivered)
        print(tpl_loc.format(val=nr, lbl=_('delivered')))
        nr = adj_int_units_localized(self.results.msgs_total.forwarded)
        print(tpl_loc.format(val=nr, lbl=_('forwarded')))
        nr = adj_int_units_localized(self.results.msgs_total.deferred)
        print(tpl_loc.format(val=nr, lbl=_('deferred')), end='')
        if self.results.msgs_total.deferrals:
            nr = adj_int_units_localized(self.results.msgs_total.deferrals)
            val = '  ({val} {lbl})'.format(lbl=_('deferrals'), val=nr)
            print(val, end='')
        print()
        nr = adj_int_units_localized(self.results.msgs_total.bounced)
        print(tpl_loc.format(val=nr, lbl=_('bounced')))
        nr = adj_int_units_localized(self.results.msgs_total.rejected)
        print(tpl_loc.format(val=nr, lbl=_('rejected')), end='')
        print(' ({:0.1f}%)'.format(msgs_rejected_pct))
        nr = adj_int_units_localized(self.results.msgs_total.reject_warning)
        print(tpl_loc.format(val=nr, lbl=_('reject warnings')))
        nr = adj_int_units_localized(self.results.msgs_total.held)
        print(tpl_loc.format(val=nr, lbl=_('held')))
        nr = adj_int_units_localized(self.results.msgs_total.discarded)
        print(tpl_loc.format(val=nr, lbl=_('discarded')), end='')
        print(' ({:0.1f}%)'.format(msgs_discarded_pct))
        print()

        nr = adj_int_units_localized(self.results.msgs_total.bytes_received)
        print(tpl_loc.format(val=nr, lbl=_('bytes received')))
        nr = adj_int_units_localized(self.results.msgs_total.bytes_delivered)
        print(tpl_loc.format(val=nr, lbl=_('bytes delivered')))
        nr = adj_int_units_localized(self.results.msgs_total.sending_users)
        print(tpl_loc.format(val=nr, lbl=_('senders')))
        nr = adj_int_units_localized(self.results.msgs_total.sending_domains)
        print(tpl_loc.format(val=nr, lbl=_('sending hosts/domains')))
        nr = adj_int_units_localized(self.results.msgs_total.rcpt_users)
        print(tpl_loc.format(val=nr, lbl=_('recipients')))
        nr = adj_int_units_localized(self.results.msgs_total.rcpt_domains)
        print(tpl_loc.format(val=nr, lbl=_('recipients hosts/domains')))

        print()

    # -------------------------------------------------------------------------
    def print_subsect_title(self, title, nr_items=1, count=None, quiet=None):
        """Printing the title of a sub section."""
        msg = str(title)
        if quiet is None:
            quiet = self.quiet
        print()

        if not nr_items:
            if not quiet:
                msg += ': ' + _('None')
                print(msg)
            return False

        if count:
            msg += ' ({lbl}: {c})'.format(lbl=_('top'), c=count)

        print(msg)
        print('-' * len(msg))

        return True

    # -------------------------------------------------------------------------
    def print_smtpd_stats(self):

        tpl_loc = ' {val:>8}  {lbl}'
        count_domains = len(self.results.smtpd_per_domain.keys())
        total_conn = self.results.msgs_total.connections
        time_conn = self.results.connections_time
        avg_time = 0.0
        if total_conn:
            avg_time = (time_conn / total_conn) + 0.5
        total_time_splitted = get_smh(time_conn)

        print()
        print('Smtpd:')
        print()

        print(tpl_loc.format(val=adj_int_units_localized(total_conn), lbl=_('connections')))
        print(tpl_loc.format(val=adj_int_units_localized(count_domains), lbl=_('hosts/domains')))
        print(tpl_loc.format(
            val=adj_int_units_localized(avg_time, no_unit=True), lbl=_('connections')))
        print('  {h:d}:{m:02d}:{s:02.0f}  {lbl}'.format(
            h=total_time_splitted[2], m=total_time_splitted[1],
            s=total_time_splitted[0], lbl=_('total connect time')))
        print()

    # -------------------------------------------------------------------------
    def print_nested_hash(self, data, label, count):
        if not len(data.keys()):
            if self.quiet:
                return
            print('\n{lbl}: {n}'.format(lbl=label, n=_('none')))
            return
        print('\n{lbl}'.format(lbl=label))
        print('-' * len(label))
        self.walk_nested_hash(data, count)

    # -------------------------------------------------------------------------
    def walk_nested_hash(self, data, count, level=0):
        """# 'walk' a 'nested' hash"""
        if not len(data.keys()):
            return
        level += 1
        indent = '  ' * level
        sorted_keys = sorted(data.keys(), key=str.lower)
        first_key = sorted_keys[0]
        first_value = data[first_key]

        if isinstance(first_value, dict):
            for key in sorted_keys:
                print('{i}{k}'.format(i=indent, k=key), end='')
                first_key2 = sorted(data[key].keys(), key=str.lower)[0]
                first_value2 = data[key][first_key2]
                if not isinstance(first_value2, dict):
                    if count is not None and count > 0:
                        print(' ({lbl}: {c})'.format(lbl=_('top'), c=count), end='')
                    total_count = 0
                    for key2 in data[key].keys():
                        total_count += data[key][key2]
                    val = adj_int_units_localized(total_count, no_unit=True).rstrip()
                    print(' ({lbl}: {c})'.format(lbl=_('total'), c=val), end='')
                print()
                self.walk_nested_hash(data[key], count, level)
        else:
            self.really_print_hash_by_cnt_vals(data, count, indent)

    # -------------------------------------------------------------------------
    def print_hash_by_cnt_vals(self, data, title, count):
        """Print hash contents sorted by numeric values in descending
        order (i.e.: highest first)."""
        if count:
            title = "{top} {c} ".format(top="top", c=count) + title
        if not len(data.keys()):
            if self.quiet:
                return
            print('\n{lbl}: {n}'.format(lbl=title, n=_('none')))
            return

        print('\n{lbl}'.format(lbl=title))
        print('-' * len(title))

        self.really_print_hash_by_cnt_vals(data, count, ' ')

    # -------------------------------------------------------------------------
    def really_print_hash_by_cnt_vals(self, data, count, indent):
        """*really* print hash contents sorted by numeric values in descending
        order (i.e.: highest first), then by IP/addr, in ascending order."""
        tpl = '{i}{val:>8}  {lbl}'

        i = 0
        for key in self.sorted_keys_by_count_and_key(data):
            val = adj_int_units_localized(data[key])
            print(tpl.format(i=indent, lbl=key, val=val))
            if count is not None:
                i += 1
                if i >= count:
                    break

    # -------------------------------------------------------------------------
    def print_hash_by_key(self, data, title, count=None, quiet=None):
        """Print dict contents sorted by key in ascending order."""
        if quiet is None:
            quiet = self.quiet
        indent = '  '

        nr_items = len(data.keys())
        if not self.print_subsect_title(title, nr_items=nr_items, count=count):
            return

        tpl = '{key}  {val}'
        i = 0
        for key in sorted(data.keys(), key=str.lower):
            line = tpl.format(key=key, val=data[key])
            print(indent + line)

            i += 1
            if count is not None and i >= count:
                break

    # -------------------------------------------------------------------------
    def print_problems_reports(self):
        """Print "problems" reports."""
        if self.detail_deferral != 0:
            self.print_nested_hash(
                data=self.results.deferred, label=_("Message deferral detail"),
                count=self.detail_deferral)

        if self.detail_bounce != 0:
            self.print_nested_hash(
                data=self.results.bounced, label=_("Message bounce detail (by relay)"),
                count=self.detail_bounce)

        if self.detail_reject != 0:
            self.print_nested_hash(
                data=self.results.rejects, label=_("Message reject detail"),
                count=self.detail_reject)
            self.print_nested_hash(
                data=self.results.warnings, label=_("Message reject warning detail"),
                count=self.detail_reject)
            self.print_nested_hash(
                data=self.results.holds, label=_("Message hold detail"),
                count=self.detail_reject)
            self.print_nested_hash(
                data=self.results.discards, label=_("Message discard detail"),
                count=self.detail_reject)

        if self.detail_smtp != 0:
            self.print_nested_hash(
                data=self.results.smtp_messages, label=_("SMTP delivery failures"),
                count=self.detail_smtp)

        if self.detail_smtpd_warning != 0:
            self.print_nested_hash(
                data=self.results.warnings, label=_("Warnings"), count=self.detail_smtpd_warning)

        self.print_nested_hash(data=self.results.fatals, label=_("Fatal Errors"), count=0)
        self.print_nested_hash(data=self.results.panics, label=_("Panics"), count=0)
        self.print_hash_by_cnt_vals(
            data=self.results.master_msgs, title=_('Master daemon messages'), count=0)

    # -------------------------------------------------------------------------
    def print_per_day_summary(self):
        """Print "per-day" traffic summary."""
        self.print_subsect_title(_("Per-Day Traffic Summary"))
        indent = '  '

        labels = {
            'date': _('Date'),
            'received': _('Received'),
            'sent': _('Delivered'),
            'deferred': _('Deferred'),
            'bounced': _('Bounced'),
            'rejected': _('Rejected'),
        }
        widths = {
            'date': 12,
            'received': 11,
            'sent': 11,
            'deferred': 11,
            'bounced': 11,
            'rejected': 11,
        }

        for field in labels.keys():
            label = labels[field]
            if len(label) > widths[field]:
                widths[field] = len(label)

        tpl = '{{date:<{w}}}'.format(w=widths['date'])
        tpl += '  {{received:>{w}}}'.format(w=widths['received'])
        tpl += '  {{sent:>{w}}}'.format(w=widths['sent'])
        tpl += '  {{deferred:>{w}}}'.format(w=widths['deferred'])
        tpl += '  {{bounced:>{w}}}'.format(w=widths['bounced'])
        tpl += '  {{rejected:>{w}}}'.format(w=widths['rejected'])

        header = tpl.format(**labels)
        print(indent + header)
        print(indent + ('-' * len(header)))

        for day in self.results.messages_per_day.keys():

            stats = {}
            if self.args.iso_date:
                stats['date'] = day.isoformat()
            else:
                stats['date'] = day.strftime('%b %d %Y')
            stats['received'] = adj_int_units_localized(
                self.results.messages_per_day[day].received, no_unit=True).rstrip()
            stats['sent'] = adj_int_units_localized(
                self.results.messages_per_day[day].sent, no_unit=True).rstrip()
            stats['deferred'] = adj_int_units_localized(
                self.results.messages_per_day[day].deferred, no_unit=True).rstrip()
            stats['bounced'] = adj_int_units_localized(
                self.results.messages_per_day[day].bounced, no_unit=True).rstrip()
            stats['rejected'] = adj_int_units_localized(
                self.results.messages_per_day[day].rejected, no_unit=True).rstrip()
            line = tpl.format(**stats)
            print(indent + line)

    # -------------------------------------------------------------------------
    def print_per_hour_summary(self):
        """Print "per-hour" traffic summary."""
        indent = '  '

        if self.nr_days == 1:
            title = _('Per-Hour Traffic Summary')
        else:
            title = _('Per-Hour Traffic Daily Average')
        self.print_subsect_title(title)

        labels = {
            'hour': _('Hour'),
            'received': _('Received'),
            'sent': _('Delivered'),
            'deferred': _('Deferred'),
            'bounced': _('Bounced'),
            'rejected': _('Rejected'),
        }

        widths = {
            'hour': 13,
            'received': 11,
            'sent': 11,
            'deferred': 11,
            'bounced': 11,
            'rejected': 11,
        }

        for field in labels.keys():
            label = labels[field]
            if len(label) > widths[field]:
                widths[field] = len(label)

        tpl = '{{hour:<{w}}}'.format(w=widths['hour'])
        tpl += '  {{received:>{w}}}'.format(w=widths['received'])
        tpl += '  {{sent:>{w}}}'.format(w=widths['sent'])
        tpl += '  {{deferred:>{w}}}'.format(w=widths['deferred'])
        tpl += '  {{bounced:>{w}}}'.format(w=widths['bounced'])
        tpl += '  {{rejected:>{w}}}'.format(w=widths['rejected'])

        header = tpl.format(**labels)
        print(indent + header)
        print(indent + ('-' * len(header)))

        for hour in range(self.hours_per_day):
            next_hour = hour + 1
            if next_hour >= self.hours_per_day:
                next_hour = 0
            if self.args.iso_date:
                hour_show = '{:>02d}:00 - {:>02d}:00'.format(hour, next_hour)
            else:
                hour_show = '{:>02d}00 - {:>02d}00'.format(hour, next_hour)
            values = {
                'hour': hour_show,
                'received': 0,
                'sent': 0,
                'deferred': 0,
                'bounced': 0,
                'rejected': 0,
            }
            if hour < len(self.results.received_messages_per_hour):
                val = self.results.received_messages_per_hour[hour]
                if self.nr_days:
                    val /= self.nr_days
                val = format_string('%0.1f', val, grouping=True)
                values['received'] = val
            if hour < len(self.results.delivered_messages_per_hour):
                val = self.results.delivered_messages_per_hour[hour]
                if self.nr_days:
                    val /= self.nr_days
                val = format_string('%0.1f', val, grouping=True)
                values['sent'] = val
            if hour < len(self.results.deferred_messages_per_hour):
                val = self.results.deferred_messages_per_hour[hour]
                if self.nr_days:
                    val /= self.nr_days
                val = format_string('%0.1f', val, grouping=True)
                values['deferred'] = val
            if hour < len(self.results.bounced_messages_per_hour):
                val = self.results.bounced_messages_per_hour[hour]
                if self.nr_days:
                    val /= self.nr_days
                val = format_string('%0.1f', val, grouping=True)
                values['bounced'] = val
            if hour < len(self.results.rejected_messages_per_hour):
                val = self.results.rejected_messages_per_hour[hour]
                if self.nr_days:
                    val /= self.nr_days
                val = format_string('%0.1f', val, grouping=True)
                values['rejected'] = val

            line = tpl.format(**values)
            print(indent + line)

    # -------------------------------------------------------------------------
    def print_recip_domain_summary(self):
        """Print "per-recipient-domain" traffic summary."""
        indent = '  '
        count = self.detail_host
        if count == 0:
            return

        title = _('Host/Domain Summary: Message Delivery')
        nr_items = len(self.results.rcpt_domain.keys())
        if not self.print_subsect_title(title, nr_items=nr_items, count=count):
            return

        labels = {
            'sent': _('Sent count'),
            'bytes': _('Bytes'),
            'defers': _('Defers'),
            'avg_delay': _('Avg. delay'),
            'max_delay': _('Max. delay'),
            'domain': _('Host/Domain'),
        }
        widths = {
            'sent': 8,
            'bytes': 8,
            'defers': 8,
            'avg_delay': 8,
            'max_delay': 8,
            'domain': 20,
        }

        for field in labels.keys():
            label = labels[field]
            if len(label) > widths[field]:
                widths[field] = len(label)

        tpl = '{{sent:>{w}}}'.format(w=widths['sent'])
        tpl += '  {{bytes:>{w}}}'.format(w=widths['bytes'])
        tpl += '  {{defers:>{w}}}'.format(w=widths['defers'])
        tpl += '  {{avg_delay:>{w}}}'.format(w=widths['avg_delay'])
        tpl += '  {{max_delay:>{w}}}'.format(w=widths['max_delay'])
        tpl += '  {{domain:<{w}}}'.format(w=widths['domain'])

        header = tpl.format(**labels)
        print(indent + header)
        print(indent + ('-' * len(header)))

        i = 0
        for domain in self.sorted_keys_of_msg_stats(self.results.rcpt_domain):
            nr_sent = self.results.rcpt_domain[domain].count
            size = self.results.rcpt_domain[domain].size
            defers = self.results.rcpt_domain[domain].defers
            avg_delay = 0
            if nr_sent:
                avg_delay = self.results.rcpt_domain[domain].delay_avg / nr_sent
            delay_max = self.results.rcpt_domain[domain].delay_max
            values = {}
            values['sent'] = adj_int_units_localized(nr_sent)
            values['bytes'] = adj_int_units_localized(size)
            values['defers'] = adj_int_units_localized(defers)
            values['avg_delay'] = adj_time_units(avg_delay)
            values['max_delay'] = adj_time_units(delay_max)
            values['domain'] = domain

            line = tpl.format(**values)
            print(indent + line)

            i += 1
            if count is not None and i >= count:
                break

    # -------------------------------------------------------------------------
    def print_sending_domain_summary(self):
        """Print "per-sender-domain" traffic summary."""
        indent = '  '
        count = self.detail_host
        if count == 0:
            return

        title = _('Host/Domain Summary: Messages Received')
        nr_items = len(self.results.sending_domain_data.keys())
        if not self.print_subsect_title(title, nr_items=nr_items, count=count):
            return

        labels = {
            'received': _('Message count'),
            'bytes': _('Bytes'),
            'domain': _('Host/Domain'),
        }
        widths = {
            'received': 8,
            'bytes': 8,
            'domain': 20,
        }

        for field in labels.keys():
            label = labels[field]
            if len(label) > widths[field]:
                widths[field] = len(label)

        tpl = '{{received:>{w}}}'.format(w=widths['received'])
        tpl += '  {{bytes:>{w}}}'.format(w=widths['bytes'])
        tpl += '  {{domain:<{w}}}'.format(w=widths['domain'])

        header = tpl.format(**labels)
        print(indent + header)
        print(indent + ('-' * len(header)))

        i = 0
        for domain in self.sorted_keys_of_msg_stats(self.results.sending_domain_data):
            nr = self.results.sending_domain_data[domain].count
            size = self.results.sending_domain_data[domain].size
            values = {}
            values['received'] = adj_int_units_localized(nr)
            values['bytes'] = adj_int_units_localized(size)
            values['domain'] = domain

            line = tpl.format(**values)
            print(indent + line)

            i += 1
            if count is not None and i >= count:
                break

    # -------------------------------------------------------------------------
    def print_per_day_smtpd(self):
        """print "per-day" smtpd connection summary"""
        title = _('Per-Day SMTPD Connection Summary')
        indent = '  '

        nr_items = len(self.results.smtpd_per_day.keys())
        if not self.print_subsect_title(title, nr_items=nr_items):
            return

        labels = {
            'date': _('Date'),
            'connections': _('Connections'),
            'time_conn': _('Time connections total'),
            'avg_time': _('Avg. time connection'),
            'max_time': _('Max. time connection'),
        }
        widths = {
            'date': 12,
            'connections': 11,
            'time_conn': 11,
            'avg_time': 11,
            'max_time': 11,
        }

        for field in labels.keys():
            label = labels[field]
            if len(label) > widths[field]:
                widths[field] = len(label)

        tpl = '{{date:<{w}}}'.format(w=widths['date'])
        tpl += '  {{connections:>{w}}}'.format(w=widths['connections'])
        tpl += '  {{time_conn:>{w}}}'.format(w=widths['time_conn'])
        tpl += '  {{avg_time:>{w}}}'.format(w=widths['avg_time'])
        tpl += '  {{max_time:>{w}}}'.format(w=widths['max_time'])

        header = tpl.format(**labels)
        print(indent + header)
        print(indent + ('-' * len(header)))

        for day in self.results.smtpd_per_day.keys():

            stats = self.results.smtpd_per_day[day]
            total_time_splitted = get_smh(stats.connect_time_total)
            total_time = '{h:d}:{m:02d}:{s:02.0f}'.format(
                h=total_time_splitted[2], m=total_time_splitted[1], s=total_time_splitted[0])
            avg = 0.0
            if stats.connections:
                avg = stats.connect_time_total / stats.connections

            values = {}
            if self.args.iso_date:
                values['date'] = day.isoformat()
            else:
                values['date'] = day.strftime('%b %d %Y')
            values['connections'] = adj_int_units_localized(stats.connections)
            values['time_conn'] = total_time
            values['avg_time'] = format_string('%0.1f', avg, grouping=True)
            values['max_time'] = '{:0.0f}'.format(stats.connect_time_max)
            if self.verbose > 4:
                LOG.debug("Daily SMTP stat:\n" + pp(values))

            line = tpl.format(**values)
            print(indent + line)

    # -------------------------------------------------------------------------
    def print_per_hour_smtpd(self):
        """print 'per-hour' smtpd connection summary"""
        indent = '  '
        if self.nr_days == 1:
            title = _('Per-Hour SMTPD Connection Summary')
        else:
            title = _('Per-Hour SMTPD Connection Daily Average')

        conns_total = 0
        for stat in self.results.smtpd_messages_per_hour:
            conns_total += stat.count

        if not self.print_subsect_title(title, nr_items=conns_total):
            return

        labels = {
            'hour': _('Hour'),
            'conn': _('Connections'),
            'time_total': _('Time total'),
            'time_avg': _('Time avg.'),
            'time_max': _('Time max.'),
        }

        widths = {
            'hour': 13,
            'conn': 11,
            'time_total': 11,
            'time_avg': 11,
            'time_max': 11,
        }

        for field in labels.keys():
            label = labels[field]
            if len(label) > widths[field]:
                widths[field] = len(label)

        tpl = '{{hour:<{w}}}'.format(w=widths['hour'])
        tpl += '  {{conn:>{w}}}'.format(w=widths['conn'])
        tpl += '  {{time_total:>{w}}}'.format(w=widths['time_total'])
        if self.nr_days < 2:
            tpl += '  {{time_avg:>{w}}}'.format(w=widths['time_avg'])
            tpl += '  {{time_max:>{w}}}'.format(w=widths['time_max'])

        header = tpl.format(**labels)
        print(indent + header)
        print(indent + ('-' * len(header)))

        hour = -1
        for stat in self.results.smtpd_messages_per_hour:

            # stat = self.results.smtpd_messages_per_hour[hour]
            hour += 1
            if not stat.count:
                continue

            next_hour = hour + 1
            if next_hour >= self.hours_per_day:
                next_hour = 0
            if self.args.iso_date:
                hour_show = '{:>02d}:00 - {:>02d}:00'.format(hour, next_hour)
            else:
                hour_show = '{:>02d}00 - {:>02d}00'.format(hour, next_hour)
            values = {
                'hour': hour_show,
                'conn': 0,
                'time_total': 0,
                'time_avg': 0,
                'time_max': 0,
            }

            connections = stat.count
            time_total = stat.time_total

            if self.nr_days > 1:
                connections /= self.nr_days
                time_total /= self.nr_days

            total_time_splitted = get_smh(time_total)
            avg = stat.time_total / stat.count

            values['conn'] = adj_int_units_localized(connections)
            values['time_total'] = '{h:d}:{m:02d}:{s:02.0f}'.format(
                h=total_time_splitted[2], m=total_time_splitted[1], s=total_time_splitted[0])
            values['time_avg'] = format_string('%0.1f', avg, grouping=True)
            values['time_max'] = '{:0.0f}'.format(stat.time_max)

            line = tpl.format(**values)
            print(indent + line)

    # -------------------------------------------------------------------------
    def print_domain_smtpd_summary(self):
        """print 'per-domain-smtpd' connection summary"""
        indent = '  '
        count = self.detail_host
        if count == 0:
            return

        title = _('Host/Domain Summary: SMTPD Connections')
        nr_items = len(self.results.smtpd_per_domain.keys())
        if not self.print_subsect_title(title, nr_items=nr_items, count=count):
            return

        labels = {
            'conn': _('Connections'),
            'time_total': _('Time total'),
            'time_avg': _('Time avg.'),
            'time_max': _('Time max.'),
            'domain': _('Host/Domain'),
        }

        widths = {
            'conn': 11,
            'time_total': 11,
            'time_avg': 11,
            'time_max': 11,
            'domain': 20,
        }

        for field in labels.keys():
            label = labels[field]
            if len(label) > widths[field]:
                widths[field] = len(label)

        tpl = '{{conn:>{w}}}'.format(w=widths['conn'])
        tpl += '  {{time_total:>{w}}}'.format(w=widths['time_total'])
        tpl += '  {{time_avg:>{w}}}'.format(w=widths['time_avg'])
        tpl += '  {{time_max:>{w}}}'.format(w=widths['time_max'])
        tpl += '  {{domain:<{w}}}'.format(w=widths['domain'])

        header = tpl.format(**labels)
        print(indent + header)
        print(indent + ('-' * len(header)))

        i = 0
        for domain in self.sorted_keys_of_smtpd_stats(self.results.smtpd_per_domain):

            nr = self.results.smtpd_per_domain[domain].connections
            time_total = self.results.smtpd_per_domain[domain].connect_time_total
            max_time = self.results.smtpd_per_domain[domain].connect_time_max

            total_time_splitted = get_smh(time_total)
            avg = time_total / nr

            if domain is None:
                domain = _('<None>')

            values = {
                'conn': 0,
                'time_total': 0,
                'time_avg': 0,
                'time_max': 0,
                'domain': domain,
            }

            values['conn'] = adj_int_units_localized(nr)
            values['time_total'] = '{h:d}:{m:02d}:{s:02.0f}'.format(
                h=total_time_splitted[2], m=total_time_splitted[1], s=total_time_splitted[0])
            values['time_avg'] = format_string('%0.1f', avg, grouping=True)
            values['time_max'] = '{:0.0f}'.format(max_time)

            line = tpl.format(**values)
            print(indent + line)

            i += 1
            if count is not None and i >= count:
                break

    # -------------------------------------------------------------------------
    def print_user_data(self, data, title, attribute):
        """print 'per-user' data sorted in descending order"""
        if self.detail_user == 0:
            return
        indent = '  '
        count = self.detail_user

        nr_items = len(data.keys())
        if not self.print_subsect_title(title, nr_items=nr_items, count=count):
            return

        tmp_list = []
        for addr in data.keys():
            data_point = data[addr].dict()
            data_point['addr'] = addr
            tmp_list.append(data_point)

        tmp_list.sort(key=itemgetter('addr'))
        tmp_list.sort(key=itemgetter(attribute), reverse=True)

        if self.verbose > 3:
            LOG.debug("Sorted list:\n" + pp(tmp_list))

        i = 0
        tpl = '{val:>9}  {addr}'
        for data_point in tmp_list:
            addr = data_point['addr']
            value = data_point[attribute]

            line = tpl.format(val=adj_int_units_localized(value), addr=addr)
            print(indent + line)

            i += 1
            if count is not None and i >= count:
                break

    # -------------------------------------------------------------------------
    def print_detailed_msg_data(self):
        """Print per-message info in excruciating detail."""
        indent = '  '
        title = "Message detail"

        data = self.results.message_details
        if not self.print_subsect_title(title, nr_items=len(data.keys())):
            return

        max_len = 1
        for key in data.keys():
            if len(key) > max_len:
                max_len = len(key)

        def by_domain_then_user(qid_one, qid_two):
            list_one = data[qid_one]
            list_two = data[qid_two]

            user_one = None
            domain_one = None
            user_two = None
            domain_two = None

            parts = self.re_mailsplit.split(list_one[0])
            user_one = parts[0]
            if len(parts) > 1:
                domain_one = parts[1]

            parts = self.re_mailsplit.split(list_two[0])
            user_two = parts[0]
            if len(parts) > 1:
                domain_two = parts[1]

            if domain_one:
                domain_one = self.re_maildomain.sub(r'\2.\3.\1', domain_one)
            else:
                domain_one = ''

            if domain_two:
                domain_two = self.re_maildomain.sub(r'\2.\3.\1', domain_two)
            else:
                domain_two = ''

            ret = ci_cmp(domain_one, domain_two)
            if ret:
                return ret

            user_one = self.re_bang_path.sub('', user_one)
            user_two = self.re_bang_path.sub('', user_two)

            ret = ci_cmp(user_one, user_two)
            if ret:
                return ret

            return ci_cmp(qid_one, qid_two)

        tpl = indent + '{{qid:<{max}}}  {{val}}'.format(max=(max_len + 1))
        for qid in sorted(data.keys(), key=cmp_to_key(by_domain_then_user)):
            first = True
            val_list = data[qid]
            for val in val_list:
                if first:
                    line = tpl.format(qid=(qid + ':'), val=val)
                else:
                    line = tpl.format(qid='', val=val)
                print(line)
                first = False


# =============================================================================

if __name__ == "__main__":

    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
