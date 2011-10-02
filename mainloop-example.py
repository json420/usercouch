#!/usr/bin/python3

"""
Example of how to properly shutdown a daemon running a GObject.MainLoop.
"""

import os
import signal

from usercouch.misc import TempCouch
from gi.repository import GObject


GObject.threads_init()
tmpcouch = TempCouch()
tmpcouch.bootstrap()
mainloop = GObject.MainLoop()


def on_sigterm(signum, frame):
    print('sigterm')
    mainloop.quit()
    tmpcouch.kill()

signal.signal(signal.SIGTERM, on_sigterm)

print('This pid: {}'.format(os.getpid()))
print('CouchDB pid: {}'.format(tmpcouch.couchdb.pid))
mainloop.run()

