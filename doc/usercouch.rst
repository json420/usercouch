:mod:`usercouch` API Reference
==============================

.. py:module:: usercouch
    :synopsis: Start per-user CouchDB instances for fun, profit, unit testing


Exceptions
----------

.. exception:: LockError(lockfile)

    Raised when lock cannot be acquired when creating a :class:`UserCouch`.

    .. attribute:: lockfile

        The path of the lockfile



The :class:`UserCouch` class
----------------------------

.. class:: UserCouch(basedir)

    Starts a per-user CouchDB instance.

    For example:

    >>> mycouch = UserCouch('/home/jderose/.usercouch')
    >>> env = mycouch.bootstrap()

    .. attribute:: basedir

        The directory provided when instance was created.

    .. method:: bootstrap(auth='basic', overrides=None)

        Create the one-time use config and start CouchDB.

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

.. function:: random_b32(numbytes=15)

    Return a random 120-bit base32-encoded random string.

    The ``str`` will be 24-characters long, URL and file-system safe.  For
    example:

    >>> random_b32()
    '6NOLCDV3EQCPJDL43STIZIHN'


.. function:: random_oauth()

    Return a ``dict`` containing random OAuth 1a tokens.
    
    For example:

    >>> random_oauth()
    {
        'consumer_key': 'YXOIWEJOQW4VRGNNEGT6SQYN',
        'consumer_secret': '6KFO4Y4OZQT3YGJ4ZUYOR5I2',
        'token': 'DADIN54ILMCASM2W6S77Q2KW',
        'token_secret': '6T2BFYDJLES7LPFNJOFPEBQO'
    }


.. function:: random_salt()

    Return a 128-bit hex-encoded random salt for use by :func:`couch_hashed()`.

    For example:
    
    >>> random_salt()
    'da52c844db4b8bd88ebb96d72542457a'


.. function:: couch_hashed(password, salt)

    Hash *password* using *salt*.

    This returns a CouchDB-style hashed password to be used in the session.ini
    file.  For example:

    >>> couch_hashed('secret', 'da52c844db4b8bd88ebb96d72542457a')
    '-hashed-ddf425840fd7f81cc45d9e9f5aa484d1f60964a9,da52c844db4b8bd88ebb96d72542457a'

    Typically :class:`UserCouch` is used with a per-session random password,
    so this function means that the clear-text of the password is only stored
    in memory, is never written to disk.
