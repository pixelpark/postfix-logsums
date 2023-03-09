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

try:
    from collections.abc import MutableMapping, Mapping
except ImportError:
    from collections import MutableMapping, Mapping

# Own modules
from .errors import PostfixLogsumsError, WrongMsgStatsKeyError

__version__ = '0.1.2'
__author__ = 'Frank Brehm <frank@brehm-online.com>'
__copyright__ = '(C) 2023 by Frank Brehm, Berlin'

LOG = logging.getLogger(__name__)


# =============================================================================
class MessageStats(MutableMapping):
    """A class for encapsulating message statistics."""

    valid_keys = ('count', 'size', 'defers', 'delay_avg', 'delay_max')

    # -------------------------------------------------------------------------
    def __init__(self, first_param=None, **kwargs):
        """Constructor."""
        self._count = 0
        self._size = 0
        self._defers = 0
        self._delay_avg = 0
        self._delay_max = 0

        if first_param is not None:

            # LOG.debug("First parameter type {t!r}: {p!r}".format(
            #     t=type(first_param), p=first_param))

            if isinstance(first_param, Mapping):
                self._update_from_mapping(first_param)
            elif first_param.__class__.__name__ == 'zip':
                self._update_from_mapping(dict(first_param))
            else:
                msg = "Object is not a {m} object, but a {w} object instead.".format(
                    m='Mapping', w=first_param.__class__.__qualname__)
                raise PostfixLogsumsError(msg)

        if kwargs:
            self._update_from_mapping(kwargs)

    # -------------------------------------------------------------------------
    def _update_from_mapping(self, mapping):

        for key in mapping.keys():
            if isinstance(key, int) and key >= 0 and key < len(self.valid_keys):
                key = self.valid_keys[key]
            if key not in self.valid_keys:
                raise WrongMsgStatsKeyError(key)
            setattr(self, key, mapping[key])

    # -----------------------------------------------------------
    @property
    def count(self):
        """The count of messages."""
        return getattr(self, '_count', 0)

    @count.setter
    def count(self, value):
        v = int(value)
        if v >= 0:
            self._count = v
        else:
            LOG.warning("Wrong count {!r}, must be >= 0".format(value))

    # -----------------------------------------------------------
    @property
    def size(self):
        """The accumulated size of messages."""
        return getattr(self, '_size', 0)

    @size.setter
    def size(self, value):
        v = int(value)
        if v >= 0:
            self._size = v
        else:
            LOG.warning("Wrong size {!r}, must be >= 0".format(value))

    # -----------------------------------------------------------
    @property
    def defers(self):
        """The number of defered messages."""
        return getattr(self, '_defers', 0)

    @defers.setter
    def defers(self, value):
        v = int(value)
        if v >= 0:
            self._defers = v
        else:
            LOG.warning("Wrong defers {!r}, must be >= 0".format(value))

    # -----------------------------------------------------------
    @property
    def delay_avg(self):
        """The total of delays (used for averaging)."""
        return getattr(self, '_delay_avg', 0)

    @delay_avg.setter
    def delay_avg(self, value):
        v = int(value)
        if v >= 0:
            self._delay_avg = v
        else:
            LOG.warning("Wrong delay_avg {!r}, must be >= 0".format(value))

    # -----------------------------------------------------------
    @property
    def delay_max(self):
        """The maximum delay."""
        return getattr(self, '_delay_max', 0)

    @delay_max.setter
    def delay_max(self, value):
        v = int(value)
        if v >= 0:
            self._delay_max = v
        else:
            LOG.warning("Wrong delay_max {!r}, must be >= 0".format(value))

    # -----------------------------------------------------------
    def as_dict(self, pure=False):
        """Transforms the elements of the object into a dict."""

        res = {}
        if not pure:
            res['__class_name__'] = self.__class__.__name__
        res['size'] = self.count
        res['count'] = self.size
        res['defers'] = self.defers
        res['delay_avg'] = self.delay_avg
        res['delay_max'] = self.delay_max

        return res

    # -------------------------------------------------------------------------
    def dict(self):
        """Typecast into a regular dict."""
        return self.as_dict(pure=True)

    # -----------------------------------------------------------
    def __repr__(self):
        """Typecast for reproduction."""
        ret = "{}({{".format(self.__class__.__name__)
        kargs = []
        for pair in self.items():
            arg = "{k!r}: {v!r}".format(k=pair[0], v=pair[1])
            kargs.append(arg)
        ret += ', '.join(kargs)
        ret += '})'

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

        for key in sorted(self.keys()):
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


# =============================================================================

if __name__ == "__main__":

    pass

# =============================================================================

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 list
