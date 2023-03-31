#!/bin/env python3
# -*- coding: utf-8 -*-
"""
@summary: A module for statistic objects.

@author: Frank Brehm
@contact: frank@brehm-online.com
@copyright: © 2023 by Frank Brehm, Berlin
"""
from __future__ import absolute_import

import copy
import logging
import datetime
import re

try:
    from collections.abc import MutableMapping, Mapping, MutableSequence, Sequence
except ImportError:
    from collections import MutableMapping, Mapping, MutableSequence, Sequence

# Own modules
from .errors import StatsError, WrongDateKeyError, WrongMsgStatsKeyError, WrongDailyKeyError
from .errors import MsgStatsHourValNotfoundError, MsgStatsHourInvalidMethodError
from .errors import WrongMsgStatsAttributeError, WrongMsgStatsValueError

from .xlate import XLATOR

__version__ = '0.8.0'
__author__ = 'Frank Brehm <frank@brehm-online.com>'
__copyright__ = '(C) 2023 by Frank Brehm, Berlin'

HOURS_PER_DAY = 24
LOG = logging.getLogger(__name__)
_ = XLATOR.gettext

# =============================================================================
def is_sequence(arg):
    """Return, whether the given value is a sequential object, but nat a str."""
    if not isinstance(arg, Sequence):
        return False

    if hasattr(arg, "strip"):
        return False

    return True


