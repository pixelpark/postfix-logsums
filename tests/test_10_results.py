#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
@summary: Test script (and module) for unit tests on postfix_logsums.results.

@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 Frank Brehm, Berlin
@license: GPL3
'''

import logging
import os
import sys
from pathlib import Path

try:
    import unittest2 as unittest
except ImportError:
    import unittest

libdir = str(Path(__file__).parent.parent / 'src')
sys.path.insert(0, libdir)

from general import PostfixLogsumsTestcase, get_arg_verbose, init_root_logger, pp

LOG = logging.getLogger('test_results')


# =============================================================================
class TestResults(PostfixLogsumsTestcase):

    # -------------------------------------------------------------------------
    def setUp(self):
        """Execute this on seting up before calling each particular test method."""
        pass

    # -------------------------------------------------------------------------
    def test_import(self):
        """Test import of postfix_logsums.results."""
        LOG.info(self.get_method_doc())

        import postfix_logsums.results
        LOG.debug("Version of postfix_logsums.results: {!r}".format(
            postfix_logsums.results.__version__))

    # -------------------------------------------------------------------------
    def test_init_results(self):
        """Test init of a PostfixLogSums object."""
        LOG.info(self.get_method_doc())

        from postfix_logsums.results import PostfixLogSums

        results = PostfixLogSums()

        LOG.debug("PostfixLogSums %r: {!r}".format(results))
        LOG.debug("PostfixLogSums %s: {}".format(results))

        dump = results.as_dict()
        if self.verbose > 2:
            LOG.debug("Dump as a dict:\n" + pp(dump))
        dump = results.dict()
        if self.verbose > 2:
            LOG.debug("Dump as a pure dict:\n" + pp(dump))


# =============================================================================
if __name__ == '__main__':

    verbose = get_arg_verbose()
    if verbose is None:
        verbose = 0
    init_root_logger(verbose)

    LOG.info("Starting tests ...")

    suite = unittest.TestSuite()

    suite.addTest(TestResults('test_import', verbose))
    suite.addTest(TestResults('test_init_results', verbose))

    runner = unittest.TextTestRunner(verbosity=verbose)

    result = runner.run(suite)

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
