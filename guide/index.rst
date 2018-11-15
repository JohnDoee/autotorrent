Automatic Cross-seeding
=======================

This guide will extend your setup where you are already downloading torrents live (new data as it is released) and want to seed the same content on other torrent trackers. The downloading should be automatic as this guide relies on RSS feeds where only the newest releases are shown.

Prerequisite
------------

- Working torrent client(s) for cross seeding
- Already working auto downloading setup that downloads new releases

The example used in this guide has the following setup:

Data folder structure
~~~~~~~~~~~~~~~~~~~~~

/mnt/incoming
  The download folder where incomplete releases recides. The releases will be moved on complete.

/mnt/tv/
  TV Folder, where TV episodes are moved when they are complete. The structure is */mnt/tv/Tv.Show/Season.03/TV.episode.S01E01-ReleaseGroup*

/mnt/movies/
  Movie folder, where movies are moved when they are complete. The releases are not put into any subfolders

/home/johndoe/autotorrent/
  Autotorrent installation and config file directory

/mnt/autotorrent/
  Where autotorrent can create its links.

/mnt/torrents/
  Where torrents that should be cross-seeded are stored


Torrent sites (fictional)
~~~~~~~~~~~~~~~~~~~~~~~~~

INC
  The site where releases are downloaded from, they are split into multiple .rar files and keep original naming (e.g. TV.episode.S01E01-ReleaseGroup).

IsL
  Also releases like the auto download site.

SSE
  Also releases like the auto download site but with a weird RSS feed.

Running torrent clients
~~~~~~~~~~~~~~~~~~~~~~~

Deluge
  Downloads new stuff and moves it. When the releases are complete then it can execute a command.

rtorrent A
  Used for cross seeding the torrents from IsL. SCGI runs on port 5000.

rtorrent B
  Used for cross seeding the torrents from SSE. SCGI runs on port 7554.

Getting Autotorrent running
---------------------------

Install it using `the official guide <https://github.com/JohnDoee/autotorrent#install>`_ and create a config using the *“autotorrent-env/bin/autotorrent --create_config”*. In this example Autotorrent automatically configures to connect to *“rtorrent A”*.

There is now a file called autotorrent.conf which will be used as base for all the config files needed.

Setting up Flexget
~~~~~~~~~~~~~~~~~~

First step is to install `Flexget <https://flexget.com>`_ and `Flexget Cross Seed plugin <https://github.com/JohnDoee/flexget-cross-seed/>`_ - after that, let’s make a config.yml for the cross seed job. The goal is to get Flexget to download torrents we think might match data we got locally.

`The full config.yml can be downloaded here. <./config.yml>`_

config.yml content:

.. code-block:: yml

    templates:
      cross-seed:
        seen: local
        cross-seed:
          - '/mnt/incoming/*'
          - '/mnt/movies/*'
          - '/mnt/tv/*/*/*'

    tasks:
      # Site IsL
      isl:
        rss: 'https://www.isl.example.com/rss.php'
        template: cross-seed
        download: /mnt/torrents/isl/tor/

      # Site SSE
      sse:
        rss: 'https://www.sse.example.com/rss.php'
        template: cross-seed
        download: /mnt/torrents/sse/tor/
        manipulate: # Extract name title in rss feed: Stuff 1 2 An.Item-stuff
          - title:
              extract: '(?:[^ ]+ ){3}(.+)'

What it does is check the RSS feed for entries matching what is found in the listed folders. If it matches, then it accepts them. The result is .torrent files in */mnt/torrents/isl/tor/* and */mnt/torrents/sse/tor/*


Creating a workflow
-------------------

We now have some data and a bunch of torrent files that probably matches the data. We want to get those torrents seeded.

The only data we want to seed is in */mnt/tv* and */mnt/movies* because that’s where all the complete releases are.
When running autotorrent, only one process can write to the file database at a time to avoid it from getting corrupted. Multiple processes can read from it while no rescan is ongoing.

