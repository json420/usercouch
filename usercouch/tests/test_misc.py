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
from usercouch import sslhelpers
from usercouch import misc
from usercouch.misc import TempCouch, CouchTestCase


class TestTempCerts(TestCase):
    def test_init(self):
        tc = misc.TempCerts()
        self.assertTrue(path.isdir(tc.ssldir))
        self.assertTrue(tc.ssldir.startswith('/tmp/TempCerts.'))
        self.assertIsInstance(tc.user, sslhelpers.User)
        self.assertIsInstance(tc.machine, sslhelpers.Machine)
        self.assertEqual(tc.user.ssldir, tc.ssldir)
        self.assertEqual(tc.machine.ssldir, tc.ssldir)
        self.assertIs(tc.machine.user, tc.user)
        self.assertEqual(tc.user.id, tc.user_id)
        self.assertEqual(tc.machine.machine_id, tc.machine_id)
        self.assertEqual(tc.machine.id,
            '-'.join([tc.user_id, tc.machine_id])
        )

    def test_get_user(self):
        tc = misc.TempCerts()
        user_id = usercouch.random_b32()
        user = tc.get_user(user_id)
        self.assertIsInstance(user, sslhelpers.User)
        self.assertEqual(user.ssldir, tc.ssldir)
        self.assertEqual(user.id, user_id)


class TestTempCouch(TestCase):
    def test_init(self):
        tc = TempCouch()
        self.assertIsInstance(tc, usercouch.UserCouch)
        self.assertTrue(tc.basedir.startswith('/tmp/TempCouch.'))
        tc.bootstrap()
        self.assertIsInstance(tc.couchdb, subprocess.Popen)
        self.assertTrue(path.isdir(tc.basedir))
        tc.__del__()
        self.assertIsNone(tc.couchdb)
        self.assertFalse(path.exists(tc.basedir))

    def test_repr(self):
        tc = TempCouch()
        self.assertEqual(
            repr(tc),
            'TempCouch({!r})'.format(tc.basedir)
        )


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