# =============================================================================
class BaseMessageStats(MutableMapping):
    """A base class for encapsulating message statistics."""

    valid_keys = ('value_one', 'value_two')

    # -------------------------------------------------------------------------
    def __init__(self, first_param=None, **kwargs):
        """Constructor."""

        self._values = {}

        if first_param is not None:

            # LOG.debug("First parameter type {t!r}: {p!r}".format(
            #     t=type(first_param), p=first_param))

            if isinstance(first_param, Mapping):
                self._update_from_mapping(first_param)
            elif first_param.__class__.__name__ == 'zip':
                self._update_from_mapping(dict(first_param))
            else:
                msg = _("Object is not a {m} object, but a {w} object instead.").format(
                    m='Mapping', w=first_param.__class__.__qualname__)
                raise StatsError(msg)

        if kwargs:
            self._update_from_mapping(kwargs)

    # -------------------------------------------------------------------------
    def __getattr__(self, name):
        """Getting the value of a non-pre-defined attribute, epecially the statistics
        values."""
        if name not in self.valid_keys:
            raise WrongMsgStatsAttributeError(name, self.__class__.__name__)

        if name not in self._values:
            self._values[name] = 0

        return self._values[name]

    # -------------------------------------------------------------------------
    def __setattr__(self, name, value):
        """Called when an attribute assignment is attempted."""
        if name in ('_values', ):
            return super(BaseMessageStats, self).__setattr__(name, value)

        if name not in self.valid_keys:
            raise WrongMsgStatsAttributeError(name, self.__class__.__name__)

        try:
            v = int(value)
        except ValueError as e:
            msg = _("Wrong value {v!r} for a {w} value: {e}").format(
                v=value, w=self.__class__.__name__, e=e)
            raise WrongMsgStatsValueError(msg)

        if v < 0:
            msg = _("Wrong value {v!r} for a {w} value: must be >= 0").format(
                v=value, w=self.__class__.__name__)
            raise WrongMsgStatsValueError(msg)

        self._values[name] = v

    # -------------------------------------------------------------------------
    def __delattr__(self, name):
        """Called, if an attribute should be deleted."""
        msg = _("Deleting attribute {a!r} of a {w} is not allowed.").format(
            a=name, w=self.__class__.__name__)
        raise StatsError(msg)

    # -------------------------------------------------------------------------
    def _update_from_mapping(self, mapping):

        for key in mapping.keys():
            if isinstance(key, int) and key >= 0 and key < len(self.valid_keys):
                key = self.valid_keys[key]
            if key not in self.valid_keys:
                raise WrongMsgStatsKeyError(key, self.__class__.__name__)
            setattr(self, key, mapping[key])

    # -----------------------------------------------------------
    def as_dict(self, pure=False):
        """Transforms the elements of the object into a dict."""

        res = {}
        if not pure:
            res['__class_name__'] = self.__class__.__name__

        for key in self.valid_keys:
            value = getattr(self, key)
            res[key] = value

        return res

    # -------------------------------------------------------------------------
    def dict(self):
        """Typecast into a regular dict."""
        return self.as_dict(pure=True)

    # -----------------------------------------------------------
    def __repr__(self):
        """Typecast for reproduction."""
        ret = "{}(".format(self.__class__.__name__)
        kargs = []
        for pair in self.items():
            arg = "{k}={v!r}".format(k=pair[0], v=pair[1])
            kargs.append(arg)
        ret += ', '.join(kargs)
        ret += ')'

        return ret

    # -------------------------------------------------------------------------
    def __copy__(self):
        """Return a copy of the current set."""
        return self.__class__(self.dict())

    # -------------------------------------------------------------------------
    def copy(self):
        """Return a copy of the current set."""
        return self.__copy__()

    # -------------------------------------------------------------------------
    def _get_item(self, key):
        """Return an arbitrary item by the key."""
        if isinstance(key, int) and key >= 0 and key < len(self.valid_keys):
            key = self.valid_keys[key]
        if key not in self.valid_keys:
            raise WrongMsgStatsKeyError(key)

        return getattr(self, key, 0)

    # -------------------------------------------------------------------------
    def get(self, key):
        """Return an arbitrary item by the key."""
        return self._get_item(key)

    # -------------------------------------------------------------------------
    # The next four methods are requirements of the ABC.

    # -------------------------------------------------------------------------
    def __getitem__(self, key):
        """Return an arbitrary item by the key."""
        return self._get_item(key)

    # -------------------------------------------------------------------------
    def __iter__(self):
        """Return an iterator over all keys."""
        for key in self.keys():
            yield key

    # -------------------------------------------------------------------------
    def __len__(self):
        """Return the the nuber of entries (keys) in this dict."""
        return 4

    # -------------------------------------------------------------------------
    def __contains__(self, key):
        """Return, whether the given key exists(the 'in'-operator)."""
        if isinstance(key, int) and key >= 0 and key < len(self.valid_keys):
            return True
        if key in self.valid_keys:
            return True
        return False

    # -------------------------------------------------------------------------
    def keys(self):
        """Return a list with all keys in original notation."""
        return copy.copy(self.valid_keys)

    # -------------------------------------------------------------------------
    def items(self):
        """Return a list of all items of the current dict.

        An item is a tuple, with the key in original notation and the value.
        """
        item_list = []

        for key in self.keys():
            value = self.get(key)
            item_list.append((key, value))

        return item_list

    # -------------------------------------------------------------------------
    def values(self):
        """Return a list with all values of the current dict."""
        return list(map(lambda x: self.get(x), self.keys()))

    # -------------------------------------------------------------------------
    def __setitem__(self, key, value):
        """Set the value of the given key."""
        if isinstance(key, int) and key >= 0 and key < len(self.valid_keys):
            key = self.valid_keys[key]
        if key not in self.valid_keys:
            raise WrongMsgStatsKeyError(key)

        setattr(self, key, value)

    # -------------------------------------------------------------------------
    def set(self, key, value):
        """Set the value of the given key."""
        self[key] = value

    # -------------------------------------------------------------------------
    def __delitem__(self, key):
        """Should delete the entry on the given key.
        But in real the value if this key set to zero instead."""
        if isinstance(key, int) and key >= 0 and key < len(self.valid_keys):
            key = self.valid_keys[key]
        if key not in self.valid_keys:
            raise WrongMsgStatsKeyError(key)

        setattr(self, key, 0)

    # -------------------------------------------------------------------------
    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        return self._values == other._values


# =============================================================================
class MessageStats(BaseMessageStats):
    """A class for encapsulating common message statistics."""

    valid_keys = ('count', 'size', 'defers', 'delay_avg', 'delay_max')


# =============================================================================
class SmtpdStatsPerHour(BaseMessageStats):
    """A class for encapsulating message statistics per day."""

    valid_keys = ('count', 'time_total', 'time_max')


