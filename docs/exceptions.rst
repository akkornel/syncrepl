..
   Syncrepl Client documentation: Exceptions
   
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

Syncrepl Client Exceptions
==========================

When a :class:`~syncrepl_client.Syncrepl` instance wants to tell you about
a problem, it raises an exception.

This document covers all of the exceptions thrown directly by
:class:`~syncrepl_client.Syncrel`.  Note that you should also be prepared to
catch exceptions from :mod:`ldap`, as those exceptions are allowed to percolate
up to the client, with only a few exceptions (for example, catching CANCELLED
and TIMEOUT exceptions when they are expected).

The exceptions raised by :class:`~syncrepl_client.Syncrepl` are as follows:

.. automodule:: syncrepl_client.exceptions
