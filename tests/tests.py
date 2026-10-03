#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import io
import os
import struct
import subprocess
import sys
import tempfile
import unittest
try:
    from shutil import which
except ImportError:
    from distutils.spawn import find_executable as which  # Deprecated in 3.10, removed in 3.12.

sys.path.insert(1, os.path.abspath('.'))

import polib

from polib import u

class TestFunctions(unittest.TestCase):

    def test_pofile_and_mofile1(self):
        """
        Test bad usage of pofile/mofile.
        """
        data = u('''# test for pofile/mofile with string buffer
msgid ""
msgstr ""
"Project-Id-Version: django"

msgid "foo"
msgstr "bar"
''')
        po = polib.pofile(data)
        self.assertTrue(isinstance(po, polib.POFile))
        self.assertEqual(po.encoding, 'utf-8')
        self.assertEqual(po[0].msgstr, u("bar"))

    def test_indented_pofile(self):
        """
        Test that an indented pofile returns a POFile instance.
        """
        po = polib.pofile('tests/test_indented.po')
        self.assertTrue(isinstance(po, polib.POFile))

    def test_pofile_and_mofile2(self):
        """
        Test that the pofile function returns a POFile instance.
        """
        po = polib.pofile('tests/test_utf8.po')
        self.assertTrue(isinstance(po, polib.POFile))

    def test_pofile_and_mofile3(self):
        """
        Test  that the mofile function returns a MOFile instance.
        """
        mo = polib.mofile('tests/test_utf8.mo')
        self.assertTrue(isinstance(mo, polib.MOFile))

    def test_pofile_and_mofile4(self):
        """
        Test that check_for_duplicates is passed to the instance.
        """
        po = polib.pofile('tests/test_iso-8859-15.po', check_for_duplicates=True,
                          autodetect_encoding=False, encoding='iso-8859-15')
        self.assertTrue(po.check_for_duplicates == True)

    def test_pofile_and_mofile5(self):
        """
        Test that detect_encoding works as expected.
        """
        po = polib.pofile('tests/test_iso-8859-15.po')
        self.assertTrue(po.encoding == 'ISO_8859-15')

    def test_pofile_and_mofile6(self):
        """
        Test that encoding is default_encoding when detect_encoding is False.
        """
        po = polib.pofile('tests/test_noencoding.po')
        self.assertTrue(po.encoding == 'utf-8')

    def test_pofile_and_mofile7(self):
        """
        Test that encoding is ok when encoding is explicitly given.
        """
        po = polib.pofile('tests/test_iso-8859-15.po', encoding='iso-8859-15')
        self.assertTrue(po.encoding == 'iso-8859-15')

    def test_pofile_and_mofile8(self):
        """
        Test that weird occurrences are correctly parsed.
        """
        po = polib.pofile('tests/test_weird_occurrences.po')
        self.assertEqual(len(po), 47)

    def test_pofile_and_mofile9(self):
        """
        Test that obsolete previous msgid are ignored
        """
        po = polib.pofile('tests/test_obsolete_previousmsgid.po')
        self.assertTrue(isinstance(po, polib.POFile))

    def test_pofile_and_mofile10(self):
        """
        Test mofile with a bytes object.
        """
        mo_bytes = b"\xde\x12\x04\x95\x00\x00\x00\x00\x05\x00\x00\x00\x1c\x00\x00\x00D\x00\x00\x00\x07\x00\x00\x00l\x00\x00\x00\x00\x00\x00\x00\x88\x00\x00\x00\x10\x00\x00\x00\x89\x00\x00\x00\x07\x00\x00\x00\x9a\x00\x00\x00\x0c\x00\x00\x00\xa2\x00\x00\x00\x0b\x00\x00\x00\xaf\x00\x00\x00(\x00\x00\x00\xbb\x00\x00\x00\n\x00\x00\x00\xe4\x00\x00\x00\x10\x00\x00\x00\xef\x00\x00\x00\x0f\x00\x00\x00\x00\x01\x00\x00\x16\x00\x00\x00\x10\x01\x00\x00\x01\x00\x00\x00\x03\x00\x00\x00\x05\x00\x00\x00\x00\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00SNAR_BEZEICHNUNG\x00conform\x00inconclusive\x00non-conform\x00Content-Type: text/plain; charset=UTF-8\n\x00Feldfrucht\x00\xc3\x9cbereinstimmung\x00Nicht eindeutig\x00Keine \xc3\x9cbereinstimmung\x00"
        mo = polib.mofile(mo_bytes)
        self.assertTrue(isinstance(mo, polib.MOFile))

    def test_ufeff_data_pofile(self):
        """
        Test that an ufeff prefixed pofile returns a POFile instance.
        """
        data = u('''\ufeff# test for pofile/mofile with ufeff
msgid ""
msgstr ""
"Project-Id-Version: django"

msgid "foo"
msgstr "bar"
''')
        po = polib.pofile(data)
        self.assertTrue(isinstance(po, polib.POFile))

    def test_ufeff_pofile(self):
        """
        Test that an ufeff prefixed pofile returns a POFile instance.
        """
        po = polib.pofile('tests/test_ufeff.po')
        self.assertTrue(isinstance(po, polib.POFile))

    def test_previous_msgid_1(self):
        """
        Test previous msgid multiline.
        """
        po = polib.pofile('tests/test_previous_msgid.po')
        expected = "\nPartition table entries are not in disk order\n"
        self.assertEqual(
            po[0].previous_msgid,
            expected
        )

    def test_previous_msgid_2(self):
        """
        Test previous msgid single line.
        """
        po = polib.pofile('tests/test_previous_msgid.po')
        expected = "Partition table entries are not in disk order2\n"
        self.assertEqual(
            po[1].previous_msgid,
            expected
        )

    def test_previous_msgid_3(self):
        """
        Test saving empty previous msgid.
        """
        po = polib.pofile('tests/test_previous_msgid.po')
        fd, tmpfile = tempfile.mkstemp()
        os.close(fd)
        po.save(tmpfile)
        po = polib.pofile(tmpfile)
        os.remove(tmpfile)

        expected = ""
        self.assertEqual(
            po[2].previous_msgid,
            expected
        )

    def test_previous_msgctxt_1(self):
        """
        Test previous msgctxt multiline.
        """
        po = polib.pofile('tests/test_previous_msgid.po')
        expected = "\nSome message context"
        self.assertEqual(
            po[0].previous_msgctxt,
            expected
        )

    def test_previous_msgctxt_2(self):
        """
        Test previous msgctxt single line.
        """
        po = polib.pofile('tests/test_previous_msgid.po')
        expected = "Some message context"
        self.assertEqual(
            po[1].previous_msgctxt,
            expected
        )

    def test_unescaped_double_quote1(self):
        """
        Test that polib reports an error when unescaped double quote is found.
        """
        data = r'''
msgid "Some msgid with \"double\" quotes"
msgid "Some msgstr with "double\" quotes"
'''
        try:
            po = polib.pofile(data)
            self.fail("Unescaped quote not detected")
        except IOError:
            exc = sys.exc_info()[1]
            msg = 'Syntax error in po file (line 3): unescaped double quote found'
            self.assertEqual(str(exc), msg)

    def test_unescaped_double_quote2(self):
        """
        Test that polib reports an error when unescaped double quote is found.
        """
        data = r'''
msgid "Some msgid with \"double\" quotes"
msgstr ""
"Some msgstr with "double\" quotes"
'''
        try:
            po = polib.pofile(data)
            self.fail("Unescaped quote not detected")
        except IOError:
            exc = sys.exc_info()[1]
            msg = 'Syntax error in po file (line 4): unescaped double quote found'
            self.assertEqual(str(exc), msg)

    def test_unescaped_double_quote3(self):
        """
        Test that polib reports an error when unescaped double quote is found at the beginning of the string.
        """
        data = r'''
msgid "Some msgid with \"double\" quotes"
msgid ""Some msgstr with double\" quotes"
'''
        try:
            po = polib.pofile(data)
            self.fail("Unescaped quote not detected")
        except IOError:
            exc = sys.exc_info()[1]
            msg = 'Syntax error in po file (line 3): unescaped double quote found'
            self.assertEqual(str(exc), msg)

    def test_unescaped_double_quote4(self):
        """
        Test that polib reports an error when unescaped double quote is found at the beginning of the string.
        """
        data = r'''
msgid "Some msgid with \"double\" quotes"
msgstr ""
""Some msgstr with double\" quotes"
'''
        try:
            po = polib.pofile(data)
            self.fail("Unescaped quote not detected")
        except IOError:
            exc = sys.exc_info()[1]
            msg = 'Syntax error in po file (line 4): unescaped double quote found'
            self.assertEqual(str(exc), msg)

    def test_no_double_quote_delimiters(self):
        """
        Test that polib reports an error when a string is not delimited by double quotes.
        """
        invalid_msgstr = r'''
msgid "A"
msgstr *B"
'''
        invalid_msgid = r'''
msgid "A/
msgstr "B"
'''
        invalid_msgid_plural = r'''
msgid_plural A
msgstr "B"
'''
        invalid_msgstr_continuation = r'''
msgid "A"
msgstr ""
"B
'''
        for data in (invalid_msgid, invalid_msgid_plural, invalid_msgstr, invalid_msgstr_continuation):
            try:
                polib.pofile(data)
                self.fail("Strings not delimited by double quotes not detected")
            except IOError as ex:
                msg = 'string not delimited by double quotes'
                self.assertIn(msg, str(ex))

    def test_syntax_error1(self):
        """
        Test that syntax error is raised while processing a symbol parsing.
        """
        try:
            polib.pofile('tests/test_syntax_error1.po')
            self.fail("Syntax error not detected")
        except IOError:
            exc = sys.exc_info()[1]
            msg = "Syntax error in po file tests/test_syntax_error1.po (line 5)"
            self.assertEqual(str(exc), msg)

    def test_detect_encoding1(self):
        """
        Test that given encoding is returned when file has no encoding defined.
        """
        self.assertEqual(polib.detect_encoding('tests/test_noencoding.po'), 'utf-8')

    def test_detect_encoding2(self):
        """
        Test with a .pot file.
        """
        self.assertEqual(polib.detect_encoding('tests/test_merge.pot'), 'utf-8')

    def test_detect_encoding3(self):
        """
        Test with an utf8 .po file.
        """
        self.assertEqual(polib.detect_encoding('tests/test_utf8.po'), 'UTF-8')

    def test_detect_encoding4(self):
        """
        Test with utf8 data (no file).
        """
        if polib.PY3:
            f = open('tests/test_utf8.po', 'rb')
            data = str(f.read(), 'utf-8')
        else:
            f = open('tests/test_utf8.po', 'r')
            data = f.read()
        try:
            self.assertEqual(polib.detect_encoding(data), 'UTF-8')
        finally:
            f.close()

    def test_detect_encoding5(self):
        """
        Test with utf8 .mo file.
        """
        self.assertEqual(polib.detect_encoding('tests/test_utf8.mo', True), 'UTF-8')

    def test_detect_encoding6(self):
        """
        Test with iso-8859-15 .po file.
        """
        self.assertEqual(polib.detect_encoding('tests/test_iso-8859-15.po'), 'ISO_8859-15')

    def test_detect_encoding7(self):
        """
        Test with iso-8859-15 .mo file.
        """
        self.assertEqual(polib.detect_encoding('tests/test_iso-8859-15.mo', True), 'ISO_8859-15')

    def test_escape(self):
        """
        Tests the escape function.
        """
        self.assertEqual(
            polib.escape('\\t and \\n and \\r and " and \\ and \\\\ and \\v and \\b and \\f and \\a'),
            '\\\\t and \\\\n and \\\\r and \\" and \\\\ and \\\\\\\\ and \\\\v and \\\\b and \\\\f and \\\\a'
        )

    def test_unescape(self):
        """
        Tests the unescape function.
        """
        self.assertEqual(
            polib.unescape('\\t and \\n and \\r and \\" and \\\\ and \\v and \\b and \\f and \\a'),
            '\t and \n and \r and \" and \\ and \v and \b and \f and \a'
        )

    def test_pofile_with_subclass(self):
        """
        Test that the pofile function correctly returns an instance of the
        passed in class
        """
        class CustomPOFile(polib.POFile):
            pass

        pofile = polib.pofile('tests/test_indented.po', klass=CustomPOFile)
        self.assertEqual(pofile.__class__, CustomPOFile)

    def test_mofile_with_subclass(self):
        """
        Test that the mofile function correctly returns an instance of the
        passed in class
        """
        class CustomMOFile(polib.MOFile):
            pass

        mofile = polib.mofile('tests/test_utf8.mo', klass=CustomMOFile)
        self.assertEqual(mofile.__class__, CustomMOFile)

    def test_empty(self):
        po = polib.pofile('')
        self.assertEqual(po.__unicode__(), '#\nmsgid ""\nmsgstr ""\n')

    def test_linenum_1(self):
        po = polib.pofile('tests/test_utf8.po')
        self.assertEqual(po[0].linenum, 17)

    def test_linenum_2(self):
        po = polib.pofile('tests/test_utf8.po')
        self.assertEqual(po.find('XML text').linenum, 1798)

    def test_linenum_3(self):
        po = polib.pofile('tests/test_utf8.po')
        self.assertEqual(po[-1].linenum, 3477)

    def test_windows_path_occurrences(self):
        po = polib.pofile('tests/test_weird_occurrences.po')
        self.assertEqual(po[0].occurrences, [('C:\\foo\\bar.py', '12')])

    def test_is_file(self):
        self.assertTrue(polib._is_file(os.path.abspath(__file__)))
        self.assertFalse(polib._is_file('This is not a file !!!!'))
        self.assertFalse(polib._is_file(True))


