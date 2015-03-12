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

from io import BytesIO

from six.moves.xmlrpc_client import Transport

def encode_netstring(input):
    return str(len(input)).encode() + b':' + input + b','

def encode_header(key, value):
    return key + b'\x00' + value + b'\x00'

class SCGITransport(Transport):
    def __init__(self, *args, **kwargs):
        self.socket_path = kwargs.pop('socket_path', '')
        Transport.__init__(self, *args, **kwargs)
    
    def single_request(self, host, handler, request_body, verbose=False):
        self.verbose = verbose
        if self.socket_path:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(self.socket_path)
        else:
            host, port = host.split(':')
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, int(port)))

        request = encode_header(b'CONTENT_LENGTH', str(len(request_body)).encode())
        request += encode_header(b'SCGI', b'1')
        request += encode_header(b'REQUEST_METHOD', b'POST')
        request += encode_header(b'REQUEST_URI', handler.encode())

        request = encode_netstring(request)
        request += request_body

        s.send(request)

        response = b''
        while True:
            r = s.recv(1024)
            if not r:
                break
            response += r

        response_body = BytesIO(b'\r\n\r\n'.join(response.split(b'\r\n\r\n')[1:]))

        return self.parse_response(response_body)

if not hasattr(Transport, 'single_request'):
    SCGITransport.request = SCGITransport.single_request
