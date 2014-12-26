:mod:`usercouch.misc` --- Test fixtures
=======================================

.. py:module:: usercouch.misc
    :synopsis: Misc helpers for unit testing
    
The :mod:`usercouch.misc` module provides some helper classes to make it easy
to use good CouchDB unit testing idioms.


:class:`TempCouch` class
------------------------

.. class:: TempCouch

    A throw-away CouchDB that stores files in a temporary directory.



:class:`CouchTestCase` class
-----------------------------

If subclasses need to provide their own ``setUp()`` or ``tearDown()`` methods,
be sure to call the super methods.

As your CouchDB unit tests can be rather long-running, you can set an
environment variable that will cause all :class:`CouchTestCase` based test-cases
to be skipped.

For example, when running your own tests, you can do something like this on
the command line::

    SKIP_USERCOUCH_TEST_CASES=true ./setup.py test


.. class:: CouchTestCase

    Base-class for CouchDB using unit tests.

    .. attribute:: tmpcouch

        The :class:`TempCouch` instance created by :meth:`CouchTestCase.setUp()`.

    .. attribute:: env

        The *env* returned by :meth:`usercouch.UserCouch.bootstrap()`.

    .. method:: setUp()

        Create and bootstrap a :class:`TempCouch` instance.

    .. method:: tearDown()

        Destroy the :class:`TempCouch` instance.

