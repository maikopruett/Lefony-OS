#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Conservative offline HP YAFFS logical export/recreation for private fixtures.

Wire fields follow the YAFFS2 object-header/packed-tag interface. HP's captured
format stores tag/header integers big-endian and tag ECC little-endian. This
implementation reconstructs files/directories, not raw page relocation. It
resolves shrink/shadow history and refuses links, ambiguous trees, ECC errors
and missing data rather than claiming a complete backup. No device access.

References: Aleph-One-Ltd/yaffs2 core/yaffs_guts.h, yaffs_packedtags2.c and
yaffs_ecc.c. The parity calculation below derives Hamming coordinate parities
bit by bit; no vendor code or parity lookup table is embedded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prime_dual_boot_contract import canonical,sha,require
from analyze_hp_prime_compatibility import private_output
from prime_gpmi_bch import Layout
from prime_bch_native import NativeBCH

PAGE=2048
RAW=2112
HP=Layout(0x03241080,0x08401080)


def tag_ecc(tags):
    column=row=inverse=0
    for index,value in enumerate(tags):
        for bit in range(8):
            if value>>bit&1:
                column ^= sum((2 if bit>>axis&1 else 1)<<(axis*2) for axis in range(3))
                row ^= index
                inverse ^= (~index)&0xffffffff
    return struct.pack('<B3xII',column,row,inverse)


def decode(raw,native):
    decoded=HP.decode(raw,decoder=native)
    require(not decoded.failed,'uncorrectable HP codeword')
    payload=bytearray(decoded.payload)
    # HP preserves the overwritten payload byte at metadata[34], not [0].
    pair=int.from_bytes(payload[1992:1994],'little')
    pair=(pair&~(255<<4)) | decoded.metadata[34]<<4
    payload[1992:1994]=pair.to_bytes(2,'little')
    return bytes(payload),decoded.metadata


def encode(payload,tags,native):
    require(len(payload)==PAGE and len(tags)==16,'invalid HP logical page')
    data=bytearray(payload);metadata=bytearray(b'\xff'*36)
    metadata[:16]=tags;metadata[16:28]=tag_ecc(tags)
    pair=int.from_bytes(data[1992:1994],'little')
    metadata[34]=(pair>>4)&255
    data[1992:1994]=(pair|(255<<4)).to_bytes(2,'little')
    return HP.encode(bytes(data),bytes(metadata),native)


