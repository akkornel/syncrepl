# Upstream Patches

syncrepl\_client relies on either the
[python-ldap](https://pypi.python.org/pypi/python-ldap/) package (on Python 2),
or the [pyldap](https://pypi.python.org/pypi/pyldap) package (on Python 3).
Both packages provide a Python interface on top of `libldap`, the OpenLDAP
client library.

The syncrepl portion of our parents is clearly little-used, as each package has
a bug that is affecting this software.

The sections below describe the bugs.  If a patch is available, that is noted
and the patch will be available in this directory.

## python-ldap: Timeout exception handling

There are two ways to do a syncrepl search: `refreshOnly` mode and
`refreshAndPersist` mode.

In the former mode, timeouts are unlikely, and are cause for alarm.  When doing
a refresh, the LDAP server provides a stream of changes that need to be made to
your local view of the directory, in order to become up-to-date.  If a timeout
happens during this update, it is likely due to a problem with the LDAP server,
or with your connection to the LDAP server.

In `refreshAndPersist` mode, timeouts are possible, intentionally so.  If you
perform a `poll` with a timeout, an `ldap.TIMEOUT` exception is supposed to be
raised if the timeout expires and there are no updates from the LDAP server.

`python-ldap` does not currently handle this exception properly.  Instead, it
tries to manipulate the exception, triggering another exception (an
`IndexError` exception).

This has been reported to python-ldap, but the project doesn't have a bug
tracker.  To track the progress of this, see [the python-ldap mailing list
thread](https://mail.python.org/pipermail/python-ldap/2017q2/003919.html).

This bug does not affect pyldap, which has fixed it as part of release
2.4.35.1.

**NOTE:** It is still possible to use python-ldap with this software.  If you
restrict yourself to the `refreshOnly` mode, then you should not be affected by
this bug.

## pyldap: UUID instantiation

In an LDAP directory, every entry has a normally-hidden UUID.  These UUIDs are
necessary because it is possible for DNs to change; the UUID is used to track
entries across DN changes.

As part of syncrepl, the UUID attribute is exposed to the client.  python-ldap
uses the Python UUID object to parse the UUID from the LDAP server.  When the
UUID object is created, it is possible to pass a byte string, which is parsed
as a UUID.

In Python 2, strings default to being byte strings.  In Python 3, strings
default to being Unicode strings.  This is where the error happens: The UUID
constructor is told to expect a bytes string, but instead it is provided a
native (Unicode) string.

In a way, you could say this is a bug in python-ldap, but python-ldap doesn't
support Python 3.  Nonetheless, this patch has been submitted to python-ldap,
so that it will trickle down to pyldap without pyldap needing to do a separate
patch.

python-ldap doesn't have a bug tracker.  To track the progress of this patch,
see [the python-ldap mailing list
thread](https://mail.python.org/pipermail/python-ldap/2017q2/003924.html).

If python-ldap does not accept the patch, it will be submitted instead to
pyldap for inclusion there.

The file `pyldap.patch` contains a form of patch that you can apply locally,
which will fix this problem.
