..
   Syncrepl Client documentation: Gotchas page
   
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

Syncrepl "Gotcha!"s
===================

The Syncrepl protocol is definitely not the simplest thing in the world to deal
with [#f1]_.  In my (limited) time dealing with Syncrepl stuff, I have run in
to a number of areas where I get behavior that is not what I expect, even
though Syncrepl is doing exactly what it is supposed to do.

.. [#f1] Source: Me; the LDAP admins of Stanford University IT, including Linda
   Laubenheimer and Adam Lewenberg; and others.

In this document, I plan on covering some of the weirdnesses I have discovered
when dealing with Syncrepl.

Changing Binds, and Changing ACLs
=================================

..

    *If your bind changes, or your ACLs change, start with a fresh database.*

Since Syncrepl is essentially an LDAP search, the results you get back are
influenced by the ACLs which apply to you at the time.  But, the Syncrepl
cookie you get does not normally contain any reference to those ACLs.  The
Syncrepl cookie is typically some sort of timestamp, so that when you
reconnect, the LDAP server can know how far to go back in its logs.

If your ACLs change, then the LDAP server will be sending you notifications
about entries which (until just now) did not exist to you, or the LDAP server
will *not* send you notifications about entries that you now can no longer see.
This manifests as weird consistency issues, which might cause exceptions to be
thrown, or (even worse) might not.

So, if your ACL on the LDAP Server is going to change, it is suggested that you
stop your Syncrepl-using service, *delete the DB file*, and wait for the ACL
change to complete *and propagate* before you restart.

Changing binds are mentioned here mainly because a changed bind DN is also
likely to mean a new effective ACL.
