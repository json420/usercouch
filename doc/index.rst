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
>>> db.post({'_id': 'mydoc'})  # Create a document
{'rev': '1-967a00dff5e02add41819138abb3284d', 'ok': True, 'id': 'mydoc'}

UserCouch is being developed as part of the `Novacut`_ project.  UserCouch
packages are available for Ubuntu in the `Novacut Stable Releases PPA`_ and the
`Novacut Daily Builds PPA`_.

If you have questions or need help getting started with UserCouch, please stop
by the `#novacut`_ IRC channel on freenode.

UserCouch is licensed `LGPLv3+`_.


Contents:

.. toctree::
    :maxdepth: 2

    tutorial
    usercouch
    usercouch_misc



.. _`UserCouch`: https://launchpad.net/usercouch
.. _`CouchDB`: http://couchdb.apache.org/
.. _`Microfiber`: https://launchpad.net/microfiber
.. _`LGPLv3+`: http://www.gnu.org/licenses/lgpl-3.0.html


.. _`Novacut`: https://wiki.ubuntu.com/Novacut
.. _`Novacut Stable Releases PPA`: https://launchpad.net/~novacut/+archive/stable
.. _`Novacut Daily Builds PPA`: https://launchpad.net/~novacut/+archive/daily
.. _`#novacut`: http://webchat.freenode.net/?channels=novacut