class TestBaseFile(unittest.TestCase):
    """
    Tests for the _BaseFile class.
    """

    def test_append1(self):
        pofile = polib.pofile('tests/test_pofile_helpers.po')
        entry = polib.POEntry(msgid="Foo", msgstr="Bar", msgctxt="Some context")
        pofile.append(entry)
        self.assertTrue(entry in pofile)

    def test_append2(self):
        def add_duplicate():
            pofile = polib.pofile('tests/test_pofile_helpers.po', check_for_duplicates=True)
            pofile.append(polib.POEntry(msgid="and"))
        self.assertRaises(ValueError, add_duplicate)

    def test_append3(self):
        def add_duplicate():
            pofile = polib.pofile('tests/test_pofile_helpers.po', check_for_duplicates=True)
            pofile.append(polib.POEntry(msgid="and", msgctxt="some context"))
        self.assertRaises(ValueError, add_duplicate)

    def test_append4(self):
        pofile = polib.pofile('tests/test_pofile_helpers.po', check_for_duplicates=True)
        entry = polib.POEntry(msgid="and", msgctxt="some different context")
        pofile.append(entry)
        self.assertTrue(entry in pofile)

    def test_insert1(self):
        pofile = polib.pofile('tests/test_pofile_helpers.po')
        entry = polib.POEntry(msgid="Foo", msgstr="Bar", msgctxt="Some context")
        pofile.insert(0, entry)
        self.assertEqual(pofile[0], entry)

    def test_insert2(self):
        def add_duplicate():
            pofile = polib.pofile('tests/test_pofile_helpers.po', check_for_duplicates=True)
            pofile.insert(0, polib.POEntry(msgid="and", msgstr="y"))
        self.assertRaises(ValueError, add_duplicate)

    def test_metadata_as_entry(self):
        pofile = polib.pofile('tests/test_fuzzy_header.po')
        f = open('tests/test_fuzzy_header.po')
        lines  = f.readlines()[2:]
        f.close()
        self.assertEqual(pofile.metadata_as_entry().__unicode__(), "".join(lines))

    def test_find1(self):
        pofile = polib.pofile('tests/test_pofile_helpers.po')
        entry = pofile.find('and')
        self.assertEqual(entry.msgstr, u('y'))

    def test_find2(self):
        pofile = polib.pofile('tests/test_pofile_helpers.po')
        entry = pofile.find('pacote', by="msgstr")
        self.assertEqual(entry, None)

    def test_find3(self):
        pofile = polib.pofile('tests/test_pofile_helpers.po')
        entry = pofile.find('package', include_obsolete_entries=True)
        self.assertEqual(entry.msgstr, u('pacote'))

    def test_find4(self):
        pofile = polib.pofile('tests/test_utf8.po')
        entry1 = pofile.find('test context', msgctxt='@context1')
        entry2 = pofile.find('test context', msgctxt='@context2')
        self.assertEqual(entry1.msgstr, u('test context 1'))
        self.assertEqual(entry2.msgstr, u('test context 2'))

    def test_find5(self):
        pofile = polib.pofile('tests/test_msgctxt.po')
        entry1 = pofile.find('some string')
        entry2 = pofile.find('some string', msgctxt='Some message context')
        self.assertEqual(entry1.msgstr, u('une cha\u00eene sans contexte'))
        self.assertEqual(entry2.msgstr, u('une cha\u00eene avec contexte'))

    def test_save1(self):
        pofile = polib.POFile()
        self.assertRaises(IOError, pofile.save)

    def test_save2(self):
        fd, tmpfile = tempfile.mkstemp()
        os.close(fd)
        try:
            pofile = polib.POFile()
            pofile.save(tmpfile)
            pofile.save()
            self.assertTrue(os.path.isfile(tmpfile))
        finally:
            os.remove(tmpfile)

    def test_ordered_metadata(self):
        pofile = polib.pofile('tests/test_fuzzy_header.po')
        f = open('tests/test_fuzzy_header.po')
        lines  = f.readlines()[2:]
        f.close()
        mdata  = [
            ('Project-Id-Version', u('PACKAGE VERSION')),
            ('Report-Msgid-Bugs-To', u('')),
            ('POT-Creation-Date', u('2010-02-08 16:57+0100')),
            ('PO-Revision-Date', u('YEAR-MO-DA HO:MI+ZONE')),
            ('Last-Translator', u('FULL NAME <EMAIL@ADDRESS>')),
            ('Language-Team', u('LANGUAGE <LL@li.org>')),
            ('MIME-Version', u('1.0')),
            ('Content-Type', u('text/plain; charset=UTF-8')),
            ('Content-Transfer-Encoding', u('8bit')),
            ('X-Poedit-SearchPath-1', u('Foo')),
            ('X-Poedit-SearchPath-2', u('Bar')),
            ('X-Poedit-SearchPath-10', u('Baz')),
        ]
        self.assertEqual(pofile.ordered_metadata(), mdata)

    def test_unicode1(self):
        pofile  = polib.pofile('tests/test_merge_after.po')
        f = codecs.open('tests/test_merge_after.po', encoding='utf8')
        expected = f.read()
        f.close()
        self.assertEqual(pofile.__unicode__(), expected)

    def test_unicode2(self):
        pofile  = polib.pofile('tests/test_iso-8859-15.po')
        f = codecs.open('tests/test_iso-8859-15.po', encoding='iso-8859-15')
        expected = f.read()
        f.close()
        self.assertEqual(pofile.__unicode__(), expected)

    def test_str(self):
        pofile  = polib.pofile('tests/test_iso-8859-15.po')
        if polib.PY3:
            f = codecs.open('tests/test_iso-8859-15.po', encoding='iso-8859-15')
        else:
            f = open('tests/test_iso-8859-15.po')
        expected = f.read()
        f.close()
        self.assertEqual(str(pofile), expected)

    def test_wrapping(self):
        pofile  = polib.pofile('tests/test_wrap.po', wrapwidth=50)
        expected = r'''# test wrapping
msgid ""
msgstr ""

msgid "This line will not be wrapped"
msgstr ""

msgid ""
"Some line that contain special characters \" and"
" that \t is very, very, very long...: %s \n"
msgstr ""

msgid ""
"Some line that contain special characters "
"\"foobar\" and that contains whitespace at the "
"end          "
msgstr ""
'''
        self.assertEqual(str(pofile), expected)

    def test_sort(self):
        a1 = polib.POEntry(msgid='a1', occurrences=[('b.py', 1), ('b.py', 3)])
        a2 = polib.POEntry(msgid='a2')
        a3 = polib.POEntry(msgid='a1', occurrences=[('b.py', 1), ('b.py', 3)], obsolete=True)
        b1 = polib.POEntry(msgid='b1', occurrences=[('b.py', 1), ('b.py', 3)])
        b2 = polib.POEntry(msgid='b2', occurrences=[('d.py', 3), ('b.py', 1)])
        c1 = polib.POEntry(msgid='c1', occurrences=[('a.py', 1), ('b.py', 1)])
        c2 = polib.POEntry(msgid='c2', occurrences=[('a.py', 1), ('a.py', 3)])
        pofile = polib.POFile()
        pofile.append(b1)
        pofile.append(a3)
        pofile.append(a2)
        pofile.append(a1)
        pofile.append(b2)
        pofile.append(c1)
        pofile.append(c2)
        pofile.sort()
        expected = u('''#
msgid ""
msgstr ""

msgid "a2"
msgstr ""

#: a.py:1 a.py:3
msgid "c2"
msgstr ""

#: a.py:1 b.py:1
msgid "c1"
msgstr ""

#: b.py:1 b.py:3
msgid "a1"
msgstr ""

#: b.py:1 b.py:3
msgid "b1"
msgstr ""

#: d.py:3 b.py:1
msgid "b2"
msgstr ""

#~ msgid "a1"
#~ msgstr ""
''')
        self.assertEqual(pofile.__unicode__(), expected)

    def test_trailing_comment(self):
        pofile  = polib.pofile('tests/test_trailing_comment.po')
        expected = r'''#
msgid ""
msgstr "Content-Type: text/plain; charset=UTF-8\n"

msgid "foo"
msgstr "oof"
'''
        self.assertEqual(str(pofile), expected)

    def test_comment_ordering(self):
        """
        Test that "# " comments appear before "#. " comments when writing.
        """
        pofile  = polib.pofile('tests/test_comment_ordering.po')
        expected = r'''#
msgid ""
msgstr "Content-Type: text/plain; charset=UTF-8\n"

# First comment line
#. Second comment line
msgid "foo"
msgstr "oof"
'''
        self.assertEqual(str(pofile), expected)

