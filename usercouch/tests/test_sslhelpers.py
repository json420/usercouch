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

from usercouch import random_b32
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


class TestHelper(TestCase):
    def test_init(self):
        tmp = TempDir()
        _id = random_b32()
        inst = sslhelpers.Helper(tmp.dir, _id)
        self.assertEqual(inst.ssldir, tmp.dir)
        self.assertEqual(inst.id, _id)
        self.assertEqual(inst.subject, '/CN=' + _id)
        self.assertEqual(inst.key, tmp.join(_id + '-key.pem'))

    def test_gen_key(self):
        tmp = TempDir()
        _id = random_b32()
        inst = sslhelpers.Helper(tmp.dir, _id)
        self.assertFalse(path.isfile(inst.key))
        inst.gen_key()
        self.assertGreater(path.getsize(inst.key), 0)


class TestUser(TestCase):
    def test_init(self):
        tmp = TempDir()
        _id = random_b32()
        inst = sslhelpers.User(tmp.dir, _id)
        self.assertEqual(inst.ssldir, tmp.dir)
        self.assertEqual(inst.id, _id)
        self.assertEqual(inst.subject, '/CN=' + _id)
        self.assertEqual(inst.key, tmp.join(_id + '-key.pem'))
        self.assertEqual(inst.ca, tmp.join(_id + '-ca.pem'))

    def test_gen(self):
        tmp = TempDir()
        _id = random_b32()
        inst = sslhelpers.User(tmp.dir, _id)
        self.assertFalse(path.isfile(inst.key))
        self.assertFalse(path.isfile(inst.ca))
        inst.gen()
        self.assertGreater(path.getsize(inst.key), 0)
        self.assertGreater(path.getsize(inst.ca), 0)

    def test_sign(self):
        tmp = TempDir()
        user_id = random_b32()
        machine_id = random_b32()
        user = sslhelpers.User(tmp.dir, user_id)
        user.gen()
        machine = sslhelpers.Machine(tmp.dir, machine_id)
        machine.gen()
        self.assertFalse(path.isfile(machine.cert))
        user.sign(machine)
        self.assertGreater(path.getsize(machine.cert), 0)


class TestMachine(TestCase):
    def test_init(self):
        tmp = TempDir()
        _id = random_b32()
        inst = sslhelpers.Machine(tmp.dir, _id)
        self.assertEqual(inst.ssldir, tmp.dir)
        self.assertEqual(inst.id, _id)
        self.assertEqual(inst.subject, '/CN=' + _id)
        self.assertEqual(inst.key, tmp.join(_id + '-key.pem'))
        self.assertEqual(inst.csr, tmp.join(_id + '-csr.pem'))
        self.assertEqual(inst.cert, tmp.join(_id + '-cert.pem'))

    def test_gen(self):
        tmp = TempDir()
        _id = random_b32()
        inst = sslhelpers.Machine(tmp.dir, _id)
        self.assertFalse(path.isfile(inst.key))
        self.assertFalse(path.isfile(inst.csr))
        inst.gen()
        self.assertGreater(path.getsize(inst.key), 0)
        self.assertGreater(path.getsize(inst.csr), 0)

    def test_get_ssl_env(self):
        tmp = TempDir()
        user_id = random_b32()
        machine_id = random_b32()
        user = sslhelpers.User(tmp.dir, user_id)
        machine = sslhelpers.Machine(tmp.dir, machine_id)
        self.assertEqual(
            machine.get_ssl_env(user),
            {
                'key_file': tmp.join(machine_id + '-key.pem'),
                'cert_file': tmp.join(machine_id + '-cert.pem'),
                'ca_file': tmp.join(user_id + '-ca.pem'),
                'check_hostname': False,
            }
        )
