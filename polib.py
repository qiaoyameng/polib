# -* coding: utf-8 -*-
#
# License: MIT (see LICENSE file provided)
# vim: set expandtab tabstop=4 shiftwidth=4 softtabstop=4:

"""
**polib** allows you to manipulate, create, modify gettext files (pot, po and
mo files).  You can load existing files, iterate through it's entries, add,
modify entries, comments or metadata, etc. or create new po files from scratch.

**polib** provides a simple and pythonic API via the :func:`~polib.pofile` and
:func:`~polib.mofile` convenience functions.
"""

import array
import codecs
import copy
import hashlib
import json
import os
import re
import struct
import sys
import textwrap
import io


__author__ = 'David Jean Louis <izimobil@gmail.com>'
__version__ = '1.2.0'
__all__ = ['pofile', 'POFile', 'POEntry', 'mofile', 'MOFile', 'MOEntry',
           'default_encoding', 'escape', 'unescape', 'detect_encoding', ]
__all__.extend([
    'split_pofile', 'collect_pofile',
    'PO_ASSIGNMENT_MANIFEST_VERSION',
    'PO_ASSIGNMENT_MANIFEST_FILENAME',
])

PO_ASSIGNMENT_MANIFEST_VERSION = 1
PO_ASSIGNMENT_MANIFEST_FILENAME = 'polib-assignment-manifest.json'


# the default encoding to use when encoding cannot be detected
default_encoding = 'utf-8'

# python 2/3 compatibility helpers {{{


if sys.version_info < (3,):
    PY3 = False
    text_type = unicode

    def b(s):
        return s

    def u(s):
        return unicode(s, "unicode_escape")

else:
    PY3 = True
    text_type = str

    def b(s):
        return s.encode("latin-1")

    def u(s):
        return s
# }}}
# _pofile_or_mofile {{{


def _pofile_or_mofile(f, type, **kwargs):
    """
    Internal function used by :func:`polib.pofile` and :func:`polib.mofile` to
    honor the DRY concept.
    """
    # get the file encoding
    enc = kwargs.get('encoding')
    if enc is None:
        enc = detect_encoding(f, type == 'mofile')

    # parse the file
    kls = type == 'pofile' and _POFileParser or _MOFileParser
    parser = kls(
        f,
        encoding=enc,
        check_for_duplicates=kwargs.get('check_for_duplicates', False),
        klass=kwargs.get('klass')
    )
    instance = parser.parse()
    instance.wrapwidth = kwargs.get('wrapwidth', 78)
    return instance
# }}}
# _is_file {{{


def _is_file(filename_or_contents):
    """
    Safely returns the value of os.path.exists(filename_or_contents).

    Arguments:

    ``filename_or_contents``
        either a filename, or a string holding the contents of some file.
        In the latter case, this function will always return False.
    """
    if not isinstance(filename_or_contents, (str, bytes) if PY3
                      else (basestring,)):
        return False
    try:
        return os.path.isfile(filename_or_contents)
    except (TypeError, ValueError, UnicodeEncodeError):
        return False
# }}}
# function pofile() {{{


def pofile(pofile, **kwargs):
    """
    Convenience function that parses the po or pot file ``pofile`` and returns
    a :class:`~polib.POFile` instance.

    Arguments:

    ``pofile``
        string, full or relative path to the po/pot file or its content (data).

    ``wrapwidth``
        integer, the wrap width, only useful when the ``-w`` option was passed
        to xgettext (optional, default: ``78``).

    ``encoding``
        string, the encoding to use (e.g. "utf-8") (default: ``None``, the
        encoding will be auto-detected).

    ``check_for_duplicates``
        whether to check for duplicate entries when adding entries to the
        file (optional, default: ``False``).

    ``klass``
        class which is used to instantiate the return value (optional,
        default: ``None``, the return value with be a :class:`~polib.POFile`
        instance).
    """
    return _pofile_or_mofile(pofile, 'pofile', **kwargs)
# }}}
# function mofile() {{{


def mofile(mofile, **kwargs):
    """
    Convenience function that parses the mo file ``mofile`` and returns a
    :class:`~polib.MOFile` instance.

    Arguments:

    ``mofile``
        string, full or relative path to the mo file or its content (string
        or bytes).

    ``wrapwidth``
        integer, the wrap width, only useful when the ``-w`` option was passed
        to xgettext to generate the po file that was used to format the mo file
        (optional, default: ``78``).

    ``encoding``
        string, the encoding to use (e.g. "utf-8") (default: ``None``, the
        encoding will be auto-detected).

    ``check_for_duplicates``
        whether to check for duplicate entries when adding entries to the
        file (optional, default: ``False``).

    ``klass``
        class which is used to instantiate the return value (optional,
        default: ``None``, the return value with be a :class:`~polib.POFile`
        instance).
    """
    return _pofile_or_mofile(mofile, 'mofile', **kwargs)
# }}}
# function detect_encoding() {{{


def detect_encoding(file, binary_mode=False):
    """
    Try to detect the encoding used by the ``file``. The ``file`` argument can
    be a PO or MO file path or a string containing the contents of the file.
    If the encoding cannot be detected, the function will return the value of
    ``default_encoding``.

    Arguments:

    ``file``
        string, full or relative path to the po/mo file or its content.

    ``binary_mode``
        boolean, set this to True if ``file`` is a mo file.
    """
    PATTERN = r'"?Content-Type:.+? charset=([\w_\-:\.]+)'
    rxt = re.compile(u(PATTERN))
    rxb = re.compile(b(PATTERN))

    def charset_exists(charset):
        """Check whether ``charset`` is valid or not."""
        try:
            codecs.lookup(charset)
        except LookupError:
            return False
        return True

    if not _is_file(file):
        try:
            match = rxt.search(file)
        except TypeError:
            match = rxb.search(file)
        if match:
            enc = match.group(1).strip()
            if not isinstance(enc, text_type):
                enc = enc.decode('utf-8')
            if charset_exists(enc):
                return enc
    else:
        # For PY3, always treat as binary
        if binary_mode or PY3:
            mode = 'rb'
            rx = rxb
        else:
            mode = 'r'
            rx = rxt
        with open(file, mode) as f:
            for line in f.readlines():
                match = rx.search(line)
                if match:
                    f.close()
                    enc = match.group(1).strip()
                    if not isinstance(enc, text_type):
                        enc = enc.decode('utf-8')
                    if charset_exists(enc):
                        return enc
    return default_encoding
# }}}
# function escape() {{{


def escape(st):
    """
    Escapes the characters ``\\\\``, ``\\t``, ``\\n``, ``\\r``, ``\\v``,
    ``\\b``, ``\\f``, ``\\a`` and ``"`` in the given string ``st`` and returns it.
    """
    return st.replace('\\', r'\\')\
             .replace('\t', r'\t')\
             .replace('\r', r'\r')\
             .replace('\n', r'\n')\
             .replace('\v', r'\v')\
             .replace('\b', r'\b')\
             .replace('\f', r'\f')\
             .replace('\a', r'\a')\
             .replace('\"', r'\"')
# }}}
# function unescape() {{{


def unescape(st):
    """
    Unescapes the characters ``\\\\``, ``\\t``, ``\\n``, ``\\r``, ``\\v``,
    ``\\b``, ``\\f``, ``\\a`` and ``"`` in the given string ``st`` and returns it.
    """
    def unescape_repl(m):
        m = m.group(1)
        if m == 'n':
            return '\n'
        if m == 't':
            return '\t'
        if m == 'r':
            return '\r'
        if m == 'v':
            return '\v'
        if m == 'b':
            return '\b'
        if m == 'f':
            return '\f'
        if m == 'a':
            return '\a'
        if m == '\\':
            return '\\'
        return m  # handles escaped double quote
    return re.sub(r'\\(\\|n|t|r|v|b|f|a|")', unescape_repl, st)
# }}}
# function natural_sort() {{{


def natural_sort(lst):
    """
    Sort naturally the given list.
    Credits: http://stackoverflow.com/a/4836734
    """
    def convert(text):
        return int(text) if text.isdigit() else text.lower()

    def alphanum_key(key):
        return [convert(c) for c in re.split('([0-9]+)', key)]

    return sorted(lst, key=alphanum_key)

# }}}
# class _BaseFile {{{


