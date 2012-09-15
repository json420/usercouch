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
import os
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
        self.assertEqual(inst.key_file, tmp.join(_id + '-key.pem'))

    def test_gen_key(self):
        tmp = TempDir()
        _id = random_b32()
        inst = sslhelpers.Helper(tmp.dir, _id)
        self.assertFalse(path.isfile(inst.key_file))
        self.assertTrue(inst.gen_key())
        self.assertGreater(path.getsize(inst.key_file), 0)
        self.assertFalse(inst.gen_key())
        os.remove(inst.key_file)
        self.assertTrue(inst.gen_key())
        self.assertGreater(path.getsize(inst.key_file), 0)
        self.assertFalse(inst.gen_key())


class TestUser(TestCase):
    def test_init(self):
        tmp = TempDir()
        user_id = random_b32()
        user = sslhelpers.User(tmp.dir, user_id)
        self.assertEqual(user.ssldir, tmp.dir)
        self.assertEqual(user.id, user_id)
        self.assertEqual(user.subject, '/CN=' + user_id)
        self.assertEqual(user.key_file, tmp.join(user_id + '-key.pem'))
        self.assertEqual(user.ca_file, tmp.join(user_id + '-ca.pem'))

    def test_gen_ca(self):
        tmp = TempDir()
        user_id = random_b32()
        user = sslhelpers.User(tmp.dir, user_id)
        self.assertFalse(path.isfile(user.key_file))
        self.assertFalse(path.isfile(user.ca_file))
        self.assertTrue(user.gen_ca())
        self.assertGreater(path.getsize(user.key_file), 0)
        self.assertGreater(path.getsize(user.ca_file), 0)
        self.assertFalse(user.gen_ca())
        os.remove(user.ca_file)
        self.assertTrue(user.gen_ca())
        self.assertGreater(path.getsize(user.ca_file), 0)

    def test_sign(self):
        tmp = TempDir()
        user_id = random_b32()
        user = sslhelpers.User(tmp.dir, user_id)
        key = tmp.join('key.pem')
        csr = tmp.join('csr.pem')
        cert = tmp.join('cert.pem')
        sslhelpers.gen_key(key)
        sslhelpers.gen_csr(key, '/CN=foobar', csr)
        self.assertTrue(user.gen())
        self.assertFalse(path.exists(cert))
        user.sign(csr, cert)
        self.assertGreater(path.getsize(cert), 0)

    def test_get_machine(self):
        tmp = TempDir()
        user_id = random_b32()
        machine_id = random_b32()
        _id = user_id + '-' + machine_id
        user = sslhelpers.User(tmp.dir, user_id)
        machine = user.get_machine(machine_id)
        self.assertIsInstance(machine, sslhelpers.Machine)
        self.assertIs(machine.user, user)
        self.assertIs(machine.machine_id, machine_id)
        self.assertEqual(machine.ssldir, tmp.dir)
        self.assertEqual(machine.id, _id)
        self.assertFalse(user.gen())
        self.assertFalse(machine.gen())

class TestMachine(TestCase):
    def test_init(self):
        tmp = TempDir()
        user_id = random_b32()
        machine_id = random_b32()
        _id = user_id + '-' + machine_id
        user = sslhelpers.User(tmp.dir, user_id)
        machine = sslhelpers.Machine(user, machine_id)
        self.assertIs(machine.user, user)
        self.assertIs(machine.machine_id, machine_id)
        self.assertEqual(machine.ssldir, tmp.dir)
        self.assertEqual(machine.id, _id)
        self.assertEqual(machine.subject, '/CN=' + _id)
        self.assertEqual(machine.key_file, tmp.join(_id + '-key.pem'))
        self.assertEqual(machine.csr_file, tmp.join(_id + '-csr.pem'))
        self.assertEqual(machine.cert_file, tmp.join(_id + '-cert.pem'))

    def test_gen_csr(self):
        tmp = TempDir()
        user_id = random_b32()
        machine_id = random_b32()
        _id = user_id + '-' + machine_id
        user = sslhelpers.User(tmp.dir, user_id)
        machine = sslhelpers.Machine(user, machine_id)
        self.assertFalse(path.isfile(machine.key_file))
        self.assertFalse(path.isfile(machine.csr_file))
        self.assertTrue(machine.gen_csr())
        self.assertGreater(path.getsize(machine.key_file), 0)
        self.assertGreater(path.getsize(machine.csr_file), 0)
        self.assertFalse(machine.gen_csr())
        os.remove(machine.csr_file)
        self.assertTrue(machine.gen_csr())
        self.assertGreater(path.getsize(machine.csr_file), 0)
        self.assertFalse(machine.gen_csr())

    def test_gen_cert(self):
        tmp = TempDir()
        user_id = random_b32()
        machine_id = random_b32()
        _id = user_id + '-' + machine_id
        user = sslhelpers.User(tmp.dir, user_id)
        machine = sslhelpers.Machine(user, machine_id)
        self.assertFalse(path.isfile(machine.key_file))
        self.assertFalse(path.isfile(machine.csr_file))
        self.assertFalse(path.isfile(machine.cert_file))
        self.assertTrue(machine.gen_cert())
        self.assertGreater(path.getsize(machine.key_file), 0)
        self.assertGreater(path.getsize(machine.csr_file), 0)
        self.assertGreater(path.getsize(machine.cert_file), 0)
        self.assertFalse(machine.gen_cert())
        os.remove(machine.cert_file)
        self.assertTrue(machine.gen_cert())
        self.assertGreater(path.getsize(machine.cert_file), 0)
        self.assertFalse(machine.gen_cert())

    def test_get_ssl_env(self):
        tmp = TempDir()
        user_id = random_b32()
        machine_id = random_b32()
        _id = user_id + '-' + machine_id
        user = sslhelpers.User(tmp.dir, user_id)
        machine = sslhelpers.Machine(user, machine_id)
        self.assertEqual(
            machine.get_ssl_env(),
            {
                'ca_file': tmp.join(user_id + '-ca.pem'),
                'cert_file': tmp.join(_id + '-cert.pem'),
                'key_file': tmp.join(_id + '-key.pem'),
                'check_hostname': False,
            }
        )
