#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Minimal, self-contained GNU mo hash-table lookup.

This module is deliberately kept separate from polib's mo writer: it only
knows how to *read* a binary catalog and resolve keys, the same way an
embedded gettext runtime does. Both little-endian and big-endian catalogs
are supported, and lookups through the hash table always terminate within
``hash_size`` probes, whether or not the key exists.
"""

import struct

__all__ = ['gnu_hash', 'MoLookup']

_MAGIC = 0x950412de
_MAGIC_SWAPPED = 0xde120495


def gnu_hash(key):
    """
    GNU gettext ``hash_string()`` over encoded key bytes. Like the C
    original, the hash stops at the first NUL byte.
    """
    hval = 0
    for byte in bytearray(key):
        if byte == 0:
            break
        hval = (hval << 4) + byte
        g = hval & 0xf0000000
        if g != 0:
            hval ^= g >> 24
            hval ^= g
        hval &= 0xffffffff
    return hval


class MoLookup(object):
    """
    Minimal mo reader resolving keys through the GNU hash table.

    ``data`` is the raw mo file content as bytes. ``last_probes`` holds
    the number of hash-table slots inspected by the most recent lookup.
    """

    def __init__(self, data):
        magic = struct.unpack('<I', data[:4])[0]
        if magic == _MAGIC:
            self._order = '<'
        elif magic == _MAGIC_SWAPPED:
            self._order = '>'
        else:
            raise ValueError('bad magic number')
        (self.nstrings,
         self._orig_off,
         self._trans_off,
         self.hash_size,
         self._hash_off) = struct.unpack(self._order + '5I', data[8:28])
        self._data = data
        self.last_probes = 0

    @classmethod
    def from_file(cls, fpath):
        with open(fpath, 'rb') as fhandle:
            return cls(fhandle.read())

    def _word(self, offset):
        return struct.unpack(
            self._order + 'I', self._data[offset:offset + 4])[0]

    def _entry(self, index):
        data = self._data
        olen, ooff = struct.unpack(
            self._order + '2I', data[self._orig_off + index * 8:
                                     self._orig_off + index * 8 + 8])
        tlen, toff = struct.unpack(
            self._order + '2I', data[self._trans_off + index * 8:
                                     self._trans_off + index * 8 + 8])
        return data[ooff:ooff + olen], data[toff:toff + tlen]

    @staticmethod
    def _matches(stored_key, key):
        # Like the gettext runtime, the stored original is compared up to
        # its first NUL byte, so plural originals ("singular\0plural")
        # match a lookup of the singular form.
        return stored_key.split(b'\0', 1)[0] == key

    def lookup(self, key):
        """
        Return the translation bytes for ``key`` (the encoded msgid,
        including any msgctxt <EOT> prefix), or None if the key is not in
        the catalog. Hash-table lookups perform at most ``hash_size``
        probes; catalogs without a hash table are scanned linearly.
        """
        self.last_probes = 0
        if self.hash_size:
            size = self.hash_size
            hval = gnu_hash(key)
            idx = hval % size
            incr = 1 + (hval % (size - 2))
            for _ in range(size):
                self.last_probes += 1
                nstr = self._word(self._hash_off + idx * 4)
                if nstr == 0:
                    return None  # empty slot: key not in catalog
                orig, trans = self._entry(nstr - 1)
                if self._matches(orig, key):
                    return trans
                idx += incr
                if idx >= size:
                    idx -= size
            return None
        for index in range(self.nstrings):
            self.last_probes += 1
            orig, trans = self._entry(index)
            if self._matches(orig, key):
                return trans
        return None
