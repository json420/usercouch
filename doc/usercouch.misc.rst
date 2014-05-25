:mod:`usercouch.misc` API Reference
===================================

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

