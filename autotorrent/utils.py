import os
import re

__all__ = [
    'is_scene_modeable',
    'get_actual_scene_name',
]

SCENE_FILE_EXTENSIONS = set([
    '.rar',
    '.mp3',
])

def is_scene_modeable(files):
    """
    Checks if a list of files can be considered scene stuff
    """
    extensions = set(os.path.splitext(f)[1].lower() for f in files)
    return '.sfv' in extensions and SCENE_FILE_EXTENSIONS & extensions

def get_actual_scene_name(path):
    """
    Scans a path for the actual scene release name, e.g. skipping cd1 folders.
    
    Returns None if no scene folder could be found
    """
    path = path[::-1]
    for p in path:
        if not p:
            continue
        
        if re.match('^cd[1-9]$', p, re.IGNORECASE):
            continue
        
        if re.match('^samples?$', p, re.IGNORECASE):
            continue
        
        if re.match('^proofs?$', p, re.IGNORECASE):
            continue
        
        if re.match('^(vob)?sub(title)?s?$', p, re.IGNORECASE):
            continue
        
        return p