class TestPoFile(unittest.TestCase):
    """
    Tests for PoFile class.
    """

    def test_save_as_mofile(self):
        """
        Test for the POFile.save_as_mofile() method.
        """
        msgfmt = which('msgfmt')
        if msgfmt is None:
            try:
                return unittest.skip('msgfmt is not installed')
            except AttributeError:
                return
        reffiles = ['tests/test_utf8.po', 'tests/test_iso-8859-15.po']
        encodings = ['utf-8', 'iso-8859-15']
        for reffile, encoding in zip(reffiles, encodings):
            fd, tmpfile1 = tempfile.mkstemp()
            os.close(fd)
            fd, tmpfile2 = tempfile.mkstemp()
            os.close(fd)
            po = polib.pofile(reffile, autodetect_encoding=False, encoding=encoding)
            po.save_as_mofile(tmpfile1)
            subprocess.call([msgfmt, '--no-hash', '--endianness=%s' % sys.byteorder, '-o', tmpfile2, reffile])
            try:
                f = open(tmpfile1, 'rb')
                s1 = f.read()
                f.close()
                f = open(tmpfile2, 'rb')
                s2 = f.read()
                f.close()
                self.assertEqual(s1, s2)
            finally:
                os.remove(tmpfile1)
                os.remove(tmpfile2)

    def test_merge(self):
        refpot = polib.pofile('tests/test_merge.pot')
        po = polib.pofile('tests/test_merge_before.po')
        po.merge(refpot)
        expected_po = polib.pofile('tests/test_merge_after.po')
        self.assertEqual(po, expected_po)

    def test_percent_translated(self):
        po = polib.pofile('tests/test_pofile_helpers.po')
        self.assertEqual(po.percent_translated(), 53)
        po = polib.POFile()
        self.assertEqual(po.percent_translated(), 100)

    def test_translated_entries(self):
        po = polib.pofile('tests/test_pofile_helpers.po')
        self.assertEqual(len(po.translated_entries()), 7)

    def test_untranslated_entries(self):
        po = polib.pofile('tests/test_pofile_helpers.po')
        self.assertEqual(len(po.untranslated_entries()), 4)

    def test_fuzzy_entries(self):
        po = polib.pofile('tests/test_pofile_helpers.po')
        self.assertEqual(len(po.fuzzy_entries()), 2)

    def test_obsolete_entries(self):
        po = polib.pofile('tests/test_pofile_helpers.po')
        self.assertEqual(len(po.obsolete_entries()), 4)

    def test_unusual_metadata_location(self):
        po = polib.pofile('tests/test_unusual_metadata_location.po')
        self.assertNotEqual(po.metadata, {})
        self.assertEqual(po.metadata['Content-Type'], 'text/plain; charset=UTF-8')

    def test_comment_starting_with_two_hashes(self):
        po = polib.pofile('tests/test_utf8.po')
        e = po.find("Some comment starting with two '#'", by='tcomment')
        self.assertTrue(isinstance(e, polib.POEntry))

    def test_word_garbage(self):
        po = polib.pofile('tests/test_word_garbage.po')
        e = po.find("Whatever", by='msgid')
        self.assertTrue(isinstance(e, polib.POEntry))

    def test_compare1(self):
        entry = polib.POEntry(msgid="foo")
        other = polib.POEntry(msgctxt="Some context", msgid="foo")
        self.assertNotEqual(entry, other)

    def test_compare2(self):
        entry = polib.POEntry(msgid="foo")
        other = polib.POEntry(msgid_plural="Plural", msgid="foo")
        self.assertNotEqual(entry, other)

    def test_compare3(self):
        entry = polib.POEntry(
            msgid_plural="Plural", msgid="foo"
        )
        other = polib.POEntry(
            msgid_plural="Plural", msgstr_plural={0: "Value", 1: "Values"}, msgid="foo"
        )
        self.assertNotEqual(entry, other)

    def test_compare4(self):
        entry = polib.POEntry(msgctxt="Some context", msgid="foo")
        other = polib.POEntry(msgctxt="Other context", msgid="foo")
        self.assertNotEqual(entry, other)

    def test_compare5(self):
        entry = polib.POEntry(msgid_plural="Some plural", msgid="foo")
        other = polib.POEntry(msgid_plural="Other plural", msgid="foo")
        self.assertNotEqual(entry, other)

    def test_compare6(self):
        entry = polib.POEntry(msgstr_plural={0: "Value", 1: "Values"}, msgid="foo")
        other = polib.POEntry(msgstr_plural={0: "Other value", 1: "Other values"}, msgid="foo")
        self.assertTrue(entry > other)

    def test_compare7(self):
        entry = polib.POEntry(msgstr="Some msgstr", msgid="foo")
        other = polib.POEntry(msgstr="Other msgstr", msgid="foo")
        self.assertTrue(entry >= other)
        self.assertNotEqual(entry, other)
        entry = polib.POEntry(msgstr="A msgstr", msgid="foo")
        other = polib.POEntry(msgstr="Other msgstr", msgid="foo")
        self.assertTrue(entry <= other)
        self.assertNotEqual(entry, other)

    def test_compare8(self):
        entry = polib.POEntry(
            msgctxt="Some context", msgid_plural="Plural",
            msgstr_plural={0: "Value", 1: "Values"}, msgid="foo"
        )
        other = polib.POEntry(
            msgctxt="Some context", msgid_plural="Plural",
            msgstr_plural={0: "Value", 1: "Values"}, msgid="foo"
        )
        self.assertEqual(entry, other)

    def test_fuzzy_obsolete(self):
        pofile = polib.pofile('tests/test_obsolete_is_not_fuzzy.po')
        self.assertEqual(len(pofile.fuzzy_entries()), 1)

    def test_set_fuzzy(self):
        pofile = polib.pofile('tests/test_set_fuzzy.po')
        pofile[0].fuzzy = True
        pofile[1].fuzzy = False
        self.assertTrue(pofile[0].fuzzy)
        self.assertFalse(pofile[1].fuzzy)

