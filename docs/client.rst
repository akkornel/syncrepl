..
   Syncrepl Client documentation: Client class
   
   Refer to the AUTHORS file for copyright statements.
   
   This work is licensed under a
   Creative Commons Attribution-ShareAlike 4.0 International Public License.
   
   Code contained in this document is also licensed under the BSD 3-Clause License.
   
   See the LICENSE file for full license texts.

The Syncrepl Client's Syncrepl Class
====================================

The :class:`~syncrepl_client.Syncrepl` class is the main class that you will be
using.  It is responsible for all LDAP operations, and will issue callbacks to
an object you provide (see the :class:`~syncrepl_client.callbacks.BaseCallback`
class).

.. autoclass:: syncrepl_client.Syncrepl
   :members:
   :special-members:
