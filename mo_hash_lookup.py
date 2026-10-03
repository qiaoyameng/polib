# -*- coding: utf-8 -*-
#
# License: MIT (see LICENSE file provided)
# vim: set expandtab tabstop=4 shiftwidth=4 softtabstop=4:

"""
Minimal .mo reader that resolves translations through the GNU gettext
hash table.

This module is intentionally independent from polib's .mo writer: it
implements the "PJW" hash function and the open addressing probing
sequence on its own, so it can be used to check .mo files produced with
``with_hash_table=True``.
"""

import re
import struct


class MOHashLookup(object):
    """
    Looks up translations in a .mo file using its hash table.

    ``mofile`` may be a file path, a file object or a bytes string.
    Both little and big endian files are supported.
    """

    def __init__(self, mofile, encoding=None):
        if hasattr(mofile, 'read'):
            data = mofile.read()
        elif isinstance(mofile, bytes):
            data = mofile
        else:
            with open(mofile, 'rb') as fhandle:
                data = fhandle.read()
        magic = struct.unpack('<I', data[:4])[0]
        if magic == 0x950412de:
            byte_order = '<'
        elif magic == 0xde120495:
            byte_order = '>'
        else:
            raise IOError('Invalid mo file, magic number is incorrect !')
        (
            _version,
            num_strings,
            msgids_offset,
            msgstrs_offset,
            hash_size,
            hash_offset,
        ) = struct.unpack(byte_order + '6I', data[4:28])
        if hash_size == 0:
            raise ValueError('The mo file does not contain a hash table')
        self.hash_size = hash_size
        self.hash_table = struct.unpack(
            byte_order + '%dI' % hash_size,
            data[hash_offset:hash_offset + 4 * hash_size]
        )
        self._entries = []
        for i in range(num_strings):
            klen, koff = struct.unpack(
                byte_order + '2I', data[msgids_offset + 8 * i:][:8]
            )
            vlen, voff = struct.unpack(
                byte_order + '2I', data[msgstrs_offset + 8 * i:][:8]
            )
            self._entries.append((
                data[koff:koff + klen],
                data[voff:voff + vlen]
            ))
        self.encoding = encoding or self._detect_encoding()

    def lookup(self, msgid, msgctxt=None, msgid_plural=None):
        """
        Returns the translation stored for ``msgid`` (a list of plural
        forms for plural entries), or ``None`` if the key is not present
        in the hash table.
        """
        key = self._encode_key(msgid, msgctxt, msgid_plural)
        hash_value = self._hash(key)
        index = hash_value % self.hash_size
        step = 1 + (hash_value % (self.hash_size - 2))
        # probing always terminates: either on an empty slot or, in the
        # worst case, after hash_size steps
        for _probe in range(self.hash_size):
            entry_number = self.hash_table[index]
            if entry_number == 0:
                return None
            stored_key, stored_value = self._entries[entry_number - 1]
            if stored_key == key:
                if b'\0' in stored_key:
                    return [
                        plural.decode(self.encoding)
                        for plural in stored_value.split(b'\0')
                    ]
                return stored_value.decode(self.encoding)
            index = (index + step) % self.hash_size
        return None

    def _encode_key(self, msgid, msgctxt, msgid_plural):
        """
        Builds the lookup key bytes exactly as they are stored in the .mo
        string table: optional context followed by an EOT byte, then the
        msgid, then a NUL byte and the plural msgid for plural entries.
        """
        key = ''
        if msgctxt:
            key += msgctxt + '\4'
        key += msgid
        if msgid_plural:
            key += '\0' + msgid_plural
        return key.encode(self.encoding)

    def _detect_encoding(self):
        """
        Returns the charset declared in the metadata entry, defaulting to
        utf-8.
        """
        for key, value in self._entries:
            if key == b'':
                match = re.search(br'charset=([\w-]+)', value)
                if match:
                    return match.group(1).decode('ascii')
        return 'utf-8'

    @staticmethod
    def _hash(key):
        """
        GNU gettext "PJW" hash of the given byte string.
        """
        hash_value = 0
        for char in key:
            if not isinstance(char, int):
                char = ord(char)
            hash_value = (hash_value << 4) + char
            g = hash_value & 0xf0000000
            if g != 0:
                hash_value ^= g >> 24
                hash_value ^= g
        return hash_value & 0xffffffff
