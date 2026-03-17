#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@summary: The module for i18n.

It provides translation object, usable from all other modules in this package.

@author: Frank Brehm
@contact: frank.brehm@pixelpark.com
@copyright: © 2023 by Frank Brehm, Berlin
"""
from __future__ import absolute_import, print_function

# Standard modules
import logging
import gettext
import copy
import sys

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

# Third party modules
import babel
import babel.lists
from babel.support import Translations

try:
    from packaging.version import Version
except ImportError:
    from distutils.version import LooseVersion as Version

DOMAIN = 'postfix_logsums'

LOG = logging.getLogger(__name__)

__version__ = '0.1.0'

__me__ = Path(__file__).resolve()
__module_dir__ = __me__.parent
__base_dir__ = __module_dir__.parent
LOCALE_DIR = __base_dir__.joinpath('locale')
if LOCALE_DIR.is_dir():
    LOCALE_DIR = str(LOCALE_DIR)
else:
    LOCALE_DIR = __module_dir__.joinpath('locale')
    if LOCALE_DIR.is_dir():
        LOCALE_DIR = str(LOCALE_DIR)
    else:
        LOCALE_DIR = sys.prefix + '/share/locale'

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

CUR_BABEL_VERSION = Version(babel.__version__)
NEWER_BABEL_VERSION = Version('2.6.0')

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

    print(_("Module directory: {!r}").format(str(__module_dir__)))
    print(_("Base directory: {!r}").format(str(__base_dir__)))
    print(_("Locale directory: {!r}").format(str(LOCALE_DIR)))
    print(_("Locale domain: {!r}").format(DOMAIN))
    print(_("Found .mo-file: {!r}").format(__mo_file__))

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
