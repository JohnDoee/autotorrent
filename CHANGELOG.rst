Version 1.6.1 (11-05-2016)
===========================================================

*   Feature: Can now try and auto-detect local torrent clients
*   Feature: Now possible to have multiple clients configured
*   Bugfix: Fixed small bugs with Deluge client
*   Bugfix: Dry run tried to connect to the client
*   Bugfix: Encoding problems with transmission and Python 3

Version 1.6.0 (30-04-2015)
===========================================================

*   Feature: Added a new range of scan modes that uses hash
    instead of just filename or size to figure out the correct file
*   Feature: Added support for dry-run with both text and
    json output format
*   Feature: Added support for scanning a single path
*   Feature: Added commandline option to create base configuration
    file.
*   Bugfix: Trying to make sure torrent is added to rtorrent before
    deleting it.

Version 1.5.2 (19-03-2015)
===========================================================

*   Bugfix: Fixed typo in a previous utf-8 bugfix
*   Bugfix: Fixed small priority bug with rtorrent.

Version 1.5.1 (08-03-2015)
===========================================================

*   Bugfix: Readme was not updated properly
*   Bugfix: Some Python 2.6 tests failed

Version 1.5.0 (08-03-2015)
===========================================================

*   Feature: Added a new mode called "exact" where items
    are not linked, but the client is pointed to the exact
    matched folder. This feature is meant to facilitate client
    change.
*   Feature: Added support for Deluge
*   Change: Configuration file changed to fit the new
    multi-client format
*   Change: Renamed scene mode to unsplitable mode and added
    support for bluray (m2ts) and dvd (ifo/vob)
*   Change: unsplitable mode now relies more on path to find the
    correct file


Version 1.4.0 (22-02-2015)
===========================================================

*   Change: Changed how the add_limits work, if either of them are
    violated, the torrent is skipped.
*   Change: Added "scene_mode" that allows to easily cross-seed
    scene releases. This is a new option in the config file.

Version 1.3.1 (20-02-2015)
===========================================================

*   Bugfix: Wrong license in setup.py.
*   Bugfix: Forgot to populate already seeded torrents.
*   Bugfix: Added logging to db scanning and fixed a small bug.

Version 1.3.0 (19-02-2015)
===========================================================

*   Feature: Added support for deleting torrent when added
    to the client.
*   Bugfix: Fixed SCGI bug with Python 2.6.
*   Change: The paths in the configuration file are relative
    to the folder the configuration file is in.
*   Change: Restructured project.
*   Feature: added Python 3 support.
*   Bugfix: Test cases covering the project and Travis CI.
*   Change: Verify command removed for now due to the restructured
    folder system.
*   Change: To prepare for multi-client support, configuration file
    has been restructured.
