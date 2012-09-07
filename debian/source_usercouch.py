'''apport package hook for usercouch.

(c) 2012 Novacut Inc
Author: Jason Gerard DeRose <jderose@novacut.com>
'''

def add_info(report):
    report['CrashDB'] = 'usercouch'

