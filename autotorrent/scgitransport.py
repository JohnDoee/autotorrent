"""SCGI XMLRPC Transport.

XMLRPC in Python only supports HTTP(S). This module extends the transport to also support SCGI.

SCGI is required by rTorrent if you want to communicate directly with an instance.

Example:
  Small usage example

  literal blocks::
    from xmlrpc.client import ServerProxy

    proxy = ServerProxy('http://127.0.0.1:8000/', transport=SCGITransport())
    proxy.system.listMethods()

License:
    Public Domain (no attribution needed).
    The license only applies to THIS file.
"""

import socket
import urllib

from io import BytesIO
from xmlrpclib import Transport

def encode_netstring(input):
    return str(len(input)) + ':' + input + ','

def encode_header(key, value):
    return key + '\x00' + value + '\x00'

class SCGITransport(Transport):
    def single_request(self, host, handler, request_body, verbose=False):
        self.verbose = verbose
        host, port = urllib.splitport(host)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, int(port)))

        request = encode_header('CONTENT_LENGTH', str(len(request_body)))
        request += encode_header('SCGI', '1')
        request += encode_header('REQUEST_METHOD', 'POST')
        request += encode_header('REQUEST_URI', handler)

        request = encode_netstring(request)
        request += request_body

        s.send(request)

        response = ''
        while True:
            r = s.recv(1024)
            if not r:
                break
            response += r

        response_body = BytesIO('\r\n\r\n'.join(response.split('\r\n\r\n')[1:]))

        return self.parse_response(response_body)