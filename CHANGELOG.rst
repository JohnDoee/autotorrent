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