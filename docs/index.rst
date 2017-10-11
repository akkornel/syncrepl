..
   Syncrepl Client documentation: Main page
   Originally created by sphinx-quickstart on Thu May 25 21:02:02 2017.
   
   Refer to the AUTHORS file for copyright statements.
   
   This work is licensed under a
   Creative Commons Attribution-ShareAlike 4.0 International Public License,
   the text of which may be found in the file `LICENSE_others.md` that was
   included with this distribution, and also at
   https://github.com/akkornel/syncrepl/blob/master/LICENSE_others.md
   
   Code contained in this document is also licensed under the BSD 3-Clause
   License, the text of which may be found in the file `LICENSE.md` that was
   included with this distribution, and also at
   https://github.com/akkornel/syncrepl/blob/master/LICENSE.md
   
   See the LICENSE file for full license texts.

Welcome to Syncrepl Client's documentation!
===========================================

.. toctree::
   :hidden:
   :maxdepth: 2

   Requirements <requirements>
   The Client Class <client>
   Callbacks <callbacks>
   Exceptions <exceptions>
   Index <genindex>

**syncrepl_client** is a Python module that makes LDAP Syncrepl easy to use.

`LDAP Syncrepl`_ allows you to keep up-to-date with an LDAP server, effectively
in real time, even without LDAP administrator credentials.

.. _LDAP Syncrepl: https://www.openldap.org/doc/admin24/replication.html#LDAP%20Sync%20Replication

If your LDAP directory is used as the source of truth (or a delegate for the
soource of truth), this keeps you informed when something changes.
Callbacks—which you write—are triggered by this code when something happens.
You can then take appropriate action, such as by inserting into a queue or
sending a message over a bus.

What is Syncrepl?
-----------------

Syncrepl (as described in `RFC 4533`_) is a standard which allows an LDAP
server to keep clients in sync with itself.  The clients keep track of a
"cookie", an opaque string that the server uses to know how far behind the
client is.  The LDAP server then "refreshes" the client by sending details of
new & changed entries, as well as information on which entries have been
deleted.  After the refresh is complete, the client is able to keep a
long-running connection open to the server, and receive notice as soon as a
change happens on the server.

.. _RFC 4533: https://datatracker.ietf.org/doc/rfc4533/

Syncrepl is the way that OpenLDAP uses to implement replication (from a master
LDAP server to one or more slaves), but the client does not have to be an
OpenLDAP server.  In fact, because Syncrepl is layered on top of an ordinary
LDAP search, regular LDAP clients—even those with limited access—are able to
use Syncrepl to effectively be notified as soon as the results of their search
has changed.  This includes notification on:

* New entries that match your search filter.

* Entries being deleted.

* Entries, which used to match, no longer matching.  This is essentially the
  same as deletion (at least, it is when you are using a search filter).

* Existing entries having their attributes or DN changed.

The entries you see, and the changes made to them, are based on the
intersection of four things.

1. The entries currently in the directory.

2. Your access rights, as determined by your bind DN.

3. Your search filter.

4. Your list of requested attributes.

Thanks to the Syncrepl protocol, you don't have to worry about all of the
above.  The LDAP server handles the work of figuring out what you can see.

Requirements
============

`syncrepl_client` has four major requirements:

* Python 2.7, or Python 3.3+.

  If you use Python 2.7 or 3.3, you will also need
  `enum34`_.

  If you plan on doing "refresh and persist" operations (which run for a long
  time), your Python should support threads.

* An appropriate Python LDAP library:

  * For Python 2.7, `python-ldap`_ 99 or later is needed.

  * For Python 3, `pyldap`_ 2.4.37 or later is needed.

* The `pyasn1`_ module, at least version 0.2.2, and less than version 0.3.1.

  Technically, this is a requirement of `python-ldap`_ / `pyldap`_.  It is an
  optional dependency for them, and is only used when using
  :mod:`ldap.syncrepl`.  That makes it a requirement for us.

* A fast data store, large enough to store a copy of all the LDAP data
  received, and a corresponding amount of RAM.

* An LDAP server which supports RFC 4533, and which is keeping track of changes.

  In the case of OpenLDAP, this means following the instructions in
  `Section 18.3.1`_ of the `Admin Guide`_.

Lots more details are available on the :doc:`Requirements page </requirements>`.

.. _enum34: https://bitbucket.org/stoneleaf/enum34
.. _python-ldap: https://www.python-ldap.org
.. _pyldap: https://github.com/pyldap/pyldap
.. _pyasn1: http://pyasn1.sourceforge.net
.. _Section 18.3.1: https://www.openldap.org/doc/admin24/replication.html#Syncrepl
.. _Admin Guide: https://www.openldap.org/doc/admin24/index.html

How to Use
==========

Although you'll still need to do a fair bit of coding (mainly in Step 1),
syncrepl_client is (intentionally) pretty easy to use!  Over the life of your
code's execution, you should do these four things:

1. Create a class which implements the methods defined in
   :class:`~syncrepl_client.callbacks.BaseCallback`
   This is how you are notified of changes from the LDAP server.

2. In your main code, import :mod:`syncrepl_client` and instantiate a new
   :class:`~syncrepl_client.Syncrepl` object.  The instantiation will handle
   the connection and the search setup.

3. Call :meth:`~syncrepl_client.Syncrepl.poll` until it returns :obj:`False`.
   If you're running single-threaded, set `timeout` to some positive, non-zero
   value.  Call :meth:`~syncrepl_client.Syncrepl.please_stop` when you want to
   safely shut down, and then resume calling
   :meth:`~syncrepl_client.Syncrepl.poll` until it returns :obj:`False`.

4. Call :meth:`~syncrepl_client.Syncrepl.unbind`.  You're done!

Lots more details are available in the :doc:`Requirements page
</requirements>`, and see syncrepl_client (which setup.py and pip install as a
script) for a simple example.

Copyright and License
=====================

The contents of this repository are copywrited according to the contents of the 
`AUTHORS`_ file.

The code is made available under the BSD 3-Clause License.

Other code is made available under the Creative Commons CC0 Public Domain Dedication.

Documentation is made available under the Creative Commons
Attribution-ShareAlike 4.0 International Public License (the CC BY-SA License).
Code contained within documentation is made available under both the BSD
3-Clause License, and the CC BY-SA License.

To identify the license for any particular file, refer to the contents of the
file.

The text of the BSD 3-Clause License is reproduced in the file `LICENSE.md`_.
The text of the other licenses may be found in the file `LICENSE_others.md`_.
Note that all three licenses are equally important, but are kept in a separate
files to aid GitHub's irepository license-detection mechanisms.

.. _AUTHORS: https://github.com/akkornel/syncrepl/blob/master/AUTHORS
.. _LICENSE.md: https://github.com/akkornel/syncrepl/blob/master/LICENSE.md
.. _LICENSE_others.md: https://github.com/akkornel/syncrepl/blob/master/LICENSE_others.md
