from __future__ import division

import hashlib
import logging
import os
import re

__all__ = [
    'is_unsplitable',
    'get_root_of_unsplitable',
    'Pieces',
]

UNSPLITABLE_FILE_EXTENSIONS = [
    set(['.rar', '.sfv']),
    set(['.mp3', '.sfv']),
    set(['.vob', '.ifo']),
]

logger = logging.getLogger(__name__)

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

class Pieces(object):
    """
    Can help check if files match the files found in a torrent.
    """
    
    def __init__(self, torrent):
        self.piece_size = torrent[b'info'][b'piece length']
        self.pieces = []
        for i in range(0, len(torrent[b'info'][b'pieces']), 20):
            self.pieces.append(torrent[b'info'][b'pieces'][i:i+20])
    
    def get_complete_pieces(self, start_size, end_size):
        """
        Finds complete pieces and returns the alignment needed from
        the beginning and the end (to match the file).
        """
        logger.debug('Getting complete pieces for file starting at %i and ending at %i. Piece size is %i' % (start_size, end_size, self.piece_size))
        
        start_piece, start_offset = divmod(start_size, self.piece_size)
        if start_offset:
            start_piece += 1
        
        if start_offset:
            start_offset = self.piece_size - start_offset
        
        end_piece, end_offset = divmod(end_size, self.piece_size)

        logger.debug('Start piece:%i end piece:%i' % (start_piece, end_piece-1))
        return start_offset, end_offset, self.pieces[start_piece:end_piece]
    
    def find_piece_breakpoint(self, file_path, start_size, end_size):
        """
        Finds the point where a file with a different size is modified and tries to align it with pieces.
        """
        start_offset, end_offset, pieces = self.get_complete_pieces(start_size, end_size)
        
        failed_pieces = (len(pieces) // 20) or 1 # number of pieces that can fail in a row and then put an end to checking
        success_count = failed_pieces
        piece_status = []
        
        with open(file_path, 'rb') as f:
            f.seek(start_offset)
            for i, piece in enumerate(pieces):
                logger.debug('Checking piece %i for breakingpoint' % (i, ))
                h = hashlib.sha1(f.read(self.piece_size)).digest()
                if h == piece:
                    logger.debug('Piece %i matched' % i)
                    if success_count < failed_pieces:
                        success_count += 1
                    piece_status.append(True)
                else:
                    logger.debug('Piece %i did not match' % i)
                    success_count -= 1
                    piece_status.append(False)
                
                if success_count <= 0:
                    logger.debug('The breakingpoint has been found after piece %i - more than %i failed pieces' % (i, failed_pieces))
                    break
        
        for p in piece_status[::-1]:
            if p:
                break
            i -= 1
        
        breakingpoint = start_offset + self.piece_size*i
        logger.debug('A total of %i pieces were ok, so we set breakingpoint at %i' % (i, breakingpoint))
        return breakingpoint

    def match_file(self, file_path, start_size, end_size):
        """
        Try to match file starting at start_size and ending at end_size.
        """
        start_offset, end_offset, pieces = self.get_complete_pieces(start_size, end_size)
        logger.debug('Stuff to check start_offset:%i end_offset:%i pieces:%s' % (start_offset, end_offset, len(pieces)))
        if not pieces:
            logger.debug('No whole pieces found for %r, taking this as a not-match' % file_path)
            return False, False
        
        check_pieces = (len(pieces) // 10) or 1
        
        match_start, match_end = 0, 0
        size = os.path.getsize(file_path)
        with open(file_path, 'rb') as f:
            for i in range(check_pieces): # check from beginning
                seek_offset = start_offset+self.piece_size*i
                logger.debug('Checking piece %i from beginning of file, reading from %i bytes. Filesize: %i' % (i, seek_offset, size))
                f.seek(seek_offset)
                h = hashlib.sha1(f.read(self.piece_size)).digest()
                logger.debug('Matching hash %r against %r' % (h, pieces[i]))
                if h == pieces[i]:
                    logger.debug('Piece %i matched' % i)
                    match_start += 1
                else:
                    logger.debug('Piece %i did not match' % i)
            
            for i in range(check_pieces): # check from end
                seek_offset = size-end_offset-self.piece_size*(i+1)
                logger.debug('Checking piece %i from end of file, reading from %i bytes. Filesize: %i' % (i, seek_offset, size))
                f.seek(seek_offset)
                h = hashlib.sha1(f.read(self.piece_size)).digest()
                piece = pieces[(i+1)*-1]
                logger.debug('Matching hash %r against %r' % (h, piece))
                if h == piece:
                    logger.debug('Piece %i matched' % i)
                    match_end += 1
                else:
                    logger.debug('Piece %i did not match' % i)
        
        logger.debug('Checked %i pieces from both start and end. %i matched from start and %i matched from end.' % (check_pieces, match_start, match_end))
        
        if check_pieces < 4:
            must_match = 1
        elif check_pieces < 10:
            must_match = 2
        else:
            must_match = max(check_pieces // 10, 3)
        
        return (match_start and check_pieces - match_start <= must_match,
                match_end and check_pieces - match_end <= must_match)
