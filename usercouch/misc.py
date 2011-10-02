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
`TempCouch` and `CouchTestCase`.
"""

from unittest import TestCase
import tempfile
import shutil

from usercouch import UserCouch


class TempCouch(UserCouch):
    def __init__(self):
        basedir = tempfile.mkdtemp(prefix='tmpcouch.')
        super().__init__(basedir)
        assert self.basedir == basedir

    def __del__(self):
        super().__del__()
        shutil.rmtree(self.basedir)


class CouchTestCase(TestCase):
    create_databases = []
    oauth = False

    def setUp(self):
        self.tmpcouch = TempCouch()
        self.env = self.tmpcouch.bootstrap(self.oauth)
        for name in self.create_databases:
            self.tmpcouch.server.put(None, name)

    def tearDown(self):
        self.tmpcouch.__del__()
        self.tmpcouch = None
        self.env = None
        
