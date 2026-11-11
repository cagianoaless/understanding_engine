"""Loopback-only PDF inspection. Explicit verified inputs; no parsing/inference API."""

import argparse
from collections import OrderedDict
from copy import deepcopy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import struct
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pypdfium2 as pdfium

from .contracts import ExtractionError, json_bytes
from .hybrid import _docling_geometry
from .selection import SelectionIndex
from .viewer_coordinates import browser_to_pdf, require
from .viewer_assets import ASSETS

MAX_BODY = 16384
MAX_RESPONSE = 4*1024**2
RENDER_SCALE = 1.5


def verified_bytes(path, expected, maximum):
    require(isinstance(expected, dict) and set(expected) == {"bytes", "sha256"}, "Invalid input manifest")
    require(type(expected["bytes"]) is int and 0 < expected["bytes"] <= maximum and
            isinstance(expected["sha256"], str) and re.fullmatch('[a-f0-9]{64}', expected["sha256"]), "Invalid input identity")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size == expected['bytes'], "Input type/length differs")
        payload = stream.read(maximum+1)
    require(len(payload) == expected['bytes'] and hashlib.sha256(payload).hexdigest() == expected['sha256'], "Input SHA256 differs")
    return payload


def _float32(value):
    return struct.unpack('f', struct.pack('f', value))[0]


def _renderer_geometry(page, geometry):
    _docling_geometry(geometry, {k: geometry[k] for k in ['width', 'height']})
    require(page.get_rotation() == 0, "Renderer rotation differs")
    def same(actual, original):
        return actual is not None and list(actual) in [list(original), [_float32(v) for v in original]]
    require(same(page.get_size(), [geometry['width'], geometry['height']]), "Renderer page size differs")
    for name in ['mediabox', 'cropbox', 'bbox']:
        require(same(getattr(page, 'get_'+name)(), geometry[name]), "Renderer "+name+" differs")


