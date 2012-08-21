UserCouch Tutorial
==================

.. py:currentmodule:: usercouch

To create a :class:`UserCouch` instance, you must supply the *basedir*
directory in which all the CouchDB data will be stored.  For example:

>>> from usercouch import UserCouch
>>> mycouch = UserCouch('/home/jderose/.usercouch')

Then  call :meth:`UserCouch.bootstrap()` to create the one-time configuration
and start CouchDB:

>>> env = mycouch.bootstrap()

The returned *env* will be a ``dict`` with an extensible environment
following the same conventions as `Microfiber`_.

Because this is a per-user CouchDB instance, a random port is chosen when you
call :meth:`UserCouch.bootstrap()`, and *env* will contain this port:

>>> env['port']
53206

The *env* also contains the HTTP URL of the CouchDB instance:

>>> env['url']
'http://localhost:53206/'

By default, :meth:`UserCouch.bootstrap()` will configure CouchDB for basic
HTTP auth, using a random username and password each time:

>>> env['basic']
{'username': '72UT4WBTH3HFGT4S5OMYXGWA', 'password': 'WP5DUTBRQRYXFYKGZQ4MPDHB'}

Normally the CouchDB process will be automatically killed for you when the
:class:`UserCouch` instance is garbage collected.  However, in certain
circumstances, you may need to manually call :meth:`UserCouch.kill()`.


Bootstrap Options
-----------------


The Lockfile
------------

The :class:`UserCouch` instance will store all the CouchDB data within the
*basedir* you provide.  To prevent multiple :class:`UserCouch` instances from
starting multiple CouchDB instances pointing at the same database files, a
lockfile is used.

If the lock cannot be aquired, a :exc:`LockError` is raised:

>>> mycouch2 = UserCouch('/home/jderose/.usercouch')
Traceback (most recent call last):
  ...
usercouch.LockError: cannot acquire exclusive lock on '/home/jderose/.usercouch/lockfile'

Note that it's perfectly fine for multiple :class:`UserCouch` instances to be running
simultaneously as long as each uses its own *basedir*.


.. _`Microfiber`: https://launchpad.net/microfiber

