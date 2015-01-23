AutoTorrent
===========

Given an input torrent, it will scan your collection for the files in
the torrent. If all the files are found, a folder with links to all the
files will be created.

The idea is to be able to organise your collection as you want to and
still be able to seed with the folder structure required by the torrent.

Install
-------

From GitHub (develop):
::

    virtualenv autotorrent-env
    autotorrent-env/bin/pip install git+https://github.com/JohnDoee/autotorrent.git

From PyPi (stable):
::

    virtualenv autotorrent-env
    autotorrent-env/bin/pip install autotorrent

Configuration
-------------

All settings can be found and changed in autotorrent.conf, this file
must reside in the same folder as autotorrent is executed from.

general
~~~~~~~

-  db - Path to the database file
-  store\_path - Folder where the virtual folders seeded, resides
-  ignore\_files - A comma seperated list of files that should be
   ignored (does not support wildcard)
-  rtorrent\_url - URL to rtorrent, must be to the XMLRPC server
-  label - Label added to torrents when added to rtorrent (used in
   rutorrent only)
-  add\_limit\_size - Max size, in bytes, the total torrent size is
   allowed to vary
-  add\_limit\_percent - Max percent the total torrent size is allowed
   to vary

the add\_limit\_\* variables allow for downloading of e.g. different
NFOs and other small files that makes a difference in the torrents.

disks
~~~~~

A list of disks where to build the search database from.

The keys must be sequential, i.e. disk1, disk2, disk3 etc.

Instructions
------------

Start by installing and configuring.

Step 1, build the database with ``autotorrent -r``, this can take some
time.

Step 2, have some torrents ready and run
``autotorrent -a folder/with/torrents/*.torrents``, this command will
spit out how it went with adding the torrents.

And you're good to go, it is possible to verify the integrity of the
currently seeded torrents with ``autotorrent -v``

Limitations
-----------

-  Only works with rtorrent
-  Probably only works on Linux

License
-------

MIT, see LICENSE