class _BaseFile(list):
    """
    Common base class for the :class:`~polib.POFile` and :class:`~polib.MOFile`
    classes. This class should **not** be instantiated directly.
    """

    def __init__(self, *args, **kwargs):
        """
        Constructor, accepts the following keyword arguments:

        ``pofile``
            string, the path to the po or mo file, or its content as a string.

        ``wrapwidth``
            integer, the wrap width, only useful when the ``-w`` option was
            passed to xgettext (optional, default: ``78``).

        ``encoding``
            string, the encoding to use, defaults to ``default_encoding``
            global variable (optional).

        ``check_for_duplicates``
            whether to check for duplicate entries when adding entries to the
            file, (optional, default: ``False``).
        """
        list.__init__(self)
        # the opened file handle
        pofile = kwargs.get('pofile', None)
        if pofile and _is_file(pofile):
            self.fpath = pofile
        else:
            self.fpath = kwargs.get('fpath')
        # the width at which lines should be wrapped
        self.wrapwidth = kwargs.get('wrapwidth', 78)
        # the file encoding
        self.encoding = kwargs.get('encoding', default_encoding)
        # whether to check for duplicate entries or not
        self.check_for_duplicates = kwargs.get('check_for_duplicates', False)
        # header
        self.header = ''
        # both po and mo files have metadata
        self.metadata = {}
        self.metadata_is_fuzzy = 0

    def __unicode__(self):
        """
        Returns the unicode representation of the file.
        """
        ret = []
        entries = [self.metadata_as_entry()] + \
                  [e for e in self if not e.obsolete]
        for entry in entries:
            ret.append(entry.__unicode__(self.wrapwidth))
        for entry in self.obsolete_entries():
            ret.append(entry.__unicode__(self.wrapwidth))
        ret = u('\n').join(ret)
        return ret

    if PY3:
        def __str__(self):
            return self.__unicode__()
    else:
        def __str__(self):
            """
            Returns the string representation of the file.
            """
            return unicode(self).encode(self.encoding)

    def __contains__(self, entry):
        """
        Overridden ``list`` method to implement the membership test (in and
        not in).
        The method considers that an entry is in the file if it finds an entry
        that has the same msgid (the test is **case sensitive**) and the same
        msgctxt (or none for both entries).

        Argument:

        ``entry``
            an instance of :class:`~polib._BaseEntry`.
        """
        return self.find(entry.msgid, by='msgid', msgctxt=entry.msgctxt) \
            is not None

    def __eq__(self, other):
        return str(self) == str(other)

    def append(self, entry):
        """
        Overridden method to check for duplicates entries, if a user tries to
        add an entry that is already in the file, the method will raise a
        ``ValueError`` exception.

        Argument:

        ``entry``
            an instance of :class:`~polib._BaseEntry`.
        """
        # check_for_duplicates may not be defined (yet) when unpickling.
        # But if pickling, we never want to check for duplicates anyway.
        if getattr(self, 'check_for_duplicates', False) and entry in self:
            raise ValueError('Entry "%s" already exists' % entry.msgid)
        super(_BaseFile, self).append(entry)

    def insert(self, index, entry):
        """
        Overridden method to check for duplicates entries, if a user tries to
        add an entry that is already in the file, the method will raise a
        ``ValueError`` exception.

        Arguments:

        ``index``
            index at which the entry should be inserted.

        ``entry``
            an instance of :class:`~polib._BaseEntry`.
        """
        if self.check_for_duplicates and entry in self:
            raise ValueError('Entry "%s" already exists' % entry.msgid)
        super(_BaseFile, self).insert(index, entry)

    def metadata_as_entry(self):
        """
        Returns the file metadata as a :class:`~polib.POFile` instance.
        """
        e = POEntry(msgid='')
        mdata = self.ordered_metadata()
        if mdata:
            strs = []
            for name, value in mdata:
                # Strip whitespace off each line in a multi-line entry
                strs.append('%s: %s' % (name, value))
            e.msgstr = '\n'.join(strs) + '\n'
        if self.metadata_is_fuzzy:
            e.flags.append('fuzzy')
        return e

    def save(self, fpath=None, repr_method='__unicode__', newline=None):
        """
        Saves the po file to ``fpath``.
        If it is an existing file and no ``fpath`` is provided, then the
        existing file is rewritten with the modified data.

        Keyword arguments:

        ``fpath``
            string, full or relative path to the file.

        ``repr_method``
            string, the method to use for output.

        ``newline``
            string, controls how universal newlines works
        """
        if self.fpath is None and fpath is None:
            raise IOError('You must provide a file path to save() method')
        contents = getattr(self, repr_method)()
        if fpath is None:
            fpath = self.fpath
        if repr_method == 'to_binary':
            with open(fpath, 'wb') as fhandle:
                fhandle.write(contents)
        else:
            with io.open(
                fpath,
                'w',
                encoding=self.encoding,
                newline=newline
            ) as fhandle:
                if not isinstance(contents, text_type):
                    contents = contents.decode(self.encoding)
                fhandle.write(contents)

        # set the file path if not set
        if self.fpath is None and fpath:
            self.fpath = fpath

    def find(self, st, by='msgid', include_obsolete_entries=False,
             msgctxt=False):
        """
        Find the entry which msgid (or property identified by the ``by``
        argument) matches the string ``st``.

        Keyword arguments:

        ``st``
            string, the string to search for.

        ``by``
            string, the property to use for comparison (default: ``msgid``).

        ``include_obsolete_entries``
            boolean, whether to also search in entries that are obsolete.

        ``msgctxt``
            string, allows specifying a specific message context for the
            search.
        """
        if include_obsolete_entries:
            entries = self[:]
        else:
            entries = [e for e in self if not e.obsolete]
        matches = []
        for e in entries:
            if getattr(e, by) == st:
                if msgctxt is not False and e.msgctxt != msgctxt:
                    continue
                matches.append(e)
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            if not msgctxt:
                # find the entry with no msgctx
                e = None
                for m in matches:
                    if not m.msgctxt:
                        e = m
                if e:
                    return e
                # fallback to the first entry found
                return matches[0]
        return None

    def ordered_metadata(self):
        """
        Convenience method that returns an ordered version of the metadata
        dictionary. The return value is list of tuples (metadata name,
        metadata_value).
        """
        # copy the dict first
        metadata = self.metadata.copy()
        data_order = [
            'Project-Id-Version',
            'Report-Msgid-Bugs-To',
            'POT-Creation-Date',
            'PO-Revision-Date',
            'Last-Translator',
            'Language-Team',
            'Language',
            'MIME-Version',
            'Content-Type',
            'Content-Transfer-Encoding',
            'Plural-Forms'
        ]
        ordered_data = []
        for data in data_order:
            try:
                value = metadata.pop(data)
                ordered_data.append((data, value))
            except KeyError:
                pass
        # the rest of the metadata will be alphabetically ordered since there
        # are no specs for this AFAIK
        for data in natural_sort(metadata.keys()):
            value = metadata[data]
            ordered_data.append((data, value))
        return ordered_data

    def to_binary(self):
        """
        Return the binary representation of the file.
        """
        offsets = []
        entries = self.translated_entries()

        # the keys are sorted in the .mo file
        def cmp(_self, other):
            # msgfmt compares entries with msgctxt if it exists
            self_msgid = _self.msgctxt and _self.msgctxt or _self.msgid
            other_msgid = other.msgctxt and other.msgctxt or other.msgid
            if self_msgid > other_msgid:
                return 1
            elif self_msgid < other_msgid:
                return -1
            else:
                return 0
        # add metadata entry
        entries.sort(key=lambda o: o.msgid_with_context.encode('utf-8'))
        mentry = self.metadata_as_entry()
        entries = [mentry] + entries
        entries_len = len(entries)
        ids, strs = b(''), b('')
        for e in entries:
            # For each string, we need size and file offset.  Each string is
            # NUL terminated; the NUL does not count into the size.
            msgid = b('')
            if e.msgctxt:
                # Contexts are stored by storing the concatenation of the
                # context, a <EOT> byte, and the original string
                msgid = self._encode(e.msgctxt + '\4')
            if e.msgid_plural:
                msgstr = []
                for index in sorted(e.msgstr_plural.keys()):
                    msgstr.append(e.msgstr_plural[index])
                msgid += self._encode(e.msgid + '\0' + e.msgid_plural)
                msgstr = self._encode('\0'.join(msgstr))
            else:
                msgid += self._encode(e.msgid)
                msgstr = self._encode(e.msgstr)
            offsets.append((len(ids), len(msgid), len(strs), len(msgstr)))
            ids += msgid + b('\0')
            strs += msgstr + b('\0')

        # The header is 7 32-bit unsigned integers.
        keystart = 7 * 4 + 16 * entries_len
        # and the values start after the keys
        valuestart = keystart + len(ids)
        koffsets = []
        voffsets = []
        # The string table first has the list of keys, then the list of values.
        # Each entry has first the size of the string, then the file offset.
        for o1, l1, o2, l2 in offsets:
            koffsets += [l1, o1 + keystart]
            voffsets += [l2, o2 + valuestart]
        offsets = koffsets + voffsets

        output = struct.pack(
            "Iiiiiii",
            # Magic number
            MOFile.MAGIC,
            # Version
            0,
            # number of entries
            entries_len,
            # start of key index
            7 * 4,
            # start of value index
            7 * 4 + entries_len * 8,
            # size and offset of hash table, we don't use hash tables
            0, keystart

        )
        if PY3 and sys.version_info.minor > 1:  # python 3.2 or superior
            output += array.array("i", offsets).tobytes()
        else:
            output += array.array("i", offsets).tostring()
        output += ids
        output += strs
        return output

    def _encode(self, mixed):
        """
        Encodes the given ``mixed`` argument with the file encoding if and
        only if it's an unicode string and returns the encoded string.
        """
        if isinstance(mixed, text_type):
            mixed = mixed.encode(self.encoding)
        return mixed
# }}}
# class POFile {{{


class POFile(_BaseFile):
    """
    Po (or Pot) file reader/writer.
    This class inherits the :class:`~polib._BaseFile` class and, by extension,
    the python ``list`` type.
    """

    def __unicode__(self):
        """
        Returns the unicode representation of the po file.
        """
        ret, headers = '', self.header.split('\n')
        for header in headers:
            if not len(header):
                ret += "#\n"
            elif header[:1] in [',', ':']:
                ret += '#%s\n' % header
            else:
                ret += '# %s\n' % header

        if not isinstance(ret, text_type):
            ret = ret.decode(self.encoding)

        return ret + _BaseFile.__unicode__(self)

    def save_as_mofile(self, fpath):
        """
        Saves the binary representation of the file to given ``fpath``.

        Keyword argument:

        ``fpath``
            string, full or relative path to the mo file.
        """
        _BaseFile.save(self, fpath, 'to_binary')

    def percent_translated(self):
        """
        Convenience method that returns the percentage of translated
        messages.
        """
        total = len([e for e in self if not e.obsolete])
        if total == 0:
            return 100
        translated = len(self.translated_entries())
        return int(translated * 100 / float(total))

    def translated_entries(self):
        """
        Convenience method that returns the list of translated entries.
        """
        return [e for e in self if e.translated()]

    def untranslated_entries(self):
        """
        Convenience method that returns the list of untranslated entries.
        """
        return [e for e in self if not e.translated() and not e.obsolete
                and not e.fuzzy]

    def fuzzy_entries(self):
        """
        Convenience method that returns the list of fuzzy entries.
        """
        return [e for e in self if e.fuzzy and not e.obsolete]

    def obsolete_entries(self):
        """
        Convenience method that returns the list of obsolete entries.
        """
        return [e for e in self if e.obsolete]

    def merge(self, refpot):
        """
        Convenience method that merges the current pofile with the pot file
        provided. It behaves exactly as the gettext msgmerge utility:

        * comments of this file will be preserved, but extracted comments and
          occurrences will be discarded;
        * any translations or comments in the file will be discarded, however,
          dot comments and file positions will be preserved;
        * the fuzzy flags are preserved.

        Keyword argument:

        ``refpot``
            object POFile, the reference catalog.
        """
        # Store entries in dict/set for faster access
        self_entries = dict(
            (entry.msgid_with_context, entry) for entry in self
        )
        refpot_msgids = set(entry.msgid_with_context for entry in refpot)
        # Merge entries that are in the refpot
        for entry in refpot:
            e = self_entries.get(entry.msgid_with_context)
            if e is None:
                e = POEntry()
                self.append(e)
            e.merge(entry)
        # ok, now we must "obsolete" entries that are not in the refpot anymore
        for entry in self:
            if entry.msgid_with_context not in refpot_msgids:
                entry.obsolete = True


