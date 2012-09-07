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
Helper functions for non-interactive creation of SSL certs.
"""

from subprocess import check_call


def gen_key(dst, bits=2048):
    """
    Create an RSA keypair and save it to the file *dst*.
    """
    check_call(['openssl', 'genrsa', '-out', dst, str(bits)])


def gen_ca(key, subj, dst):
    """
    Create a self-signed X509 certificate authority.

    *subj* should be an str in the form ``'/CN=foobar'``.
    """
    check_call(['openssl', 'req',
        '-new',
        '-x509',
        '-days', '3650',
        '-key', key,
        '-subj', subj,
        '-out', dst,
    ])


def gen_csr(key, subj, dst):
    """
    Create a certificate signing request.

    *subj* should be an str in the form ``'/CN=foobar'``.
    """
    check_call(['openssl', 'req',
        '-new',
        '-key', key,
        '-subj', subj,
        '-out', dst,
    ])


def sign_csr(csr, ca, ca_key, dst):
    """
    Create a signed certificate from a certificate signing request.
    """
    check_call(['openssl', 'x509',
        '-req',
        '-days', '3650',
        '-CAcreateserial',
        '-in', csr,
        '-CA', ca,
        '-CAkey', ca_key,
        '-out', dst
    ])

