#!/usr/bin/env python3

# usercouch: Start per-user CouchDB instances for fun and unit testing
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
Install `usercouch`.
"""

import sys
if sys.version_info < (3, 3):
    sys.exit('UserCouch requires Python 3.3 or newer')

from distutils.core import setup
from distutils.cmd import Command

import usercouch
from usercouch.tests.run import run_tests


class Test(Command):
    description = 'run unit tests and doc tests'

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        if not run_tests():
            print('Tests FAILED!', file=sys.stderr)
            raise SystemExit('2')
        print('Tests passed.', file=sys.stderr)


setup(
    name='usercouch',
    description='Start per-user CouchDB instances for fun and unit testing',
    url='https://launchpad.net/usercouch',
    version=usercouch.__version__,
    author='Jason Gerard DeRose',
    author_email='jderose@novacut.com',
    license='LGPLv3+',
    packages=[
        'usercouch',
        'usercouch.tests',
    ],
    package_data={'usercouch': ['data/usercouch.ini']},
    cmdclass={'test': Test},
)