def split_pofile(source_path, output_dir, group_for_entry, groups=None,
                 manifest_path=PO_ASSIGNMENT_MANIFEST_FILENAME,
                 filename_template='{group}.po', unassigned_groups=None,
                 wrapwidth=78):
    """
    Split a PO catalog into one or more team packages.

    ``group_for_entry`` is called once for each non-header entry. It receives
    a :class:`POEntry` and must return a group name, an iterable of group
    names, or ``None``. Groups can inspect ``entry.occurrences`` to allocate
    work by source path. Returning several groups puts the same original entry
    in several packages; the manifest keeps the shared identity.

    The function writes one PO file per group and a JSON manifest. It returns
    the manifest as a dictionary.
    """
    source_path = os.fspath(source_path) if hasattr(os, 'fspath') else source_path
    if not os.path.isfile(source_path):
        raise IOError('PO file not found: %s' % source_path)

    source_bytes = _read_binary_file(source_path)
    source_checksum = _sha256(source_bytes)
    source = pofile(source_path, wrapwidth=wrapwidth)
    source_metadata = _source_compatibility(source)

    if unassigned_groups is None:
        unassigned_groups = []
    if groups is None:
        explicit_groups = None
        resolved_groups = set()
    else:
        explicit_groups = True
        resolved_groups = set(_validate_group_name(group) for group in groups)

    assignments = []
    seen_identities = set()
    grouped_entries = {}

    for index, entry in enumerate(source):
        identity = _entry_identity(entry)
        if identity in seen_identities:
            raise ValueError('Duplicate PO identity: %s' % identity)
        seen_identities.add(identity)

        if entry.msgid_plural and source_metadata['plural_forms']:
            _validate_plural_entry(entry, source_metadata['plural_forms'])

        entry_groups = _groups_for_entry(group_for_entry, entry,
                                         unassigned_groups,
                                         resolved_groups if explicit_groups
                                         else None)
        for group in entry_groups:
            _validate_group_name(group)
            resolved_groups.add(group)
            grouped_entries.setdefault(group, []).append(entry)

        assignments.append({
            'identity': identity,
            'index': index,
            'msgctxt': entry.msgctxt,
            'msgid': entry.msgid,
            'msgid_plural': entry.msgid_plural,
            'translation': _translation_as_json(entry),
            'occurrences': _occurrences_as_json(entry.occurrences),
            'groups': sorted(set(entry_groups)),
        })

    ordered_groups = sorted(resolved_groups)
    if explicit_groups and not ordered_groups:
        raise ValueError('At least one group is required')

    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    manifest_abs_path = _resolve_manifest_path(output_dir, manifest_path)
    if os.path.abspath(manifest_abs_path) == os.path.abspath(source_path):
        raise ValueError('The manifest path must not be the source PO file')

    group_records = []
    package_paths = set()
    for group in ordered_groups:
        package_rel_path = filename_template.format(group=group)
        package_path = os.path.join(output_dir, package_rel_path)
        _ensure_within_directory(output_dir, package_path)
        if package_path in package_paths:
            raise ValueError('Package file name template resolves duplicate paths')
        package_paths.add(package_path)
        if os.path.abspath(package_path) == os.path.abspath(source_path):
            raise ValueError('A package path must not be the source PO file')
        if os.path.abspath(package_path) == manifest_abs_path:
            raise ValueError('A package path must not be the manifest')

        package_directory = os.path.dirname(package_path)
        if not os.path.isdir(package_directory):
            os.makedirs(package_directory)
        package = _new_catalog_like(source)
        for entry in grouped_entries.get(group, []):
            package.append(copy.deepcopy(entry))
        package.save(package_path)
        group_records.append({
            'name': group,
            'file': package_rel_path.replace(os.sep, '/'),
            'entry_count': len(grouped_entries.get(group, [])),
        })

    source_path_abs = os.path.abspath(source_path)
    manifest = {
        'version': PO_ASSIGNMENT_MANIFEST_VERSION,
        'source': {
            'path': source_path,
            'absolute_path': source_path_abs,
            'relative_path': os.path.relpath(source_path_abs, output_dir),
            'checksum_sha256': source_checksum,
            'size': len(source_bytes),
        },
        'encoding': source.encoding,
        'language': source_metadata['language'],
        'plural_forms': source_metadata['plural_forms'],
        'header': source.header,
        'metadata': source.ordered_metadata(),
        'metadata_is_fuzzy': list(source.metadata_is_fuzzy),
        'wrapwidth': wrapwidth,
        'source_directories': _source_directories(source),
        'occurrence_paths': _occurrence_paths(source),
        'groups': group_records,
        'assignments': assignments,
    }
    _write_json(manifest_abs_path, manifest)
    return manifest


def collect_pofile(manifest, output_path, report_path=None, wrapwidth=None):
    """
    Collect team packages described by ``manifest`` into one release catalog.

    ``manifest`` may be a manifest path or the dictionary returned by
    :func:`split_pofile`. Translation conflicts are never resolved by package
    file order: conflicting entries retain the source translation and are
    listed in the returned report. Comments, occurrences and flags are merged
    as sorted, de-duplicated unions.

    The return value contains the output path, report path, per-entry statuses
    and all compatibility/missing-package/source-change reports.
    """
    manifest_dir = '.'
    manifest_file_path = None
    if not isinstance(manifest, dict):
        manifest_path = os.fspath(manifest) if hasattr(os, 'fspath') else manifest
        with io.open(manifest_path, 'r', encoding='utf-8') as handle:
            manifest = json.load(handle)
        manifest_file_path = os.path.abspath(manifest_path)
        manifest_dir = os.path.dirname(manifest_file_path)

    _validate_manifest(manifest)
    output_path = os.path.abspath(output_path)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
    if report_path is None:
        report_path = os.path.splitext(output_path)[0] + '.report.json'
    report_path = os.path.abspath(report_path)

    source_path = _resolve_source_path(manifest, manifest_dir)
    source = None
    source_checksum = None
    reports = []
    source_changed = False
    source_missing = False

    if source_path and os.path.isfile(source_path):
        source_bytes = _read_binary_file(source_path)
        source_checksum = _sha256(source_bytes)
        if source_checksum != manifest['source']['checksum_sha256']:
            source_changed = True
            reports.append(_report(
                'source-changed',
                'The source PO catalog changed after splitting.',
                source_path=source_path
            ))
        source = pofile(source_path, wrapwidth=manifest.get('wrapwidth', 78))
        actual_directories = _source_directories(source)
        if actual_directories != manifest['source_directories']:
            reports.append(_report(
                'source-directories-changed',
                'Occurrence source directories no longer match the manifest.',
                expected=manifest['source_directories'],
                actual=actual_directories
            ))
    else:
        source_missing = True
        reports.append(_report(
            'source-missing',
            'The source PO catalog used for splitting is unavailable.',
            source_path=source_path
        ))

    source_entries = {}
    if source is not None:
        for entry in source:
            identity = _entry_identity(entry)
            if identity in source_entries:
                reports.append(_report(
                    'duplicate-source-identity',
                    'The changed source catalog contains a duplicate identity.',
                    identity=identity
                ))
            else:
                source_entries[identity] = entry

    expected_identities = [item['identity'] for item in manifest['assignments']]
    expected_set = set(expected_identities)
    for identity in sorted(set(source_entries) - expected_set):
        reports.append(_report(
            'source-entry-added',
            'The changed source catalog contains an entry absent from the manifest.',
            identity=identity
        ))

    package_copies = {}
    package_status = {}
    group_records = dict((record['name'], record)
                         for record in manifest['groups'])
    for group_record in manifest['groups']:
        group = group_record['name']
        package_rel_path = group_record['file']
        package_path = os.path.join(manifest_dir, package_rel_path)
        _ensure_within_directory(manifest_dir, package_path)
        if not os.path.isfile(package_path):
            package_status[group] = 'missing'
            reports.append(_report(
                'package-missing',
                'An assigned team package is missing.',
                group=group,
                path=package_rel_path
            ))
            continue

        package = pofile(package_path,
                         wrapwidth=manifest.get('wrapwidth', 78))
        compatibility = _package_compatibility(package, manifest)
        for issue in compatibility:
            issue['group'] = group
            reports.append(issue)

        entries = {}
        for entry in package:
            identity = _entry_identity(entry)
            if identity not in expected_set:
                reports.append(_report(
                    'package-unknown-entry',
                    'A package contains an identity absent from the manifest.',
                    group=group,
                    identity=identity
                ))
                continue
            if identity in entries:
                reports.append(_report(
                    'duplicate-package-identity',
                    'A package contains the same identity more than once.',
                    group=group,
                    identity=identity
                ))
                continue
            entries[identity] = entry
        package_copies[group] = entries
        package_status[group] = 'present'

    result = _new_catalog_from_manifest(manifest, wrapwidth)
    entry_statuses = []
    manifest_entries = dict((item['identity'], item)
                            for item in manifest['assignments'])

    for assignment in manifest['assignments']:
        identity = assignment['identity']
        source_entry = source_entries.get(identity)
        if source is not None and source_entry is None:
            reports.append(_report(
                'source-entry-missing',
                'The changed source catalog no longer contains a manifest entry.',
                identity=identity
            ))

        merged_entry, decision = _merged_entry(
            assignment, source_entry, manifest, package_copies, reports
        )
        result.append(merged_entry)

        copies = []
        for group in [record['name'] for record in manifest['groups']]:
            if group in package_copies and identity in package_copies[group]:
                copies.append(group)
        if source is not None and source_entry is not None:
            actual_occurrences = _occurrences_as_json(source_entry.occurrences)
            if actual_occurrences != assignment['occurrences']:
                reports.append(_report(
                    'source-occurrences-changed',
                    'An entry occurrence changed after splitting.',
                    identity=identity,
                    expected=assignment['occurrences'],
                    actual=actual_occurrences
                ))

        entry_statuses.append({
            'identity': identity,
            'msgctxt': assignment['msgctxt'],
            'msgid': assignment['msgid'],
            'msgid_plural': assignment['msgid_plural'],
            'status': decision['status'],
            'groups': copies,
        })

    if source_path and os.path.abspath(output_path) == os.path.abspath(source_path):
        raise ValueError('The output path must not be the source PO file')
    if source_path and report_path == os.path.abspath(source_path):
        raise ValueError('The report path must not be the source PO file')
    if report_path == output_path:
        raise ValueError('The report path must not be the release PO file')
    if manifest_file_path and output_path == manifest_file_path:
        raise ValueError('The output path must not be the assignment manifest')
    if manifest_file_path and report_path == manifest_file_path:
        raise ValueError('The report path must not be the assignment manifest')
    package_paths = set()
    for record in manifest['groups']:
        package_paths.add(os.path.abspath(
            os.path.join(manifest_dir, record['file'])
        ))
    if output_path in package_paths:
        raise ValueError('The output path must not overwrite a team package')
    if report_path in package_paths:
        raise ValueError('The report path must not overwrite a team package')

    result.save(output_path)
    report = {
        'version': PO_ASSIGNMENT_MANIFEST_VERSION,
        'source_path': source_path,
        'source_checksum_sha256': source_checksum,
        'source_changed': source_changed,
        'source_missing': source_missing,
        'packages': package_status,
        'entries': entry_statuses,
        'reports': reports,
        'conflicts': [issue for issue in reports
                     if issue['code'] == 'translation-conflict'],
    }
    _write_json(report_path, report)
    report['output_path'] = output_path
    report['report_path'] = report_path
    return report


