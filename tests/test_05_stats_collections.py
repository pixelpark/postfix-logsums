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
import datetime

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

        msg_stats = BaseMessageStats(value_one=6, value_two=7)
        with self.assertRaises(PostfixLogsumsError) as cm:
            del msg_stats.value_one
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

    # -------------------------------------------------------------------------
    def test_common_msg_stats(self):

        LOG.info("Testing init and attributes of a MessageStats object.")

        from postfix_logsums.errors import PostfixLogsumsError
        from postfix_logsums.stats import MessageStats

        LOG.debug("Testing init of an empty MessageStats object.")

        msg_stats = MessageStats()

        LOG.debug("MessageStats %r: {!r}".format(msg_stats))
        LOG.debug("MessageStats %s: {}".format(msg_stats))

        exp_dict = {
            'count': 0,
            'size': 0,
            'defers': 0,
            'delay_avg': 0,
            'delay_max': 0,
        }
        LOG.debug("Expecting from dict():\n" + pp(exp_dict))

        got_dict = msg_stats.dict()
        LOG.debug("Got dict():\n" + pp(got_dict))
        self.assertEqual(got_dict, exp_dict)

        exp_keys = ('count', 'size', 'defers', 'delay_avg', 'delay_max')
        LOG.debug("Expected keys:\n" + pp(exp_keys))
        got_keys = msg_stats.keys()
        LOG.debug("Got keys:\n" + pp(got_keys))
        self.assertEqual(exp_keys, got_keys)

        LOG.debug("Testing access to attributes ...")
        msg_stats.count = 4
        msg_stats[0] = 3
        msg_stats['count'] = 2

        with self.assertRaises(PostfixLogsumsError) as cm:
            msg_stats = MessageStats({'value_one': 1})
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        with self.assertRaises(PostfixLogsumsError) as cm:
            msg_stats = MessageStats(value_two=2)
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

    # -------------------------------------------------------------------------
    def test_msg_stats_per_day(self):

        LOG.info("Testing init and attributes of a MessageStatsPerDay object.")

        from postfix_logsums.errors import PostfixLogsumsError
        from postfix_logsums.stats import MessageStatsPerDay

        LOG.debug("Testing init of an empty MessageStatsPerDay object.")

        msg_stats = MessageStatsPerDay()

        LOG.debug("MessageStatsPerDay %r: {!r}".format(msg_stats))
        LOG.debug("MessageStatsPerDay %s: {}".format(msg_stats))

        exp_dict = {
            'received': 0,
            'sent': 0,
            'deferred': 0,
            'bounced': 0,
            'rejected': 0,
        }
        LOG.debug("Expecting from dict():\n" + pp(exp_dict))

        got_dict = msg_stats.dict()
        LOG.debug("Got dict():\n" + pp(got_dict))
        self.assertEqual(got_dict, exp_dict)

        exp_keys = ('received', 'sent', 'deferred', 'bounced', 'rejected')
        LOG.debug("Expected keys:\n" + pp(exp_keys))
        got_keys = msg_stats.keys()
        LOG.debug("Got keys:\n" + pp(got_keys))
        self.assertEqual(exp_keys, got_keys)

        LOG.debug("Testing access to attributes ...")
        msg_stats.bounced = 4
        msg_stats[3] = 3
        msg_stats['bounced'] = 2

        with self.assertRaises(PostfixLogsumsError) as cm:
            msg_stats = MessageStatsPerDay({'value_one': 1})
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        with self.assertRaises(PostfixLogsumsError) as cm:
            msg_stats = MessageStatsPerDay(defers=2)
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

    # -------------------------------------------------------------------------
    def test_hourly_stats(self):

        LOG.info("Testing init and attributes of a HourlyStats object ..""")

        from postfix_logsums.errors import PostfixLogsumsError
        from postfix_logsums.stats import HourlyStats

        LOG.debug("Testing init of an empty HourlyStats object.")

        msg_stats = HourlyStats()

        LOG.debug("HourlyStats %r: {!r}".format(msg_stats))
        LOG.debug("HourlyStats %s: {}".format(msg_stats))

        for hour in range(24):
            self.assertEqual(msg_stats[hour], 0)

        LOG.debug("Testing wrong index 'bla' ...")
        with self.assertRaises(TypeError) as cm:
            uhu = msg_stats['bla']
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        LOG.debug("Testing wrong index 25 ...")
        with self.assertRaises(IndexError) as cm:
            uhu = msg_stats[25]
            LOG.debug("Uhu: {!r}.".format(uhu))
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        LOG.debug("Test setting correct value ...")
        msg_stats[3] = 5
        self.assertEqual(msg_stats[3], 5)

        LOG.debug("Test setting incorrect value 'bla' ...")
        with self.assertRaises(ValueError) as cm:
            msg_stats[3] = 'bla'
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        LOG.debug("Test setting incorrect value -1 ...")
        with self.assertRaises(ValueError) as cm:
            msg_stats[3] = -1
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        LOG.debug("Test deleting a value in the list ...")
        with self.assertRaises(PostfixLogsumsError) as cm:
            del msg_stats[3]
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

    # -------------------------------------------------------------------------
    def test_daily_stats(self):

        LOG.info("Testing init and attributes of a DailyStatsDict object ..""")

        from postfix_logsums.errors import PostfixLogsumsError
        from postfix_logsums.stats import DailyStatsDict, BaseMessageStats

        daily_stats = DailyStatsDict()

        LOG.debug("DailyStatsDict %r: {!r}".format(daily_stats))
        LOG.debug("DailyStatsDict %s: {}".format(daily_stats))
        LOG.debug("DailyStatsDict as a dict: {}".format(pp(daily_stats.as_dict())))
        LOG.debug("DailyStatsDict as a pure dict: {}".format(pp(daily_stats.dict())))

        LOG.debug("Assigning valid values ....")
        daily_stats[datetime.date.today()] = {'value_one': 1, 'value_two': 2}
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        daily_stats[yesterday] = BaseMessageStats({'value_one': 3, 'value_two': 4})
        one_week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
        daily_stats[one_week_ago] = {'value_one': 5, 'value_two': 6}
        daily_stats['2023-03-01'] = BaseMessageStats(value_one=7, value_two=8)
        daily_stats[123456789] = {}
        daily_stats[(2020, 1, 1)] = {'value_one': 2020}
        daily_stats[[2021, 1, 1]] = {'value_two': 2021}
        LOG.debug("DailyStatsDict as a dict:\n{}".format(pp(daily_stats.as_dict())))
        LOG.debug("DailyStatsDict as a pure dict:\n{}".format(pp(daily_stats.dict())))

        LOG.debug("Using wrong keys and values ...")

        with self.assertRaises(PostfixLogsumsError) as cm:
            daily_stats['uhu'] = 'bla'
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        with self.assertRaises(PostfixLogsumsError) as cm:
            daily_stats['2022-12-32'] = {'value_one': 1, 'value_two': 2}
        e = cm.exception
        LOG.debug("%s raised: %s", e.__class__.__name__, e)

        with self.assertRaises(PostfixLogsumsError) as cm:
            daily_stats['2022-12-12'] = 'bla'
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
    suite.addTest(TestStatsCollections('test_common_msg_stats', verbose))
    suite.addTest(TestStatsCollections('test_msg_stats_per_day', verbose))
    suite.addTest(TestStatsCollections('test_hourly_stats', verbose))
    suite.addTest(TestStatsCollections('test_daily_stats', verbose))

    runner = unittest.TextTestRunner(verbosity=verbose)

    result = runner.run(suite)

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
