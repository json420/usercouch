#!/usr/bin/env python3

# usercouch: Start per-user CouchDB instances for fun and unit testing
# Copyright (C) 2011-2016 Novacut Inc
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
if sys.version_info < (3, 4):
    sys.exit('ERROR: UserCouch requires Python 3.4 or newer')

import os
from os import path
import subprocess
from distutils.core import setup
from distutils.cmd import Command

import usercouch
from usercouch.tests.run import run_tests


TREE = path.dirname(path.abspath(__file__))


def run_under_same_interpreter(opname, script, args):
    print('\n** running: {}...'.format(script), file=sys.stderr)
    if not os.access(script, os.R_OK | os.X_OK):
        print('ERROR: cannot read and execute: {!r}'.format(script),
            file=sys.stderr
        )
        print('Consider running `setup.py test --skip-{}`'.format(opname),
            file=sys.stderr
        )
        sys.exit(3)
    cmd = [sys.executable, script] + args
    print('check_call:', cmd, file=sys.stderr)
    subprocess.check_call(cmd)
    print('** PASSED: {}\n'.format(script), file=sys.stderr)


def run_pyflakes3():
    script = '/usr/bin/pyflakes3'
    names = [
        'usercouch',
        'setup.py',
    ]
    args = [path.join(TREE, name) for name in names]
    run_under_same_interpreter('flakes', script, args)


def run_sphinx_doctest():
    script = '/usr/share/sphinx/scripts/python3/sphinx-build'
    doc = path.join(TREE, 'doc')
    doctest = path.join(TREE, 'doc', '_build', 'doctest')
    args = ['-EW', '-b', 'doctest', doc, doctest]
    run_under_same_interpreter('sphinx', script, args)


class Test(Command):
    description = 'run unit tests and doctests'

    user_options = [
        ('skip-flakes', None, 'do not run pyflakes static checks'),
        ('skip-sphinx', None, 'do not run Sphinx doctests'),
    ]

    def initialize_options(self):
        self.skip_sphinx = 0
        self.skip_flakes = 0

    def finalize_options(self):
        pass

    def run(self):
        if not self.skip_flakes:
            run_pyflakes3()
        if not run_tests():
            sys.exit(2)
        if not self.skip_sphinx:
            run_sphinx_doctest()


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
