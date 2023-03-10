#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 Frank Brehm, Berlin
@license: GPL3
@summary: test script (and module) for unit tests on error (exception) classes
'''

import os
import sys
import logging

try:
    import unittest2 as unittest
except ImportError:
    import unittest

libdir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, libdir)

from general import PostfixLogsumsTestcase, get_arg_verbose, init_root_logger

LOG = logging.getLogger('test_errors')


# =============================================================================
class TestErrors(PostfixLogsumsTestcase):

    # -------------------------------------------------------------------------
    def setUp(self):
        pass

    # -------------------------------------------------------------------------
    def test_import(self):

        LOG.info("Testing import of postfix_logsums.errors ...")
        import postfix_logsums.errors
        LOG.debug("Version of postfix_logsums.errors: {!r}".format(
            postfix_logsums.errors.__version__))
        from postfix_logsums.errors import PostfixLogsumsError, StatsError      # noqa
        from postfix_logsums.errors import WrongMsgStatsAttributeError          # noqa
        from postfix_logsums.errors import WrongMsgStatsValueError              # noqa
        from postfix_logsums.errors import WrongMsgStatsKeyError                # noqa
        from postfix_logsums.errors import WrongMsgPerDayKeyError               # noqa
        from postfix_logsums.errors import WrongMsgStatsHourError               # noqa
        from postfix_logsums.errors import MsgStatsHourValNotfoundError         # noqa
        from postfix_logsums.errors import MsgStatsHourInvalidMethodError       # noqa

    # -------------------------------------------------------------------------
    def test_general_errors(self):

        test_txt = "Bla blub"

        LOG.info("Test raising a PostfixLogsumsError exception ...")

        from postfix_logsums.errors import PostfixLogsumsError

        with self.assertRaises(PostfixLogsumsError) as cm:
            raise PostfixLogsumsError("Bla blub")
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)
        self.assertEqual(test_txt, str(e))

        LOG.info("Test raising a StatsError exception ...")

        from postfix_logsums.errors import StatsError

        with self.assertRaises(PostfixLogsumsError) as cm:
            raise StatsError("Bla blub")
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)
        self.assertEqual(test_txt, str(e))

# =============================================================================
if __name__ == '__main__':

    verbose = get_arg_verbose()
    if verbose is None:
        verbose = 0
    init_root_logger(verbose)

    LOG.info("Starting tests ...")

    suite = unittest.TestSuite()

    suite.addTest(TestErrors('test_import', verbose))
    suite.addTest(TestErrors('test_general_errors', verbose))

    runner = unittest.TextTestRunner(verbosity=verbose)

    result = runner.run(suite)

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

