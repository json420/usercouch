UserCouch
=========

`UserCouch`_ is a Python3 library for starting per-user `CouchDB`_ instances,
including throw-away instances for unit testing.  It's especially easy to use
with `Microfiber`_, for example:

>>> from usercouch.misc import TempCouch
>>> from microfiber import Database
>>> tmpcouch = TempCouch()
>>> env = tmpcouch.bootstrap()
>>> db = Database('mydb', env)
>>> db.put(None)  # Create the database
{'ok': True}
>>> db.post({'_id': 'mydoc'}) == {  # Create a document
...     'id': 'mydoc',
...     'rev': '1-967a00dff5e02add41819138abb3284d',
...     'ok': True,
... }
True


UserCouch is being developed as part of the `Novacut`_ project.  UserCouch
packages are available for Ubuntu in the `Novacut Stable Releases PPA`_ and the
`Novacut Daily Builds PPA`_.

If you have questions or need help getting started with UserCouch, please stop
by the `#novacut`_ IRC channel on freenode.

UserCouch is licensed `LGPLv3+`_, requires `Python 3.4`_ or newer, and depends
upon `Degu`_ and `Dbase32`_.

.. note::
    As of UserCouch 16.03, the CouchDB configuration API is disabled by default.
    See :doc:`usercouch` for details.


Contents:

.. toctree::
    :maxdepth: 2

    install
    tutorial
    usercouch
    usercouch.misc



.. _`UserCouch`: https://launchpad.net/usercouch
.. _`CouchDB`: http://couchdb.apache.org/
.. _`Microfiber`: https://launchpad.net/microfiber
.. _`Novacut`: https://launchpad.net/novacut
.. _`Novacut Stable Releases PPA`: https://launchpad.net/~novacut/+archive/stable
.. _`Novacut Daily Builds PPA`: https://launchpad.net/~novacut/+archive/daily
.. _`#novacut`: http://webchat.freenode.net/?channels=novacut
.. _`LGPLv3+`: https://www.gnu.org/licenses/lgpl-3.0.html
.. _`Python 3.4`: https://docs.python.org/3.4/
.. _`Degu`: https://launchpad.net/degu
.. _`Dbase32`: https://launchpad.net/dbase32

