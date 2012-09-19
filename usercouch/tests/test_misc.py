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


class TestTempPKI(TestCase):
    def test_init(self):
        # client_pki = False
        pki = misc.TempPKI()
        self.assertIsInstance(pki, sslhelpers.PKI)
        self.assertTrue(path.isdir(pki.ssldir))
        self.assertTrue(pki.ssldir.startswith('/tmp/TempPKI.'))
        self.assertEqual(
            repr(pki),
            'TempPKI({!r})'.format(pki.ssldir)
        )

        self.assertIsInstance(pki.server_ca, sslhelpers.CA)
        self.assertIsInstance(pki.server_cert, sslhelpers.Cert)
        self.assertIs(pki.server_ca.ssldir, pki.ssldir)
        self.assertIs(pki.server_cert.ssldir, pki.ssldir)
        self.assertIs(pki.server_cert.ca_id, pki.server_ca.id)

        self.assertIsNone(pki.client_ca)
        self.assertIsNone(pki.client_cert)

        # client_pki = True
        pki = misc.TempPKI(client_pki=True)
        self.assertIsInstance(pki, sslhelpers.PKI)
        self.assertTrue(path.isdir(pki.ssldir))
        self.assertTrue(pki.ssldir.startswith('/tmp/TempPKI.'))
        self.assertEqual(
            repr(pki),
            'TempPKI({!r})'.format(pki.ssldir)
        )

        self.assertIsInstance(pki.server_ca, sslhelpers.CA)
        self.assertIsInstance(pki.server_cert, sslhelpers.Cert)
        self.assertIs(pki.server_ca.ssldir, pki.ssldir)
        self.assertIs(pki.server_cert.ssldir, pki.ssldir)
        self.assertIs(pki.server_cert.ca_id, pki.server_ca.id)

        self.assertIsInstance(pki.client_ca, sslhelpers.CA)
        self.assertIsInstance(pki.client_cert, sslhelpers.Cert)
        self.assertIs(pki.client_ca.ssldir, pki.ssldir)
        self.assertIs(pki.client_cert.ssldir, pki.ssldir)
        self.assertIs(pki.client_cert.ca_id, pki.client_ca.id)


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

    def test_self(self):
        self.assertEqual(self.auth, 'basic')
        self.assertEqual(self.bind_address, '127.0.0.1')
        self.assertIsInstance(self.tmpcouch, TempCouch)
        self.assertEqual(set(self.env), set(['port', 'url', 'basic']))
        self.assertTrue(self.env['url'].startswith('http://127.0.0.1:'))


class SelfTest2(CouchTestCase):
    bind_address = '::1'

    def test_self(self):
        self.assertEqual(self.auth, 'basic')
        self.assertIsInstance(self.tmpcouch, TempCouch)
        self.assertEqual(set(self.env), set(['port', 'url', 'basic']))
        self.assertTrue(self.env['url'].startswith('http://[::1]:'))


class SelfTest3(CouchTestCase):
    auth = 'open'

    def test_self(self):
        self.assertEqual(self.bind_address, '127.0.0.1')
        self.assertIsInstance(self.tmpcouch, TempCouch)
        self.assertEqual(set(self.env), set(['port', 'url']))
        self.assertTrue(self.env['url'].startswith('http://127.0.0.1:'))


class SelfTest4(CouchTestCase):
    auth = 'oauth'

    def test_self(self):
        self.assertEqual(self.bind_address, '127.0.0.1')
        self.assertIsInstance(self.tmpcouch, TempCouch)
        self.assertEqual(set(self.env), set(['port', 'url', 'basic', 'oauth']))
        self.assertTrue(self.env['url'].startswith('http://127.0.0.1:'))


