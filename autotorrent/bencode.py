# The contents of this file are subject to the BitTorrent Open Source License
# Version 1.1 (the License).  You may not copy or use this file, in either
# source code or executable form, except in compliance with the License.  You
# may obtain a copy of the License at http://www.bittorrent.com/license/.
#
# Software distributed under the License is distributed on an AS IS basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied.  See the License
# for the specific language governing rights and limitations under the
# License.

# Written by Petru Paler
# Modified to have Python 3 support by Anders Jensen

import six

class BTFailure(Exception):
    pass

def decode_int(x, f):
    f += 1
    newf = x.find(b'e', f)
    n = int(x[f:newf])
    if six.indexbytes(x, f) == 45:
        if six.indexbytes(x, f+1) == 48:
            raise ValueError
    elif six.indexbytes(x, f) == 48 and newf != f+1:
        raise ValueError
    return (n, newf+1)

def decode_string(x, f):
    colon = x.find(b':', f)
    n = int(x[f:colon])
    if six.indexbytes(x, f) == 48 and colon != f+1:
        raise ValueError
    colon += 1
    return (x[colon:colon+n], colon+n)

def decode_list(x, f):
    r, f = [], f+1
    while six.indexbytes(x, f) != 101:
        v, f = decode_func[six.indexbytes(x, f)](x, f)
        r.append(v)
    return (r, f + 1)

def decode_dict(x, f):
    r, f = {}, f+1
    while six.indexbytes(x, f) != 101:
        k, f = decode_string(x, f)
        r[k], f = decode_func[six.indexbytes(x, f)](x, f)
    return (r, f + 1)

decode_func = {}
decode_func[108] = decode_list
decode_func[100] = decode_dict
decode_func[105] = decode_int

for i in range(48, 59):
    decode_func[i] = decode_string

def bdecode(x):
    try:
        r, l = decode_func[six.indexbytes(x, 0)](x, 0)
    except (IndexError, KeyError, ValueError):
        raise
        raise BTFailure("not a valid bencoded string")
    if l != len(x):
        raise BTFailure("invalid bencoded value (data after valid prefix)")
    return r


class Bencached(object):
    __slots__ = ['bencoded']

    def __init__(self, s):
        self.bencoded = s

def encode_bencached(x,r):
    r.append(x.bencoded)

def encode_int(x, r):
    r.extend((b'i', str(x).encode(), b'e'))

def encode_bool(x, r):
    if x:
        encode_int(1, r)
    else:
        encode_int(0, r)

def encode_string(x, r):
    r.extend((str(len(x)).encode(), b':', x))

def encode_list(x, r):
    r.append(b'l')
    for i in x:
        encode_func[type(i)](i, r)
    r.append(b'e')

def encode_dict(x,r):
    r.append(b'd')
    for k, v in sorted(x.items()):
        r.extend((str(len(k)).encode(), b':', k))
        encode_func[type(v)](v, r)
    r.append(b'e')

encode_func = {}
encode_func[Bencached] = encode_bencached
encode_func[int] = encode_int
if six.PY2:
    encode_func[long] = encode_int
encode_func[str] = encode_string
encode_func[bytes] = encode_string
encode_func[list] = encode_list
encode_func[tuple] = encode_list
encode_func[dict] = encode_dict

try:
    from types import BooleanType
    encode_func[BooleanType] = encode_bool
except ImportError:
    pass

def bencode(x):
    r = []
    encode_func[type(x)](x, r)
    return b''.join(r)
