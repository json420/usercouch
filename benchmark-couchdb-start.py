#!/usr/bin/python3

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
Benchmark time it takes CouchDB to start.
"""

import time

from usercouch.misc import TempCouch


count = 10
times = []
for i in range(count):
    tmp = TempCouch()
    start = time.monotonic()
    tmp.bootstrap()
    elapsed = time.monotonic() - start
    times.append(elapsed)
    
print('')
print('Average: {:.3f}'.format(sum(times) / count))
print('Max: {:.3f}'.format(max(times)))
print('Min: {:.3f}'.format(min(times)))