# =============================================================================
class MessageStatsPerDay(BaseMessageStats):
    """A class for encapsulating message statistics per day."""

    valid_keys = ('received', 'sent', 'deferred', 'bounced', 'rejected')


# =============================================================================
class SmtpdStats(BaseMessageStats):
    """A class for encapsulating smtpd statistics."""

    valid_keys = ('connections', 'connect_time_total', 'connect_time_max')


# =============================================================================
class MessageStatsTotals(BaseMessageStats):
    """A class for encapsulating total message statistics."""

    valid_keys = (
        'received', 'delivered', 'forwarded', 'deferred', 'deferrals', 'rejected',
        'discarded', 'bounced', 'reject_warning', 'held', 'bytes_received',
        'bytes_delivered', 'sending_users', 'sending_domains', 'rcpt_users',
        'rcpt_domains', 'connections', 'master')


# =============================================================================
class CommonStatsDict(dict):
    """Extending the base dict class by some methods."""

    # -------------------------------------------------------------------------
    def as_dict(self, pure=False):
        """
        Transform the elements of the object into a dict.

        @param pure: Only include keys and values of the internal map
        @type pure: bool

        @return: structure as dict
        @rtype:  dict
        """
        res = {}
        if not pure:
            res['__class_name__'] = self.__class__.__name__

        for key in self.keys():
            val = self[key]
            if isinstance(val, BaseMessageStats):
                res[key] = val.as_dict(pure=pure)
            else:
                res[key] = copy.copy(val)

        return res

    # -------------------------------------------------------------------------
    def dict(self):
        """Typecast into a regular dict."""
        return self.as_dict(pure=True)