def _read_binary_file(path):
    with open(path, 'rb') as handle:
        return handle.read()


def _write_json(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        os.makedirs(directory)
    contents = json.dumps(
        data, sort_keys=True, indent=2, ensure_ascii=False
    ) + u('\n')
    with io.open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(contents)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _resolve_manifest_path(output_dir, manifest_path):
    if os.path.isabs(manifest_path):
        return manifest_path
    return os.path.join(output_dir, manifest_path)


def _resolve_source_path(manifest, manifest_dir):
    source = manifest['source']
    absolute_path = source.get('absolute_path')
    if absolute_path and os.path.isfile(absolute_path):
        return absolute_path
    relative_path = source.get('relative_path')
    if relative_path:
        candidate = os.path.abspath(os.path.join(manifest_dir, relative_path))
        if os.path.isfile(candidate):
            return candidate
    path = source.get('path')
    if path and os.path.isabs(path):
        return path
    return absolute_path or path or None


def _validate_group_name(group):
    if not isinstance(group, str if PY3 else basestring):
        raise ValueError('Group names must be strings')
    group = text_type(group)
    if not group:
        raise ValueError('Group names must not be empty')
    if group in ('.', '..') or group.startswith('.') or os.sep in group or \
       (os.altsep and os.altsep in group) or group.startswith('/'):
        raise ValueError('Invalid group name: %s' % group)
    if any(char in group for char in '\0\r\n'):
        raise ValueError('Invalid group name: %s' % group)
    return group


def _groups_for_entry(group_for_entry, entry, unassigned_groups,
                      allowed_groups=None):
    result = group_for_entry(entry)
    if result is None:
        result = unassigned_groups
    elif isinstance(result, str if PY3 else basestring):
        result = [result]
    groups = [_validate_group_name(group) for group in result]
    if not groups:
        return []
    if allowed_groups is not None:
        for group in groups:
            if group not in allowed_groups:
                raise ValueError('Entry assigned to undeclared group: %s' %
                                 group)
    return sorted(set(groups))


def _ensure_within_directory(directory, path):
    directory = os.path.abspath(directory)
    path = os.path.abspath(path)
    relative = os.path.relpath(path, directory)
    escapes = relative == os.pardir or \
        relative.startswith(os.pardir + os.sep)
    if os.path.altsep:
        escapes = escapes or relative.startswith(os.pardir + os.altsep)
    if escapes:
        raise ValueError('Path escapes its containing directory')
    return path


def _entry_identity(entry):
    payload = (
        entry.msgctxt,
        entry.msgid,
        entry.msgid_plural,
        bool(entry.msgid_plural or entry.msgstr_plural)
    )
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                            separators=(',', ':'))
    if not PY3 and isinstance(serialized, str):
        serialized = serialized.decode('utf-8')
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def _occurrences_as_json(occurrences):
    return [[path, text_type(line)] for path, line in occurrences]


def _translation_as_json(entry):
    if entry.msgid_plural:
        return dict((text_type(index), value)
                    for index, value in entry.msgstr_plural.items())
    return entry.msgstr


def _translation_as_json_payload(payload):
    if isinstance(payload, dict):
        return dict((text_type(index), value)
                    for index, value in payload.items())
    return payload


def _source_directories(pofile):
    directories = set()
    for entry in pofile:
        for path, line in entry.occurrences:
            directory = os.path.dirname(path)
            if directory:
                directories.add(directory)
    return sorted(directories)


def _occurrence_paths(pofile):
    paths = set()
    for entry in pofile:
        for path, line in entry.occurrences:
            paths.add(path)
    return sorted(paths)


def _canonical_charset(encoding):
    if not encoding:
        return None
    try:
        return codecs.lookup(encoding).name.lower()
    except LookupError:
        return None


def _content_type_charset(pofile):
    content_type = pofile.metadata.get('Content-Type', '')
    match = re.search(r'charset=([^;\s]+)', content_type, re.I)
    if not match:
        return None
    return match.group(1)


def _normalize_language(language):
    if not language:
        return None
    normalized = language.strip().replace('_', '-')
    normalized = re.sub(r'[^A-Za-z0-9-]', '-', normalized)
    parts = normalized.split('-')
    if not parts or not parts[0] or not parts[0].isalpha():
        return None
    return '-'.join(
        [parts[0].lower()] +
        [part.upper() if len(part) == 2 and index == 1 else
         part[0].upper() + part[1:].lower() if part.isalpha() else part
          for index, part in enumerate(parts[1:])]
    )


def _parse_plural_forms(value):
    if not value:
        return None
    nplurals_match = re.search(r'nplurals\s*=\s*([0-9]+)\s*;', value)
    plural_match = re.search(r'plural\s*=\s*(.*?)\s*;?\s*$', value,
                             re.S | re.I)
    if not nplurals_match or not plural_match:
        raise ValueError('Invalid Plural-Forms header: %s' % value)
    nplurals = int(nplurals_match.group(1))
    expression = plural_match.group(1).strip()
    if nplurals < 1 or not expression or expression.count('(') != \
       expression.count(')'):
        raise ValueError('Invalid Plural-Forms header: %s' % value)
    if not re.match(r'^[0-9n()?:<>=!&|% \t\r\n+\-*/.]+$', expression):
        raise ValueError('Unsupported Plural-Forms expression: %s' % expression)
    return {
        'raw': value,
        'nplurals': nplurals,
        'expression': re.sub(r'\s+', ' ', expression),
    }


def _validate_plural_entry(entry, plural_forms):
    keys = set(entry.msgstr_plural.keys())
    expected = set(range(plural_forms['nplurals']))
    if keys != expected:
        raise ValueError(
            'Plural entry "%s" uses %d forms, Plural-Forms declares %d' %
            (entry.msgid, len(keys), plural_forms['nplurals'])
        )


def _source_compatibility(pofile):
    charset = _content_type_charset(pofile)
    if charset and not _canonical_charset(charset):
        raise ValueError('Unknown source charset: %s' % charset)
    language = pofile.metadata.get('Language')
    if language and not _normalize_language(language):
        raise ValueError('Invalid Language header: %s' % language)
    plural_forms = _parse_plural_forms(pofile.metadata.get('Plural-Forms'))
    return {'language': language, 'plural_forms': plural_forms}


def _metadata_from_manifest(manifest):
    return dict((key, value) for key, value in manifest['metadata'])


def _new_catalog_from_manifest(manifest, wrapwidth):
    catalog = POFile(
        encoding=manifest['encoding'],
        wrapwidth=wrapwidth if wrapwidth is not None
        else manifest.get('wrapwidth', 78)
    )
    catalog.header = manifest.get('header', '')
    catalog.metadata = _metadata_from_manifest(manifest)
    catalog.metadata_is_fuzzy = list(manifest.get('metadata_is_fuzzy', []))
    return catalog


def _new_catalog_like(catalog):
    result = POFile(encoding=catalog.encoding, wrapwidth=catalog.wrapwidth)
    result.header = catalog.header
    result.metadata = catalog.metadata.copy()
    result.metadata_is_fuzzy = list(catalog.metadata_is_fuzzy)
    return result


def _validate_manifest(manifest):
    if manifest.get('version') != PO_ASSIGNMENT_MANIFEST_VERSION:
        raise ValueError('Unsupported assignment manifest version')
    for key in ('source', 'encoding', 'groups', 'assignments', 'metadata'):
        if key not in manifest:
            raise ValueError('Invalid assignment manifest: missing %s' % key)


def _report(code, message, **details):
    report = {'code': code, 'message': message}
    report.update(details)
    return report


def _translation_payload(entry):
    if entry.msgid_plural:
        return True, dict((int(index), value) for index, value
                          in entry.msgstr_plural.items())
    return False, entry.msgstr


