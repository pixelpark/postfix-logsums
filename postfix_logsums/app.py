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

# from argparse import RawDescriptionHelpFormatter
from argparse import RawTextHelpFormatter

from pathlib import Path

from functools import cmp_to_key

from locale import strcoll

LOG = logging.getLogger(__name__)

from . import __version__ as GLOBAL_VERSION
from . import pp, to_bytes, MAX_TERMINAL_WIDTH
from . import DEFAULT_TERMINAL_WIDTH, DEFAULT_TERMINAL_HEIGHT
from . import get_generic_appname, get_smh
from . import PostfixLogParser

__version__ = '0.6.6'


# =============================================================================
class NonNegativeItegerOptionAction(argparse.Action):

    # -------------------------------------------------------------------------
    def __call__(self, parser, namespace, value, option_string=None):

        try:
            val = int(value)
        except Exception as e:
            Gmsg = "Got a {c} for converting {v!r} into an integer value: {e}".format(
                c=e.__class__.__name__, v=value, e=e)
            raise argparse.ArgumentError(self, msg)

        if val < 0:
            msg = "The option must not be negative (given: {}).".format(value)
            raise argparse.ArgumentError(self, msg)

        setattr(namespace, self.dest, val)


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
                msg = "Logfile {!r} does not exists.".format(logfile)
                raise argparse.ArgumentError(self, msg)

            if not path.is_file():
                msg = "File {!r} is not a regular file.".format(logfile)
                raise argparse.ArgumentError(self, msg)

            if not os.access(str(path), os.R_OK):
                msg = "File {!r} is not readable.".format(logfile)
                raise argparse.ArgumentError(self, msg)

            logfiles.append(path.resolve())

        setattr(namespace, self.dest, logfiles)


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
    def wrap_msg(cls, message, width=None):
        """Wrap the given message to the max terminal witdt.."""
        if width is None:
            width = cls.max_width
        return textwrap.fill(message, width)

    # -------------------------------------------------------------------------
    def __init__(self):

        self._appname = get_generic_appname()
        self._version = __version__
        self._verbose = 0
        self._quiet = False
        self._initialized = False
        self.parser = None

        self.init_arg_parser()
        self.perform_arg_parser()
        self.init_logging()

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
            LOG.warning("Wrong verbose level {!r}, must be >= 0".format(value))

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
        desc.append('{} is a log analyzer/summarizer for the Postfix MTA.'.format(appname))
        desc.append(
            'It is designed to provide an over-view of Postfix activity, with just enough '
            'detail to give the administrator a "heads up" for potential trouble spots.')
        desc.append((
            '{} generates summaries and, in some cases, detailed reports of mail server traffic '
            'volumes, rejected and bounced email, and server warnings, '
            'errors and panics.').format(appname))

        description = ''
        for des in desc:
            des = self.wrap_msg(des)
            if description:
                description += '\n\n'
            description += des

        day_values = ('today', 'yesterday')

        self.arg_parser = argparse.ArgumentParser(
            prog=self.appname,
            description=description,
            formatter_class=RawTextHelpFormatter,
            add_help=False,
        )

        logfile_group = self.arg_parser.add_argument_group('Options for scanning Postfix logfiles')

        # --day
        desc = 'Generate report for just today or yesterday.'
        desc = self.wrap_msg(desc, arg_width)
        logfile_group.add_argument(
            '-d', '--day', metavar='|'.join(day_values), dest='day', choices=day_values,
            help=desc)

        # --extended
        desc = 'Extended (extreme? excessive?) detail.\n'
        desc += self.wrap_msg(
            'At present, this includes only a per-message report, sorted by sender domain, '
            'then user-in-domain, then by queue i.d.', arg_width) + '\n'
        desc += self.wrap_msg(
            'WARNING: the data built to generate this report can quickly consume very large '
            'amounts of memory if a ot of log entries are processed!', arg_width)
        logfile_group.add_argument(
            '-e', '--extended', dest='extended', action="store_true", help=desc)

        # --ignore-case
        desc = self.wrap_msg(
            'Handle complete email address in a case-insensitive manner.', arg_width)
        desc += '\n'
        desc += self.wrap_msg(
            'Normally {} lower-cases only the host and domain parts, leaving the user part alone. '
            'This option causes the entire email address to be lower-cased.'.format(appname),
            arg_width)
        logfile_group.add_argument(
            '-i', '--ignore-case', dest='ignore_case', action="store_true", help=desc)

        # --no-no-msg-size
        desc = self.wrap_msg('Do not emit report on "Messages with no size data".', arg_width)
        desc += '\n'
        desc += self.wrap_msg((
            'Message size is reported only by the queue manager. The message may be delivered '
            'long-enough after the (last) qmgr log entry that the information is not in '
            'the log(s) processed by a particular run of {a}. This throws off "Recipients by '
            'message size" and the total for "bytes delivered." These are normally reported by '
            '{a} as "Messages with nosize data.').format(a=appname), arg_width)
        logfile_group.add_argument(
            '--no-no-msg-size', dest='nono_msgsize', action="store_true", help=desc)

        # --rej-add-from
        desc = self.wrap_msg(
            'For those reject reports that list IP addresses or host/domain names: append the '
            'email from address to each listing. (Does not apply to "Improper use of '
            'SMTP command pipelining" report.)', arg_width)
        logfile_group.add_argument(
            '--rej-add-from', dest='rej_add_from', action="store_true", help=desc)

        # --smtpd-stats
        desc = self.wrap_msg('Generate smtpd connection statistics.', arg_width) + '\n'
        desc += self.wrap_msg(
            'The "per-day" report is not generated for single-day reports. For multiple-day '
            'reports: "per-hour" numbers are daily averages (reflected in the report '
            'heading).', arg_width)
        logfile_group.add_argument(
            '--smtpd-stats', dest='smtpd_stats', action="store_true", help=desc)

        # --verp-mung
        desc = self.wrap_msg(
            'Do "VERP" generated address (?) munging. Convert sender addresses of the form '
            '"list-return-NN-someuser=some.dom@host.sender.dom" to'
            '"list-return-ID-someuser=some.dom@host.sender.dom".', arg_width) + '\n'
        desc += self.wrap_msg(
            'In other words: replace the numeric value with "ID".', arg_width) + '\n'
        desc += self.wrap_msg(
            'By specifying the optional "=2" (second form), the munging is more "aggressive", '
            'converting the address to something like: "list-return@host.sender.dom".',
            arg_width) + '\n'
        desc += self.wrap_msg(
            'Actually: specifying anything less than 2 does the "simple" munging and anything '
            'greater than 1 results in the more "aggressive" hack being applied.', arg_width)
        logfile_group.add_argument(
            '--verp-mung', type=int, metavar='1|2', const=0, dest='verp_mung', nargs='?',
            action=NonNegativeItegerOptionAction, help=desc)

        #######
        # Select compression
        compression_section = self.arg_parser.add_argument_group('Logfile compression options')

        compression_group = compression_section.add_mutually_exclusive_group()

        # --gzip
        desc = self.wrap_msg(
            'Assume, that stdin stream or the given files are bgzip compressed.', arg_width) + '\n'
        desc += self.wrap_msg(
            'If not given, filenames with the extension ".gz" are assumed to be compressed with '
            'the gzip compression.', arg_width)
        compression_group.add_argument(
            '-z', '--gzip', dest='gzip', action="store_true", help=desc)

        # --bzip2
        desc = self.wrap_msg(
            'Assume, that stdin stream or the given files are bzip2 compressed.', arg_width) + '\n'
        desc += self.wrap_msg(
            'If not given, filenames with the extensions ".bz2" or ".bzip2" are assumed to be '
            'compressed with the bzip2 compression.', arg_width)
        compression_group.add_argument(
            '-j', '--bzip2', dest='bzip2', action="store_true", help=desc)

        # --xz
        desc = self.wrap_msg(
            'Assume, that stdin stream or the given files are xz or lzma compressed.',
            arg_width) + '\n'
        desc += self.wrap_msg(
            'If not given, filenames with the extensions ".xz" or ".lzma" are assumed to be '
            'compressed with the xz or lzma compression.', arg_width)
        compression_group.add_argument(
            '-J', '--xz', '--lzma', dest='xz', action="store_true", help=desc)

        # last parse option
        desc = 'The logfile(s) to analyze. If no file(s) specified, reads from stdin.'
        desc = self.wrap_msg(desc, arg_width)
        logfile_group.add_argument(
            'logfiles', metavar='FILE', nargs='*', action=LogFilesOptionAction, help=desc)

        #######
        # Output
        output_options = self.arg_parser.add_argument_group('Output options')

        # --detail
        desc = self.wrap_msg(
            'Sets all --*-detail, -h and -u to COUNT. Is over-ridden by '
            'individual settings.', arg_width) + '\n'
        desc += self.wrap_msg('--detail 0 suppresses *all* detail.', arg_width)
        output_options.add_argument(
            '-D', '--detail', type=int, metavar='COUNT', dest='detail',
            action=NonNegativeItegerOptionAction, help=desc)

        # --bounce-detail
        desc = self.wrap_msg(
            'Limit detailed bounce reports to the top COUNT.', arg_width) + '\n'
        desc += self.wrap_msg('0 to suppress entirely.', arg_width)
        output_options.add_argument(
            '--bounce-detail', type=int, metavar='COUNT', dest='detail_bounce',
            action=NonNegativeItegerOptionAction, help=desc)

        # --deferral-detail
        desc = self.wrap_msg(
            'Limit detailed deferral reports to the top COUNT.', arg_width) + '\n'
        desc += self.wrap_msg('0 to suppress entirely.', arg_width)
        output_options.add_argument(
            '--deferral-detail', type=int, metavar='COUNT', dest='detail_deferral',
            action=NonNegativeItegerOptionAction, help=desc)

        # --reject-detail
        desc = self.wrap_msg(
            'Limit detailed smtpd reject, warn, hold and discard reports to the top '
            'COUNT.', arg_width) + '\n'
        desc += self.wrap_msg('0 to suppress entirely.', arg_width)
        output_options.add_argument(
            '--reject-detail', type=int, metavar='COUNT', dest='detail_reject',
            action=NonNegativeItegerOptionAction, help=desc)

        # --smtp-detail
        desc = self.wrap_msg(
            'Limit detailed smtp delivery reports to the top COUNT.', arg_width) + '\n'
        desc += self.wrap_msg('0 to suppress entirely.', arg_width)
        output_options.add_argument(
            '--smtp-detail', type=int, metavar='COUNT', dest='detail_smtp',
            action=NonNegativeItegerOptionAction, help=desc)

        # --smtpd-warning-detail
        desc = self.wrap_msg(
            'Limit detailed smtpd warnings reports to the top COUNT.', arg_width) + '\n'
        desc += self.wrap_msg('0 to suppress entirely.', arg_width)
        output_options.add_argument(
            '--smtpd-warning-detail', type=int, metavar='COUNT', dest='detail_smtpd_warning',
            action=NonNegativeItegerOptionAction, help=desc)

        # --host
        desc = self.wrap_msg('Top COUNT to display in host/domain reports.', arg_width)
        desc += '\n0 = none.\n'
        desc += self.wrap_msg(
            'See also: "-u" and "--*-detail" options for further report-limiting options.',
            arg_width)
        output_options.add_argument(
            '-h', '--host', type=int, metavar='COUNT', dest='detail_host',
            action=NonNegativeItegerOptionAction, help=desc)

        # --user
        desc = self.wrap_msg('Top COUNT to display in user reports.', arg_width) + '\n'
        desc += '0 = none.'
        output_options.add_argument(
            '-u', '--user', type=int, metavar='COUNT', dest='detail_user',
            action=NonNegativeItegerOptionAction, help=desc)

        # --problems-first
        desc = self.wrap_msg(
            'Emit "problems" reports (bounces, defers, warnings, etc.) before "normal" stats.',
            arg_width)
        output_options.add_argument(
            '--problems-first', dest='problems_first', action="store_true", help=desc)

        # --iso-date-time
        desc = self.wrap_msg(
            'For summaries that contain date or time information, use ISO 8601 standard formats '
            '(CCYY-MM-DD and HH:MM), rather than "Mon DD CCYY" and "HHMM".', arg_width)
        output_options.add_argument(
            '--iso-date-time', dest='iso_date', action="store_true", help=desc)

        # --verbose-msg-detail
        desc = self.wrap_msg(
            'For the message deferral, bounce and reject summaries: display the full "reason", '
            'rather than a truncated one.', arg_width) + '\n'
        desc += self.wrap_msg(
            'NOTE: this can result in quite long lines in the report.', arg_width)
        output_options.add_argument(
            '--verbose-msg-detail', dest='detail_verbose_msg', action="store_true", help=desc)

        # --zero-fill
        desc = self.wrap_msg(
            '"Zero-fill" certain arrays so reports come out with data in columns that might '
            'otherwise be blank.', arg_width)
        output_options.add_argument(
            '--zero-fill', dest='zero_fill', action="store_true", help=desc)

        #######
        # General stuff
        general_group = self.arg_parser.add_argument_group('General_options')

        verbose_group = general_group.add_mutually_exclusive_group()

        desc = 'Increase the verbosity level.'
        verbose_group.add_argument(
            "-v", "--verbose", action="count", dest='verbose', help=desc)

        # --quiet
        desc = self.wrap_msg("quiet - don't print headings for empty reports.", arg_width)
        desc += '\n'
        desc += self.wrap_msg(
            'NOTE: headings for warning, fatal, and "master"  messages will always be '
            'printed.', arg_width)
        verbose_group.add_argument(
            '-q', '--quiet', dest='quiet', action="store_true", help=desc)

        general_group.add_argument(
            "--help", action='help', dest='help',
            help='Show this help message and exit.'
        )

        general_group.add_argument(
            "--usage", action='store_true', dest='usage',
            help="Display brief usage message and exit."
        )

        v_msg = "Version of %(prog)s: {}".format(GLOBAL_VERSION)
        general_group.add_argument(
            "-V", '--version', action='version', version=v_msg,
            help="Show program's version number and exit."
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
            msg = 'undefined error.'
        title = None

        if isinstance(error_message, Exception):
            title = error_message.__class__.__name__
        else:
            if exception_name is not None:
                title = exception_name.strip()
            else:
                title = 'Exception happened'
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

        LOG.debug("And here wo go ...")

        self.parser.parse(*self.args.logfiles)
        self.results = self.parser.results

        if self.verbose > 1:
            LOG.info('Result of parsing:' + '\n' + pp(self.results.as_dict()))

        print()
        if self.parser.date_str:
            msg = "Postfix log summaries for {}".format(self.parser.date_str)
        else:
            msg = "Postfix log summaries"
        print(msg)
        print('=' * len(msg))

        self.print_grand_totals()

        if self.args.smtpd_stats:
            self.print_smtpd_stats()

        if self.args.problems_first:
            self.print_problems_reports()

        self.print_per_day_summary()

        if not self.args.problems_first:
            self.print_problems_reports()

        print()

    # -------------------------------------------------------------------------
    def print_grand_totals(self):
        """Printing the grand total numbers and data."""
        self.print_subsect_title('Grand Totals')

        if self.results.logdate_oldest or self.results.logdate_latest:
            lbl_oldest = 'Date of oldest log entry:'
            lbl_latest = 'Date of latest log entry:'
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
        print('Messages:')
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

        tpl = ' {value:6.0f}{unit}  {lbl}'
        msgs_rejected_pct = 0
        msgs_discarded_pct = 0
        msgs_total = (
            self.results.msgs_total.delivered + self.results.msgs_total.rejected + \
            self.results.msgs_total.discarded)
        if msgs_total:
            msgs_rejected_pct = self.results.msgs_total.rejected / msgs_total * 100
            msgs_discarded_pct = self.results.msgs_total.discarded / msgs_total * 100

        print(tpl.format(
            lbl='received', **self.adj_int_units(self.results.msgs_total.received)))
        print(tpl.format(
            lbl='delivered', **self.adj_int_units(self.results.msgs_total.delivered)))
        print(tpl.format(
            lbl='forwarded', **self.adj_int_units(self.results.msgs_total.forwarded)))
        print(tpl.format(
            lbl='deferred', **self.adj_int_units(self.results.msgs_total.deferred)),
            end='')
        if self.results.msgs_total.deferrals:
            val = '  ({value:d}{unit} {lbl})'.format(
                lbl='deferrals', **self.adj_int_units(self.results.msgs_total.deferrals))
            print(val, end='')
        print()
        print(tpl.format(
            lbl='bounced', **self.adj_int_units(self.results.msgs_total.bounced)))
        print(tpl.format(
            lbl='rejected', **self.adj_int_units(self.results.msgs_total.rejected)),
            end='')
        print(' ({:0.1n}%)'.format(msgs_rejected_pct))
        print(tpl.format(
            lbl='reject warnings', **self.adj_int_units(self.results.msgs_total.reject_warning)))
        print(tpl.format(
            lbl='held', **self.adj_int_units(self.results.msgs_total.held)))
        print(tpl.format(
            lbl='discarded', **self.adj_int_units(self.results.msgs_total.discarded)),
            end='')
        print(' ({:0.1f}%)'.format(msgs_discarded_pct))
        print()

        print(tpl.format(
            lbl='bytes received', **self.adj_int_units(self.results.msgs_total.bytes_received)))
        print(tpl.format(
            lbl='bytes delivered', **self.adj_int_units(self.results.msgs_total.bytes_delivered)))
        print(tpl.format(
            lbl='senders', **self.adj_int_units(self.results.msgs_total.sending_users)))
        print(tpl.format(
            lbl='sending hosts/domains', **self.adj_int_units(self.results.msgs_total.sending_domains)))
        print(tpl.format(
            lbl='recipients', **self.adj_int_units(self.results.msgs_total.rcpt_users)))
        print(tpl.format(
            lbl='recipient hosts/domains', **self.adj_int_units(self.results.msgs_total.rcpt_domains)))


        print()

    # -------------------------------------------------------------------------
    def print_subsect_title(self, title):
        """Printing the title of a sub section."""
        msg = str(title)
        print()
        print(msg)
        print('-' * len(msg))

    # -------------------------------------------------------------------------
    def adj_int_units(self, value):

        val = value
        unit = ' '
        if not value:
            val = 0
        if value > PostfixLogParser.div_by_one_mb_at:
            val = value / PostfixLogParser.one_mb
            unit = 'M'
        elif value > PostfixLogParser.div_by_one_k_at:
            val = value / PostfixLogParser.one_k
            unit = 'K'

        return {'value': val, 'unit': unit}

    # -------------------------------------------------------------------------
    def print_smtpd_stats(self):

        tpl = ' {value:6.0f}{unit}  {lbl}'
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

        print(tpl.format(
            lbl='connections', **self.adj_int_units(total_conn)))
        print(tpl.format(
            lbl='hosts/domains', value=count_domains, unit=' '))
        print(tpl.format(
            lbl='avg. connect time (seconds)', value=avg_time, unit=' '))
        print(' {h:d}:{m:02d}:{s:02.0f}  {lbl}'.format(
            h=total_time_splitted[2], m=total_time_splitted[1],
            s=total_time_splitted[0], lbl='total connect time'))
        print()

    # -------------------------------------------------------------------------
    def print_nested_hash(self, data, label, count):
        if not len(data.keys()):
            if self.quiet:
                return
            print('\n{lbl}: {n}'.format(lbl=label, n='none'))
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
                        print(' ({lbl}: {c})'.format(lbl='top', c=count), end='')
                    total_count = 0
                    for key2 in data[key].keys():
                        total_count += data[key][key2]
                    print(' ({lbl}: {c})'.format(lbl='total', c=total_count), end='')
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
            print('\n{lbl}: {n}'.format(lbl=title, n='none'))
            return

        print('\n{lbl}'.format(lbl=title))
        print('-' * len(title))

        self.really_print_hash_by_cnt_vals(data, count, ' ')

    # -------------------------------------------------------------------------
    def really_print_hash_by_cnt_vals(self, data, count, indent):
        """*really* print hash contents sorted by numeric values in descending
        order (i.e.: highest first), then by IP/addr, in ascending order."""
        tpl = '{i}{value:6.0f}{unit}  {lbl}'

        i = 0
        for key in self.sorted_keys_by_count_and_key(data):
            print(tpl.format(i=indent, lbl=key, **self.adj_int_units(data[key])))
            if count is not None:
                i += 1
                if i >= count:
                    break

    # -------------------------------------------------------------------------
    def print_problems_reports(self):
        """Print "problems" reports."""
        if self.detail_deferral != 0:
            self.print_nested_hash(
                data=self.results.deferred, label="Message deferral detail",
                count=self.detail_deferral)

        if self.detail_bounce != 0:
            self.print_nested_hash(
                data=self.results.bounced, label="Message bounce detail (by relay)",
                count=self.detail_bounce)

        if self.detail_reject != 0:
            self.print_nested_hash(
                data=self.results.rejects, label="Message reject detail",
                count=self.detail_reject)
            self.print_nested_hash(
                data=self.results.warnings, label="Message reject warning detail",
                count=self.detail_reject)
            self.print_nested_hash(
                data=self.results.holds, label="Message hold detail",
                count=self.detail_reject)
            self.print_nested_hash(
                data=self.results.discards, label="Message discard detail",
                count=self.detail_reject)

        if self.detail_smtp != 0:
            self.print_nested_hash(
                data=self.results.smtp_messages, label="SMTP delivery failures",
                count=self.detail_smtp)

        if self.detail_smtpd_warning != 0:
            self.print_nested_hash(
                data=self.results.warnings, label="Warnings", count=self.detail_smtpd_warning)

        self.print_nested_hash(data=self.results.fatals, label="Fatal Errors", count=0)
        self.print_nested_hash(data=self.results.panics, label="Panics", count=0)
        self.print_hash_by_cnt_vals(
            data=self.results.master_msgs, title='Master daemon messages', count=0)

    # -------------------------------------------------------------------------
    def print_per_day_summary(self):
        """Print "per-day" traffic summary."""
        self.print_subsect_title("Per-Day Traffic Summary")
        indent = '  '

        fields = ('date', 'received', 'sent', 'deferred', 'bounced', 'rejected')
        labels = {
            'date': 'Date',
            'received': 'Received',
            'sent': 'Delivered',
            'deferred': 'Deferred',
            'bounced': 'Bounced',
            'rejected': 'Rejected',
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

        tpl = '{{date:<{w}}}'.format(w=widths['date'])
        tpl += '  {{received:>{w:n}}}'.format(w=widths['received'])
        tpl += '  {{sent:>{w:n}}}'.format(w=widths['sent'])
        tpl += '  {{deferred:>{w:n}}}'.format(w=widths['deferred'])
        tpl += '  {{bounced:>{w:n}}}'.format(w=widths['bounced'])
        tpl += '  {{rejected:>{w:n}}}'.format(w=widths['rejected'])

        for day in sorted(self.results.messages_per_day.keys()):

            stats = self.results.messages_per_day[day].dict()
            stats['date'] = day
            line = tpl.format(**stats)
            print(indent + line)


# =============================================================================

if __name__ == "__main__":

    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
