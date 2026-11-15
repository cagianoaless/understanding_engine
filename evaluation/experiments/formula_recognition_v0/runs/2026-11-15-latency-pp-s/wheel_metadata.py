"""Bounded official wheel ZIP metadata inspection, without package acquisition."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import struct
import urllib.parse
import urllib.request
from html.parser import HTMLParser


def official_links(html):
    """Vendor index uses unquoted hrefs; do not mistake regex misses for absence."""
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.links=[]
        def handle_starttag(self,tag,attrs):
            if tag=='a':
                for key,value in attrs:
                    if key=='href' and value:self.links.append(value)
    parser=Links();parser.feed(html);return parser.links


def read_range(url,start,end,total):
    p=urllib.parse.urlsplit(url)
    if p.scheme!='https' or p.hostname not in {'files.pythonhosted.org','paddle-whl.cdn.bcebos.com'} or p.username or p.password:raise ValueError('Unexpected wheel source')
    if not 0<=start<=end<total or end-start+1>4*1024**2:raise ValueError('Range bound')
    req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}','Accept-Encoding':'identity'})
    with urllib.request.urlopen(req,timeout=30) as r:
        if r.status!=206 or r.headers.get('Content-Range')!=f'bytes {start}-{end}/{total}':raise ValueError('Exact HTTP Range unsupported; do not fetch payload')
        data=r.read(end-start+2)
    if len(data)!=end-start+1:raise ValueError('Range length mismatch')
    return data


def central_records(data):
    entries=[];seen=set();offset=0
    while offset<len(data):
        if len(data)-offset<46:raise ValueError('Truncated ZIP directory')
        row=struct.unpack_from('<4s6H3I5H2I',data,offset)
        if row[0]!=b'PK\x01\x02' or row[3]&1:raise ValueError('Invalid/encrypted ZIP directory')
        n,e,c=row[10:13];name=data[offset+46:offset+46+n].decode('utf-8' if row[3]&2048 else 'cp437')
        if not name or PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts or '\\' in name or name in seen:raise ValueError('Unsafe/duplicate ZIP member')
        if ((row[15]>>16)&0o170000)==0o120000:raise ValueError('Symlink member')
        if row[8]==0xffffffff or row[9]==0xffffffff:raise ValueError('ZIP64 unsupported')
        seen.add(name);entries.append(dict(name=name,compressed_bytes=row[8],uncompressed_bytes=row[9],local_header_offset=row[16],crc32=row[7],method=row[4]))
        offset+=46+n+e+c
        if offset>len(data) or len(entries)>20000:raise ValueError('ZIP entry bound')
    return entries


def inspect(row):
    total=row['size'];start=max(0,total-65557);tail=read_range(row['url'],start,total-1,total)
    pos=tail.rfind(b'PK\x05\x06')
    if pos<0 or len(tail)-pos<22:raise ValueError('No ZIP footer')
    end=struct.unpack_from('<4s4H2IH',tail,pos)
    if end[1] or end[2] or end[3]!=end[4] or end[4]==65535:raise ValueError('Multipart/ZIP64 unsupported')
    size,off=end[5:7];directory=read_range(row['url'],off,off+size-1,total);entries=central_records(directory)
    if len(entries)!=end[4]:raise ValueError('ZIP member count mismatch')
    files=[v for v in entries if not v['name'].endswith('/')]
    return dict(filename=row['filename'],source_url=row['url'],expected_compressed_bytes=total,expected_wheel_sha256=row['digests']['sha256'],
        whole_payload_acquired=False,whole_payload_sha256_verified=False,metadata_http_bytes=len(tail)+len(directory),
        central_directory_sha256=hashlib.sha256(directory).hexdigest(),files=len(files),declared_unpacked_logical_bytes=sum(v['uncompressed_bytes'] for v in files),
        rounded_4KiB_file_estimate_bytes=sum(((v['uncompressed_bytes']+4095)//4096)*4096 for v in files),
        caveat='ZIP declarations, not measured installed allocation; excludes directories, pyc and temporary buffers',
        largest_members=sorted(files,key=lambda v:v['uncompressed_bytes'],reverse=True)[:15],entries=entries)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--metadata',type=Path,required=True);p.add_argument('--filename',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    data=json.loads(a.metadata.read_text());row=next(v for v in data['urls'] if v['filename']==a.filename);result=inspect(row)
    with a.out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'entries','largest_members'}},indent=2))
