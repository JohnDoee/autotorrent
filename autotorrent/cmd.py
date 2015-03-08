import argparse
import logging
import os

from six.moves import configparser

from autotorrent.at import AutoTorrent
from autotorrent.db import Database

def commandline_handler():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", dest="config_file", default="autotorrent.conf", help="Path to config file")
    
    parser.add_argument("-t", "--test_connection", action="store_true", dest="test_connection", default=False, help='Tests the connection to the torrent client')
    parser.add_argument("-r", "--rebuild", action="store_true", dest="rebuild", default=False, help='Rebuild the database')
    parser.add_argument("-a", "--addfile", dest="addfile", default=False, help='Add a new torrent file to client', nargs='+')
    parser.add_argument("-d", "--delete_torrents", action="store_true", dest="delete_torrents", default=False, help='Delete torrents when they are added to the client')
    parser.add_argument("--verbose", help="increase output verbosity", action="store_true", dest="verbose")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR)
    
    if not os.path.isfile(args.config_file):
        parser.error("Config file not found %r" % args.config_file)
    
    config = configparser.ConfigParser()
    config.read(args.config_file)
    
    current_path = os.getcwd()
    os.chdir(os.path.dirname(os.path.abspath(args.config_file))) # Changing directory to where the config file is.
    
    if not config.has_section('general'):
        parser.error('AutoTorrent is not properly configured, please edit %r' % args.config_file)
        quit(1)

    i = 1
    disks = []
    while config.has_option('disks', 'disk%s' % i):
        disks.append(config.get('disks', 'disk%s' % i))
        i += 1
    
    normal_mode = False
    unsplitable_mode = False
    exact_mode = False
    scan_mode = set(config.get('general', 'scan_mode').split(','))
    
    if 'exact' in scan_mode:
        exact_mode = True
    
    if 'unsplitable' in scan_mode:
        unsplitable_mode = True
    
    if 'normal' in scan_mode:
        normal_mode = True
    
    db = Database(config.get('general', 'db'), disks,
                  config.get('general', 'ignore_files').split(','),
                  normal_mode, unsplitable_mode, exact_mode)
    
    client_name = config.get('client', 'client')
    if client_name == 'rtorrent':
        from autotorrent.clients.rtorrent import RTorrentClient
        client = RTorrentClient(config.get('client', 'url'),
                                config.get('client', 'label'))
    elif client_name == 'deluge':
        from autotorrent.clients.deluge import DelugeClient
        host, port = config.get('client', 'host').split(':')
        client = DelugeClient(host, int(port),
                              config.get('client', 'username'),
                              config.get('client', 'password'))
    elif client_name == 'transmission':
        from autotorrent.clients.transmission import TransmissionClient
        client = TransmissionClient(config.get('client', 'url'))
    else:
        print('Unknown client %r' % client_name)
        quit(1)
    
    at = AutoTorrent(
        db,
        client,
        config.get('general', 'store_path'),
        config.getint('general', 'add_limit_size'),
        config.getfloat('general', 'add_limit_percent'),
        args.delete_torrents,
        (config.get('general', 'link_type') if config.has_option('general', 'link_type') else 'soft'),
    )
    
    if args.test_connection:
        proxy_test_result = client.test_connection()
        if proxy_test_result:
            print('Connected to torrent client successfully!')
            print('  result: %s' % proxy_test_result)
    
    if args.rebuild:
        print('Rebuilding database')
        db.rebuild()
        print('Database rebuilt')

    if args.addfile:
        print('Found %s torrent(s)' % len(args.addfile))
        at.populate_torrents_seeded()
        for torrent in args.addfile:
            at.handle_torrentfile(os.path.join(current_path, torrent))

if __name__ == '__main__':
    commandline_handler()