def _baseline_translation(assignment):
    if assignment['msgid_plural']:
        return True, dict((int(index), value)
                          for index, value in
                          assignment.get('translation', {}).items())
    return False, assignment.get('translation', '')


def _apply_translation(entry, plural, payload):
    if plural:
        entry.msgstr = ''
        entry.msgstr_plural = dict(payload)
    else:
        entry.msgstr = payload
        entry.msgstr_plural = {}


def _placeholder_entry(assignment, manifest):
    plural_forms = manifest.get('plural_forms')
    kwargs = {
        'msgctxt': assignment['msgctxt'],
        'msgid': assignment['msgid'],
        'msgid_plural': assignment['msgid_plural'],
        'occurrences': [(path, line) for path, line
                        in assignment['occurrences']],
    }
    entry = POEntry(**kwargs)
    if assignment['msgid_plural'] and plural_forms:
        entry.msgstr_plural = dict(
            (index, '') for index in range(plural_forms['nplurals'])
        )
    plural, payload = _baseline_translation(assignment)
    _apply_translation(entry, plural, payload)
    return entry


def _merge_comments(existing, incoming):
    lines = []
    for value in [existing] + incoming:
        if value:
            lines.extend(value.split('\n'))
    seen = set()
    for line in lines:
        if line not in seen:
            seen.add(line)
    return '\n'.join(sorted(seen))


def _merge_flags(flags):
    values = set()
    for group_flags in flags:
        values.update(group_flags)
    return sorted(values)


def _package_compatibility(package, manifest):
    reports = []
    actual_charset = _canonical_charset(package.encoding)
    declared_charset = _canonical_charset(_content_type_charset(package) or
                                          package.encoding)
    if actual_charset != declared_charset:
        reports.append(_report(
            'encoding-mismatch',
            'Package encoding does not match its Content-Type header.',
            actual=package.encoding,
            declared=declared_charset
        ))
    if _canonical_charset(manifest['encoding']) != actual_charset:
        reports.append(_report(
            'encoding-incompatible',
            'Package encoding is incompatible with the split manifest.',
            expected=manifest['encoding'],
            actual=package.encoding
        ))

    expected_language = _normalize_language(manifest.get('language'))
    actual_language = _normalize_language(package.metadata.get('Language'))
    if expected_language and actual_language and \
       expected_language != actual_language:
        reports.append(_report(
            'language-incompatible',
            'Package Language header is incompatible with the split manifest.',
            expected=manifest.get('language'),
            actual=package.metadata.get('Language')
        ))

    expected_plural = manifest.get('plural_forms')
    try:
        actual_plural = _parse_plural_forms(
            package.metadata.get('Plural-Forms')
        )
    except ValueError as error:
        reports.append(_report(
            'plural-forms-invalid', str(error),
            actual=package.metadata.get('Plural-Forms')
        ))
        actual_plural = None
    if expected_plural:
        if actual_plural is None:
            reports.append(_report(
                'plural-forms-missing',
                'Package is missing the expected Plural-Forms header.'
            ))
        elif actual_plural['nplurals'] != expected_plural['nplurals'] or \
                actual_plural['expression'] != expected_plural['expression']:
            reports.append(_report(
                'plural-forms-incompatible',
                'Package Plural-Forms are incompatible with the split manifest.',
                expected=expected_plural['raw'],
                actual=package.metadata.get('Plural-Forms')
            ))
        else:
            for entry in package:
                if entry.msgid_plural:
                    try:
                        _validate_plural_entry(entry, actual_plural)
                    except ValueError as error:
                        reports.append(_report(
                            'plural-entry-invalid', str(error),
                            identity=_entry_identity(entry)
                        ))
    return reports


def _translation_decision(assignment, manifest, package_copies):
    plural, baseline_payload = _baseline_translation(assignment)
    changed = []
    for group in assignment['groups']:
        entry = package_copies.get(group, {}).get(assignment['identity'])
        if entry is None:
            continue
        payload = _translation_payload(entry)[1]
        if payload != baseline_payload:
            changed.append((group, payload))

    if not changed:
        return {'status': 'unmodified', 'payload': baseline_payload,
                'values': []}
    distinct = []
    for group, payload in changed:
        if payload not in [item[1] for item in distinct]:
            distinct.append((group, payload))

    if len(distinct) == 1:
        status = 'identical' if len(changed) > 1 else 'modified'
        return {'status': status, 'payload': distinct[0][1],
                'values': changed}
    return {'status': 'conflict', 'payload': baseline_payload,
            'values': changed}


def _merged_entry(assignment, source_entry, manifest, package_copies, reports):
    identity = assignment['identity']
    if source_entry is None:
        merged = _placeholder_entry(assignment, manifest)
    else:
        merged = copy.deepcopy(source_entry)
        plural, baseline_payload = _baseline_translation(assignment)
        _apply_translation(merged, plural, baseline_payload)

    copies = []
    for group in assignment['groups']:
        if group not in package_copies:
            continue
        entry = package_copies[group].get(identity)
        if entry is None:
            reports.append(_report(
                'package-entry-missing',
                'An assigned package does not contain an expected entry.',
                group=group,
                identity=identity
            ))
            continue
        copies.append(entry)

    merged.tcomment = _merge_comments(
        merged.tcomment, [entry.tcomment for entry in copies]
    )
    merged.comment = _merge_comments(
        merged.comment, [entry.comment for entry in copies]
    )

    occurrences = set((path, line) for path, line in merged.occurrences)
    for entry in copies:
        occurrences.update(entry.occurrences)
    merged.occurrences = sorted(occurrences)
    merged.flags = _merge_flags(
        [merged.flags] + [entry.flags for entry in copies]
    )

    for field in ('previous_msgctxt', 'previous_msgid',
                  'previous_msgid_plural'):
        baseline = getattr(merged, field)
        changed_values = []
        for entry in copies:
            value = getattr(entry, field)
            if value is not None and value != baseline and \
               value not in changed_values:
                changed_values.append(value)
        if len(changed_values) > 1:
            reports.append(_report(
                'previous-field-conflict',
                'Packages disagree on a previous-translation field.',
                identity=identity,
                field=field,
                values=changed_values
            ))
        elif changed_values:
            setattr(merged, field, changed_values[0])

    decision = _translation_decision(
        assignment, manifest, package_copies
    )
    if decision['status'] == 'conflict':
        reports.append(_report(
            'translation-conflict',
            'Packages contain different translations for one identity.',
            identity=identity,
            msgctxt=assignment['msgctxt'],
            msgid=assignment['msgid'],
            groups=[group for group, payload in decision['values']],
            translations=dict(
                (group, _translation_as_json_payload(payload))
                for group, payload in decision['values']
            )
        ))
    _apply_translation(
        merged, bool(assignment['msgid_plural']), decision['payload']
    )
    return merged, decision
# }}}
# class MOFile {{{


class MOFile(_BaseFile):
    """
    Mo file reader/writer.
    This class inherits the :class:`~polib._BaseFile` class and, by
    extension, the python ``list`` type.
    """
    MAGIC = 0x950412de
    MAGIC_SWAPPED = 0xde120495

    def __init__(self, *args, **kwargs):
        """
        Constructor, accepts all keywords arguments accepted by
        :class:`~polib._BaseFile` class.
        """
        _BaseFile.__init__(self, *args, **kwargs)
        self.magic_number = None
        self.version = 0

    def save_as_pofile(self, fpath):
        """
        Saves the mofile as a pofile to ``fpath``.

        Keyword argument:

        ``fpath``
            string, full or relative path to the file.
        """
        _BaseFile.save(self, fpath)

    def save(self, fpath=None):
        """
        Saves the mofile to ``fpath``.

        Keyword argument:

        ``fpath``
            string, full or relative path to the file.
        """
        _BaseFile.save(self, fpath, 'to_binary')

    def percent_translated(self):
        """
        Convenience method to keep the same interface with POFile instances.
        """
        return 100

    def translated_entries(self):
        """
        Convenience method to keep the same interface with POFile instances.
        """
        return self

    def untranslated_entries(self):
        """
        Convenience method to keep the same interface with POFile instances.
        """
        return []

    def fuzzy_entries(self):
        """
        Convenience method to keep the same interface with POFile instances.
        """
        return []

    def obsolete_entries(self):
        """
        Convenience method to keep the same interface with POFile instances.
        """
        return []
# }}}
# class _BaseEntry {{{


