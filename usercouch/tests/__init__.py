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
Unit tests for `usercouch` package.
"""

from unittest import TestCase
import socket

import usercouch


B32ALPHABET = frozenset('234567ABCDEFGHIJKLMNOPQRSTUVWXYZ')


class TestFunctions(TestCase):

    def test_random_port(self):
        (sock, port) = usercouch.random_port()
        self.assertIsInstance(sock, socket.socket)
        self.assertIsInstance(port, int)
        self.assertEqual(sock.getsockname(), ('127.0.0.1', port))
        self.assertNotEqual(usercouch.random_port()[1], port)

    def test_random_oauth(self):
        kw = usercouch.random_oauth()
        self.assertIsInstance(kw, dict)
        self.assertEqual(
            set(kw),
            set(['consumer_key', 'consumer_secret', 'token', 'token_secret'])
        )
        for value in kw.values():
            self.assertIsInstance(value, str)
            self.assertEqual(len(value), 24)
            self.assertTrue(set(value).issubset(B32ALPHABET))
  
    def test_random_basic(self):
        kw = usercouch.random_basic()
        self.assertIsInstance(kw, dict)
        self.assertEqual(
            set(kw),
            set(['username', 'password'])
        )
        for value in kw.values():
            self.assertIsInstance(value, str)
            self.assertEqual(len(value), 24)
            self.assertTrue(set(value).issubset(B32ALPHABET))
        
        
        
class TestUserCouch(TestCase):
    def test_kill(self):
        inst = usercouch.UserCouch()
        self.assertIs(inst.kill(), False)
        
    def test_start(self):
        inst = usercouch.UserCouch()
        inst.couchdb = 'hello'
        self.assertIs(inst.start(), False)
        inst.couchdb = None
        
        
    
