# usercouch: Starts per-user CouchDB instances for fun and unit testing
# Copyright (C) 2012 Novacut Inc
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
Unit tests for the `usercouch.sslhelpers` module.
"""

from unittest import TestCase
from os import path

from usercouch import sslhelpers

from . import TempDir


class TestFunctions(TestCase):
    def test_gen_key(self):
        tmp = TempDir()
        key = tmp.join('key.pem')
        self.assertFalse(path.isfile(key))
        sslhelpers.gen_key(key)
        self.assertTrue(path.isfile(key))
        self.assertGreater(path.getsize(key), 0)

    def test_gen_ca(self):
        tmp = TempDir()
        key = tmp.join('key.pem')
        ca = tmp.join('ca.pem')
        sslhelpers.gen_key(key)
        self.assertFalse(path.isfile(ca))
        sslhelpers.gen_ca(key, '/CN=foobar', ca)
        self.assertTrue(path.isfile(ca))
        self.assertGreater(path.getsize(ca), 0)

    def test_gen_csr(self):
        tmp = TempDir()
        key = tmp.join('key.pem')
        csr = tmp.join('csr.pem')
        sslhelpers.gen_key(key)
        self.assertFalse(path.isfile(csr))
        sslhelpers.gen_csr(key, '/CN=foobar', csr)
        self.assertTrue(path.isfile(csr))
        self.assertGreater(path.getsize(csr), 0)

    def test_sign_csr(self):
        tmp = TempDir()

        # Create the ca
        ca_key = tmp.join('ca_key.pem')
        ca = tmp.join('ca.pem')
        sslhelpers.gen_key(ca_key)
        sslhelpers.gen_ca(ca_key, '/CN=user_id', ca)

        # Create the machine key and csr
        key = tmp.join('key.pem')
        csr = tmp.join('csr.pem')
        sslhelpers.gen_key(key)
        sslhelpers.gen_csr(key, '/CN=machine_id', csr)

        # Now sign the csr
        cert = tmp.join('cert.pem')
        self.assertFalse(path.isfile(cert))
        sslhelpers.sign_csr(csr, ca, ca_key, cert)
        self.assertTrue(path.isfile(cert))
        self.assertGreater(path.getsize(cert), 0)     