class _BaseEntry(object):
    """
    Base class for :class:`~polib.POEntry` and :class:`~polib.MOEntry` classes.
    This class should **not** be instantiated directly.
    """

    def __init__(self, *args, **kwargs):
        """
        Constructor, accepts the following keyword arguments:

        ``msgid``
            string, the entry msgid.

        ``msgstr``
            string, the entry msgstr.

        ``msgid_plural``
            string, the entry msgid_plural.

        ``msgstr_plural``
            dict, the entry msgstr_plural lines.

        ``msgctxt``
            string, the entry context (msgctxt).

        ``obsolete``
            bool, whether the entry is "obsolete" or not.

        ``encoding``
            string, the encoding to use, defaults to ``default_encoding``
            global variable (optional).
        """
        self.msgid = kwargs.get('msgid', '')
        self.msgstr = kwargs.get('msgstr', '')
        self.msgid_plural = kwargs.get('msgid_plural', '')
        self.msgstr_plural = kwargs.get('msgstr_plural', {})
        self.msgctxt = kwargs.get('msgctxt', None)
        self.obsolete = kwargs.get('obsolete', False)
        self.encoding = kwargs.get('encoding', default_encoding)

    def __unicode__(self, wrapwidth=78):
        """
        Returns the unicode representation of the entry.
        """
        if self.obsolete:
            delflag = '#~ '
        else:
            delflag = ''
        ret = []
        # write the msgctxt if any
        if self.msgctxt is not None:
            ret += self._str_field("msgctxt", delflag, "", self.msgctxt,
                                   wrapwidth)
        # write the msgid
        ret += self._str_field("msgid", delflag, "", self.msgid, wrapwidth)
        # write the msgid_plural if any
        if self.msgid_plural:
            ret += self._str_field("msgid_plural", delflag, "",
                                   self.msgid_plural, wrapwidth)
        if self.msgstr_plural:
            # write the msgstr_plural if any
            msgstrs = self.msgstr_plural
            keys = list(msgstrs)
            keys.sort()
            for index in keys:
                msgstr = msgstrs[index]
                plural_index = '[%s]' % index
                ret += self._str_field("msgstr", delflag, plural_index, msgstr,
                                       wrapwidth)
        else:
            # otherwise write the msgstr
            ret += self._str_field("msgstr", delflag, "", self.msgstr,
                                   wrapwidth)
        ret.append('')
        ret = u('\n').join(ret)
        return ret

    if PY3:
        def __str__(self):
            return self.__unicode__()
    else:
        def __str__(self):
            """
            Returns the string representation of the entry.
            """
            return unicode(self).encode(self.encoding)

    def __eq__(self, other):
        return str(self) == str(other)

    def _str_field(self, fieldname, delflag, plural_index, field,
                   wrapwidth=78):
        lines = field.splitlines(True)
        if len(lines) > 1:
            lines = [''] + lines  # start with initial empty line
        else:
            escaped_field = escape(field)
            specialchars_count = 0
            for c in ['\\', '\n', '\r', '\t', '\v', '\b', '\f', '\a', '"']:
                specialchars_count += field.count(c)
            # comparison must take into account fieldname length + one space
            # + 2 quotes (eg. msgid "<string>")
            flength = len(fieldname) + 3
            if plural_index:
                flength += len(plural_index)
            real_wrapwidth = wrapwidth - flength + specialchars_count
            if wrapwidth > 0 and len(field) > real_wrapwidth:
                # Wrap the line but take field name into account
                lines = [''] + [unescape(item) for item in textwrap.wrap(
                    escaped_field,
                    wrapwidth - 2,  # 2 for quotes ""
                    drop_whitespace=False,
                    break_long_words=False
                )]
            else:
                lines = [field]
        if fieldname.startswith('previous_'):
            # quick and dirty trick to get the real field name
            fieldname = fieldname[9:]

        ret = ['%s%s%s "%s"' % (delflag, fieldname, plural_index,
                                escape(lines.pop(0)))]
        for line in lines:
            ret.append('%s"%s"' % (delflag, escape(line)))
        return ret

    @property
    def msgid_with_context(self):
        if self.msgctxt:
            return '%s%s%s' % (self.msgctxt, "\x04", self.msgid)
        return self.msgid
# }}}
# class POEntry {{{


class POEntry(_BaseEntry):
    """
    Represents a po file entry.
    """

    def __init__(self, *args, **kwargs):
        """
        Constructor, accepts the following keyword arguments:

        ``comment``
            string, the entry comment.

        ``tcomment``
            string, the entry translator comment.

        ``occurrences``
            list, the entry occurrences.

        ``flags``
            list, the entry flags.

        ``previous_msgctxt``
            string, the entry previous context.

        ``previous_msgid``
            string, the entry previous msgid.

        ``previous_msgid_plural``
            string, the entry previous msgid_plural.

        ``linenum``
            integer, the line number of the entry
        """
        _BaseEntry.__init__(self, *args, **kwargs)
        self.comment = kwargs.get('comment', '')
        self.tcomment = kwargs.get('tcomment', '')
        self.occurrences = kwargs.get('occurrences', [])
        self.flags = kwargs.get('flags', [])
        self.previous_msgctxt = kwargs.get('previous_msgctxt', None)
        self.previous_msgid = kwargs.get('previous_msgid', None)
        self.previous_msgid_plural = kwargs.get('previous_msgid_plural', None)
        self.linenum = kwargs.get('linenum', None)

    def __unicode__(self, wrapwidth=78):
        """
        Returns the unicode representation of the entry.
        """
        ret = []
        # comments first, if any (with text wrapping as xgettext does)
        if self.obsolete:
            comments = [('tcomment', '# ')]
        else:
            comments = [('tcomment', '# '), ('comment', '#. ')]
        for c in comments:
            val = getattr(self, c[0])
            if val:
                for comment in val.split('\n'):
                    if wrapwidth > 0 and len(comment) + len(c[1]) > wrapwidth:
                        ret += textwrap.wrap(
                            comment,
                            wrapwidth,
                            initial_indent=c[1],
                            subsequent_indent=c[1],
                            break_long_words=False
                        )
                    else:
                        ret.append('%s%s' % (c[1], comment))

        # occurrences (with text wrapping as xgettext does)
        if not self.obsolete and self.occurrences:
            filelist = []
            for fpath, lineno in self.occurrences:
                if lineno:
                    filelist.append('%s:%s' % (fpath, lineno))
                else:
                    filelist.append(fpath)
            filestr = ' '.join(filelist)
            if wrapwidth > 0 and len(filestr) + 3 > wrapwidth:
                # textwrap split words that contain hyphen, this is not
                # what we want for filenames, so the dirty hack is to
                # temporally replace hyphens with a char that a file cannot
                # contain, like "*"
                ret += [line.replace('*', '-') for line in textwrap.wrap(
                    filestr.replace('-', '*'),
                    wrapwidth,
                    initial_indent='#: ',
                    subsequent_indent='#: ',
                    break_long_words=False
                )]
            else:
                ret.append('#: ' + filestr)

        # flags (TODO: wrapping ?)
        if self.flags:
            ret.append('#, %s' % ', '.join(self.flags))

        # previous context and previous msgid/msgid_plural
        fields = ['previous_msgctxt', 'previous_msgid',
                  'previous_msgid_plural']
        if self.obsolete:
            prefix = "#~| "
        else:
            prefix = "#| "
        for f in fields:
            val = getattr(self, f)
            if val is not None:
                ret += self._str_field(f, prefix, "", val, wrapwidth)

        ret.append(_BaseEntry.__unicode__(self, wrapwidth))
        ret = u('\n').join(ret)
        return ret

    def __cmp__(self, other):
        """
        Called by comparison operations if rich comparison is not defined.
        """
        # First: Obsolete test
        if self.obsolete != other.obsolete:
            if self.obsolete:
                return -1
            else:
                return 1
        # Work on a copy to protect original
        occ1 = sorted(self.occurrences[:])
        occ2 = sorted(other.occurrences[:])
        if occ1 > occ2:
            return 1
        if occ1 < occ2:
            return -1
        # Compare context
        msgctxt = self.msgctxt or '0'
        othermsgctxt = other.msgctxt or '0'
        if msgctxt > othermsgctxt:
            return 1
        elif msgctxt < othermsgctxt:
            return -1
        # Compare msgid_plural
        msgid_plural = self.msgid_plural or '0'
        othermsgid_plural = other.msgid_plural or '0'
        if msgid_plural > othermsgid_plural:
            return 1
        elif msgid_plural < othermsgid_plural:
            return -1
        # Compare msgstr_plural
        if self.msgstr_plural and isinstance(self.msgstr_plural, dict):
            msgstr_plural = list(self.msgstr_plural.values())
        else:
            msgstr_plural = []
        if other.msgstr_plural and isinstance(other.msgstr_plural, dict):
            othermsgstr_plural = list(other.msgstr_plural.values())
        else:
            othermsgstr_plural = []
        if msgstr_plural > othermsgstr_plural:
            return 1
        elif msgstr_plural < othermsgstr_plural:
            return -1
        # Compare msgid
        if self.msgid > other.msgid:
            return 1
        elif self.msgid < other.msgid:
            return -1
        # Compare msgstr
        if self.msgstr > other.msgstr:
            return 1
        elif self.msgstr < other.msgstr:
            return -1
        return 0

    def __gt__(self, other):
        return self.__cmp__(other) > 0

    def __lt__(self, other):
        return self.__cmp__(other) < 0

    def __ge__(self, other):
        return self.__cmp__(other) >= 0

    def __le__(self, other):
        return self.__cmp__(other) <= 0

    def __eq__(self, other):
        return self.__cmp__(other) == 0

    def __ne__(self, other):
        return self.__cmp__(other) != 0

    def translated(self):
        """
        Returns ``True`` if the entry has been translated or ``False``
        otherwise.
        """
        if self.obsolete or self.fuzzy:
            return False
        if self.msgstr != '':
            return True
        if self.msgstr_plural:
            for pos in self.msgstr_plural:
                if self.msgstr_plural[pos] == '':
                    return False
            return True
        return False

    def merge(self, other):
        """
        Merge the current entry with the given pot entry.
        """
        self.msgid = other.msgid
        self.msgctxt = other.msgctxt
        self.occurrences = other.occurrences
        self.comment = other.comment
        fuzzy = self.fuzzy
        self.flags = other.flags[:]  # clone flags
        if fuzzy:
            self.flags.append('fuzzy')
        self.msgid_plural = other.msgid_plural
        self.obsolete = other.obsolete
        self.previous_msgctxt = other.previous_msgctxt
        self.previous_msgid = other.previous_msgid
        self.previous_msgid_plural = other.previous_msgid_plural
        if other.msgstr_plural:
            for pos in other.msgstr_plural:
                try:
                    # keep existing translation at pos if any
                    self.msgstr_plural[pos]
                except KeyError:
                    self.msgstr_plural[pos] = ''

    @property
    def fuzzy(self):
        return 'fuzzy' in self.flags

    @fuzzy.setter
    def fuzzy(self, value):
        if value and not self.fuzzy:
            self.flags.insert(0, 'fuzzy')
        elif not value and self.fuzzy:
            self.flags.remove('fuzzy')

    def __hash__(self):
        return hash((self.msgid, self.msgstr))
# }}}
# class MOEntry {{{


class MOEntry(_BaseEntry):
    """
    Represents a mo file entry.
    """
    def __init__(self, *args, **kwargs):
        """
        Constructor, accepts the following keyword arguments,
        for consistency with :class:`~polib.POEntry`:

        ``comment``
        ``tcomment``
        ``occurrences``
        ``flags``
        ``previous_msgctxt``
        ``previous_msgid``
        ``previous_msgid_plural``

        Note: even though these keyword arguments are accepted,
        they hold no real meaning in the context of MO files
        and are simply ignored.
        """
        _BaseEntry.__init__(self, *args, **kwargs)
        self.comment = ''
        self.tcomment = ''
        self.occurrences = []
        self.flags = []
        self.previous_msgctxt = None
        self.previous_msgid = None
        self.previous_msgid_plural = None

    def __hash__(self):
        return hash((self.msgid, self.msgstr))

