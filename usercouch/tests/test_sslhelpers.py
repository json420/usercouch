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

    def test_gen_cert(self):
        tmp = TempDir()

        # Create the ca
        foo_key = tmp.join('foo.key')
        foo_ca = tmp.join('foo.ca')
        sslhelpers.gen_key(foo_key)
        sslhelpers.gen_ca(foo_key, '/CN=foo', foo_ca)

        # Create csr
        bar_key = tmp.join('bar.key')
        bar_csr = tmp.join('bar.csr')
        sslhelpers.gen_key(bar_key)
        sslhelpers.gen_csr(bar_key, '/CN=bar', bar_csr)

        # Now sign the csr
        foo_srl = tmp.join('foo.srl')
        bar_cert = tmp.join('bar.cert')
        self.assertFalse(path.isfile(foo_srl))
        self.assertFalse(path.isfile(bar_cert))
        sslhelpers.gen_cert(bar_csr, foo_ca, foo_key, foo_srl, bar_cert)
        self.assertGreater(path.getsize(bar_cert), 0)
        self.assertGreater(path.getsize(foo_srl), 0)


class TestPKIHelper(TestCase):
    def test_init(self):
        tmp = TempDir()
        pki = sslhelpers.PKIHelper(tmp.dir)
        self.assertIs(pki.ssldir, tmp.dir)
        self.assertIsNone(pki.server_ca)
        self.assertIsNone(pki.server)
        self.assertIsNone(pki.client_ca)
        self.assertIsNone(pki.client)

    def test_repr(self):
        pki = sslhelpers.PKIHelper('/some/dir')
        self.assertEqual(
            repr(pki),
            "PKIHelper('/some/dir')"
        )

    def test_get_ca(self):
        tmp = TempDir()
        ca_id = random_b32()
        pki = sslhelpers.PKIHelper(tmp.dir)
        ca = pki.get_ca(ca_id)
        self.assertIsInstance(ca, sslhelpers.CAHelper)
        self.assertIs(ca.ssldir, tmp.dir)
        self.assertIs(ca.id, ca_id)
        self.assertIs(ca.exists(), False)

    def test_load_server_pki(self):
        tmp = TempDir()
        ca_id = random_b32()
        cert_id = random_b32()
        pki = sslhelpers.PKIHelper(tmp.dir)
        self.assertIsNone(pki.load_server_pki(ca_id, cert_id))

        self.assertIsInstance(pki.server_ca, sslhelpers.CAHelper)
        self.assertIs(pki.server_ca.ssldir, tmp.dir)
        self.assertIs(pki.server_ca.id, ca_id)
        self.assertIs(pki.server_ca.exists(), False)

        self.assertIsInstance(pki.server, sslhelpers.CertHelper)
        self.assertIs(pki.server.ca_id, ca_id)
        self.assertIs(pki.server.cert_id, cert_id)
        self.assertIs(pki.server.ssldir, tmp.dir)
        self.assertEqual(pki.server.id, '-'.join([ca_id, cert_id]))
        self.assertIs(pki.server.exists(), False)

        self.assertIsNone(pki.client_ca)
        self.assertIsNone(pki.client)

    def test_load_client_pki(self):
        tmp = TempDir()
        ca_id = random_b32()
        cert_id = random_b32()
        pki = sslhelpers.PKIHelper(tmp.dir)
        self.assertIsNone(pki.load_client_pki(ca_id, cert_id))

        self.assertIsInstance(pki.client_ca, sslhelpers.CAHelper)
        self.assertIs(pki.client_ca.ssldir, tmp.dir)
        self.assertIs(pki.client_ca.id, ca_id)
        self.assertIs(pki.client_ca.exists(), False)

        self.assertIsInstance(pki.client, sslhelpers.CertHelper)
        self.assertIs(pki.client.ca_id, ca_id)
        self.assertIs(pki.client.cert_id, cert_id)
        self.assertIs(pki.client.ssldir, tmp.dir)
        self.assertEqual(pki.client.id, '-'.join([ca_id, cert_id]))
        self.assertIs(pki.client.exists(), False)

        self.assertIsNone(pki.server_ca)
        self.assertIsNone(pki.server)

    def test_get_server_config(self):
        tmp = TempDir()
        pki = sslhelpers.PKIHelper(tmp.dir)

        with self.assertRaises(Exception) as cm:
            pki.get_server_config()
        self.assertEqual(
            str(cm.exception),
            'You must first call PKIHelper.load_server_pki()'
        )

        ca_id = random_b32()
        cert_id = random_b32()
        server = sslhelpers.CertHelper(tmp.dir, ca_id, cert_id)
        pki.server = server
        self.assertEqual(pki.get_server_config(),
            {
                'cert_file': server.cert_file,
                'key_file': server.key_file,
            }
        )

        ca_id = random_b32()
        client_ca = sslhelpers.CAHelper(tmp.dir, ca_id)
        pki.client_ca = client_ca
        self.assertEqual(pki.get_server_config(),
            {
                'cert_file': server.cert_file,
                'key_file': server.key_file,
                'ca_file': client_ca.ca_file,
                'check_hostname': False,
            }
        )

    def test_get_client_config(self):
        tmp = TempDir()
        pki = sslhelpers.PKIHelper(tmp.dir)

        with self.assertRaises(Exception) as cm:
            pki.get_client_config()
        self.assertEqual(
            str(cm.exception),
            'You must first call PKIHelper.load_server_pki()'
        )

        ca_id = random_b32()
        server_ca = sslhelpers.CAHelper(tmp.dir, ca_id)
        pki.server_ca = server_ca
        self.assertEqual(pki.get_client_config(),
            {
                'ca_file': server_ca.ca_file,
                'check_hostname': False,
            }
        )

        ca_id = random_b32()
        cert_id = random_b32()
        client = sslhelpers.CertHelper(tmp.dir, ca_id, cert_id)
        pki.client = client
        self.assertEqual(pki.get_client_config(),
            {
                'ca_file': server_ca.ca_file,
                'check_hostname': False,
                'cert_file': client.cert_file,
                'key_file': client.key_file,
            }
        )


