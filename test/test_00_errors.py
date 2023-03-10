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

    # -------------------------------------------------------------------------
    def test_attribute_errors(self):

        wrong_attr = 'uhu'

        LOG.info("Test raising a WrongMsgStatsAttributeError ...")

        from postfix_logsums.errors import PostfixLogsumsError
        from postfix_logsums.errors import WrongMsgStatsAttributeError

        with self.assertRaises(PostfixLogsumsError) as cm:
            raise WrongMsgStatsAttributeError(wrong_attr, self.__class__.__name__)
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)
        self.assertEqual(e.__class__.__name__, 'WrongMsgStatsAttributeError')

        LOG.info("Test raising a WrongMsgStatsValueError ...")

        from postfix_logsums.errors import WrongMsgStatsValueError

        msg = "Wrong value {v!r} in test_attribute_errors() of {c}.".format(
            v=wrong_attr, c=self.__class__.__name__)

        with self.assertRaises(PostfixLogsumsError) as cm:
            raise WrongMsgStatsValueError(msg)
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)
        self.assertEqual(e.__class__.__name__, 'WrongMsgStatsValueError')

    # -------------------------------------------------------------------------
    def test_key_errors(self):

        wrong_key = 'uhu'

        LOG.info("Test raising a WrongMsgStatsKeyError ...")

        from postfix_logsums.errors import PostfixLogsumsError
        from postfix_logsums.errors import WrongMsgStatsKeyError

        with self.assertRaises(PostfixLogsumsError) as cm:
            raise WrongMsgStatsKeyError(wrong_key, self.__class__.__name__)
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)
        self.assertEqual(e.__class__.__name__, 'WrongMsgStatsKeyError')

        LOG.info("Test raising a WrongMsgPerDayKeyError ...")

        from postfix_logsums.errors import WrongMsgPerDayKeyError

        with self.assertRaises(PostfixLogsumsError) as cm:
            raise WrongMsgPerDayKeyError(wrong_key, self.__class__.__name__)
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)
        self.assertEqual(e.__class__.__name__, 'WrongMsgPerDayKeyError')

    # -------------------------------------------------------------------------
    def test_hour_errors(self):

        wrong_hour = 'uhu'

        LOG.info("Test raising a WrongMsgStatsHourError ...")

        from postfix_logsums.errors import PostfixLogsumsError
        from postfix_logsums.errors import WrongMsgStatsHourError

        with self.assertRaises(PostfixLogsumsError) as cm:
            raise WrongMsgStatsHourError(wrong_hour, self.__class__.__name__)
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)
        self.assertEqual(e.__class__.__name__, 'WrongMsgStatsHourError')

        LOG.info("Test raising a MsgStatsHourValNotfoundError ...")

        from postfix_logsums.errors import MsgStatsHourValNotfoundError

        with self.assertRaises(PostfixLogsumsError) as cm:
            raise MsgStatsHourValNotfoundError(wrong_hour, self.__class__.__name__)
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)
        self.assertEqual(e.__class__.__name__, 'MsgStatsHourValNotfoundError')

        LOG.info("Test raising a MsgStatsHourInvalidMethodError ...")

        from postfix_logsums.errors import MsgStatsHourInvalidMethodError

        with self.assertRaises(PostfixLogsumsError) as cm:
            raise MsgStatsHourInvalidMethodError(wrong_hour, self.__class__.__name__)
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)
        self.assertEqual(e.__class__.__name__, 'MsgStatsHourInvalidMethodError')


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
    suite.addTest(TestErrors('test_attribute_errors', verbose))
    suite.addTest(TestErrors('test_key_errors', verbose))
    suite.addTest(TestErrors('test_hour_errors', verbose))

    runner = unittest.TextTestRunner(verbosity=verbose)

    result = runner.run(suite)

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
