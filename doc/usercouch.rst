:mod:`usercouch` --- core API
=============================

.. py:module:: usercouch
    :synopsis: Start per-user CouchDB instances for fun, profit, unit testing


Exceptions
----------

.. exception:: LockError(lockfile)

    Raised when lock cannot be acquired when creating a :class:`UserCouch`.

    .. attribute:: lockfile

        The path of the lockfile



:class:`Paths` class
------------------------

.. class:: Paths(basedir)

    Various files and directories within a :attr:`UserCouch.basedir`.
    
    Attributes include:

    .. attribute:: ini

        The CouchDB ``'session.ini'`` configuration file

    .. attribute:: databases

        The directory containing the CouchDB database files

    .. attribute:: views

        The directory containing the CouchDB view files

    .. attribute:: log

        A directory for log files, including those used by UserCouch itself

    .. attribute:: logfile

        The ``'couchdb.log'`` used by CouchDB

    .. attribute:: ssl

        A directory for SSL certificates and keys (not used by UserCouch)

    .. attribute:: dump

        A directory for storing JSON dumps of CouchDB databases (not used by UserCouch)



:class:`UserCouch` class
------------------------

.. class:: UserCouch(basedir)

    Starts a per-user CouchDB instance.

    For example:

    >>> import tempfile
    >>> from usercouch import UserCouch
    >>> mytmpdir = tempfile.mkdtemp()
    >>> mycouch = UserCouch(mytmpdir)
    >>> env = mycouch.bootstrap()

    .. attribute:: basedir

        The directory provided when instance was created.

    .. attribute:: paths

        A :class:`Paths` instances for handy access to the files and
        directories inside the *basedir*

    .. method:: bootstrap(auth='basic', config=None, extra=None)

        Create the one-time configuration and start CouchDB.

        *auth* must be ``'open'``, ``'basic'``, or ``'oauth'``.

        If provided, *config* must be a ``dict`` with configuration values.

        If provide, *extra* must be an ``str`` with CouchDB configuration text
        that will be appended to the session.ini file.

        The return value is an *env* dictionary that follows the
        `Microfiber`_ conventions.

    .. method:: start()

        Start (or re-start) CouchDB.

    .. method:: kill()

        Kill the CouchDB process.

        Normally this method will be called automatically when the
        :class:`UserCouch` instance is garbage collected, but in certain
        circumstances you may need to explicitly call it.

    .. method:: isalive()

        Make an HTTP request to see if the CouchDB server is alive.

    .. method:: check()
    
        Test if the CouchDB server is alive, restart it if not.

    .. method:: crash()

        Terminate the CouchDB process to simulate a CouchDB crash.



Helper functions
----------------

.. function:: random_oauth()

    Return a ``dict`` containing random OAuth 1a tokens.
    
    For example:

    >>> from usercouch import random_oauth
    >>> random_oauth()  #doctest: +SKIP
    {
        'consumer_key': 'YXOIWEJOQW4VRGNNEGT6SQYN',
        'consumer_secret': '6KFO4Y4OZQT3YGJ4ZUYOR5I2',
        'token': 'DADIN54ILMCASM2W6S77Q2KW',
        'token_secret': '6T2BFYDJLES7LPFNJOFPEBQO'
    }


.. function:: random_salt()

    Return a 128-bit hex-encoded random salt for use by :func:`couch_hashed()`.

    For example:

    >>> from usercouch import random_salt
    >>> random_salt()  #doctest: +SKIP
    'da52c844db4b8bd88ebb96d72542457a'


.. function:: couch_hashed(password, salt)

    Hash *password* using *salt*.

    This returns a CouchDB-style hashed password to be used in the session.ini
    file.  For example:

    >>> from usercouch import couch_hashed
    >>> couch_hashed('secret', 'da52c844db4b8bd88ebb96d72542457a')
    '-hashed-ddf425840fd7f81cc45d9e9f5aa484d1f60964a9,da52c844db4b8bd88ebb96d72542457a'

    Typically :class:`UserCouch` is used with a per-session random password,
    so this function means that the clear-text of the password is only stored
    in memory, is never written to disk.



.. _`Microfiber`: https://launchpad.net/microfiber
