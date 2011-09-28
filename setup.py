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

from distutils.core import setup
from distutils.cmd import Command
from unittest import TestLoader, TextTestRunner
from doctest import DocTestSuite

import usercouch


class Test(Command):
    description = 'run unit tests and doc tests'

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        pynames = [
            'usercouch',
            'usercouch.misc',
            'usercouch.tests',
            'usercouch.tests.test_misc',
        ]

        # Add unit-tests:
        loader = TestLoader()
        suite = loader.loadTestsFromNames(pynames)

        # Add doc-tests:
        for name in pynames:
            suite.addTest(DocTestSuite(name))

        # Run the tests:
        runner = TextTestRunner(verbosity=2)
        result = runner.run(suite)
        if not result.wasSuccessful():
            raise SystemExit(2)


setup(
    name='usercouch',
    description='Start per-user CouchDB instances for fun and unit testing',
    url='https://launchpad.net/usercouch',
    version=usercouch.__version__,
    author='Jason Gerard DeRose',
    author_email='jderose@novacut.com',
    license='LGPLv3+',
    packages=['usercouch'],
    cmdclass={
        'test': Test,
        #'build': build_with_docs,
    },
)
