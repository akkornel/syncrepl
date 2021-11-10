..
   Syncrepl Client documentation: Requirements
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

  - `RFC 3909`_: Lightweight Directory Access Protocol (LDAP) Cancel Operation;
    and

  - `RFC 4533`_: The Lightweight Directory Access Protocol (LDAP) Content
    Synchronization Operation.

  The demo script (syncrepl-client) also requires support for an additional RFC:

  - `RFC 4532`_: Lightweight Directory Access Protocol (LDAP) "Who am I?"
    Operation.

  OpenLDAP is known to support these RFCs, although your OpenLDAP server must be
  configured to support Syncrepl.

  .. note::

    For more information, refer to the OpenLDAP Software 2.4 Administrator's
    Guide, Section 18.3.1, and to the man page for :manpage:`slapo-syncprov(5)`.

.. _RFC 3909: https://datatracker.ietf.org/doc/rfc3909/
.. _RFC 4532: https://datatracker.ietf.org/doc/rfc4532/
.. _RFC 4533: https://datatracker.ietf.org/doc/rfc4533/


* `libldap`_, the OpenLDAP client library.

  libldap is the client library from `OpenLDAP`_.  On most Linux distributions,
  it is packaged separately from the rest of OpenLDAP, so that you can install
  the client library without installing the server stack.

  This module is Pure Python, but other modules (listed below) are not.  If you
  are building other modules, you will also need the libldap headers.

  * On Debian (and derivatives, like Ubuntu), the library is part of the
    `libldap-2.4-2` package, and headers are in the `libldap2-dev` package.

  * On Red Hat Enterprise Linux (and derivatives, like CentOS), the library is
    part of the `openldap` package, and headers are in the `openldap-devel`
    package.

  * On SUSE Linux, the library is part of the `openldap2-client` package, and
    the headers are part of the `openldap2-devel` package.

  * On Arch Linux, the library and headers are part of the `libldap` package.

  * On Macports, the library *and* the headers are part of the `openldap` port.

  At the same time, you may also wish to install the `ldap-utils`, which gives
  you helpful tools like `ldapsearch`_.

.. _libldap: https://linux.die.net/man/3/ldap
.. _OpenLDAP: https://www.openldap.org
.. _ldapsearch: https://linux.die.net/man/1/ldapsearch

* Python 2.7, or Python 3.3.

  It is likely that Python 2.6 will work, but this has not yet been tested.
  CentOS 6 users, which have Python 2.6, should consider using Python 3.4 from
  EPEL.

  When using Python 3, Python 3.3 or later is required because of `python-ldap`'s (formerly `pyldap`_)
  requirements (see `issue 117`_).  If you are on a system which has Python 3.2
  (such as Debian wheezy), consider using Python 2.7 instead.

.. _issue 117: https://github.com/pyldap/pyldap/issues/117

* `python-ldap`_ 99 or later (Python 2), or `python-ldap`_ 3.0.0 or later
  (Python 3).

  python-ldap is an object-oriented wrapper around `libldap`. pyldap is a fork of
  python-ldap, which adds support for Python 3. pyldap has been merged back into
  the python-ldap project.

  pyldap does also work with Python 2, but this software has not been tested
  with pyldap on Python 2.

  .. warning::

    As of this writing, the latest release of python-ldap is 2.4.41.
    However, it has a bug which affects us:

    * python-ldap has a bug in which the `ldap.TIMEOUT` exception is not
      properly raised back to the client.

    The bug has been reported to the python-ldap project.

.. _python-ldap: https://www.python-ldap.org
.. _pyldap: https://github.com/pyldap/pyldap

* The `pyasn1`_ module, at least version 0.2.2, and less than version 0.3.1.

  In Syncrepl, messages from the LDAP server are encoded using ASN.1.
  `libldap`_ does not decode these for us, so we use the well-established
  `pyasn1`_ module to handle the decoding.

  Technically, this is a requirement of `python-ldap`_ / `pyldap`_.  It is an
  optional dependency for them, and is only used when using
  :mod:`ldap.syncrepl`.  That makes it a requirement for us.

  In version 0.3.1, there were a number of breaking API changes.  This causes
  occasional exceptions to be thrown.  Until `pyasn1`_ fixes the issue
  (assuming it's a bug), or `pyldap`_ / `python-ldap`_ change their code,
  `pyasn1`_ 0.3.1 and later may not be used.

.. _pyasn1: http://pyasn1.sourceforge.net


Storage Requirements
--------------------

The Syncrepl client keeps an on-disk copy of the LDAP entries it has received,
along with additional data.  When the connection to the LDAP server is
interrupted, this on-disk data is used to speed up the process of
re-synchronizing with the LDAP server.

To estimate the storage needs for the Syncrepl Client, convert your LDAP URL
into an execution of :manpage:`ldapsearch`.  Measure the size of the
execution's output, and use that as your estimate.

The storage you use **really should** be *fast*, redundant, and battery-backed.
For consistency purposes, the Syncrepl client occasionally pauses to ensure
that changes are synced to disk; speeding up that process will speed up code
execution.  A simple RAID-1 of two SSDs would work.

Memory Requirements
-------------------

For the data referenced in the above section, the Syncrepl client keeps a copy
of the data in memory, in addition to on disk.  This in-memory copy speeds up
data store changes, which is important when LDAP updates are coming in.

Beyond whatever memory requirements this code (and your code) has, you should
also have enough RAM to match the storage requirments listed above.  In other
words, if you estimate needing 5 GB of storage, you should also plan on having
5 GB of RAM.
