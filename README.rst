AutoTorrent
===========

Given an input torrent, it will scan your collection for the files in
the torrent. If all (or most) the files are found, a folder with links to all the
files will be created and the torrent added to the torrent client.

All you need to do is download the torrents and AutoTorrent plays mix and match
to make it possible to seed as much as possible across trackers.

Requirements
------------

- Linux, BSD, OSX - Something not windows
- rTorrent, Deluge, qBittorrent or Transmission
- Python 2.6+, 3.3+
- Shell / SSH / Putty

Status
------

Master branch
~~~~~~~~~~~~~~
.. image:: https://coveralls.io/repos/github/JohnDoee/autotorrent/badge.svg?branch=master
   :target: https://coveralls.io/github/JohnDoee/autotorrent?branch=master
.. image:: https://travis-ci.org/JohnDoee/autotorrent.svg?branch=master
   :target: https://travis-ci.org/JohnDoee/autotorrent


Develop branch
~~~~~~~~~~~~~~
.. image:: https://coveralls.io/repos/github/JohnDoee/autotorrent/badge.svg?branch=develop
   :target: https://coveralls.io/github/JohnDoee/autotorrent?branch=develop
.. image:: https://travis-ci.org/JohnDoee/autotorrent.svg?branch=develop
   :target: https://travis-ci.org/JohnDoee/autotorrent

Install
-------

From PyPi (stable):
::

    virtualenv autotorrent-env
    autotorrent-env/bin/pip install autotorrent

From GitHub (develop):
::

    virtualenv autotorrent-env
    autotorrent-env/bin/pip install git+https://github.com/JohnDoee/autotorrent.git#develop

Create the configuration file
::

    autotorrent-env/bin/autotorrent --create_config

Upgrade from previous version
-----------------------------

Upgrading from PyPi (stable)
::

    autotorrent-env/bin/pip install --upgrade autotorrent

Upgrading from Github (develop)
::

    autotorrent-env/bin/pip install git+https://github.com/JohnDoee/autotorrent.git#develop --upgrade --force-reinstall

