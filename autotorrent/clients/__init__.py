import logging

logger = logging.getLogger(__name__)

TORRENT_CLIENTS = {}

try:
    from .rtorrent import RTorrentClient
    TORRENT_CLIENTS[RTorrentClient.identifier] = RTorrentClient
    
    logger.debug('Enabled client %s' % RTorrentClient.identifier)
except ImportError:
    logger.debug('Failed to enable client rtorrent')

try:
    from .deluge import DelugeClient
    TORRENT_CLIENTS[DelugeClient.identifier] = DelugeClient
    
    logger.debug('Enabled client %s' % DelugeClient.identifier)
except ImportError:
    logger.debug('Failed to enable client deluge')

try:
    from .transmission import TransmissionClient
    TORRENT_CLIENTS[TransmissionClient.identifier] = TransmissionClient
    
    logger.debug('Enabled client %s' % TransmissionClient.identifier)
except ImportError:
    logger.debug('Failed to enable client transmission')