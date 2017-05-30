..
   Syncrepl Client documentation: Requirements
   Originally created by sphinx-quickstart on Thu May 25 21:02:02 2017.
   
   Refer to the AUTHORS file for copyright statements.
   
   This work is licensed under a
   Creative Commons Attribution-ShareAlike 4.0 International Public License.
   
   Code contained in this document is also licensed under the BSD 3-Clause License.
   
   See the LICENSE file for full license texts.

Syncrepl Client requirements
============================

The Syncrepl client doesn't have many direct requires, but those requirements
have a large-enough number of requirements that it's worth listing everything.

This page is broken into two sections: The software you need, and the storage
you need.

Software Requirements
---------------------

The Syncrepl client has a number of direct and indirect requirements.

* A compatible LDAP server.

"compatible" means that the LDAP server must implement a number of RFCs,
including:

- `RFC 3909`_: Lightweight Directory Access Protocol (LDAP) Cancel Operation.

- `RFC 4533`_: The Lightweight Directory Access Protocol (LDAP) Content
  Synchronization Operation.

The demo script also requires support for an additional RFC:

- `RFC 4532`_: Lightweight Directory Access Protocol (LDAP) "Who am I?" Operation.

OpenLDAP is known to support these RFCs, although your OpenLDAP server must be
configured to support Syncrepl.

.. _RFC 3909: https://datatracker.ietf.org/doc/rfc3909/
.. _RFC 4532: https://datatracker.ietf.org/doc/rfc4532/
.. _RFC 4533: https://datatracker.ietf.org/doc/rfc4533/

.. note::

    For more information, refer to the OpenLDAP Software 2.4 Administrator's
    Guide, Section 18.3.1, and to the man page for :manpage:`slapo-syncprov(5)`.

* `libldap`_, the OpenLDAP client library.

libldap is the client library from OpenLDAP.  On most Linux distributions, it
is packaged separately from the rest of OpenLDAP, so that you can install the
client library without installing the server stack.

At the same time, you may also wish to install the `ldap-utils`, which gives
you helpful tools like `ldapsearch`_.

.. _libldap: https://linux.die.net/man/3/ldap
.. _ldapsearch: https://linux.die.net/man/1/ldapsearch

* Python 2.7, or Python 3.6.

* `python-ldap`_ 2.4.38 or later (Python 2), *or* `pyldap`_ 2.4.35.1 or later
  (Python 3).

python-ldap is an object-oriented wrapper around `libldap`, and works in Python
2 only.  pyldap is a fork of python-ldap, which adds support for Python 3.

.. warning::

    As of this writing, pyldap is missing some parts of python-ldap, which
    cause breakage in Python 2.  If you are running Python 2, you **must** use
    python-ldap.

    On Python 3, pyldap has a bug related to UUID-handling, which has not yet
    been fixed.

.. _python-ldap: https://www.python-ldap.org
.. _pyldap: https://github.com/pyldap/pyldap

Storage Requirements
--------------------

The Syncrepl client keeps an on-disk copy of the LDAP entries it has received,
along with additional data.  When the connection is interrupted, this on-disk
data is used to speed up the process of re-synchronizing with the LDAP server.

To estimate the storage needs for the Syncrepl Client, convert your LDAP URL
into an execution of :manpage:`ldapsearch`.  Measure the size of the
execution's output, and use that as your estimate.

The storage you use should be fast, redundant, and battery-backed.  For consistency
purposes, the Syncrepl client occasionally pauses to ensure that changes are
synced to disk; speed up that process will speed up code execution.

Memory Requirements
-------------------

Beyond whatever memory requirements this code (and your code) has, you should
also have enough RAM to match the storage requirments listed above.  In other
words, if you estimate needing 5 GB of storage, you should also plan on having
5 GB of RAM.