# }}}
# class _POFileParser {{{


class _POFileParser(object):
    """
    A finite state machine to efficiently and correctly parse po
    file format.
    """

    def __init__(self, pofile, *args, **kwargs):
        """
        Constructor.

        Keyword arguments:

        ``pofile``
            string, path to the po file or its content

        ``encoding``
            string, the encoding to use, defaults to ``default_encoding``
            global variable (optional).

        ``check_for_duplicates``
            whether to check for duplicate entries when adding entries to the
            file (optional, default: ``False``).
        """
        enc = kwargs.get('encoding', default_encoding)
        if _is_file(pofile):
            try:
                self.fhandle = io.open(pofile, 'rt', encoding=enc)
            except LookupError:
                enc = default_encoding
                self.fhandle = io.open(pofile, 'rt', encoding=enc)
        else:
            self.fhandle = pofile.splitlines()

        klass = kwargs.get('klass')
        if klass is None:
            klass = POFile
        self.instance = klass(
            pofile=pofile,
            encoding=enc,
            check_for_duplicates=kwargs.get('check_for_duplicates', False)
        )
        self.transitions = {}
        self.current_line = 0
        self.current_entry = POEntry(linenum=self.current_line)
        self.current_state = 'st'
        self.current_token = None
        # two memo flags used in handlers
        self.msgstr_index = 0
        self.entry_obsolete = 0
        # Configure the state machine, by adding transitions.
        # Signification of symbols:
        #     * ST: Beginning of the file (start)
        #     * HE: Header
        #     * TC: a translation comment
        #     * GC: a generated comment
        #     * OC: a file/line occurrence
        #     * FL: a flags line
        #     * CT: a message context
        #     * PC: a previous msgctxt
        #     * PM: a previous msgid
        #     * PP: a previous msgid_plural
        #     * MI: a msgid
        #     * MP: a msgid plural
        #     * MS: a msgstr
        #     * MX: a msgstr plural
        #     * MC: a msgid or msgstr continuation line
        all = ['st', 'he', 'gc', 'oc', 'fl', 'ct', 'pc', 'pm', 'pp', 'tc',
               'ms', 'mp', 'mx', 'mi']

        self.add('tc', ['st', 'he'],                                     'he')
        self.add('tc', ['gc', 'oc', 'fl', 'tc', 'pc', 'pm', 'pp', 'ms',
                        'mp', 'mx', 'mi'],                               'tc')
        self.add('gc', all,                                              'gc')
        self.add('oc', all,                                              'oc')
        self.add('fl', all,                                              'fl')
        self.add('pc', all,                                              'pc')
        self.add('pm', all,                                              'pm')
        self.add('pp', all,                                              'pp')
        self.add('ct', ['st', 'he', 'gc', 'oc', 'fl', 'tc', 'pc', 'pm',
                        'pp', 'ms', 'mx'],                               'ct')
        self.add('mi', ['st', 'he', 'gc', 'oc', 'fl', 'ct', 'tc', 'pc',
                 'pm', 'pp', 'ms', 'mx'],                                'mi')
        self.add('mp', ['tc', 'gc', 'pc', 'pm', 'pp', 'mi'],             'mp')
        self.add('ms', ['mi', 'mp', 'tc'],                               'ms')
        self.add('mx', ['mi', 'mx', 'mp', 'tc'],                         'mx')
        self.add('mc', ['ct', 'mi', 'mp', 'ms', 'mx', 'pm', 'pp', 'pc'], 'mc')

    def parse(self):
        """
        Run the state machine, parse the file line by line and call process()
        with the current matched symbol.
        """
        try:
            keywords = {
                'msgctxt': 'ct',
                'msgid': 'mi',
                'msgstr': 'ms',
                'msgid_plural': 'mp',
            }
            prev_keywords = {
                'msgid_plural': 'pp',
                'msgid': 'pm',
                'msgctxt': 'pc',
            }
            tokens = []
            fpath = '%s ' % self.instance.fpath if self.instance.fpath else ''
            for line in self.fhandle:
                self.current_line += 1
                if self.current_line == 1:
                    BOM = codecs.BOM_UTF8.decode('utf-8')
                    if line.startswith(BOM):
                        line = line[len(BOM):]
                line = line.strip()
                if line == '':
                    continue

                tokens = line.split(None, 2)
                nb_tokens = len(tokens)

                if tokens[0] == '#~|':
                    continue

                if tokens[0] == '#~' and nb_tokens > 1:
                    line = line[3:].strip()
                    tokens = tokens[1:]
                    nb_tokens -= 1
                    self.entry_obsolete = 1
                else:
                    self.entry_obsolete = 0

                # Take care of keywords like
                # msgid, msgid_plural, msgctxt & msgstr.
                if tokens[0] in keywords and nb_tokens > 1:
                    line = line[len(tokens[0]):].lstrip()
                    if re.search(r'([^\\]|^)"', line[1:-1]):
                        raise IOError('Syntax error in po file %s(line %s): '
                                      'unescaped double quote found' %
                                      (fpath, self.current_line))
                    if line[0] != '"' or line[-1] != '"':
                        raise IOError('Syntax error in po file %s(line %s): '
                                      'string not delimited by double quotes' %
                                      (fpath, self.current_line))
                    self.current_token = line
                    self.process(keywords[tokens[0]])
                    continue

                self.current_token = line

                if tokens[0] == '#:':
                    if nb_tokens <= 1:
                        continue
                    # we are on a occurrences line
                    self.process('oc')

                elif line[:1] == '"':
                    # we are on a continuation line
                    if re.search(r'([^\\]|^)"', line[1:-1]):
                        raise IOError('Syntax error in po file %s(line %s): '
                                      'unescaped double quote found' %
                                      (fpath, self.current_line))
                    if line[-1] != '"':
                        raise IOError('Syntax error in po file %s(line %s): '
                                      'string not delimited by double quotes' %
                                      (fpath, self.current_line))
                    self.process('mc')

                elif line[:7] == 'msgstr[':
                    # we are on a msgstr plural
                    self.process('mx')

                elif tokens[0] == '#,':
                    if nb_tokens <= 1:
                        continue
                    # we are on a flags line
                    self.process('fl')

                elif tokens[0] == '#' or tokens[0].startswith('##'):
                    if line == '#':
                        line += ' '
                    # we are on a translator comment line
                    self.process('tc')

                elif tokens[0] == '#.':
                    if nb_tokens <= 1:
                        continue
                    # we are on a generated comment line
                    self.process('gc')

                elif tokens[0] == '#|':
                    if nb_tokens <= 1:
                        raise IOError('Syntax error in po file %s(line %s)' %
                                      (fpath, self.current_line))

                    # Remove the marker and any whitespace right after that.
                    line = line[2:].lstrip()
                    self.current_token = line

                    if tokens[1].startswith('"'):
                        # Continuation of previous metadata.
                        self.process('mc')
                        continue

                    if nb_tokens == 2:
                        # Invalid continuation line.
                        raise IOError('Syntax error in po file %s(line %s): '
                                      'invalid continuation line' %
                                      (fpath, self.current_line))

                    # we are on a "previous translation" comment line,
                    if tokens[1] not in prev_keywords:
                        # Unknown keyword in previous translation comment.
                        raise IOError('Syntax error in po file %s(line %s): '
                                      'unknown keyword %s' %
                                      (fpath, self.current_line,
                                       tokens[1]))

                    # Remove the keyword and any whitespace
                    # between it and the starting quote.
                    line = line[len(tokens[1]):].lstrip()
                    self.current_token = line
                    self.process(prev_keywords[tokens[1]])

                else:
                    raise IOError('Syntax error in po file %s(line %s)' %
                                  (fpath, self.current_line))

            if self.current_entry and len(tokens) > 0 and \
               not tokens[0].startswith('#'):
                # since entries are added when another entry is found, we must
                # add the last entry here (only if there are lines). Trailing
                # comments are ignored
                self.instance.append(self.current_entry)

            # before returning the instance, check if there's metadata and if
            # so extract it in a dict
            metadataentry = self.instance.find('')
            if metadataentry:  # metadata found
                # remove the entry
                self.instance.remove(metadataentry)
                self.instance.metadata_is_fuzzy = metadataentry.flags
                key = None
                for msg in metadataentry.msgstr.splitlines():
                    try:
                        key, val = msg.split(':', 1)
                        self.instance.metadata[key] = val.strip()
                    except (ValueError, KeyError):
                        if key is not None:
                            self.instance.metadata[key] += '\n' + msg.strip()
        finally:
            # close opened file
            if not isinstance(self.fhandle, list):  # must be file
                self.fhandle.close()
        return self.instance

    def add(self, symbol, states, next_state):
        """
        Add a transition to the state machine.

        Keywords arguments:

        ``symbol``
            string, the matched token (two chars symbol).

        ``states``
            list, a list of states (two chars symbols).

        ``next_state``
            the next state the fsm will have after the action.
        """
        for state in states:
            action = getattr(self, 'handle_%s' % next_state)
            self.transitions[(symbol, state)] = (action, next_state)

    def process(self, symbol):
        """
        Process the transition corresponding to the current state and the
        symbol provided.

        Keywords arguments:

        ``symbol``
            string, the matched token (two chars symbol).

        ``linenum``
            integer, the current line number of the parsed file.
        """
        try:
            (action, state) = self.transitions[(symbol, self.current_state)]
            if action():
                self.current_state = state
        except Exception:
            fpath = '%s ' % self.instance.fpath if self.instance.fpath else ''
            if hasattr(self.fhandle, 'close'):
                self.fhandle.close()
            raise IOError('Syntax error in po file %s(line %s)' %
                          (fpath, self.current_line))

    # state handlers

    def handle_he(self):
        """Handle a header comment."""
        if self.instance.header != '':
            self.instance.header += '\n'
        self.instance.header += self.current_token[2:]
        return 1

    def handle_tc(self):
        """Handle a translator comment."""
        if self.current_state in ['mc', 'ms', 'mx']:
            self.instance.append(self.current_entry)
            self.current_entry = POEntry(linenum=self.current_line)
        if self.current_entry.tcomment != '':
            self.current_entry.tcomment += '\n'
        tcomment = self.current_token.lstrip('#')
        if tcomment.startswith(' '):
            tcomment = tcomment[1:]
        self.current_entry.tcomment += tcomment
        return True

    def handle_gc(self):
        """Handle a generated comment."""
        if self.current_state in ['mc', 'ms', 'mx']:
            self.instance.append(self.current_entry)
            self.current_entry = POEntry(linenum=self.current_line)
        if self.current_entry.comment != '':
            self.current_entry.comment += '\n'
        self.current_entry.comment += self.current_token[3:]
        return True

    def handle_oc(self):
        """Handle a file:num occurrence."""
        if self.current_state in ['mc', 'ms', 'mx']:
            self.instance.append(self.current_entry)
            self.current_entry = POEntry(linenum=self.current_line)
        occurrences = self.current_token[3:].split()
        for occurrence in occurrences:
            if occurrence != '':
                try:
                    fil, line = occurrence.rsplit(':', 1)
                    if not line.isdigit():
                        fil = occurrence
                        line = ''
                    self.current_entry.occurrences.append((fil, line))
                except (ValueError, AttributeError):
                    self.current_entry.occurrences.append((occurrence, ''))
        return True

    def handle_fl(self):
        """Handle a flags line."""
        if self.current_state in ['mc', 'ms', 'mx']:
            self.instance.append(self.current_entry)
            self.current_entry = POEntry(linenum=self.current_line)
        self.current_entry.flags += [c.strip() for c in
                                     self.current_token[3:].split(',')]
        return True

    def handle_pp(self):
        """Handle a previous msgid_plural line."""
        if self.current_state in ['mc', 'ms', 'mx']:
            self.instance.append(self.current_entry)
            self.current_entry = POEntry(linenum=self.current_line)
        self.current_entry.previous_msgid_plural = \
            unescape(self.current_token[1:-1])
        return True

    def handle_pm(self):
        """Handle a previous msgid line."""
        if self.current_state in ['mc', 'ms', 'mx']:
            self.instance.append(self.current_entry)
            self.current_entry = POEntry(linenum=self.current_line)
        self.current_entry.previous_msgid = \
            unescape(self.current_token[1:-1])
        return True

    def handle_pc(self):
        """Handle a previous msgctxt line."""
        if self.current_state in ['mc', 'ms', 'mx']:
            self.instance.append(self.current_entry)
            self.current_entry = POEntry(linenum=self.current_line)
        self.current_entry.previous_msgctxt = \
            unescape(self.current_token[1:-1])
        return True

    def handle_ct(self):
        """Handle a msgctxt."""
        if self.current_state in ['mc', 'ms', 'mx']:
            self.instance.append(self.current_entry)
            self.current_entry = POEntry(linenum=self.current_line)
        self.current_entry.msgctxt = unescape(self.current_token[1:-1])
        return True

    def handle_mi(self):
        """Handle a msgid."""
        if self.current_state in ['mc', 'ms', 'mx']:
            self.instance.append(self.current_entry)
            self.current_entry = POEntry(linenum=self.current_line)
        self.current_entry.obsolete = self.entry_obsolete
        self.current_entry.msgid = unescape(self.current_token[1:-1])
        return True

    def handle_mp(self):
        """Handle a msgid plural."""
        self.current_entry.msgid_plural = unescape(self.current_token[1:-1])
        return True

    def handle_ms(self):
        """Handle a msgstr."""
        self.current_entry.msgstr = unescape(self.current_token[1:-1])
        return True

    def handle_mx(self):
        """Handle a msgstr plural."""
        index = self.current_token[7]
        value = self.current_token[self.current_token.find('"') + 1:-1]
        self.current_entry.msgstr_plural[int(index)] = unescape(value)
        self.msgstr_index = int(index)
        return True

    def handle_mc(self):
        """Handle a msgid or msgstr continuation line."""
        token = unescape(self.current_token[1:-1])
        if self.current_state == 'ct':
            self.current_entry.msgctxt += token
        elif self.current_state == 'mi':
            self.current_entry.msgid += token
        elif self.current_state == 'mp':
            self.current_entry.msgid_plural += token
        elif self.current_state == 'ms':
            self.current_entry.msgstr += token
        elif self.current_state == 'mx':
            self.current_entry.msgstr_plural[self.msgstr_index] += token
        elif self.current_state == 'pp':
            self.current_entry.previous_msgid_plural += token
        elif self.current_state == 'pm':
            self.current_entry.previous_msgid += token
        elif self.current_state == 'pc':
            self.current_entry.previous_msgctxt += token
        # don't change the current state
        return False
