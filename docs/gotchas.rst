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

.. [#f1] Source: Me; the LDAP admins of Stanford University IT's Authentication
   and Collaboration Solutions group, including Linda Laubenheimer and Adam
   Lewenberg; and others.

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

Derived Attribites (like memberOf)
==================================

..

    *Derived attributes must not be trusted.*

This is a piece of knowledge that LDAP administrators have, but which LDAP
clients normally do not know about (or do not think about):

*Not all populated LDAP attributes actually exist.*

Here is an example:  You have two trees in a directory:

* The tree `cn=accounts, dc=domain` contains one entry for every computer
  account.  All of the POSIX attributes are present.  For example, the `uid`
  attribute contains the account's username.

* The tree `cn=groups, dc=domain` contains one entry for every group.  The `cn`
  attribute holds the group name, and the multi-valued `member` attribute holds
  the DN of each account that is a member of the group.

In the above example, let's say you want to find out what groups an account is
in.  The only apparent option is to enumerate every group, looking for the
user; or to do an LDAP search with a filter like `(member=DN OF ACCOUNT OF
INTEREST)`.  If the LDAP server has an index on the `member` attribute, then
that search will at least be fast, but it's still up to you to assemble all of
the results into a list.

In most cases, your schema will have a `memberOf` multi-valued attribute in the
accounts tree, containing the DNs of the groups where the account is a member.
But that means changing group membership now has to be a transaction, because
you need to atomically change two records.  That is made more difficult because
each record is in a different tree, and the two trees may use different
database backends.

The solution is to have the contents of the `memberOf` attribute generated only
at the time you need it.  With 389 Directory Server, you use the `MemberOf plugin`_.  With OpenLDAP, you use the `memberof overlay`_.  In both cases, the LDAP server is doing the sub-search in the background (which, because the attributes are indexed, is fast) and inserting the results into the record.


.. _MemberOf plugin: http://directory.fedoraproject.org/docs/389ds/design/memberof-plugin.html
.. _memberof overlay: https://www.openldap.org/doc/admin24/overlays.html#Reverse%20Group%20Membership%20Maintenance

For a normal LDAP client, this is perfect, because you get all the information
you need in one record.  For a Syncrepl client, this is **bad**.

One must remember that a Syncrepl search starts out as a regular LDAP search,
but then it becomes (in a way) a `tail` of the LDAP server's change log.  In
the above example, the `memberOf` attribute's values are generated at
query-time, not when changes are made, so derived attributes are not logged in
change logs.

This warning applies to any attributes, and even to entire records, that are
generated by plugins or overlays: You might get the results you expect in the
original search, but what will happen after that is undefined.

Unfortunately, there is no clear way of dealing with this issue, because it is
entirely dependent on what data you want, and what you are trying to do.  The
only advice the author can give is that you make friends with the LDAP admin,
because they are the ones who can best tell you which data in the directory are
"real", and which aren't.