# =============================================================================
class DailyStatsDict(MutableMapping):
    """A dict like class for containing message statistics per day."""

    re_isoformat = re.compile(r'^(?P<year>\d{1,4})-?(?P<month>\d{2})-?(?P<day>\d{2})$')

    # -------------------------------------------------------------------------
    @classmethod
    def key_to_date(cls, key):
        """Typecasting given date into a datetime.date object."""
        # LOG.debug("Init key for a {c} object: {k!r}".format(c=cls.__name__, k=key))
        if isinstance(key, datetime.datetime):
            return key.date()
        if isinstance(key, datetime.date):
            return key
        if isinstance(key, int):
            return datetime.date.fromtimestamp(key)
        if is_sequence(key):
            try:
                return datetime.date(*key)
            except (ValueError, KeyError) as e:
                raise WrongDateKeyError(key, str(e))
        if isinstance(key, str):
            try:
                m = cls.re_isoformat.match(key)
                if m:
                    return datetime.date(int(m['year']), int(m['month']), int(m['day']))
                raise WrongDateKeyError(key)
            except (ValueError, KeyError) as e:
                if isinstance(e, WrongDateKeyError):
                    raise e
                raise WrongDateKeyError(key, str(e))
        raise WrongDateKeyError(key)

    # -------------------------------------------------------------------------
    def __init__(self, stats_class=BaseMessageStats, first_param=None, **kwargs):
        """Constructor."""

        self._stats = {}
        if not issubclass(stats_class, BaseMessageStats):
            msg = _(
                "Wrong class {c} for using as an item class, must be a subclas of {sc}.").format(
                c=stats_class.__name__, sc='BaseMessageStats')
            raise TypeError(msg)
        self._stats_class = stats_class

        if first_param is not None:

            if isinstance(first_param, self.__class__):
                self._update_from_other(first_param)
            elif isinstance(first_param, Mapping):
                self._update_from_mapping(first_param)
            elif first_param.__class__.__name__ == 'zip':
                self._update_from_mapping(dict(first_param))
            else:
                msg = _("Object is not a {m} object, but a {w} object instead.").format(
                    m='Mapping', w=first_param.__class__.__qualname__)
                raise StatsError(msg)

        if kwargs:
            self._update_from_mapping(kwargs)

    # -------------------------------------------------------------------------
    def _update_from_mapping(self, mapping):

        for key in mapping.keys():
            used_key = self.key_to_date(key)
            stats = self._stats_class(mapping[key])
            self._stats[used_key] = stats

    # -------------------------------------------------------------------------
    def __copy__(self):
        """Return a copy of the current dict."""
        new = self.__class__(self._stats_class)
        for key in self:
            new[key] = copy.copy(self[key])

        return new

    # -------------------------------------------------------------------------
    def copy(self):
        """Return a copy of the current set."""
        return self.__copy__()

    # -------------------------------------------------------------------------
    def _get_item(self, key):
        """Return an arbitrary item by the key."""
        used_key = self.key_to_date(key)
        return self._stats[used_key]

    # -------------------------------------------------------------------------
    def get(self, key):
        """Return an arbitrary item by the key."""
        return self._get_item(key)

    # -------------------------------------------------------------------------
    def __getitem__(self, key):
        """Return an arbitrary item by the key."""
        return self._get_item(key)

    # -------------------------------------------------------------------------
    def __iter__(self):
        """Return an iterator over all keys."""
        for key in self.keys():
            yield key

    # -------------------------------------------------------------------------
    def __len__(self):
        """Return the the nuber of entries (keys) in this dict."""
        return len(self._stats)

    # -------------------------------------------------------------------------
    def __repr__(self):
        """Typecast into string for reproduction."""
        ret = "{cn}({{stats_class={sc}".format(
            cn=self.__class__.__name__, sc=self._stats_class.__name__)
        if len(self) == 0:
            return ret + '})'

        kargs = ['']
        for pair in self.items():
            arg = "{k!r}: {v!r}".format(k=pair[0], v=pair[1])
            kargs.append(arg)
        ret += ', '.join(kargs)
        ret += '})'

        return ret

    # -------------------------------------------------------------------------
    def as_dict(self, pure=False):
        """
        Transform the elements of the object into a dict.

        @param pure: Only include keys and values of the internal map
        @type pure: bool

        @return: structure as dict
        @rtype:  dict
        """
        res = {}
        if not pure:
            res['__class_name__'] = self.__class__.__name__
            res['__stats_class__'] = self._stats_class.__name__

        for pair in self.items():
            key = pair[0]
            val = pair[1].as_dict()
            if pure:
                key = pair[0].isoformat()
                val = pair[1].dict()
            res[key] = val

        return res

    # -------------------------------------------------------------------------
    def dict(self):
        """Typecast into a regular dict."""
        return self.as_dict(pure=True)

    # -------------------------------------------------------------------------
    def __contains__(self, key):
        """Return, whether the given key exists(the 'in'-operator)."""
        used_key = self.key_to_date(key)
        if used_key in self._stats:
            return True
        return False

    # -------------------------------------------------------------------------
    def keys(self):
        """Return a list with all keys in original notation."""
        return sorted(self._stats.keys())

    # -------------------------------------------------------------------------
    def items(self):
        """Return a list of all items of the current dict.

        An item is a tuple, with the key in original notation and the value.
        """
        item_list = []

        for key in self.keys():
            value = self._stats[key]
            item_list.append((key, value))

        return item_list

    # -------------------------------------------------------------------------
    def values(self):
        """Return a list with all values of the current dict."""
        return list(map(lambda x: self._stats[x], self.keys()))

    # -------------------------------------------------------------------------
    def __eq__(self, other):
        """Return the equality of current dict with another (the '=='-operator)."""
        if not isinstance(other, DailyStatsDict):
            return False
        if self._stats_class.__name__ != other._stats_class.__name__:
            return False
        if len(self) != len(other):
            return False
        if len(self) == 0:
            return True

        for key in self.keys():
            if key not in other:
                return False
            if self[key] != other[key]:
                return False

        return True

    # -------------------------------------------------------------------------
    def __setitem__(self, key, value):
        """Set the value of the given key."""
        used_key = self.key_to_date(key)
        stats = self._stats_class(value)
        self._stats[used_key] = stats

    # -------------------------------------------------------------------------
    def set(self, key, value):
        """Set the value of the given key."""
        self[key] = value

    # -------------------------------------------------------------------------
    def __delitem__(self, key):
        """Delete the entry on the given key.

        Raise a KeyError, if the does not exists.
        """
        used_key = self.key_to_date(key)
        try:
            del self._stats[used_key]
        except KeyError as e:
            raise WrongDailyKeyError(key, str(e))

    # -------------------------------------------------------------------------
    def pop(self, key, *args):
        """Remove and return an arbitrary element from the dict."""
        used_key = self.key_to_date(key)

        if len(args) > 1:
            msg = _("The method {met}() expected at most {max} arguments, got {got}.").format(
                met='pop', max=2, got=(len(args) + 1))
            raise TypeError(msg)

        if used_key not in self._stats:
            if args:
                return args[0]
            raise WrongDailyKeyError(key)

        val = self._stats[used_key]
        del self._stats[used_key]

        return val

    # -------------------------------------------------------------------------
    def popitem(self):
        """Remove and return the first element from the dict."""
        if not len(self._stats):
            return None

        key = self.keys()[0]
        value = self[key]
        del self._stats[key]
        return (key, value)

    # -------------------------------------------------------------------------
    def clear(self):
        """Remove all items from the dict."""
        self._stats = dict()

    # -------------------------------------------------------------------------
    def setdefault(self, key, default=None):
        """Set the item of the given key to a default value."""
        used_key = self.key_to_date(key)

        if used_key in self:
            return self[used_key]

        self[used_key] = default
        return default

    # -------------------------------------------------------------------------
    def update(self, other):
        """Update the current dict with the items of the other dict."""
        if isinstance(other, self.__class__):
            self._update_from_other(other)
        elif isinstance(other, Mapping):
            self._update_from_mapping(other)
        elif other.__class__.__name__ == 'zip':
            self._update_from_mapping(dict(other))
        else:
            msg = _("Object is not a {m} object, but a {w} object instead.").format(
                m='Mapping', w=other.__class__.__qualname__)
            raise StatsError(msg)

    # -------------------------------------------------------------------------
    def _update_from_other(self, other):
        if not isinstance(other, self.__class__):
            raise StatsError("Wtf, not a {} class?!?".format(self.__class__.__name__))
        if self._stats_class.__name__ != other._stats_class.__name__:
            msg = "Invalid stats class {oc!r}, must be class {sc!r}.".format(
                oc=other._stats_class.__name__, sc=self._stats_class.__name__)
            raise StatsError(msg)
        for key in other.keys():
            self[key] = other[key]


