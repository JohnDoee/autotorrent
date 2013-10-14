import ConfigParser
from optparse import OptionParser

from autotorrent.at import AutoTorrent

def commandline_handler():
    config = ConfigParser.ConfigParser()
    config.read('autotorrent.conf')

    at = AutoTorrent(config)
    at.populate_torrents_seeded()

    parser = OptionParser()
    parser.add_option("-r", "--rebuild", action="store_true", dest="rebuild", default=False, help='Rebuild the database')
    parser.add_option("-a", "--addfile", action="store_true", dest="addfile", default=False, help='Add a new torrent file to client')
    parser.add_option("-v", "--verify", action="store_true", dest="verify", default=False, help='Verify currently added torrents')
    (options, args) = parser.parse_args()

    if options.rebuild:
        at.rebuild_database()

    if options.addfile:
        for arg in args:
            at.handle_torrentfile(arg)

    if options.verify:
        at.verify_all()

if __name__ == '__main__':
    commandline_handler()