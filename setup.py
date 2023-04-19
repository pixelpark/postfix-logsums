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
import glob
import subprocess

from pathlib import Path

# Third party modules
from setuptools import setup
from setuptools.command.sdist import sdist

from babel.messages import frontend as babel

# own modules:
__module_name__ = 'postfix_logsums'
__setup_script__ = Path(__file__).resolve()
__base_dir__ = __setup_script__.parent
__module_dir__ = __base_dir__ / __module_name__
__init_py__ = __module_dir__ / '__init__.py'
__share_dir__ = Path(sys.base_prefix) / 'share'
__locale_dir__ = __share_dir__ / 'locale'

PATHS = {
    '__setup_script__': str(__setup_script__),
    '__base_dir__': str(__base_dir__),
    '__module_dir__': str(__module_dir__),
    '__init_py__': str(__init_py__),
    '__share_dir__': __share_dir__,
    '__locale_dir__': __locale_dir__,
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
PO_FILES = 'locale/*/LC_MESSAGES/*.po'
__package_data__ = {}
__data_files__ = []

def create_mo_files():
    """Compile the translation files."""
    mo_files = []
    for po_path in glob.glob(PO_FILES):
        mo = Path(po_path.replace('.po', '.mo'))
        if not mo.exists():
            subprocess.call(['msgfmt', '-o', str(mo), po_path])
        mo_files.append(mo)

    # print("Found mo files: {}\n".format(pp(mo_files)))
    return mo_files


__pkg_mo_paths__ = create_mo_files()
__pkg_mo_files__ = []
for mo_file in __pkg_mo_paths__:
    __pkg_mo_files__.append(str(mo_file))

__package_data__[''] = __pkg_mo_files__
# print("Package_data:\n" + pp(__package_data__) + "\n")


for mo_file in __pkg_mo_paths__:
    ltype = mo_file.parent.name
    lname = mo_file.parent.parent.name
    ldir = __locale_dir__ / lname / ltype
    mo_file_rel = str(mo_file).lstrip('/')
    __data_files__.append((str(ldir), [mo_file_rel]))

# print("Found data files:\n" + pp(__data_files__) + "\n")


# -----------------------------------
class Sdist(sdist):
    """Custom ``sdist`` command to ensure that mo files are always created."""

    def run(self):
        self.run_command('compile_catalog')
        # sdist is an old style class so super cannot be used.
        sdist.run(self)


# -----------------------------------
setup(
    version=__packet_version__,
    long_description=read(__readme_file__),
    scripts=__scripts__,
    requires=__requirements__,
    package_data=__package_data__,
    data_files=__data_files__,
    cmdclass={
        'compile_catalog': babel.compile_catalog,
        'extract_messages': babel.extract_messages,
        'init_catalog': babel.init_catalog,
        'update_catalog': babel.update_catalog,
        'sdist': Sdist,
    },
)


# =============================================================================
# vim: fileencoding=utf-8 filetype=python ts=4 et list