# =============================================================================
class HourlyStats(MutableSequence):
    """A class for encapsulating per hour message statistics."""

    hours_per_day = HOURS_PER_DAY

    # -------------------------------------------------------------------------
    def __init__(self, *args):
        """Constructor."""

        self._list = []
        for hour in range(self.hours_per_day):
            self._list.append(0)

        if args:
            if len(args) > self.hours_per_day:
                msg = _("Invalid number {} of statistics per hour given.").format(len(args))
                raise StatsError(msg)
            index = 0
            for value in args:
                self[index] = value
                index += 1

    # -------------------------------------------------------------------------
    def __repr__(self):
        """Typecast for reproduction."""
        ret = "{}(".format(self.__class__.__name__)
        pairs = []

        for value in self:
            pairs.append(repr(value))
        ret += ', '.join(pairs) + ')'

        return ret

    # -------------------------------------------------------------------------
    def as_list(self):
        """Typecasting into a simple list."""
        return copy.copy(self._list)

    # -------------------------------------------------------------------------
    def __getitem__(self, hour):
        """Returns the value of the given hour."""
        return self._list[hour]

    # -------------------------------------------------------------------------
    def __len__(self):
        """Returns the length of the current array."""
        return len(self._list)

    # -------------------------------------------------------------------------
    def __contains__(self, value):
        """Returns, whether the given value is one of the values in current list."""
        for val in self:
            if value == val:
                return True
        return False

    # -------------------------------------------------------------------------
    def __iter__(self):
        """Return an iterator over all entries."""
        for value in self._list:
            yield value

    # -------------------------------------------------------------------------
    def __reversed__(self):
        """Return an reversed iterator over all entries."""
        index = len(self._list)
        while index > 0:
            index -= 1
            yield self._list[index]

    # -------------------------------------------------------------------------
    def index(self, value, i=0, j=None):
        """index of the first occurrence of x in s (at or after index i and before index j)."""

        if j is None:
            j = len(self._list)
        while i < j:
            if self._list[i] == value:
                return i
            i += 1

        raise MsgStatsHourValNotfoundError(value)

    # -------------------------------------------------------------------------
    def count(self, value):
        """total number of occurrences of svaluex in current list."""
        number = 0
        for val in self:
            if value == val:
                number += 1

        return number

    # -------------------------------------------------------------------------
    def __setitem__(self, hour, value):
        """Setting the value for the given hour."""
        try:
            v = int(value)
        except ValueError as e:
            msg = _("Wrong value {v!r} for a per hour stat: {e}").format(v=value, e=e)
            raise WrongMsgStatsValueError(msg)
        if v < 0:
            msg = _("Wrong value {v!r} for a per hour stat: must be >= 0").format(v=value)
            raise WrongMsgStatsValueError(msg)
        self._list[hour] = int(value)

    # -------------------------------------------------------------------------
    def __delitem__(self, hour):
        """Deleting an item in the list - invalid action."""

        raise MsgStatsHourInvalidMethodError('__delitem__')

    # -------------------------------------------------------------------------
    def insert(self, hour, value):
        """Insert an item in the list - invalid action."""

        raise MsgStatsHourInvalidMethodError('insert')

    # -------------------------------------------------------------------------
    def append(self, value):
        """Appending the given value to the current list - invalid action."""

        raise MsgStatsHourInvalidMethodError('append')

    # -------------------------------------------------------------------------
    def reverse(self):
        """Reverses the values of the current list in place."""

        self._list.reverse()

    # -------------------------------------------------------------------------
    def extend(self, other_list):
        """Extends the current list with the contents of other_list - invalid action."""

        raise MsgStatsHourInvalidMethodError('extend')

    # -------------------------------------------------------------------------
    def pop(self, value):
        """Retrieves the item at i and also removes it from s - invalid action."""

        raise MsgStatsHourInvalidMethodError('pop')

    # -------------------------------------------------------------------------
    def remove(self, value):
        """Remove the first item from the current list where s[i] is equal to x -
        invalid action."""

        raise MsgStatsHourInvalidMethodError('remove')

    # -------------------------------------------------------------------------
    def __iadd__(self, other_list):
        """Extends the current list with the contents of other_list and return -
        invalid action."""

        raise MsgStatsHourInvalidMethodError('__iadd__')


