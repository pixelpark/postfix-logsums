#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 Frank Brehm, Berlin
@license: GPL3
@summary: test script (and module) for unit tests on postfix_logsums.stats
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

from general import PostfixLogsumsTestcase, get_arg_verbose, init_root_logger, pp

LOG = logging.getLogger('test_stats_collections')


# =============================================================================
class TestStatsCollections(PostfixLogsumsTestcase):

    # -------------------------------------------------------------------------
    def setUp(self):
        pass

    # -------------------------------------------------------------------------
    def test_import(self):

        LOG.info("Testing import of postfix_logsums.stats ...")
        import postfix_logsums.stats
        LOG.debug("Version of postfix_logsums.stats: {!r}".format(
            postfix_logsums.stats.__version__))

    # -------------------------------------------------------------------------
    def test_init_base_stats(self):

        LOG.info("Testing init and attributes of a BaseMessageStats object.")

        from postfix_logsums.stats import BaseMessageStats

        LOG.debug("Testing init of an empty BaseMessageStats object.")

        msg_stats = BaseMessageStats()

        LOG.debug("BaseMessageStats %r: {!r}".format(msg_stats))
        LOG.debug("BaseMessageStats %s: {}".format(msg_stats))

        exp_dict = {
            'value_one': 0,
            'value_two': 0,
        }
        LOG.debug("Expecting from dict():\n" + pp(exp_dict))

        got_dict = msg_stats.dict()
        LOG.debug("Got dict():\n" + pp(got_dict))
        self.assertEqual(got_dict, exp_dict)

        exp_keys = ('value_one', 'value_two')
        LOG.debug("Expected keys:\n" + pp(exp_keys))
        got_keys = msg_stats.keys()
        LOG.debug("Got keys:\n" + pp(got_keys))
        self.assertEqual(exp_keys, got_keys)

        LOG.debug("Testing access to attributes ...")
        msg_stats.value_two = 4
        msg_stats[1] = 3
        msg_stats['value_two'] = 2

        self.assertEqual(msg_stats.value_one, 0)
        self.assertEqual(msg_stats[0], 0)
        self.assertEqual(msg_stats['value_one'], 0)
        self.assertEqual(msg_stats.value_two, 2)
        self.assertEqual(msg_stats[1], 2)
        self.assertEqual(msg_stats['value_two'], 2)

        LOG.debug("Testing init  of a BaseMessageStats object with values.")

        msg_stats = BaseMessageStats({'value_one': 4, 'value_two': 5})
        LOG.debug("BaseMessageStats %r: {!r}".format(msg_stats))
        self.assertEqual(msg_stats.value_one, 4)
        self.assertEqual(msg_stats.value_two, 5)

        msg_stats = BaseMessageStats(value_one=6, value_two=7)
        LOG.debug("BaseMessageStats %r: {!r}".format(msg_stats))
        self.assertEqual(msg_stats.value_one, 6)
        self.assertEqual(msg_stats.value_two, 7)


    # -------------------------------------------------------------------------
    def test_base_stats_failures(self):

        LOG.info("Testing wrong attributes, keys or values of a BaseMessageStats object.")

        from postfix_logsums.errors import PostfixLogsumsError
        from postfix_logsums.stats import BaseMessageStats

        with self.assertRaises(PostfixLogsumsError) as cm:
            msg_stats = BaseMessageStats('uhu')
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        with self.assertRaises(PostfixLogsumsError) as cm:
            msg_stats = BaseMessageStats(uhu='banane')
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        with self.assertRaises(PostfixLogsumsError) as cm:
            msg_stats = BaseMessageStats({'bla': 'banane'})
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        with self.assertRaises(PostfixLogsumsError) as cm:
            msg_stats = BaseMessageStats(value_one='banane')
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        with self.assertRaises(PostfixLogsumsError) as cm:
            msg_stats = BaseMessageStats(value_one=-1)
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)


# =============================================================================
if __name__ == '__main__':

    verbose = get_arg_verbose()
    if verbose is None:
        verbose = 0
    init_root_logger(verbose)

    LOG.info("Starting tests ...")

    suite = unittest.TestSuite()

    suite.addTest(TestStatsCollections('test_import', verbose))
    suite.addTest(TestStatsCollections('test_init_base_stats', verbose))
    suite.addTest(TestStatsCollections('test_base_stats_failures', verbose))

    runner = unittest.TextTestRunner(verbosity=verbose)

    result = runner.run(suite)

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
