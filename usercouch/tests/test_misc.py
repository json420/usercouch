# usercouch: Starts per-user CouchDB instances for fun and unit testing
# Copyright (C) 2011 Novacut Inc
#
# This file is part of `usercouch`.
#
# `usercouch` is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# `usercouch` is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with `usercouch`.  If not, see <http://www.gnu.org/licenses/>.
#
# Authors:
#   Jason Gerard DeRose <jderose@novacut.com>

"""
Unit tests for `usercouch.misc` module.
"""

from unittest import TestCase
import subprocess
from os import path

import usercouch
from usercouch.misc import TempCouch, CouchTestCase


class TestTempCouch(TestCase):
    def test_init(self):
        tc = TempCouch()
        self.assertIsInstance(tc, usercouch.UserCouch)
        self.assertTrue(tc.basedir.startswith('/tmp/tmpcouch.'))
        tc.bootstrap()
        self.assertIsInstance(tc.couchdb, subprocess.Popen)
        self.assertTrue(path.isdir(tc.basedir))
        tc.__del__()
        self.assertIsNone(tc.couchdb)
        self.assertFalse(path.exists(tc.basedir))


class SelfTest1(CouchTestCase):
    auth = 'open'

    def test_self(self):
        self.assertIsInstance(self.tmpcouch, TempCouch)
        self.assertEqual(set(self.env), set(['port', 'url']))


class SelfTest2(CouchTestCase):
    auth = 'basic'

    def test_self(self):
        self.assertIsInstance(self.tmpcouch, TempCouch)
        self.assertEqual(set(self.env), set(['port', 'url', 'basic']))


class SelfTest3(CouchTestCase):
    auth = 'oauth'

    def test_self(self):
        self.assertIsInstance(self.tmpcouch, TempCouch)
        self.assertEqual(set(self.env), set(['port', 'url', 'basic', 'oauth']))