First we need to edit *autotorrent.conf* and change disk1 and disk2 to. Only folders with completed releases should be used (i.e. no */mnt/incoming/*).


.. code-block:: ini

    disk1 = /mnt/tv
    disk2 = /mnt/movies

Secondly we need to change *store_path* to a path where autotorrent can store link and *torrent A* can access.

.. code-block:: ini

    store_path = /mnt/autotorrent/isl/

That’s where we expect torrents from the site IsL to have its links and additional data.

Now we are looking for data in the correct locations and can create links. We also need to rescan but only when there is new data. Lets build a bash script called *run-autotorrent.sh* with the full path */home/johndoe/run-autotorrent.sh*.

`The full autotorrent.conf can be downloaded here. <./autotorrent.conf>`_

.. code-block:: bash
    #!/bin/bash

    # Ensure we are in the correct folder so relative paths work
    parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
    cd "$parent_path"

    # Rescan option, only needed when we know there is new data
    # We need to prevent all database access while rescanning
    if [ $1 = "rescan" ]; then
      sleep 1 # make sure deluge finished moving data before rescanning
      flock -x ./autotorrent.lock autotorrent-env/bin/autotorrent -r # flock to prevent multiple rescans
      # ~/flexget/bin/flexget execute --tasks sse isl # It might be smart to execute flexget when we know there might be.
    fi

    if [ $1 = "flexget" ]; then
      ~/flexget/bin/flexget execute --tasks sse isl
    fi

We can now schedule a data rescan every time we have moved new data into the data folders. Since we are using deluge we can add an execution command on torrent complete using the Execute plugin. The full command would be */home/johndoe/run-autotorrent.sh rescan* .

The script isn’t finished yet and we now need an autotorrent.conf which can be used for sse.
- Copy autotorrent.conf to autotorrent-sse.conf
- Edit autotorrent-sse.conf to be able to connect to rtorrent B instead (e.g. with a different port).
- Change autotorrent-sse.conf store_path to /mnt/autotorrent/sse/ so links won’t conflict with IsL

`The full autotorrent-sse.conf can be downloaded here. <./autotorrent-sse.conf>`_

.. code-block:: bash

    # Add the actual data
    flock -s ./autotorrent.lock autotorrent-env/bin/autotorrent -a /mnt/torrents/isl/tor/*.torrent &
    flock -s ./autotorrent.lock autotorrent-env/bin/autotorrent -c autotorrent-sse.conf -a /mnt/torrents/sse/tor/*.torrent &

    # Wait for them all to finish
    wait

    # Cleanup torrent folders, there is no need to check old torrents (it will slow down autotorrent)
    find /mnt/torrents/isl/tor/*.torrent -cmin +2880 -exec mv '{}' /mnt/torrents/isl/tor-done/ \;
    find /mnt/torrents/sse/tor/*.torrent -cmin +2880 -exec mv '{}' /mnt/torrents/sse/tor-done/ \;

Now save *run-autotorrent.sh*. Make sure the script is executable and all the required folders exist by running this one-off command after saving the script.

`The full run-autotorrent.sh can be downloaded here. <./run-autotorrent.sh>`_

.. code-block:: bash

    # Make script executable
    chmod +x /home/johndoe/run-autotorrent.sh

    # Create folders
    mkdir -p /mnt/autotorrent/isl/ /mnt/torrents/isl/tor/ /mnt/torrents/isl/tor-done/
    mkdir -p /mnt/autotorrent/sse/ /mnt/torrents/sse/tor/ /mnt/torrents/sse/tor-done/

It might be smart to also just run cross-seed flexget periodically with a crontab along the lines of:

.. code-block:: crontab

    */15 * * * * /home/johndoe/run-autotorrent.sh flexget > /dev/null

Finishing up
------------

We now have a flow that can fetch new torrents and get them seeded on other sites.
It should be easy to add new sites and it can work fast if the original source is `irssi-autodl <https://github.com/autodl-community/autodl-irssi>`_
even though the cross-seed sites use RSS.