Tutorial
========

.. py:currentmodule:: usercouch

To create a :class:`UserCouch` instance, you must supply the *basedir*
directory in which all the `CouchDB`_ data will be stored.  For example:

>>> import tempfile
>>> from usercouch import UserCouch
>>> mytmpdir = tempfile.mkdtemp()
>>> mycouch = UserCouch(mytmpdir)

Then  call :meth:`UserCouch.bootstrap()` to create the one-time configuration
and start CouchDB:

>>> env = mycouch.bootstrap()

The returned *env* will be a ``dict`` with an extensible environment
following the same conventions as `Microfiber`_.

Because this is a per-user CouchDB instance, a random port is chosen when you
call :meth:`UserCouch.bootstrap()`, and *env* will contain this port, which will
be something like:

>>> env['port']  #doctest: +SKIP
53206

The *env* also contains the HTTP URL of the CouchDB instance:

>>> env['url']  #doctest: +SKIP
'http://127.0.0.1:53206/'

By default, :meth:`UserCouch.bootstrap()` will configure CouchDB for basic
HTTP auth, using a random username and password each time, which will be
something like:

>>> env['basic']  #doctest: +SKIP
{'username': '72UT4WBTH3HFGT4S5OMYXGWA', 'password': 'WP5DUTBRQRYXFYKGZQ4MPDHB'}

Normally the CouchDB process will be automatically killed for you when the
:class:`UserCouch` instance is garbage collected.  However, in certain
circumstances, you may need to manually call :meth:`UserCouch.kill()`, which
will return ``True`` if the CouchDB instance was running:

>>> mycouch.kill()
True
>>> import shutil
>>> shutil.rmtree(mytmpdir)



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

The typical :class:`CouchTestCase` pattern looks like this:

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

You can skip all :class:`CouchTestCase` based test cases by setting a
``'SKIP_USERCOUCH_TEST_CASES'`` environment variable to ``'true'``.

For example, something like this on the commandline::

    SKIP_USERCOUCH_TEST_CASES=true python3 run-my-tests.py


Bootstrap *auth* Options
------------------------

.. py:currentmodule:: usercouch


The :meth:`UserCouch.bootstrap()` *auth* kwarg can be ``'open'``, ``'basic'``,
or ``'oauth'``.  As noted above, it defaults to ``'basic'``.

If you use ``auth='open'``, you'll get an *env* similar to this::

    {
        'port': 41505,
        'url': 'http://localhost:41505/',
    }

If you use ``auth='basic'``, you'll get an *env* similar to this::

    {
        'port': 57910,
        'url': 'http://localhost:57910/',
        'authorization': 'Basic QktCVEc3TVg1WjZDVFdIQk9CWE9YNjNTOllHUVFSU0RNSUY2R1RaNkpNRVRXUFVVRQ==',
        'basic': {
            'username': 'BKBTG7MX5Z6CTWHBOBXOX63S',
            'password': 'YGQQRSDMIF6GTZ6JMETWPUUE',
        },
    }


If you use ``auth='oauth'``, you'll get an *env* similar to this::

    {
        'port': 56618,
        'url': 'http://localhost:56618/',
        'authorization': 'Basic TUFPNVZRSUtDSldTN05HR01WMklZQzdTOkE3UkRGREFNVUZGRkJQNzJWV1NHSzVRRA==',
        'basic': {
            'username': 'MAO5VQIKCJWS7NGGMV2IYC7S',
            'password': 'A7RDFDAMUFFFBP72VWSGK5QD',
        },
        'oauth': {
            'consumer_key': 'MDWS6LVY4N7TSBKCNW4UWMVW',
            'consumer_secret': 'DA2TGMAUTRASC67ZZPVJAXYY',
            'token': 'PU7WWZNC3RJDX3CAOW3Q6TZW',
            'token_secret': 'H7XPTS2QHKYFQ4Z35NSKF3FR',
        },
    }

.. versionchanged:: 16.05

    When using ``auth='basic'`` or ``auth='oauth'``, the *env* returned by
    :meth:`UserCouch.bootstrap()` now includes a pre-built HTTP (Basic)
    Authorization header value in ``env['authorization']``.



Bootstrap *config* Options
--------------------------

If provided, the :meth:`UserCouch.bootstrap()` *config* kwarg must be a
dictionary.  These values generally map directly into values in the
session.ini file that is written just before your per-user CouchDB instance
is started.  For example:

