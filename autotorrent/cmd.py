import argparse
import json
import logging
import os
import shutil

from six.moves import configparser, input

from autotorrent.at import AutoTorrent
from autotorrent.clients import TORRENT_CLIENTS
from autotorrent.db import Database
from autotorrent.humanize import humanize_bytes

def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        print(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            print("Please respond with 'yes' or 'no' (or 'y' or 'n').\n")
        

def commandline_handler():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", dest="config_file", default="autotorrent.conf", help="Path to config file")
    parser.add_argument("-l", "--client", dest="client", default="default", help="Name of client to use (when multiple configured)")
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

        client_config = {
            'client': 'rtorrent',
            'url': 'http://user:pass@127.0.0.1/RPC2',
            'label': 'autotorrent',
        }
        
        if query_yes_no('Do you want to try and auto-configure torrent client?'):
            working_clients = []
            for client_name, cls in TORRENT_CLIENTS.items():
                obj = cls.auto_config()
                try:
                    if obj.test_connection():
                        working_clients.append(obj)
                except:
                    continue
            
            if working_clients:
                print('Found %i clients - please choose a client to use' % len(working_clients))
                for i, client in enumerate(working_clients, 1):
                    print('[%i] %s' % (i, client.identifier))
                print('[0] None of the above - do not auto-configure any client\n')
                
                while True:
                    error = False
                    try:
                        choice = int(input('> '))
                    except ValueError:
                        error = True
                    else:
                        if len(working_clients) < choice or choice < 0:
                            error = True
                    
                    if error:
                        print('Invalid choice, please choose again')
                    else:
                        if choice > 0:
                            client = working_clients[choice-1]
                            print('Setting client to %s' % client.identifier)
                            client_config = client.get_config()
                            client_config['client'] = client.identifier
                        
                        break
            else:
                print('Unable to auto-detect any clients, you will have to configure it manually.')
            
        config = configparser.ConfigParser()
        config.read(args.create_config_file)
        for k, v in client_config.items():
            config.set('client', k, v)
            
        with open(args.create_config_file, 'w') as configfile:
            config.write(configfile)
        
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
    
    client_option = 'client'
    if args.client != 'default':
        client_option += '-%s' % args.client
    
    try:
        client_name = config.get(client_option, 'client')
    except configparser.NoSectionError:
        print('It seems like %r is not a configured client' % args.client)
        quit(1)
    
    if client_name not in TORRENT_CLIENTS:
        print('Unknown client %r - Known clients are: %s' % (client_name, ', '.join(TORRENT_CLIENTS.keys())))
        quit(1)
    
    client_options = dict(config.items(client_option))
    client_options.pop('client')
    client = TORRENT_CLIENTS[client_name](**client_options)
    
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
        if not dry_run:
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