class TestHelper(TestCase):
    def test_init(self):
        tmp = TempDir()
        _id = random_b32()
        inst = sslhelpers.Helper(tmp.dir, _id)
        self.assertEqual(inst.ssldir, tmp.dir)
        self.assertEqual(inst.id, _id)
        self.assertEqual(inst.subject, '/CN=' + _id)
        self.assertEqual(inst.key_file, tmp.join(_id + '.key'))

    def test_repr(self):
        inst = sslhelpers.Helper('/some/dir', 'foo')
        self.assertEqual(
            repr(inst),
            "Helper('/some/dir', 'foo')"
        )

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


class TestCAHelper(TestCase):
    def test_init(self):
        tmp = TempDir()
        ca_id = random_b32()
        ca = sslhelpers.CAHelper(tmp.dir, ca_id)
        self.assertEqual(ca.ssldir, tmp.dir)
        self.assertEqual(ca.id, ca_id)
        self.assertEqual(ca.subject, '/CN=' + ca_id)
        self.assertEqual(ca.key_file, tmp.join(ca_id + '.key'))
        self.assertEqual(ca.ca_file, tmp.join(ca_id + '.ca'))
        self.assertEqual(ca.srl_file, tmp.join(ca_id + '.srl'))

    def test_repr(self):
        ca = sslhelpers.CAHelper('/some/dir', 'foo')
        self.assertEqual(
            repr(ca),
            "CAHelper('/some/dir', 'foo')"
        )

    def test_exists(self):
        tmp = TempDir()
        ca_id = random_b32()
        ca = sslhelpers.CAHelper(tmp.dir, ca_id)
        self.assertIs(ca.exists(), False)
        open(ca.ca_file, 'wb').close()
        self.assertIs(ca.exists(), True)

    def test_create(self):
        tmp = TempDir()
        ca_id = random_b32()
        ca = sslhelpers.CAHelper(tmp.dir, ca_id)
        self.assertFalse(path.isfile(ca.key_file))
        self.assertFalse(path.isfile(ca.ca_file))

        open(ca.ca_file, 'wb').close()
        with self.assertRaises(Exception) as cm:
            ca.create()
        self.assertEqual(
            str(cm.exception),
            'ca_file already exists: {!r}'.format(ca.ca_file)
        )
        os.remove(ca.ca_file)

        self.assertIsNone(ca.create())
        self.assertGreater(path.getsize(ca.key_file), 0)
        self.assertGreater(path.getsize(ca.ca_file), 0)

    def test_sign(self):
        tmp = TempDir()
        ca_id = random_b32()
        ca = sslhelpers.CAHelper(tmp.dir, ca_id)
        key_file = tmp.join('key.pem')
        csr_file = tmp.join('csr.pem')
        cert_file = tmp.join('cert.pem')
        sslhelpers.gen_key(key_file)
        sslhelpers.gen_csr(key_file, '/CN=foobar', csr_file)
        ca.create()
        self.assertFalse(path.exists(cert_file))
        ca.sign(csr_file, cert_file)
        self.assertGreater(path.getsize(cert_file), 0)

    def test_issue(self):
        tmp = TempDir()
        ca_id = random_b32()
        cert_id = random_b32()
        ca = sslhelpers.CAHelper(tmp.dir, ca_id)
        cert = sslhelpers.CertHelper(tmp.dir, ca_id, cert_id)

        open(cert.cert_file, 'wb').close()
        with self.assertRaises(Exception) as cm:
            ca.issue(cert)
        self.assertEqual(
            str(cm.exception),
            'cert_file already exists: {!r}'.format(cert.cert_file)
        )
        os.remove(cert.cert_file)

        ca.create()
        cert.create()
        self.assertFalse(path.exists(cert.cert_file))
        self.assertIsNone(ca.issue(cert))
        self.assertGreater(path.getsize(cert.csr_file), 0)

    def test_get_cert(self):
        tmp = TempDir()
        ca_id = random_b32()
        cert_id = random_b32()
        _id = ca_id + '-' + cert_id
        ca = sslhelpers.CAHelper(tmp.dir, ca_id)
        cert = ca.get_cert(cert_id)
        self.assertIsInstance(cert, sslhelpers.CertHelper)
        self.assertIs(cert.ca_id, ca_id)
        self.assertIs(cert.cert_id, cert_id)
        self.assertEqual(cert.ssldir, tmp.dir)
        self.assertEqual(cert.id, _id)
        self.assertIs(ca.exists(), False)
        self.assertIs(cert.exists(), False)

    def test_get_config(self):
        tmp = TempDir()
        ca_id = random_b32()
        ca = sslhelpers.CAHelper(tmp.dir, ca_id)
        self.assertEqual(
            ca.get_config(),
            {
                'ca_file': tmp.join(ca_id + '.ca'),
                'check_hostname': False,
            }
        )


