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
import os
from os import path
import tempfile
import shutil

import usercouch


B32ALPHABET = frozenset('234567ABCDEFGHIJKLMNOPQRSTUVWXYZ')


class TempDir(object):
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix='unittest.')

    def __del__(self):
        self.rmtree()

    def rmtree(self):
        if self.dir is not None:
            shutil.rmtree(self.dir)
            self.dir = None

    def join(self, *parts):
        return path.join(self.dir, *parts)

    def makedirs(self, *parts):
        d = self.join(*parts)
        if not path.exists(d):
            os.makedirs(d)
        assert path.isdir(d), d
        return d

    def touch(self, *parts):
        self.makedirs(*parts[:-1])
        f = self.join(*parts)
        open(f, 'wb').close()
        return f

    def write(self, data, *parts):
        self.makedirs(*parts[:-1])
        f = self.join(*parts)
        open(f, 'wb').write(data)
        return f

    def copy(self, src, *parts):
        self.makedirs(*parts[:-1])
        dst = self.join(*parts)
        shutil.copy(src, dst)
        return dst


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

    def test_mkdir(self):
        tmp = TempDir()

        # Test that os.makedirs() is not used:
        basedir = tmp.join('foo')
        d = tmp.join('foo', 'bar')
        with self.assertRaises(OSError) as cm:
            usercouch.mkdir(basedir, 'bar')
        self.assertEqual(
            str(cm.exception),
            '[Errno 2] No such file or directory: {!r}'.format(d)
        )
        self.assertFalse(path.exists(basedir))
        self.assertFalse(path.exists(d))

        # Test when dir does not exist
        d = tmp.join('foo')
        self.assertFalse(path.exists(d))
        self.assertEqual(usercouch.mkdir(tmp.dir, 'foo'), d)
        self.assertTrue(path.isdir(d))

        # Test when dir exists:
        self.assertEqual(usercouch.mkdir(tmp.dir, 'foo'), d)
        self.assertTrue(path.isdir(d))

        # Test when dir exists and is a file:
        d = tmp.touch('bar')
        with self.assertRaises(ValueError) as cm:
            usercouch.mkdir(tmp.dir, 'bar')
        self.assertEqual(str(cm.exception), 'not a directory: {!r}'.format(d))

        # Test when dir exists and is a symlink to a dir:
        target = tmp.makedirs('target')
        link = tmp.join('link')
        os.symlink(target, link)
        self.assertTrue(path.isdir(link))
        self.assertTrue(path.islink(link))
        with self.assertRaises(ValueError) as cm:
            usercouch.mkdir(tmp.dir, 'link')
        self.assertEqual(str(cm.exception), 'not a directory: {!r}'.format(link))

    def test_logfile(self):
        tmp = TempDir()
        self.assertEqual(
            usercouch.logfile(tmp.dir, 'foo'),
            tmp.join('foo.log')
        )
        self.assertEqual(os.listdir(tmp.dir), [])
        tmp.touch('bar.log')
        self.assertEqual(
            usercouch.logfile(tmp.dir, 'bar'),
            tmp.join('bar.log')
        )
        self.assertTrue(path.isfile(tmp.join('bar.log.previous')))
        self.assertEqual(os.listdir(tmp.dir), ['bar.log.previous'])
        


class TestUserCouch(TestCase):
    def test_kill(self):
        tmp = TempDir()
        inst = usercouch.UserCouch(tmp.dir)
        self.assertIs(inst.kill(), False)

        
        
    
