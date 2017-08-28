#!/bin/bash
# vim: ts=4 sw=4 et

# 
# syncrepl_client dev environment setup.
#
# Refer to the AUTHORS file for copyright statements.
#
# This file is made available under the terms of the BSD 3-Clause License, the
# text of which may be found in the file `LICENSE.md` that was included with
# this distribution, and also at
# https://github.com/akkornel/syncrepl/blob/master/LICENSE.md 
#
# The Python docstrings contained in this file are also made available under
# the terms of the Creative Commons Attribution-ShareAlike 4.0 International
# Public License, the text of which may be found in the file
# `LICENSE_others.md` that was included with this distribution, and also at
# https://github.com/akkornel/syncrepl/blob/master/LICENSE_others.md
#

# This BASH script does everything needed to set up your environment, so long
# as you have Python, pip, setuptools, and OpenLDAP installed.  So, I guess
# then it doesn't do that much, but it's still helpful, because so many of
# these downloads are repetetive.

# Also, if you use MacPorts, setting `MACPORTS=1` will call the `port` command
# to install the Python/pip/setuptools/OpenLDAP stuff for you.

# You should run this from inside the syncrepl_client source directory.

MACPORTS=${MACPORTS:-0}
OLDCWD=$(pwd)
set -e

# Install packages from MacPorts
if [ $MACPORTS ]; then
    echo "BEGIN MacPorts package install (prepare to enter your admin password)"
    sudo port selfupdate
    sudo port install python27 +readline python33 python34 +readline \
                      python35 +readline python36 +readline \
                      py27-pip py27-setuptools py33-pip py33-setuptools \
                      py34-pip py34-setuptools py35-pip py35-setuptools \
                      py36-pip py36-setuptools \
                      openldap +overlays
else
    echo 'NOTE: Please ensure the following things are installed:'
    echo '* Pythons 2.7 through 3.6.'
    echo '* The headers for Pythons 2.7 through 3.6.'
    echo '* For Python 2.7, pip and setuptools.'
    echo '* For Pythons 3.3 through 3.6, pip and setuptools.'
    echo '* OpenLDAP 2.24.x, including its headers.'
    echo 'Everything must be installed at system paths.'
    echo '(All packages installed by this script are installed at local paths.)'
    echo 'One those are installed, to continue, press Return or Enter.'
    read
fi

TMPDIR=$(mktemp -d)
echo "Temporary files being stored in $TMPDIR"
sleep 1
cd $TMPDIR

echo "For Pythons 2.7 and 3.3+, ensuring setuptools is up-to-date."
for version in 2.7 3.3 3.4 3.5 3.6; do
pip-${version} install --upgrade --user setuptools
done

# Download our LDAP packages
echo "Downloading PyLDAP and Python-LDAP."
pip-2.7 download --no-deps python-ldap
pip-3.6 download --no-deps pyldap

if [ $MACPORTS ]; then
    echo "Unpacking and patching PyLDAP and Python-LDAP"
else
    echo "Unpacking PyLDAP and Python-LDAP"
fi
mkdir ldaps
tar -xzf pyldap-*.tar.gz -C ldaps
tar -xzf python-ldap-*.tar.gz -C ldaps
if [ $MACPORTS ]; then
    for dir in $(ls ldaps); do
        sed -i -e 's|library_dirs =|library_dirs = /opt/local/lib|' ldaps/$dir/setup.cfg
        sed -i -e 's|include_dirs =|include_dirs = /opt/local/include|' ldaps/$dir/setup.cfg
    done
fi

echo "Building and installing Python-LDAP for Python 2.7"
sleep 1
cd ldaps/python-ldap-*
python2.7 setup.py build ; python2.7 setup.py install --user
cd ../..

echo "Building and installing PyLDAP for Python 3.3+"
cd ldaps/pyldap*
for version in 3.3 3.4 3.5 3.6; do
    echo "--- Python ${version}"
    sleep 1
    python${version} setup.py build ; python${version} setup.py install --user
done
cd ../..

echo "Cleaning up PyLDAP and Python-LDAP"
rm -f pyldap-*.tar.gz python-ldap-*.tar.gz
rm -rf ldaps

echo "Removing temporary directory"
cd $OLDCWD
rmdir $TMPDIR

echo "Running \`setup.py develop\` for each Python."
for version in 3.3 3.4 3.5 3.6; do
    echo "--- Python ${version}"
    sleep 1
    python${version} setup.py develop --user
done

echo ''
echo 'ALL DONE!'
echo 'The syncrepl-client has been installed at some appropriate local Python path.'
echo '(Such as .local/bin, or ~/Library/Python/x.x/bin).'
exit 0