# =============================================================================
class HourlyStatsSmtpd(HourlyStats):
    """A class for encapsulating per hour message statistics."""

    # -------------------------------------------------------------------------
    def __init__(self, *args):
        """Constructor."""

        self._list = []
        for hour in range(self.hours_per_day):
            self._list.append(SmtpdStatsPerHour())

        if args:
            if len(args) > self.hours_per_day:
                msg = _("Invalid number {} of statistics per hour given.").format(len(args))
                raise StatsError(msg)
            index = 0
            for value in args:
                if value is not None:
                    self[index] = value
                index += 1

    # -------------------------------------------------------------------------
    def __setitem__(self, hour, value):
        """Setting the value for the given hour."""
        if isinstance(value, SmtpdStatsPerHour):
            self._list[hour] = value
            return

        if isinstance(value, (list, tuple)):
            if len(value) != 3:
                msg = _(
                    "Wrong value {v!r} for a per hour stat of smtp - "
                    "must have three numbers.").format(v=value)
                raise WrongMsgStatsValueError(msg)
            v = SmtpdStatsPerHour()
            v[0] = value[0]
            v[1] = value[1]
            v[2] = value[2]
            self._list[hour] = v
            return

        if isinstance(value, dict):
            v = SmtpdStatsPerHour(**value)
            self._list[hour] = v
            return

        msg = _("Wrong value {v!r} for a per hour stat.").format(v=value)
        raise WrongMsgStatsValueError(msg)

    # -------------------------------------------------------------------------
    def as_list(self, pure=False):
        """Typecasting into a simple list."""
        vals = []
        for stat in self:
            if pure:
                vals.append(stat.dict())
            else:
                vals.append(repr(stat))
        return vals


# =============================================================================

if __name__ == "__main__":

    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
