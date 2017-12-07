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