Flags
-------------
- ``-a FILE, --addfile FILE`` - Add a new torrent file to the client. Wildcards can be used to expand to all files in a folder (eg: ``-a /some/folder/*.torrent``)
- ``-c  CONFIG_FILE, --config CONFIG_FILE`` - Path to config file. Defaults to current terminal folder.
- ``--create_config`` - Creates a new configuration file.
- ``-d, --delete_torrents`` - Delete .torrent files when they are added to the client succesfully.
- ``--dry-run`` - Don't add any torrents to client, just scan for files needed for torrents.
- ``-h, --help`` - Shows help message and exits.
- ``-l CLIENT, --client CLIENT`` - Name of client to use (when multiple configured). `Read more here <#q-can-i-have-multiple-clients-configured-simultaneously>`_.
- ``-r, --rebuild`` - Rebuilds the database (necessary for new files/file changes on disk).
- ``-t, --test-connection`` - Test the connection to the torrent client.
- ``--verbose`` - Increase output verbosity.

Configuration
-------------

All settings can be found and changed in ``autotorrent.conf``, this file
must reside in the same folder as autotorrent is executed from.

general
~~~~~~~

-  ``db`` - Path to the database file
-  ``store_path`` - Folder where the virtual folders seeded, resides
-  ``ignore_files`` - A comma seperated list of files that should be
   ignored (supports wildcards)
-  ``add_limit_size`` - Max size, in bytes, the total torrent size is
   allowed to vary
-  ``add_limit_percent`` - Max percent the total torrent size is allowed
   to vary
-  ``link_type`` - What kind of link should AutoTorrent make? the options are
   hard and soft.
-  ``scan_mode`` - options are unsplitable, normal and exact. These can be used
   in combination. See the `scan_modes <#scan-modes>`_ section for more information.

the ``add_limit_*`` variables allow for downloading of e.g. different
NFOs and other small files that makes a difference in the torrents.

client
~~~~~~

-  ``client`` - torrent client to use, choices are: rtorrent, deluge and transmission

rtorrent settings
*****************
-  ``url`` - URL to rtorrent, must be to the XMLRPC server or SCGI server.
-  ``label`` - Label added to torrents when added to rtorrent (used in
   rutorrent only)

the url supports both SCGI directly and XMLRPC via HTTP.

To use scgi, prefix the url with scgi instead of http, e.g. ``scgi://127.0.0.1:10000/``

To use unix socket for scgi, make an url with no `ip:port` and instead a path, e.g. ``scgi:///tmp/rtorrent.socket``

deluge settings
***************
- ``host`` - an ip:port pair, e.g. ``127.0.0.1:12345``
- ``username`` - deluge rpc username
- ``password`` - deluge rpc password
- ``label`` - label the torrent, remember to enable the label plugin

transmission settings
*********************
- ``url`` - an url where transmission can be reached, e.g. ``http://username:password@127.0.0.1:9091/transmission/rpc``

qbittorrent settings
*********************
- ``url`` - an url where qbittorrent web can be reached, e.g. ``http://127.0.0.1:8080``
- ``username`` - qbittorrent webui username
- ``password`` - qbittorrent webui password
- ``category`` - category applied to torrents added by AutoTorrent (similar to label)

`disks`
~~~~~~~~~~

A list of disks where to build the search database from.

Scan modes
----------

There are currently three scan modes supported by AutoTorrent. These modes can be
used in combination and should all improve the end result.

The modes are named normal, exact and unsplitable. They can be combined by adding a comma
between them, e.g. ``scan_mode=normal,exact,unsplitable``

Mode: ``normal``
~~~~~~~~~~~~~~~~~~~~~~~~

It takes the filename and size and tries to find files with same name and size.

This mode cannot handle duplicate filename/size pairs.

Mode: ``exact``
~~~~~~~~~~~~~~~~~~~~~~~

The perfect way to move torrent client as it tries to set the download path to the old path.

This mode does not allow for missing files and is intended to re-add non-renamed back to a torrent client.

Mode: ``unsplitable``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This mode takes scene releases and extracted dvd/bluray isos into consideration and relies on the folder it thinks
is the main / head folder. Perfect for cross-seeding scene releases.

Mode: ``hash_name``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This mode tries to hashcheck files with the exact name as wanted, but the size might be different (up to 10% different).
If pieces match, then it is resized to fit original size and written to the destination directory.

Make sure there is enough space in the target directory.

Mode: ``hash_size``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This mode tries to hashcheck files with the exact size as wanted, but the name might be different.|

Mode: ``hash_slow``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

This mode tries to hashcheck files with a size within 10% of the original.
If pieces match, then it is resized to fit original size and written to the destination directory.

Make sure there is enough space in the target directory.

This mode is very slow as it will try a lot of files.

Instructions
------------

Start by installing and configuring.

Step 1
~~~~~~~~~~~~~~~
Build the database with

::

    autotorrent-env/bin/autotorrent -r

this may take some time.

Step 2
~~~~~~~~~~~~~~~
Have some .torrent files ready and run

::

    autotorrent-env/bin/autotorrent -a path/to/torrents/*.torrent

this command will spit out how it went with adding the torrents.

And you're good to go.

FAQ
---

Q: How are files with relative path in the configuration file, found?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The paths should be relative to the configuration file, e.g. ``/home/user/autotorrent-env/autotorrent.conf``,
then ``store_path=store_paths/X/`` resolves to ``/home/user/autotorrent-env/store_path/``.


Q: I have three sites I cross-seed between, how do you suggest I structure it?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Say, you have site X, Y and Z. You want to seed across the sites as they share lots of content.
You download all your data into /home/user/downloads/. For this you will need three configuration file, one for each site.

AutoTorrent is installed into ``/home/user/autotorrent-env/``.

Only store_path is recommended to vary between the configuration files (the others are optional).

- ``store_path for site X - /home/user/autotorrent-env/store_paths/X/``
- ``store_path for site Y - /home/user/autotorrent-env/store_paths/Y/``
- ``store_path for site Z - /home/user/autotorrent-env/store_paths/Z/``

disks paths can be:

- ``disk1=/home/user/downloads/``
- ``disk2=/home/user/autotorrent-env/store_paths/X/``
- ``disk3=/home/user/autotorrent-env/store_paths/Y/``
- ``disk4=/home/user/autotorrent-env/store_paths/Z/``

Q: Can I use the same Database file for several configuration files?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Yes, if they have the same disks. Don't worry about adding the `store_path` to the disks, AutoTorrent will figure it out.

Q: What problems can occur?
~~~~~~~~~~~~~~~~~~~~~~~~~~~
One big problem is that the files are not checked for their actual content, just if their filename matches and size matches.
If AutoTorrent tries to use a file that is not complete, then you can end up sending loads of garbage to innocent peers,
alhough they should blackball you quite fast.

Q: I want to cross-seed RARed scene releases, what do you think about that?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The actual .rar files must be completely downloaded and the same size. Things that can vary are: nfos, sfvs, samples and subs.

The releases must also have an sfv in the same folder as the rar files files.

Q: What are hardlinks and what are the risks or problems associated with using them?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
See: http://www.cyberciti.biz/tips/understanding-unixlinux-symbolic-soft-and-hard-links.html

.. _clients:

Q: Can I have multiple clients configured simultaneously?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Yes, this can be done by prefixing a name of your choosing, with ``client-``. For example, you can name the section ``client-goodclient`` instead of just ``client``. Then specify the new client/name without the prefix using the commandline argument

::
    autotorrent -l goodclient

License
-------

MIT, see `LICENSE <../master/LICENSE>`_
