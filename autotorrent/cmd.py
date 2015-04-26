import argparse
import json
import logging
import os
import shutil

from six.moves import configparser

from autotorrent.at import AutoTorrent
from autotorrent.db import Database
from autotorrent.humanize import humanize_bytes

def commandline_handler():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", dest="config_file", default="autotorrent.conf", help="Path to config file")
    parser.add_argument("--create_config", dest="create_config_file", nargs='?', const='autotorrent.conf', default=None, help="Creates a new configuration file")
    
    parser.add_argument("-t", "--test_connection", action="store_true", dest="test_connection", default=False, help='Tests the connection to the torrent client')
    parser.add_argument("--dry-run", nargs='?', const='txt', default=None, dest="dry_run", choices=['txt', 'json'], help="Don't do any actual adding, just scan for files needed for torrents.")
    parser.add_argument("-r", "--rebuild", dest="rebuild", default=False, help='Rebuild the database', nargs='*')
    parser.add_argument("-a", "--addfile", dest="addfile", default=False, help='Add a new torrent file to client', nargs='+')
    parser.add_argument("-d", "--delete_torrents", action="store_true", dest="delete_torrents", default=False, help='Delete torrents when they are added to the client')
    parser.add_argument("--verbose", help="increase output verbosity", action="store_true", dest="verbose")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.ERROR)
    
    if args.create_config_file: # autotorrent.conf
        if os.path.exists(args.create_config_file):
            parser.error("Target %r already exists, not creating" % args.create_config_file)
        else:
            src = os.path.join(os.path.dirname(__file__), 'autotorrent.conf.dist')
            shutil.copy(src, args.create_config_file)
            print('Created configuration file %r' % args.create_config_file)
        quit()
    
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
    
    scan_mode = set(config.get('general', 'scan_mode').split(','))
    
    exact_mode = 'exact' in scan_mode
    unsplitable_mode = 'unsplitable' in scan_mode
    normal_mode = 'normal' in scan_mode

    hash_name_mode = 'hash_name' in scan_mode
    hash_size_mode = 'hash_size' in scan_mode
    hash_slow_mode = 'hash_slow' in scan_mode
    
    db = Database(config.get('general', 'db'), disks,
                  config.get('general', 'ignore_files').split(','),
                  normal_mode, unsplitable_mode, exact_mode,
                  hash_name_mode, hash_size_mode, hash_slow_mode)
    
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
    
    if isinstance(args.rebuild, list):
        if args.rebuild:
            print('Adding new folders to database')
            db.rebuild(args.rebuild)
            print('Added to database')
        else:
            print('Rebuilding database')
            db.rebuild()
            print('Database rebuilt')

    
    if args.addfile:
        dry_run = bool(args.dry_run)
        dry_run_data = []
        
        print('Found %s torrent(s)' % len(args.addfile))
        at.populate_torrents_seeded()
        for torrent in args.addfile:
            result = at.handle_torrentfile(os.path.join(current_path, torrent), dry_run)
            if dry_run:
                dry_run_data.append({
                    'torrent': torrent,
                    'found_bytes': result[0],
                    'missing_bytes': result[1],
                    'would_add': not result[2],
                    'local_files': result[3],
                })
        
        if dry_run:
            if args.dry_run == 'json':
                print(json.dumps(dry_run_data))
            elif args.dry_run == 'txt':
                for torrent in dry_run_data:
                    print('Torrent: %s' % torrent['torrent'])
                    print(' Found data: %s - Missing data: %s - Would add: %s' % (humanize_bytes(torrent['found_bytes']),
                                                                                  humanize_bytes(torrent['missing_bytes']),
                                                                                  torrent['would_add'] and 'Yes' or 'No'))
                    print(' Local files used:')
                    for f in torrent['local_files']:
                        print('  %s' % f)
                    print('')

if __name__ == '__main__':
    commandline_handler()