class DocumentContext:
    """One immutable verified document and SelectionIndex, initialized off-request."""

    def __init__(self, pdf, extraction, hybrid, manifest, initial_page=6):
        self.paths = (Path(pdf), Path(extraction), Path(hybrid))
        self.manifest = deepcopy(manifest)
        self.initial_page = initial_page
        self.state = 'loading'; self.phase = 'Verifying local input identities'; self.error = None
        self._lock = threading.RLock()
        self._images = OrderedDict()
        self._thread = None
        self._pdf = None

    def start(self):
        require(self._thread is None, "Context already started")
        self._thread = threading.Thread(target=self._load, name='viewer-initialization', daemon=True)
        self._thread.start()

    def _load(self):
        try:
            require(set(self.manifest) == {'schema_version','pdf','extraction','hybrid'} and
                    self.manifest['schema_version'] == 'local-viewer-inputs.1', "Unknown input manifest")
            pdf_bytes = verified_bytes(self.paths[0], self.manifest['pdf'], 64*1024**2)
            source_bytes = verified_bytes(self.paths[1], self.manifest['extraction'], 128*1024**2)
            hybrid_bytes = verified_bytes(self.paths[2], self.manifest['hybrid'], 128*1024**2)
            self.phase = 'Reading verified evidence once'
            source, hybrid = json.loads(source_bytes), json.loads(hybrid_bytes)
            require(source['source_sha256'] == self.manifest['pdf']['sha256'], "PDF/extraction identity differs")
            self.phase = 'Validating source and structural evidence once'
            index = SelectionIndex(hybrid, source, expected_pdf_sha256=self.manifest['pdf']['sha256'])
            pdf = pdfium.PdfDocument(pdf_bytes)
            self._pdf = pdf
            require(len(pdf) == source['page_count'], "PDF page count differs")
            require(type(self.initial_page) is int and 1 <= self.initial_page <= len(pdf), "Invalid initial page")
            pages = []
            for p in source['pages']:
                try:
                    _docling_geometry(p['geometry'], {k:p['geometry'][k] for k in ['width','height']})
                    supported = True
                except ExtractionError:
                    supported = False
                pages.append({'page_number':p['page_number'], 'source_only':p['page_number'] in hybrid['source_only_pages'],
                              'spatial_supported':supported})
            self.source, self.hybrid, self.index = source, hybrid, index
            self.page_infos = pages
            self.phase = 'Ready'; self.state = 'ready'
        except Exception as exc:
            self.error = 'Input identity, contract or renderer validation failed; check the local run log.'
            print('Viewer initialization failed: '+type(exc).__name__+': '+str(exc), file=sys.stderr, flush=True)
            self.state = 'failed'; self.phase = 'Initialization failed'

    def status(self):
        result = {'state':self.state,'phase':self.phase,'error':self.error}
        if self.state == 'ready':
            result.update(pdf_sha256=self.manifest['pdf']['sha256'], source_canonical_sha256=self.hybrid['source_canonical_sha256'],
                          page_count=len(self.page_infos), initial_page=self.initial_page, pages=self.page_infos)
        return result

    def _ready(self):
        require(self.state == 'ready', "Document is not ready")

    def _page(self, number):
        self._ready()
        require(type(number) is int and 1 <= number <= len(self.page_infos), "Unknown page")
        return self.source['pages'][number-1]

    def rendered(self, number):
        with self._lock:
            original = self._page(number)
            if number not in self._images:
                page = self._pdf[number-1]
                try:
                    _renderer_geometry(page, original['geometry'])
                    w, h = page.get_size()
                    require(math.ceil(w*RENDER_SCALE)*math.ceil(h*RENDER_SCALE) <= 8_000_000, "Render pixel limit exceeded")
                    bitmap = page.render(scale=RENDER_SCALE, may_draw_forms=False, draw_annots=False)
                    try:
                        image = bitmap.to_pil()
                        try:
                            output = io.BytesIO(); image.save(output, format='PNG'); png = output.getvalue()
                            size = list(image.size)
                        finally:
                            image.close()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
                meta = {'pdf_sha256':self.manifest['pdf']['sha256'], 'source_canonical_sha256':self.hybrid['source_canonical_sha256'],
                        'page_number':number, 'geometry':original['geometry'], 'source_only':number in self.hybrid['source_only_pages'],
                        'render':{'width':size[0], 'height':size[1], 'sha256':hashlib.sha256(png).hexdigest(),
                                  'scale':RENDER_SCALE, 'format':'image/png',
                                  'geometry_verification':'exact_original_or_IEEE_float32_backend_representation'}}
                self._images[number] = (meta, png)
                while len(self._images) > 2:
                    self._images.popitem(last=False)
            self._images.move_to_end(number)
            return self._images[number]

    def selection(self, data, click=False):
        with self._lock:
            self._ready()
            keys = {'pdf_sha256','source_canonical_sha256'} | ({'page_number','render_sha256','image_pixels','display_rect','pointer'} if click else {'query'})
            require(isinstance(data, dict) and set(data) == keys, "Unexpected request fields")
            require(data['pdf_sha256'] == self.manifest['pdf']['sha256'] and
                    data['source_canonical_sha256'] == self.hybrid['source_canonical_sha256'], "Stale/wrong source identity")
            if click:
                meta, _ = self.rendered(data['page_number'])
                require(data['render_sha256'] == meta['render']['sha256'] and
                        data['image_pixels'] == [meta['render']['width'],meta['render']['height']], "Stale/wrong rendered image")
                point = browser_to_pdf(meta['geometry'], data['image_pixels'], data['display_rect'], data['pointer'])
                return self.index.at_point(data['page_number'], point, coordinate_system='pdfplumber-native-v1')
            return self.index.select(data['query'])

    def close(self):
        if self._thread:
            self._thread.join()
        with self._lock:
            if self._pdf is not None:
                self._pdf.close(); self._pdf = None


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, context, port=0):
        require(type(port) is int and 0 <= port <= 65535, "Invalid port")
        self.context = context
        self.token = secrets.token_hex(32)
        self._slots = threading.BoundedSemaphore(16)
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = 'http://127.0.0.1:'+str(self.server_address[1])

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request); return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release(); raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version = 'UnderstandingEngineViewer/0.1'

    def setup(self):
        super().setup(); self.connection.settimeout(5)

    def log_message(self, *args):
        pass  # No tokens, paths, selections or PDF contents in access logs.

    def _send(self, status, body, mime='application/json'):
        self.send_response(status)
        headers = {'Content-Type':mime, 'Content-Length':str(len(body)), 'Cache-Control':'no-store',
            'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer',
            'Cross-Origin-Resource-Policy':'same-origin',
            'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; object-src 'none'"}
        for key,value in headers.items():self.send_header(key,value)
        self.end_headers()
        if self.command != 'HEAD':self.wfile.write(body)

    def _error(self, code, message):
        self._send(code, json_bytes({'error':message}))

    def _guard(self):
        if len(self.headers.get_all('Host',[])) != 1 or self.headers.get('Host') != self.server.origin.removeprefix('http://'):
            self._error(403,'Invalid Host'); return False
        if self.headers.get('Origin') not in (None,self.server.origin) or self.headers.get('Sec-Fetch-Site') in {'cross-site','same-site'}:
            self._error(403,'Cross-origin request denied'); return False
        if len(self.path) > 1024 or urlsplit(self.path).query:
            self._error(404,'Unknown route'); return False
        return True

    def _authorized(self):
        header = self.headers.get('Authorization','')
        if not header.isascii() or len(self.headers.get_all('Authorization',[])) != 1 or not secrets.compare_digest(header, 'Bearer '+self.server.token):
            self._error(403,'Session authorization required'); return False
        return True

    def do_GET(self):
        if not self._guard():return
        if self.path in ASSETS:
            mime,body=ASSETS[self.path]; self._send(200,body,mime); return
        if not self._authorized():return
        if self.path == '/api/status':
            self._send(200,json_bytes(self.server.context.status())); return
        if self.server.context.state != 'ready':
            self._error(409,'Document is loading or failed'); return
        match=re.fullmatch(r'/api/page/([1-9][0-9]{0,4})(/image)?',self.path)
        if not match:
            self._error(404,'Unknown route'); return
        try:
            meta,png=self.server.context.rendered(int(match[1]))
            self._send(200,png,'image/png') if match[2] else self._send(200,json_bytes(meta))
        except (ExtractionError,ValueError):self._error(400,'Unsupported page or geometry')
        except Exception:self._error(500,'Local page rendering failed')

    do_HEAD = do_GET

    def do_POST(self):
        if not self._guard() or not self._authorized():return
        if self.headers.get('Origin') != self.server.origin:
            self._error(403,'Same-origin POST required'); return
        if self.path not in {'/api/select','/api/click'}:
            self._error(404,'Unknown route'); return
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length',[])) != 1 or self.headers.get('Content-Type','').split(';')[0] != 'application/json':
            self._error(400,'Bounded application/json required'); return
        try:
            length=int(self.headers.get('Content-Length','-1'))
            if not 0 < length <= MAX_BODY:
                self._error(413,'Request exceeds local viewer limit'); return
            if self.server.context.state != 'ready':
                self._error(409,'Document is loading or failed'); return
            data=json.loads(self.rfile.read(length))
            result=self.server.context.selection(data,click=self.path=='/api/click')
            payload=json_bytes(result)
            if len(payload)>MAX_RESPONSE:
                self._error(413,'Selection exceeds 4 MiB; use a smaller selection. Nothing was truncated.'); return
            self._send(200,payload)
        except (ExtractionError,ValueError,TypeError,KeyError):self._error(400,'Invalid coordinates, selection or source identity')
        except Exception:self._error(500,'Local selection failed')

    def _unsupported(self):self._error(405,'Read-only viewer method not supported')
    do_OPTIONS = do_PUT = do_DELETE = do_PATCH = do_TRACE = do_CONNECT = _unsupported


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['pdf','extraction','hybrid','manifest']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--page',type=int,default=6); parser.add_argument('--port',type=int,default=0)
    args=parser.parse_args()
    require(args.manifest.is_file() and args.manifest.stat().st_size < 16384,'Invalid local manifest')
    context=DocumentContext(args.pdf,args.extraction,args.hybrid,json.loads(args.manifest.read_text()),args.page)
    server=LocalServer(context,args.port); context.start()
    print('Open locally: '+server.origin+'/#token='+server.token,flush=True)
    try:server.serve_forever(poll_interval=.2)
    except KeyboardInterrupt:pass
    finally:server.server_close(); context.close()


if __name__=='__main__':main()