class TestMoFile(unittest.TestCase):
    """
    Tests for MoFile class.
    """
    def test_dummy_methods(self):
        """
        This is stupid and just here for code coverage.
        """
        mo = polib.MOFile()
        self.assertEqual(mo.percent_translated(), 100)
        self.assertEqual(mo.translated_entries(), mo)
        self.assertEqual(mo.untranslated_entries(), [])
        self.assertEqual(mo.fuzzy_entries(), [])
        self.assertEqual(mo.obsolete_entries(), [])

    def test_save_as_pofile(self):
        """
        Test for the MOFile.save_as_pofile() method.
        """
        fd, tmpfile = tempfile.mkstemp()
        os.close(fd)
        mo = polib.mofile('tests/test_utf8.mo', wrapwidth=78)
        mo.save_as_pofile(tmpfile)
        try:
            if polib.PY3:
                f = open(tmpfile, encoding='utf-8')
            else:
                f = open(tmpfile)
            s1 = f.read()
            f.close()
            if polib.PY3:
                f = open('tests/test_save_as_pofile.po', encoding='utf-8')
            else:
                f = open('tests/test_save_as_pofile.po')
            s2 = f.read()
            f.close()
            self.assertEqual(s1, s2)
        finally:
            os.remove(tmpfile)

    def test_msgctxt(self):
        #import pdb; pdb.set_trace()
        mo = polib.mofile('tests/test_msgctxt.mo')
        expected = u('''msgid ""
msgstr "Content-Type: text/plain; charset=UTF-8\u005cn"

msgctxt "Some message context"
msgid "some string"
msgstr "une cha\u00eene avec contexte"

msgctxt "Some other message context"
msgid "singular"
msgid_plural "plural"
msgstr[0] "singulier"
msgstr[1] "pluriel"

msgid "some string"
msgstr "une cha\u00eene sans contexte"
''')
        self.assertEqual(mo.__unicode__(), expected)

    def test_invalid_version(self):
        self.assertRaises(IOError, polib.mofile, 'tests/test_invalid_version.mo')
        polib.mofile('tests/test_version_1.1.mo')

    def test_no_header(self):
        mo = polib.mofile('tests/test_no_header.mo')
        expected = u('''msgid ""
msgstr ""

msgid "bar"
msgstr "rab"

msgid "foo"
msgstr "oof"
''')
        self.assertEqual(mo.__unicode__(), expected)


