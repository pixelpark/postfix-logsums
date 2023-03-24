#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@summary: Produce Postfix MTA logfile summary

@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 by Frank Brehm, Berlin
@license: LGPL3+
"""

from __future__ import print_function

import os
import sys
import re
import pprint

from pathlib import Path

# Third party modules
from setuptools import setup

# own modules:
__module_name__ = 'postfix_logsums'
__setup_script__ = Path(__file__).resolve()
__base_dir__ = __setup_script__.parent
__module_dir__ = __base_dir__ / __module_name__
__init_py__ = __module_dir__ / '__init__.py'

PATHS = {
    '__setup_script__': str(__setup_script__),
    '__base_dir__': str(__base_dir__),
    '__module_dir__': str(__module_dir__),
    '__init_py__': str(__init_py__),
}

def pp(obj):
    """Human friendly output of data structures."""
    pprinter = pprint.PrettyPrinter(indent=4)
    return pprinter.pformat(obj)

# print("Paths:\n{}".format(pp(PATHS)))


if os.path.exists(__module_dir__) and os.path.isfile(__init_py__):
    sys.path.insert(0, os.path.abspath(__base_dir__))

import postfix_logsums

ENCODING = "utf-8"

__packet_version__ = postfix_logsums.__version__

__packet_name__ = __module_name__
__debian_pkg_name__ = __module_name__.replace('_', '-')

__author__ = 'Frank Brehm'
__contact__ = 'frank@brehm-online.com'
__copyright__ = '(C) 2023 Frank Brehm, Berlin'
__license__ = 'LGPL3+'
__url__ = 'https://github.com/pixelpark/postfix-logsums'
__description__ = 'Produce Postfix MTA logfile summary.'


__open_args__ = {}
if sys.version_info[0] < 3:
    __open_args__ = {'encoding': ENCODING, 'errors': 'surrogateescape'}

# -----------------------------------
def read(fname):
    """Read in a file and return content."""
    content = None
    fn = str(fname)

    if sys.version_info[0] < 3:
        with open(fn, 'r') as fh:
            content = fh.read()
    else:
        with open(fn, 'r', **__open_args__) as fh:
            content = fh.read()

    return content


# -----------------------------------
def is_python_file(filename):
    """Evaluate, whether a file is a Pyton file."""
    fn = str(filename)
    if fn.endswith('.py'):
        return True
    else:
        return False


# -----------------------------------
__debian_dir__ = __base_dir__ / 'debian'
__changelog_file__ = __debian_dir__ / 'changelog'
__readme_file__ = __base_dir__ / 'README.md'

# -----------------------------------
__requirements__ = []


# -----------------------------------
def get_debian_version():
    """Evaluate current package version from Debian changelog."""
    if not __changelog_file__.is_file():
        return None
    changelog = read(__changelog_file__)
    first_row = changelog.splitlines()[0].strip()
    if not first_row:
        return None
    pattern = r'^' + re.escape(__debian_pkg_name__) + r'\s+\(([^\)]+)\)'
    match = re.search(pattern, first_row)
    if not match:
        return None
    return match.group(1).strip()


__debian_version__ = get_debian_version()

if __debian_version__ is not None and __debian_version__ != '':
    __packet_version__ = __debian_version__


# -----------------------------------
def read_requirements():
    """Read in and evaluate file requirements.txt."""
    req_file = __base_dir__ / 'requirements.txt'
    if not req_file.is_file():
        return

    f_content = read(req_file)
    if not f_content:
        return

    re_comment = re.compile(r'\s*#.*')
    re_module = re.compile(r'([a-z][a-z0-9_]*[a-z0-9])', re.IGNORECASE)

    for line in f_content.splitlines():
        line = line.strip()
        line = re_comment.sub('', line)
        if not line:
            continue
        match = re_module.search(line)
        if not match:
            continue
        module = match.group(1)
        if module not in __requirements__:
            __requirements__.append(module)

    # print("Found required modules: {}\n".format(pp(__requirements__)))


read_requirements()

# -----------------------------------
__scripts__ = ['postfix-logsums']


# -----------------------------------
setup(
    version=__packet_version__,
    long_description=read(__readme_file__),
    scripts=__scripts__,
    requires=__requirements__,
)


# =============================================================================
# vim: fileencoding=utf-8 filetype=python ts=4 et list
