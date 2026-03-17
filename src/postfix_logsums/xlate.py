#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@summary: The module for i18n.

It provides translation object, usable from all other modules in this package.

@author: Frank Brehm
@contact: frank.brehm@pixelpark.com
@copyright: © 2023 - 2026 by Frank Brehm, Berlin
"""
from __future__ import absolute_import, print_function

# Standard modules
import copy
import gettext
import logging
import sys
from pathlib import Path

# Third party modules
import babel
import babel.lists
from babel.support import Translations

try:
    from semver import Version
except ImportError:
    from semver import VersionInfo as Version

DOMAIN = 'postfix_logsums'

LOG = logging.getLogger(__name__)

__version__ = '1.0.0'

__me__ = Path(__file__).resolve()
__module_dir__ = __me__.parent
__lib_dir__ = __module_dir__.parent
__base_dir__ = __lib_dir__.parent

LOCALE_DIR = __base_dir__ / 'locale'

if LOCALE_DIR.is_dir():
    # Not installed, in development workdir
    LOCALE_DIR = str(LOCALE_DIR)
else:
    # Somehow installed
    LOCALE_DIR = __module_dir__ / 'locale'
    if sys.prefix == sys.base_prefix:
        # installed as a package
        LOCALE_DIR = sys.prefix + "/share/locale"

    else:
        # Obviously in a virtual environment
        __base_dir__ = Path(sys.prefix)
        LOCALE_DIR = __base_dir__ / "share" / "locale"

        if LOCALE_DIR.is_dir():
            LOCALE_DIR = str(LOCALE_DIR.resolve())
        else:
            LOCALE_DIR = __module_dir__ / "locale"
            if LOCALE_DIR.is_dir():
                LOCALE_DIR = str(LOCALE_DIR)
            else:
                LOCALE_DIR = str(__base_dir__ / sys.prefix / "share" / "locale")

DEFAULT_LOCALE_DEF = 'en_US'
DEFAULT_LOCALE = babel.core.default_locale()
if not DEFAULT_LOCALE:
    DEFAULT_LOCALE = DEFAULT_LOCALE_DEF

__mo_file__ = gettext.find(DOMAIN, LOCALE_DIR)
if __mo_file__:
    try:
        with open(__mo_file__, 'rb') as F:
            XLATOR = Translations(F, DOMAIN)
    except IOError:
        XLATOR = gettext.NullTranslations()
else:
    XLATOR = gettext.NullTranslations()

CUR_BABEL_VERSION = Version.parse(babel.__version__)
NEWER_BABEL_VERSION = Version.parse('2.6.0')

SUPPORTED_LANGS = (
    'de',
    'en'
)

_ = XLATOR.gettext


# =============================================================================
def format_list(lst, do_repr=False, style='standard', locale=DEFAULT_LOCALE):
    """
    Format the items in `lst` as a list.

    :param lst: a sequence of items to format in to a list
    :param locale: the locale
    """
    if not lst:
        return ''

    my_list = copy.copy(lst)
    if do_repr:
        my_list = []
        for item in lst:
            my_list.append('{!r}'.format(item))

    if CUR_BABEL_VERSION < NEWER_BABEL_VERSION:
        return babel.lists.format_list(my_list, locale=locale)
    return babel.lists.format_list(my_list, style=style, locale=locale)


# =============================================================================

if __name__ == "__main__":

    out_list = []
    out_list.append([_("Module directory:"), str(__module_dir__)])
    out_list.append([_("Lib directory:"), str(__lib_dir__)])
    out_list.append([_("Base directory:"), str(__base_dir__)])
    out_list.append([_("Locale directory:"), LOCALE_DIR])
    out_list.append([_("Locale domain:"), DOMAIN])
    out_list.append([_("Found .mo-file:"), __mo_file__])

    max_len = 1
    for pair in out_list:
        if len(pair[0]) > max_len:
            max_len = len(pair[0])

    template = "{{label:<{}}} {{val!r}}".format(max_len)
    for pair in out_list:
        print(template.format(label=pair[0], val=pair[1]))

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