# }}}
# class _MOFileParser {{{


class _MOFileParser(object):
    """
    A class to parse binary mo files.
    """

    def __init__(self, mofile, *args, **kwargs):
        """
        Constructor.

        Keyword arguments:

        ``mofile``
            string, path to the mo file or its content

        ``encoding``
            string, the encoding to use, defaults to ``default_encoding``
            global variable (optional).

        ``check_for_duplicates``
            whether to check for duplicate entries when adding entries to the
            file (optional, default: ``False``).
        """
        if _is_file(mofile):
            self.fhandle = open(mofile, 'rb')
        else:
            self.fhandle = io.BytesIO(mofile)

        klass = kwargs.get('klass')
        if klass is None:
            klass = MOFile
        self.instance = klass(
            fpath=mofile,
            encoding=kwargs.get('encoding', default_encoding),
            check_for_duplicates=kwargs.get('check_for_duplicates', False)
        )

    def __del__(self):
        """
        Make sure the file is closed, this prevents warnings on unclosed file
        when running tests with python >= 3.2.
        """
        if self.fhandle and hasattr(self.fhandle, 'close'):
            self.fhandle.close()

    def parse(self):
        """
        Build the instance with the file handle provided in the
        constructor.
        """
        # parse magic number
        magic_number = self._readbinary('<I', 4)
        if magic_number == MOFile.MAGIC:
            ii = '<II'
        elif magic_number == MOFile.MAGIC_SWAPPED:
            ii = '>II'
        else:
            raise IOError('Invalid mo file, magic number is incorrect !')
        self.instance.magic_number = magic_number
        # parse the version number and the number of strings
        version, numofstrings = self._readbinary(ii, 8)
        # from MO file format specs: "A program seeing an unexpected major
        # revision number should stop reading the MO file entirely"
        if version >> 16 not in (0, 1):
            raise IOError('Invalid mo file, unexpected major revision number')
        self.instance.version = version
        # original strings and translation strings hash table offset
        msgids_hash_offset, msgstrs_hash_offset = self._readbinary(ii, 8)
        # move to msgid hash table and read length and offset of msgids
        self.fhandle.seek(msgids_hash_offset)
        msgids_index = []
        for i in range(numofstrings):
            msgids_index.append(self._readbinary(ii, 8))
        # move to msgstr hash table and read length and offset of msgstrs
        self.fhandle.seek(msgstrs_hash_offset)
        msgstrs_index = []
        for i in range(numofstrings):
            msgstrs_index.append(self._readbinary(ii, 8))
        # build entries
        encoding = self.instance.encoding
        for i in range(numofstrings):
            self.fhandle.seek(msgids_index[i][1])
            msgid = self.fhandle.read(msgids_index[i][0])

            self.fhandle.seek(msgstrs_index[i][1])
            msgstr = self.fhandle.read(msgstrs_index[i][0])
            if i == 0 and not msgid:  # metadata
                raw_metadata, metadata = msgstr.split(b('\n')), {}
                for line in raw_metadata:
                    tokens = line.split(b(':'), 1)
                    if tokens[0] != b(''):
                        try:
                            k = tokens[0].decode(encoding)
                            v = tokens[1].decode(encoding)
                            metadata[k] = v.strip()
                        except IndexError:
                            metadata[k] = u('')
                self.instance.metadata = metadata
                continue
            # test if we have a plural entry
            msgid_tokens = msgid.split(b('\0'))
            if len(msgid_tokens) > 1:
                entry = self._build_entry(
                    msgid=msgid_tokens[0],
                    msgid_plural=msgid_tokens[1],
                    msgstr_plural=dict((k, v) for k, v in
                                       enumerate(msgstr.split(b('\0'))))
                )
            else:
                entry = self._build_entry(msgid=msgid, msgstr=msgstr)
            self.instance.append(entry)
        # close opened file
        self.fhandle.close()
        return self.instance

    def _build_entry(self, msgid, msgstr=None, msgid_plural=None,
                     msgstr_plural=None):
        msgctxt_msgid = msgid.split(b('\x04'))
        encoding = self.instance.encoding
        if len(msgctxt_msgid) > 1:
            kwargs = {
                'msgctxt': msgctxt_msgid[0].decode(encoding),
                'msgid': msgctxt_msgid[1].decode(encoding),
            }
        else:
            kwargs = {'msgid': msgid.decode(encoding)}
        if msgstr:
            kwargs['msgstr'] = msgstr.decode(encoding)
        if msgid_plural:
            kwargs['msgid_plural'] = msgid_plural.decode(encoding)
        if msgstr_plural:
            for k in msgstr_plural:
                msgstr_plural[k] = msgstr_plural[k].decode(encoding)
            kwargs['msgstr_plural'] = msgstr_plural
        return MOEntry(**kwargs)

    def _readbinary(self, fmt, numbytes):
        """
        Private method that unpack n bytes of data using format <fmt>.
        It returns a tuple or a mixed value if the tuple length is 1.
        """
        bytes = self.fhandle.read(numbytes)
        tup = struct.unpack(fmt, bytes)
        if len(tup) == 1:
            return tup[0]
        return tup
# }}}
