# usercouch: Starts per-user CouchDB instances for fun and unit testing
# Copyright (C) 2013 Novacut Inc
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
Run the `usercouch` unit tests.

From the command line, run like this::

    $ python3 -m usercouch.tests.run
"""

import sys
from os import path
from unittest import TestLoader, TextTestRunner
from doctest import DocTestSuite

import usercouch


pynames = (
    'usercouch',
    'usercouch.misc',
    'usercouch.sslhelpers',
    'usercouch.tests',
    'usercouch.tests.test_misc',
    'usercouch.tests.test_sslhelpers',
)


def run_tests():
    # Add unit-tests:
    loader = TestLoader()
    suite = loader.loadTestsFromNames(pynames)

    # Add doc-tests:
    for name in pynames:
        suite.addTest(DocTestSuite(name))

    # Run the tests:
    runner = TextTestRunner(verbosity=2)
    result = runner.run(suite)
    success =  result.wasSuccessful()
    print(
        'usercouch: {!r}'.format(path.abspath(usercouch.__file__)),
        file=sys.stderr
    )
    print('-' * 70, file=sys.stderr)
    return result.wasSuccessful()


if __name__ == '__main__':
    if not run_tests():
        raise SystemExit('2')
