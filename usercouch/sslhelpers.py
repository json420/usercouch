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
Helpers for non-interactive creation of SSL certs.
"""

from subprocess import check_call
from os import path


def gen_key(dst_file, bits=2048):
    """
    Create an RSA keypair and save it to the file *dst*.
    """
    check_call(['openssl', 'genrsa',
        '-out', dst_file,
        str(bits)
    ])


def gen_ca(key_file, subject, dst_file):
    """
    Create a self-signed X509 certificate authority.

    *subject* should be an str in the form ``'/CN=foobar'``.
    """
    check_call(['openssl', 'req',
        '-new',
        '-x509',
        '-days', '3650',
        '-key', key_file,
        '-subj', subject,
        '-out', dst_file,
    ])


def gen_csr(key_file, subject, dst_file):
    """
    Create a certificate signing request.

    *subject* should be an str in the form ``'/CN=foobar'``.
    """
    check_call(['openssl', 'req',
        '-new',
        '-key', key_file,
        '-subj', subject,
        '-out', dst_file,
    ])


def sign_csr(csr_file, ca_file, key_file, dst_file):
    """
    Create a signed certificate from a certificate signing request.
    """
    check_call(['openssl', 'x509',
        '-req',
        '-days', '3650',
        '-CAcreateserial',
        '-in', csr_file,
        '-CA', ca_file,
        '-CAkey', key_file,
        '-out', dst_file
    ])


class PKIHelper:
    def __init__(self, ssldir):
        self.ssldir = ssldir
        self.server_ca = None
        self.server = None
        self.client_ca = None
        self.client = None

    def get_ca(self, ca_id):
        ca = CAHelper(self.ssldir, ca_id)
        ca.gen()
        return ca

    def load_server(self, ca_id, cert_id):
        self.server_ca = self.get_ca(ca_id)
        self.server = self.server_ca.get_cert(cert_id)

    def load_client(self, ca_id, cert_id):
        self.client_ca = self.get_ca(ca_id)
        self.client = self.client_ca.get_cert(cert_id)

    def get_server_config(self):
        config = self.server.get_config()
        if self.client_ca is not None:
            config.update(self.client_ca.get_config())
        return config

    def get_client_config(self):
        config = self.server_ca.get_config()
        if self.client is not None:
            config.update(self.client.get_config())
        return config


class Helper:
    def __init__(self, ssldir, _id):
        self.ssldir = ssldir
        self.id = _id
        self.subject = '/CN={}'.format(_id)
        self.key_file = path.join(ssldir, _id + '.key')

    def gen_key(self):
        if path.isfile(self.key_file):
            return False
        gen_key(self.key_file)
        return True


class CAHelper(Helper):
    def __init__(self, ssldir, _id):
        super().__init__(ssldir, _id)
        self.ca_file = path.join(ssldir, _id + '.ca')

    def gen(self):
        if path.isfile(self.ca_file):
            return False
        self.gen_key()
        gen_ca(self.key_file, self.subject, self.ca_file)
        return True

    def sign(self, csr_file, cert_file):
        self.gen()
        sign_csr(csr_file, self.ca_file, self.key_file, cert_file)

    def get_cert(self, cert_id):
        cert = CertHelper(self, cert_id)
        cert.gen()
        return cert

    def get_config(self):
        """
        Get config fragment for this Certificate Authority.

        This config is required by the client to verify the server.

        Optionally, when using client-side certs, this config is used by the
        server to verify the client.
        """
        return {
            'ca_file': self.ca_file,
            'check_hostname': False,
        }


class CertHelper(Helper):
    def __init__(self, ca, cert_id):
        assert isinstance(ca, CAHelper)
        self.ca = ca
        self.cert_id = cert_id
        _id = '-'.join([ca.id, cert_id])
        super().__init__(ca.ssldir, _id)
        self.csr_file = path.join(ca.ssldir, _id + '.csr')
        self.cert_file = path.join(ca.ssldir, _id + '.cert')

    def gen_csr(self):
        if path.isfile(self.csr_file):
            return False
        self.gen_key()
        gen_csr(self.key_file, self.subject, self.csr_file)
        return True

    def gen(self):
        if path.isfile(self.cert_file):
            return False
        self.gen_csr()
        self.ca.sign(self.csr_file, self.cert_file)
        return True

    def get_config(self):
        """
        Get config fragment for this Certificate.

        This config is required by the server in order to use SSL.

        Optionally, when using client-side certs, this config is used by the
        client to specify the client certificate.
        """
        return {
            'cert_file': self.cert_file,
            'key_file': self.key_file,
        }