>>> tmpcouch = TempCouch()
>>> config = {
...     'bind_address': '::1',
...     'file_compression': 'deflate_9',
...     'username': 'joe',
...     'ssl': {
...         'key_file': '/my/couchdb/server.key',
...         'cert_file': '/my/couchdb/server.cert',
...     },
...     'replicator': {
...         'ca_file': '/only/trust/this/remote.ca',
...         'max_depth': 1,
...         'key_file': '/my/couchdb/client.key',
...         'cert_file': '/my/couchdb/client.cert',
...     },
... }
>>> env = tmpcouch.bootstrap('basic',  config)  #doctest: +SKIP

The available options include:

    * `bind_address`: IP address CouchDB will bind to; default is
      ``'127.0.0.1'``; override with ``'0.0.0.0'``, ``'::1'``, or ``'::'``

    * `file_compression`: compression CouchDB will use for database and view
      files; default is ``'snappy'``; override with ``'none'`` or any
      ``'deflate_1'`` through ``'deflate_9'``

    * `loglevel`: CouchDB log verbosity; default is ``'notice'``; override with
      any valid CouchDB log level

    * `username`: CouchDB admin username; default is a random username

    * `password`: CouchDB admin password; default is a random 120-bit password;
       avoid using this unless you absolutely need it and have carefully thought
       through the security implications!

    * `oauth`: a dictionary containing OAuth 1.0a tokens; by default random
      tokens are created

    * `ssl`: a dictionary containing ``'key_file'`` and ``'cert_file'``

    * `replicator`: a dictionary containing at least ``'ca_file'``, and
      optionally ``'max_depth'``, ``'key_file'`` and ``'cert_file'``

The above mentioned random values are 120-bit, base32-encoded, 24 character
strings generated using ``os.urandom()``.

The *ssl* and *replicator* values are different than the rest in that they
cause additional sections of the session.ini file to be written.

If you provide *ssl*, CouchDB will be configured for SSL support and will be
listening on two different random ports (one with SSL, the other without).
When you call :meth:`UserCouch.bootstrap()`, the returned *env* will have an
``env['x_env_ssl']`` sub-dictionary like this::

    {
        'port': 56355,
        'url': 'http://127.0.0.1:56355/',
        'authorization': 'Basic QkpQSU1EVU5WRFVMSUpIRUNCRkNaSERROkY1S1RDUUFJS1RGQk9XN1RLUlJVVU5NVA==',
        'basic': {
            'password': 'F5KTCQAIKTFBOW7TKRRUUNMT',
            'username': 'BJPIMDUNVDULIJHECBFCZHDQ'
        },
        'x_env_ssl': {
            'port': 42647,
            'url': 'https://127.0.0.1:42647/',
            'authorization': 'Basic QkpQSU1EVU5WRFVMSUpIRUNCRkNaSERROkY1S1RDUUFJS1RGQk9XN1RLUlJVVU5NVA==',
            'basic': {
                'password': 'F5KTCQAIKTFBOW7TKRRUUNMT',
                'username': 'BJPIMDUNVDULIJHECBFCZHDQ'
            },
        }
    }



.. _security-notes:

Security notes
--------------

You'll typically configure UserCouch to only accept connections from localhost,
so local security is the biggest concern.  Remember, any process running as any
user can connect to your UserCouch.  Although your UserCouch will run on a
random port, that is *not* a sufficient access control mechanism.

The best security is achieved using ``auth='basic'`` (the default) when calling
:meth:`UserCouch.bootstrap()`.  In this case, only the PBKDF2 SHA-1 hashed value
of the random password will be written to the CouchDB session.ini file.  Only
the process that started the UserCouch will know the password.

For security reasons, use of a static password is not recommended.  Instead, let
:meth:`UserCouch.bootstrap()` generate a per-session 120-bit random password
for you.

For obvious reasons, ``auth='open'`` is never recommended.

Likewise, ``auth='oauth'`` is not recommended because the clear-text of the
OAuth tokens (be they random or not) must be written to the session.ini file.



The Lockfile
------------

The :class:`UserCouch` instance will store all the CouchDB data within the
*basedir* you provide.  To prevent multiple :class:`UserCouch` instances from
starting multiple CouchDB instances pointing at the same database files, a
lockfile is used.

If the lock cannot be aquired, a :exc:`LockError` is raised:

>>> tmpdir = tempfile.mkdtemp()
>>> couch1 = UserCouch(tmpdir)
>>> couch2 = UserCouch(tmpdir)
Traceback (most recent call last):
  ...
usercouch.LockError: cannot acquire exclusive lock on '/home/jderose/.usercouch/lockfile'
>>> shutil.rmtree(tmpdir)

Note that it's perfectly fine for multiple :class:`UserCouch` instances to be running
simultaneously as long as each uses its own *basedir*.



.. _`Microfiber`: https://launchpad.net/microfiber
.. _`CouchDB`: http://couchdb.apache.org/

