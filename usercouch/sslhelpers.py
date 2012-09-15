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


class Helper:
    def __init__(self, ssldir, _id):
        self.ssldir = ssldir
        self.id = _id
        self.subject = '/CN={}'.format(_id)
        self.key_file = path.join(ssldir, _id + '-key.pem')

    def gen_key(self):
        gen_key(self.key_file)


class User(Helper):
    def __init__(self, ssldir, _id):
        super().__init__(ssldir, _id)
        self.ca = path.join(ssldir, _id + '-ca.pem')

    def gen(self):
        self.gen_key()
        gen_ca(self.key_file, self.subject, self.ca)

    def gen_if_needed(self):
        if path.isfile(self.ca):
            return False
        self.gen()
        return True

    def sign(self, machine):
        assert isinstance(machine, Machine)
        sign_csr(machine.csr, self.ca, self.key_file, machine.cert)

    def get_machine(self, machine_id):
        return Machine(self.ssldir, '-'.join([self.id, machine_id]))


class Machine(Helper):
    def __init__(self, ssldir, _id):
        super().__init__(ssldir, _id)
        self.csr = path.join(ssldir, _id + '-csr.pem')
        self.cert = path.join(ssldir, _id + '-cert.pem')

    def gen(self):
        self.gen_key()
        gen_csr(self.key_file, self.subject, self.csr)

    def get_ssl_env(self, user):
        assert isinstance(user, User)
        return {
            'key_file': self.key_file,
            'cert_file': self.cert,
            'ca_file': user.ca,
            'check_hostname': False,
        }