class TestCertHelper(TestCase):
    def test_init(self):
        tmp = TempDir()
        ca_id = random_b32()
        cert_id = random_b32()
        _id = ca_id + '-' + cert_id
        cert = sslhelpers.CertHelper(tmp.dir, ca_id, cert_id)
        self.assertIs(cert.ca_id, ca_id)
        self.assertIs(cert.cert_id, cert_id)
        self.assertEqual(cert.ssldir, tmp.dir)
        self.assertEqual(cert.id, _id)
        self.assertEqual(cert.subject, '/CN=' + _id)
        self.assertEqual(cert.key_file, tmp.join(_id + '.key'))
        self.assertEqual(cert.csr_file, tmp.join(_id + '.csr'))
        self.assertEqual(cert.cert_file, tmp.join(_id + '.cert'))

    def test_repr(self):
        cert = sslhelpers.CertHelper('/some/dir', 'foo', 'bar')
        self.assertEqual(
            repr(cert),
            "CertHelper('/some/dir', 'foo-bar')"
        )

    def test_exists(self):
        tmp = TempDir()
        ca_id = random_b32()
        cert_id = random_b32()
        cert = sslhelpers.CertHelper(tmp.dir, ca_id, cert_id)
        self.assertIs(cert.exists(), False)
        open(cert.cert_file, 'wb').close()
        self.assertIs(cert.exists(), True)

    def test_create(self):
        tmp = TempDir()
        ca_id = random_b32()
        cert_id = random_b32()
        cert = sslhelpers.CertHelper(tmp.dir, ca_id, cert_id)
        self.assertFalse(path.isfile(cert.cert_file))
        self.assertFalse(path.isfile(cert.csr_file))
        self.assertFalse(path.isfile(cert.key_file))

        open(cert.cert_file, 'wb').close()
        with self.assertRaises(Exception) as cm:
            cert.create()
        self.assertEqual(
            str(cm.exception),
            'cert_file already exists: {!r}'.format(cert.cert_file)
        )
        os.remove(cert.cert_file)

        open(cert.csr_file, 'wb').close()
        with self.assertRaises(Exception) as cm:
            cert.create()
        self.assertEqual(
            str(cm.exception),
            'csr_file already exists: {!r}'.format(cert.csr_file)
        )
        os.remove(cert.csr_file)

        self.assertIsNone(cert.create())
        self.assertFalse(path.isfile(cert.cert_file))
        self.assertGreater(path.getsize(cert.csr_file), 0)
        self.assertGreater(path.getsize(cert.key_file), 0)

    def test_get_config(self):
        tmp = TempDir()
        ca_id = random_b32()
        cert_id = random_b32()
        _id = ca_id + '-' + cert_id
        cert = sslhelpers.CertHelper(tmp.dir, ca_id, cert_id)
        self.assertEqual(
            cert.get_config(),
            {
                'cert_file': tmp.join(_id + '.cert'),
                'key_file': tmp.join(_id + '.key'),
            }
        )