def export(source,output,*,end=4096,bad=()):
    output=private_output(output)
    require(not output.exists(),'archive output must be new')
    require(source.stat().st_size==4096*64*RAW and 392<end<=4096,'wrong physical NAND size/bounds')
    headers={};chunks={};sequences={};shrinks={};shadows={}
    foreign_tail=[]
    with source.open('rb') as f:
        source_digest=hashlib.file_digest(f,'sha256').hexdigest()
        # The retained capture also contains Linux flash-BBT copies in the
        # final two blocks. Recognize both clean, isolated copies explicitly;
        # never suppress an arbitrary HP ECC error as "probably metadata".
        tail=[]
        for block,magic in ((4094,b'1tbB'),(4095,b'Bbt0')):
            f.seek(block*64*RAW);raw=f.read(64*RAW)
            decoded=Layout(0x030a0880,0x08400880).decode(raw[:RAW])
            if (decoded.status==(0,0,0,0) and decoded.payload[:4]==magic and
                    decoded.metadata==b'\xff'*10 and raw[RAW:]==b'\xff'*(63*RAW)):
                tail.append((block,decoded.payload[4:],sha(raw).hex()))
        if len(tail)==2 and tail[0][1]==tail[1][1]:
            foreign_tail=[{'block':b,'sha256':digest,'kind':'preserved Linux flash BBT'} for b,_,digest in tail]
    with NativeBCH() as native,source.open('rb') as f:
        for block in range(392,end):
            if block in bad or any(item['block']==block for item in foreign_tail):continue
            f.seek(block*64*RAW)
            for offset in range(64):
                raw=f.read(RAW)
                if raw==b'\xff'*RAW:continue
                try:
                    payload,metadata=decode(raw,native)
                except ValueError as error:
                    raise ValueError(f'page {block*64+offset}: {error}') from error
                seq,obj,chunk,length=struct.unpack_from('>4I',metadata)
                if seq in (0x21,0xffff0000):continue # checkpoint or explicitly retired sequence
                require(0x1000<=seq<=0xefffff00,'unknown YAFFS sequence; incomplete backup')
                expected_ecc=tag_ecc(metadata[:16])
                require(metadata[16]==expected_ecc[0] and metadata[20:28]==expected_ecc[4:],
                        f'tag ECC mismatch at page {block*64+offset}: {metadata[16:28].hex()} expected {expected_ecc.hex()}')
                require(seq not in sequences or sequences[seq]==block,'duplicate allocation sequence')
                sequences[seq]=block
                order=(seq,offset)
                if chunk&0x80000000:
                    require(not chunk&0x10000000,'unknown extra tag flag')
                    obj &= 0x0fffffff;chunk=0
                if obj in (0x10,0x20):continue
                require(0<obj<0x40000,'invalid object id')
                if chunk==0:
                    kind=struct.unpack_from('>I',payload)[0]
                    shadow,is_shrink=struct.unpack_from('>2I',payload,504)
                    require(is_shrink in (0,1),'unknown shrink-header flag')
                    if shadow:
                        require(4<shadow<0x40000,'invalid shadow object')
                        shadows[shadow]=max(order,shadows.get(shadow,(0,0)))
                    if is_shrink:
                        parent=struct.unpack_from('>I',payload,4)[0]
                        # YAFFS marks a deleted directory's header as shrinking
                        # too. It has no data chunks to truncate.
                        require(kind==1 or (kind==3 and parent in (3,4)),
                                'unsupported non-file shrink header')
                        if kind==1:
                            bound=0 if parent in (3,4) else struct.unpack_from('>I',payload,292)[0]
                            shrinks.setdefault(obj,[]).append((order,bound))
                    if obj not in headers or order>headers[obj][0]:headers[obj]=(order,payload)
                else:
                    require(0<length<=PAGE and chunk<0x10000000,'invalid data chunk')
                    key=(obj,chunk)
                    if key not in chunks or order>chunks[key][0]:chunks[key]=(order,block*64+offset,length)
    live={}
    shadowed={obj for obj,order in shadows.items() if obj in headers and headers[obj][0]<=order}
    def reachable(obj,trail=()):
        if obj in (1,2):return True
        if obj in (3,4):return False
        if obj in shadowed:return False
        require(obj not in trail and len(trail)<128,'directory cycle/depth exceeded')
        require(obj in headers,'orphan object; incomplete backup')
        parent=struct.unpack_from('>I',headers[obj][1],4)[0]
        return reachable(parent,trail+(obj,))
    for obj,(_,header) in headers.items():
        if obj in (1,2) or not reachable(obj):continue
        kind,parent=struct.unpack_from('>2I',header)
        require(kind in (1,3),'unsupported live link/special object')
        name=header[10:266].split(b'\0',1)[0]
        require(name and b'/' not in name and name not in (b'.',b'..'),'invalid object name')
        size=struct.unpack_from('>I',header,292)[0] if kind==1 else 0
        # Data written after the most recent object header can extend a file.
        # A later shrink limits older chunks, preventing stale tail revival.
        if kind==1:
            for (owner,chunk),(order,_,length) in chunks.items():
                if owner!=obj or order<=headers[obj][0]:continue
                chunk_end=(chunk-1)*PAGE+length
                for when,bound in shrinks.get(obj,[]):
                    if when>order:chunk_end=min(chunk_end,bound)
                size=max(size,chunk_end)
        require(kind!=1 or struct.unpack_from('>I',header,496)[0] in (0,0xffffffff),'64-bit file unsupported')
        require(size<=207*1024*1024,'file does not fit smaller filesystem')
        live[obj]={'id':obj,'parent':parent,'kind':kind,'name_hex':name.hex(),'size':size,'header':header}
    siblings=set()
    for obj in live.values():
        pair=(obj['parent'],obj['name_hex'])
        require(pair not in siblings,'ambiguous duplicate filename')
        siblings.add(pair)
        require(obj['parent'] in (1,2) or (obj['parent'] in live and live[obj['parent']]['kind']==3),
                'parent is not a live directory')
    output.mkdir(parents=True)
    records=[]
    with NativeBCH() as native,source.open('rb') as f:
        for obj,item in sorted(live.items()):
            header=item.pop('header')
            (output/f'{obj}.header').write_bytes(header)
            digest=hashlib.sha256()
            with (output/f'{obj}.data').open('wb') as target:
                for at in range(0,item['size'],PAGE):
                    key=(obj,at//PAGE+1);amount=min(PAGE,item['size']-at)
                    data=bytes(amount)
                    if key in chunks:
                        order,page,length=chunks[key]
                        allowed=min(length,amount)
                        for when,bound in shrinks.get(obj,[]):
                            if when>order:allowed=min(allowed,max(0,bound-at))
                        if allowed:
                            f.seek(page*RAW);payload,_=decode(f.read(RAW),native)
                            data=payload[:allowed]+bytes(amount-allowed)
                    target.write(data);digest.update(data)
            records.append({**item,'sha256':digest.hexdigest(),'header_sha256':sha(header).hex()})
    report={'schema':1,'format':'hp-yaffs-logical-research-v1','source_sha256':source_digest,
            'first_block':392,'end_block':end,'bad_blocks':sorted(bad),'objects':records,
            'excluded_foreign_metadata':foreign_tail,
            'total_file_bytes':sum(r['size'] for r in records),'device_flash_input':False}
    with source.open('rb') as f:
        require(hashlib.file_digest(f,'sha256').hexdigest()==source_digest,'source changed during logical export')
    report['archive_sha256']=sha(canonical(report)).hex()
    (output/'archive.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def verify(archive):
    report=json.loads((archive/'archive.json').read_text())
    expected=report.pop('archive_sha256')
    require(sha(canonical(report)).hex()==expected,'archive manifest mismatch')
    require(report['schema']==1 and report['format']=='hp-yaffs-logical-research-v1' and
            report['device_flash_input'] is False,'unknown logical archive')
    objects={item['id']:item for item in report['objects']}
    require(len(objects)==len(report['objects']),'duplicate archive object')
    siblings=set()
    for item in report['objects']:
        obj=item['id'];require(type(obj) is int and 0<obj<0x40000,'invalid archive object')
        header=(archive/f'{obj}.header').read_bytes();data=archive/f'{obj}.data'
        require(len(header)==2048 and sha(header).hex()==item['header_sha256'],'header mismatch')
        kind,parent=struct.unpack_from('>2I',header)
        name=header[10:266].split(b'\0',1)[0]
        require(kind==item['kind'] and parent==item['parent'] and name.hex()==item['name_hex'],
                'archive object/header mismatch')
        require(kind in (1,3) and name and b'/' not in name and name not in (b'.',b'..'),
                'unsupported archive object')
        require(type(item['size']) is int and 0<=item['size']<=207*1024*1024 and
                (kind==1 or item['size']==0),'invalid archive file size')
        require((parent,name) not in siblings,'duplicate archive filename')
        siblings.add((parent,name))
        trail={obj}
        while parent not in (1,2):
            require(parent in objects and parent not in trail and len(trail)<128 and
                    objects[parent]['kind']==3,'invalid archive directory tree')
            trail.add(parent);parent=objects[parent]['parent']
        with data.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        require(data.stat().st_size==item['size'] and digest==item['sha256'],'file backup mismatch')
    report['archive_sha256']=expected
    return report


def recreate(archive,output,*,bad=()):
    report=verify(archive);output=private_output(output)
    require(not output.exists(),'recreation output must be new')
    good=[b for b in range(392,2048) if b not in bad]
    needed=sum(1+(o['size']+2047)//2048 for o in report['objects'])
    require((needed+63)//64+16<=len(good),'insufficient capacity and YAFFS reserve')
    output.mkdir(parents=True)
    # A sparse map of entirely recreated eraseblocks, never old raw pages.
    block_index=page_index=0;block=bytearray(b'\xff'*(64*RAW));written=[]
    with NativeBCH() as native:
        def append(payload,obj,chunk,length):
            nonlocal block_index,page_index,block
            seq=0x1000+block_index
            tags=struct.pack('>4I',seq,obj,chunk,length)
            block[page_index*RAW:(page_index+1)*RAW]=encode(payload,tags,native)
            page_index+=1
            if page_index==64:
                b=good[block_index];(output/f'{b}.raw').write_bytes(block);written.append(b)
                block_index+=1;page_index=0;block=bytearray(b'\xff'*(64*RAW))
        for item in report['objects']:
            obj=item['id'];header=bytearray((archive/f'{obj}.header').read_bytes())
            # Recreate logical objects without historical rename/truncate
            # operations or references to the old allocation history.
            struct.pack_into('>2I',header,504,0,0)
            if item['kind']==1:struct.pack_into('>I',header,292,item['size'])
            append(bytes(header),obj,0,0xffff)
            with (archive/f'{obj}.data').open('rb') as f:
                chunk=0
                while data:=f.read(PAGE):
                    chunk+=1;append(data.ljust(PAGE,b'\0'),obj,chunk,len(data))
        if page_index:
            b=good[block_index];(output/f'{b}.raw').write_bytes(block);written.append(b)
    result={'schema':1,'archive_sha256':report['archive_sha256'],'device_flash_input':False,
            'erase_good_blocks':good,'written_blocks':{str(b):sha((output/f'{b}.raw').read_bytes()).hex() for b in written},
            'used_pages':needed,'remaining_good_blocks':len(good)-(needed+63)//64}
    (output/'recreated.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    for name in ('export','recreate'):
        s=sub.add_parser(name);s.add_argument('source',type=Path);s.add_argument('output',type=Path)
        s.add_argument('--bad-blocks',type=int,nargs='*',default=[])
        if name=='export':s.add_argument('--end',type=int,default=4096)
    a=p.parse_args()
    result=export(a.source,a.output,end=a.end,bad=a.bad_blocks) if a.command=='export' else recreate(a.source,a.output,bad=a.bad_blocks)
    print({k:v for k,v in result.items() if k not in ('objects','written_blocks','erase_good_blocks')})
