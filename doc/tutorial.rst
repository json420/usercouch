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

The :meth:`UserCouch.bootstrap()` *auth* kwarg can be ``'open'``, ``'basic'``,
or ``'oauth'``.  As noted above, it defaults to ``'basic'``.

If you use ``auth='open'``, you'll get an *env* similar to this:

>>> {
...     'port': 41505,
...     'url': 'http://localhost:41505/',
... }

If you use ``auth='basic'``, you'll get an *env* similar to this:

>>> {
...     'port': 57910,
...     'url': 'http://localhost:57910/',
...     'basic': {
...         'username': 'BKBTG7MX5Z6CTWHBOBXOX63S',
...         'password': 'YGQQRSDMIF6GTZ6JMETWPUUE',
...     },
... }

If you use ``auth='oauth'``, you'll get an *env* similar to this:

>>> {
...     'port': 56618
...     'url': 'http://localhost:56618/', 
...     'basic': {
...         'username': 'MAO5VQIKCJWS7NGGMV2IYC7S',
...         'password': 'A7RDFDAMUFFFBP72VWSGK5QD',
...     },
...     'oauth': {
...         'consumer_key': 'MDWS6LVY4N7TSBKCNW4UWMVW',
...         'consumer_secret': 'DA2TGMAUTRASC67ZZPVJAXYY',
...         'token': 'PU7WWZNC3RJDX3CAOW3Q6TZW',
...         'token_secret': 'H7XPTS2QHKYFQ4Z35NSKF3FR',
...     },
... }



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



Unit Testing
------------

.. py:currentmodule:: usercouch.misc

When unit testing or experimenting with CouchDB, it's handy to have throw-away
CouchDB instances.  That way your tests start with CouchDB in a known state,
plus you can't accidentally hose your production data.

The :mod:`usercouch.misc` module contains two classes aimed at unit testing.

The first is the :class:`TempCouch` class, which you can use like this:

>>> from usercouch.misc import TempCouch
>>> tmpcouch = TempCouch()
>>> env = tmpcouch.bootstrap()

:class:`TempCouch` is a :class:`usercouch.UserCouch` subclass that creates a
one-time temporary directory to be used as the *basedir*.  When the
:class:`TempCouch` instance is garbage collected, this temporary directory
(and any files it contains) are automatically deleted.

The second is the :class:`CouchTestCase` class.  It's a ``unittest.TestCase``
subclass with ``setUp()`` and ``tearDown()`` methods that create and destroy
a :class:`TempCouch` instance for each test.

Typical :class:`CouchTestCase` usage looks like this:

>>> from usercouch.misc import CouchTestCase
>>> from microfiber import Database
>>>
>>> class TestFoo(CouchTestCase):
...     def test_bar(self):
...         db = Database('mydb', self.env)
...         self.assertEqual(db.put(None), {'ok': True})
... 
...     def test_baz(self):
...         db = Database('mydb', self.env)
...         self.assertEqual(db.put(None), {'ok': True})
...

Because a new :class:`TempCouch` is created by ``setUp()`` prior to running
each test method, both the ``test_bar()`` and ``test_baz()`` tests will pass.



.. _`Microfiber`: https://launchpad.net/microfiber
.. _`CouchDB`: http://couchdb.apache.org/

