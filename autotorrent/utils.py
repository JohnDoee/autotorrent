import os
import re

__all__ = [
    'is_unsplitable',
    'get_root_of_unsplitable',
]

UNSPLITABLE_FILE_EXTENSIONS = [
    set(['.rar', '.sfv']),
    set(['.mp3', '.sfv']),
    set(['.vob', '.ifo']),
]

def is_unsplitable(files):
    """
    Checks if a list of files can be considered unsplitable, e.g. VOB/IFO or scene release.
    This means the files can only be used in this combination.
    """
    extensions = set(os.path.splitext(f)[1].lower() for f in files)
    found_unsplitable_extensions = False
    for exts in UNSPLITABLE_FILE_EXTENSIONS:
        if len(extensions & exts) == len(exts):
            found_unsplitable_extensions = True
            break
    
    lowercased_files = set([f.lower() for f in files])
    found_magic_file = False
    if 'movieobject.bdmv' in lowercased_files:
        found_magic_file = True
    
    return found_unsplitable_extensions or found_magic_file

def get_root_of_unsplitable(path):
    """
    Scans a path for the actual scene release name, e.g. skipping cd1 folders.
    
    Returns None if no scene folder could be found
    """
    path = path[::-1]
    for p in path:
        if not p:
            continue
        
        if re.match(r'^(cd[1-9])|(samples?)|(proofs?)|((vob)?sub(title)?s?)$', p, re.IGNORECASE): # scene paths
            continue
        
        if re.match(r'^(bdmv)|(disc\d*)|(video_ts)$', p, re.IGNORECASE): # bluray / dd
            continue
        
        
        return p