class TestLazyMOFile(unittest.TestCase):
    """
    Tests for the read-only lazy mo view (LazyMOView / lazy_mofile).
    """
    def _catalog(self, n=32, charset='utf-8'):
        po = polib.POFile()
        po.metadata = {
            'Content-Type': 'text/plain; charset=%s' % charset,
            'Language': 'fr',
        }
        for i in range(n):
            po.append(polib.POEntry(
                msgid='message-%04d' % i,
                msgstr='traduction-%04d' % i
            ))
        po.append(polib.POEntry(
            msgid='one file', msgid_plural='many files',
            msgstr_plural={0: 'un fichier', 1: 'plusieurs fichiers'}
        ))
        po.append(polib.POEntry(msgid='shared', msgstr='sans contexte'))
        po.append(polib.POEntry(msgctxt='menu', msgid='shared',
                                msgstr='avec contexte'))
        return po

    def _mo_bytes(self, po, big_endian=False):
        data = po.to_binary()
        if not big_endian:
            return data
        nstrings = struct.unpack('<I', data[8:12])[0]
        # only the 7 word header and the index words are endian dependent,
        # the string tables stay byte identical
        word_area = 28 + nstrings * 16
        swapped = bytearray()
        for i in range(0, word_area, 4):
            swapped += data[i:i + 4][::-1]
        return bytes(swapped) + data[word_area:]

    def _write(self, data):
        fd, tmpfile = tempfile.mkstemp(suffix='.mo')
        os.write(fd, data)
        os.close(fd)
        return tmpfile

    def test_factory_and_basic_find(self):
        for use_mmap in (True, False):
            po = self._catalog()
            path = self._write(self._mo_bytes(po))
            try:
                view = polib.lazy_mofile(path, use_mmap=use_mmap)
                self.assertIsInstance(view, polib.LazyMOView)
                # opening the view decodes no entry at all
                self.assertEqual(view.decoded_entries, 0)
                self.assertEqual(len(view), len(po))
                self.assertEqual(view.metadata['Language'], 'fr')
                self.assertEqual(view.find('message-0007').msgstr,
                                 'traduction-0007')
                self.assertEqual(view.decoded_entries, 1)
                self.assertIsNone(view.find('does-not-exist'))
                # a miss never decodes an entry
                self.assertEqual(view.decoded_entries, 1)
                view.close()
            finally:
                os.remove(path)

    def test_both_endiannesses(self):
        po = self._catalog()
        for big_endian in (False, True):
            data = self._mo_bytes(po, big_endian=big_endian)
            view = polib.lazy_mofile(data)
            self.assertEqual(view.magic_number,
                             polib.MOFile.MAGIC_SWAPPED if big_endian
                             else polib.MOFile.MAGIC)
            self.assertEqual(view.find('message-0001').msgstr,
                             'traduction-0001')
            self.assertEqual(view.find('one file').msgstr_plural,
                             {0: 'un fichier', 1: 'plusieurs fichiers'})
            self.assertEqual(
                view.find('shared', msgctxt='menu').msgstr,
                'avec contexte'
            )
            self.assertEqual(view.find('shared').msgstr, 'sans contexte')
            # full iteration equals the eager parser content
            eager = polib.mofile(data)
            self.assertEqual(
                [e.msgid_with_context for e in view],
                [e.msgid_with_context for e in eager]
            )
            view.close()

    def test_context_and_plural_composite_keys(self):
        po = self._catalog()
        view = polib.lazy_mofile(self._mo_bytes(po))
        self.assertEqual(view.find('shared', msgctxt='menu').msgstr,
                         'avec contexte')
        # the wrong context must not match
        self.assertIsNone(view.find('shared', msgctxt='other'))
        # no msgctxt argument returns the context free message
        self.assertEqual(view.find('shared').msgstr, 'sans contexte')
        plural = view.find('one file')
        self.assertEqual(plural.msgid_plural, 'many files')
        self.assertEqual(plural.msgstr_plural[1], 'plusieurs fichiers')
        view.close()

    def test_lazy_decode_count(self):
        # laziness is verified structurally by counting decoded entries, not
        # by measuring execution time
        po = self._catalog(n=500)
        path = self._write(self._mo_bytes(po))
        try:
            view = polib.lazy_mofile(path)
            self.assertEqual(view.decoded_entries, 0)
            view.find('message-0000')
            view.find('message-0499')
            view.find('missing')
            self.assertEqual(view.decoded_entries, 2)
            entries = list(view)
            self.assertEqual(len(entries), len(po))
            self.assertEqual(view.decoded_entries, 2 + len(po))
            view.close()
        finally:
            os.remove(path)

    def test_iteration_indexing_and_contains(self):
        po = self._catalog()
        view = polib.lazy_mofile(self._mo_bytes(po))
        entries = list(view)
        self.assertEqual(len(entries), len(view))
        self.assertEqual(view[0].msgid_with_context,
                         entries[0].msgid_with_context)
        self.assertEqual(view[-1].msgid_with_context,
                         entries[-1].msgid_with_context)
        self.assertEqual(len(view[1:4]), 3)
        self.assertIn(view.find('message-0003'), view)
        self.assertNotIn(polib.MOEntry(msgid='nope'), view)
        self.assertRaises(IndexError, view.__getitem__, len(po) + 10)
        view.close()

    def test_materialized_entry_survives_close(self):
        po = self._catalog()
        path = self._write(self._mo_bytes(po))
        try:
            view = polib.lazy_mofile(path)
            entry = view.materialize(2)
            self.assertIsInstance(entry, polib.MOEntry)
            view.close()
            # the materialized entry does not depend on the mapped source
            self.assertEqual(entry.msgstr,
                             'traduction-%04d' %
                             int(entry.msgid.split('-')[1]))
        finally:
            os.remove(path)

    def test_closed_view_fails_explicitly(self):
        view = polib.lazy_mofile(self._mo_bytes(self._catalog()))
        view.close()
        self.assertTrue(view.closed)
        self.assertRaises(ValueError, view.find, 'message-0000')
        self.assertRaises(ValueError, len, view)
        self.assertRaises(ValueError, list, view)
        self.assertRaises(ValueError, view.materialize, 0)
        # context manager closes the view too
        with polib.lazy_mofile(self._mo_bytes(self._catalog())) as cm:
            self.assertEqual(cm.find('message-0000').msgstr,
                             'traduction-0000')
        self.assertTrue(cm.closed)

    def test_external_stream_not_closed(self):
        stream = io.BytesIO(self._mo_bytes(self._catalog()))
        view = polib.lazy_mofile(stream)
        self.assertEqual(view.find('message-0001').msgstr, 'traduction-0001')
        view.close()
        self.assertFalse(stream.closed)

    def test_charset_detected_from_header(self):
        header = b'Content-Type: text/plain; charset=ISO-8859-15\n'
        data = self._build_raw_mo(
            [(b'cha\xeene', b'r\xe9ponse')], header=header
        )
        view = polib.lazy_mofile(data)
        self.assertEqual(view.encoding.lower(), 'iso-8859-15')
        entry = view.find('cha\u00eene')
        self.assertEqual((entry.msgid, entry.msgstr),
                         ('cha\u00eene', 'r\u00e9ponse'))
        view.close()

    def test_to_mofile_matches_eager_parser(self):
        data = self._mo_bytes(self._catalog())
        lazy = polib.lazy_mofile(data)
        eager = polib.mofile(data)
        self.assertEqual(str(lazy.to_mofile()), str(eager))
        lazy.close()

    def test_fixture_parity(self):
        for fixture in ('tests/test_utf8.mo', 'tests/test_msgctxt.mo',
                        'tests/test_no_header.mo',
                        'tests/test_version_1.1.mo'):
            eager = polib.mofile(fixture)
            lazy = polib.lazy_mofile(fixture)
            self.assertEqual(len(lazy), len(eager), fixture)
            for entry in eager:
                found = lazy.find(entry.msgid,
                                  msgctxt=entry.msgctxt if entry.msgctxt
                                  else False)
                self.assertIsNotNone(found, (fixture, entry.msgid))
                self.assertEqual(found.msgstr, entry.msgstr, fixture)
                self.assertEqual(found.msgstr_plural, entry.msgstr_plural,
                                 fixture)
            lazy.close()

    def test_corrupt_indexes_are_rejected(self):
        data = self._mo_bytes(self._catalog())

        def corrupt(words):
            broken = bytearray(data)
            for offset, value in words.items():
                struct.pack_into('<I', broken, offset, value)
            return bytes(broken)

        # truncated file
        self.assertRaises(IOError, polib.lazy_mofile, data[:20])
        # bad magic
        self.assertRaises(IOError, polib.lazy_mofile,
                          corrupt({0: 0xdeadbeef}))
        # unsupported major revision
        self.assertRaises(IOError, polib.lazy_mofile, corrupt({4: 2 << 16}))
        # overflowing number of strings
        self.assertRaises(IOError, polib.lazy_mofile,
                          corrupt({8: 0xffffffff}))
        # index tables pointing outside the file
        self.assertRaises(IOError, polib.lazy_mofile,
                          corrupt({12: 0xfffffff0}))
        self.assertRaises(IOError, polib.lazy_mofile,
                          corrupt({16: 0xfffffff0}))
        # the key index table overlapping the 28 bytes header
        self.assertRaises(IOError, polib.lazy_mofile, corrupt({12: 0}))
        # a corrupted string offset pointing outside the file (second entry
        # of the key index table: offset word at 28 + 8 + 4)
        self.assertRaises(IOError, polib.lazy_mofile,
                          corrupt({28 + 8 + 4: 0xfffffff0}))

    @staticmethod
    def _build_raw_mo(entries, header=b'', little_endian=True):
        entries = sorted(entries)
        if header:
            entries = [(b'', header)] + entries
        n = len(entries)
        prefix = '<' if little_endian else '>'
        keystart = 28 + 16 * n
        ids, values, offsets = b'', b'', []
        for key, value in entries:
            offsets.append((len(ids), len(key), len(values), len(value)))
            ids += key + b'\0'
            values += value + b'\0'
        valuestart = keystart + len(ids)
        key_words, value_words = [], []
        for key_off, key_len, value_off, value_len in offsets:
            key_words += [key_len, key_off + keystart]
            value_words += [value_len, value_off + valuestart]
        magic = polib.MOFile.MAGIC if little_endian \
            else polib.MOFile.MAGIC_SWAPPED
        out = struct.pack(prefix + 'IIIIIII', magic, 0, n, 28,
                          28 + 8 * n, 0, 0)
        out += struct.pack(prefix + '%dI' % (4 * n),
                           *(key_words + value_words))
        return out + ids + values

    def test_mo_with_hash_table(self):
        # real msgfmt output embeds an optional hash table; make sure the
        # boundary checks do not reject the legitimate overlapping layout
        for big_endian in (False, True):
            prefix = '>' if big_endian else '<'
            keys = [b'', b'apple', b'banana', b'cherry']
            values = {
                b'': b'Content-Type: text/plain; charset=utf-8\n',
                b'apple': b'pomme',
                b'banana': b'banane',
                b'cherry': b'cerise',
            }
            n = len(keys)
            hsize = 4
            hashstart = 28 + 16 * n
            ids_start = hashstart + 4 * hsize
            ids, krecs = b'', []
            for key in keys:
                krecs.append((len(key), ids_start + len(ids)))
                ids += key + b'\0'
            vals_start = ids_start + len(ids)
            strings, vrecs = b'', []
            for key in keys:
                value = values[key]
                vrecs.append((len(value), vals_start + len(strings)))
                strings += value + b'\0'

            def hash_value(key):
                h = 0
                for byte in key:
                    h = (h << 4) + byte
                    g = h & 0xf0000000
                    if g:
                        h ^= g >> 16
                    h &= ~g & 0xffffffff
                return h % hsize

            hashtable = [0] * hsize
            for index, key in enumerate(keys):
                if not key:
                    continue
                slot = hash_value(key)
                while hashtable[slot]:
                    slot = 0 if slot == hsize - 1 else slot + 1
                hashtable[slot] = index + 1

            magic = polib.MOFile.MAGIC
            out = struct.pack(prefix + 'IIIIIII', magic, 0, n, 28,
                              28 + 8 * n, hsize, hashstart)
            records = []
            for length, offset in krecs:
                records += [length, offset]
            for length, offset in vrecs:
                records += [length, offset]
            out += struct.pack(prefix + '%dI' % (4 * n), *records)
            out += struct.pack(prefix + '%dI' % hsize, *hashtable)
            out += ids + strings

            view = polib.lazy_mofile(out)
            self.assertEqual(view.find('apple').msgstr, 'pomme')
            self.assertEqual(view.find('cherry').msgstr, 'cerise')
            self.assertEqual(str(view.to_mofile()),
                             str(polib.mofile(out)))
            view.close()


if __name__ == '__main__':
    unittest.main()
