class BaseClient(object):
    identifier = None # used to identify it in the config file

    @classmethod
    def auto_config(cls):
        """
        Tries to autoconfigure the client
        """
        raise NotImplementedError

    def get_config(self):
        """
        Gets the current configuration as a dict that can
        be used to create an entry in the .conf file.
        """
        raise NotImplementedError

    def test_connection(self):
        """
        Tests the connection to the torrent client and returns
        random information from the client.
        """
        raise NotImplementedError

    def get_torrents(self):
        """
        Returns a list of torrents currently added to the client.

        A set of ascii strings.
        """
        raise NotImplementedError

    def add_torrent(self, torrent, destination_path, file_path, files, fast_resume=True):
        """
        Adds a torrent to the torrent client.
        """
        raise NotImplementedError