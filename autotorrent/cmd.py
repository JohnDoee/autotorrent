import argparse
import ConfigParser
import logging
import os

from autotorrent.at import AutoTorrent

def commandline_handler():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", dest="config_file", default="autotorrent.conf", help="Path to config file")
    
    parser.add_argument("-t", "--test_rtorrent", action="store_true", dest="test_rtorrent", default=False, help='Tests the connection to rTorrent')
    parser.add_argument("-r", "--rebuild", action="store_true", dest="rebuild", default=False, help='Rebuild the database')
    parser.add_argument("-a", "--addfile", dest="addfile", default=False, help='Add a new torrent file to client', nargs='+')
    parser.add_argument("-v", "--verify", action="store_true", dest="verify", default=False, help='Verify currently added torrents')
    parser.add_argument("--verbose", help="increase output verbosity", action="store_true", dest="verbose")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR)
    
    if not os.path.isfile(args.config_file):
        parser.error("Config file not found %r" % args.config_file)
    
    config = ConfigParser.ConfigParser()
    config.read(args.config_file)
    
    if not config.has_section('general'):
        parser.error('AutoTorrent is not properly configured, please edit %r' % args.config_file)
        quit(1)

    i = 1
    disks = []
    while config.has_option('disks', 'disk%s' % i):
        disks.append(config.get('disks', 'disk%s' % i))
        i += 1

    at = AutoTorrent(
        config.get('general', 'db'),
        config.get('general', 'ignore_files').split(','),
        config.get('general', 'store_path'),
        config.get('general', 'rtorrent_url'),
        config.getint('general', 'add_limit_size'),
        config.getfloat('general', 'add_limit_percent'),
        disks,
        (config.get('general', 'label') if config.has_option('general', 'label') else None),
        (config.get('general', 'link_type') if config.has_option('general', 'link_type') else 'soft'),
    )
    
    if args.test_rtorrent:
        proxy_test_result = at.test_proxy()
        if proxy_test_result:
            print 'Connected to rTorrent successfully!'
            print '  cwd:%r, pid:%r' % proxy_test_result
    
    at.populate_torrents_seeded()

    if args.rebuild:
        at.rebuild_database()

    if args.addfile:
        for torrent in args.addfile:
            at.handle_torrentfile(torrent)

    if args.verify:
        at.verify_all()

if __name__ == '__main__':
    commandline_handler()