#!/bin/bash

# Ensure we are in the correct folder so relative paths work
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$parent_path"

# flexget command to fetch torrents from cross-seed target sites
# Remember to change the site names to your own!
flexget_command="~/flexget/bin/flexget execute --tasks sse isl"

# Rescan option, only needed when we know there is new data
# We need to prevent all database access while rescanning
if [ "$1" = "rescan" ]; then
    sleep 1 # make sure deluge finished moving data before rescanning
    flock -x ./autotorrent.lock autotorrent-env/bin/autotorrent -r # flock to prevent multiple rescans
    eval $flexget_command # It might be smart to execute flexget when we know there might be.
fi

if [ "$1" = "flexget" ]; then
    eval $flexget_command
fi

# Add the actual data
flock -s ./autotorrent.lock autotorrent-env/bin/autotorrent -a /mnt/torrents/isl/tor/*.torrent &
flock -s ./autotorrent.lock autotorrent-env/bin/autotorrent -c autotorrent-sse.conf -a /mnt/torrents/sse/tor/*.torrent &

# Wait for them all to finish
wait

# Cleanup torrent folders, there is no need to check old torrents (it will slow down autotorrent)
find /mnt/torrents/isl/tor/*.torrent -cmin +2880 -exec mv '{}' /mnt/torrents/isl/tor-done/ \;
find /mnt/torrents/sse/tor/*.torrent -cmin +2880 -exec mv '{}' /mnt/torrents/sse/tor-done/ \;