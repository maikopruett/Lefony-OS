# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit newlib diagnostics discovered in the exact executable ELF."""
import struct
from lfapp import elf_segments,unpack

MAGIC=0x5048464c
RECORD=struct.Struct('<10I')
SNAPSHOT=struct.Struct('<12I32s')
FIELDS=('version','bytes','flags','samples','allocated_bytes','allocated_peak_bytes',
        'arena_bytes','arena_peak_bytes','allocator_observations','loads','address','reserved','lfapp_sha256')

def address(package):
    _,image=unpack(package)
    _,segments=elf_segments(image)
    shoff=struct.unpack_from('<I',image,32)[0]
    shsize,count,names_index=struct.unpack_from('<HHH',image,46)
    if not shoff and not count:return None
    def require(condition,message):
        if not condition:raise ValueError('Heap profile ELF: '+message)
    require(shsize==40 and 0<count<=1024 and shoff>=52 and
            shoff+shsize*count<=len(image) and 0<names_index<count,'invalid section table')
    sections=[struct.unpack_from('<10I',image,shoff+shsize*i) for i in range(count)]
    strings=sections[names_index]
    require(strings[1]==3 and strings[4]+strings[5]<=len(image),'invalid section names')
    names=image[strings[4]:strings[4]+strings[5]]
    found=[]
    for section in sections:
        name=section[0]
        require(name<len(names) and names.find(b'\0',name)>=0,'unterminated section name')
        if names[name:names.find(b'\0',name)]==b'.lefony.heap_profile':found.append(section)
    if not found:return None
    require(len(found)==1,'duplicate diagnostic section')
    _,kind,flags,location,offset,size,link,info,alignment,entry=found[0]
    require(kind==1 and flags==3 and size==RECORD.size and alignment==4 and
            location%4==0 and not link and not info and not entry and offset+size<=len(image),
            'invalid diagnostic section')
    initial=image[offset:offset+size]
    require(initial==RECORD.pack(MAGIC,1,RECORD.size,0,0,0,0,0,0,0),'invalid initial diagnostic record')
    require(any(perms==6 and base<=location and location+size<=base+len(data) and
                data[location-base:location-base+size]==initial for base,data,_,perms in segments),
            'diagnostic record is outside initialized app data')
    return location

def arm(channel,location):
    if channel.command('APP PROFILE HEAP VERSION')!='VALUE 1':
        raise RuntimeError('Heap profiling requires matching VM firmware with heap profile version 1')
    if channel.command('APP PROFILE HEAP '+str(location))!='OK':
        raise RuntimeError('Could not arm heap profiling before app load')

def snapshot(channel,target,location,loads):
    reply=channel.command('APP PROFILE HEAP SNAPSHOT')
    try:
        if not reply.startswith('DATA ') or len(reply)!=5+SNAPSHOT.size*2:raise ValueError()
        values=dict(zip(FIELDS,SNAPSHOT.unpack(bytes.fromhex(reply[5:]))))
    except (ValueError,struct.error):raise RuntimeError('Invalid VM heap snapshot') from None
    flags=values.pop('flags')
    if (values.pop('version')!=1 or values.pop('bytes')!=SNAPSHOT.size or
        values.pop('reserved') or flags&~31 or not flags&1 or flags&4 or
        values.pop('lfapp_sha256').hex()!=target or values['address']!=location or
        values['loads']!=loads or not values['loads'] or not values['samples'] or
        not (values['allocated_bytes']<=values['arena_bytes']<=values['arena_peak_bytes']<=8380416) or
        not (values['allocated_bytes']<=values['allocated_peak_bytes']<=values['arena_peak_bytes'])):
        raise RuntimeError('VM heap snapshot does not match the requested app or allocator contract')
    observed=bool(flags&2);partial=bool(flags&16)
    if not observed and any(values[k] for k in ('allocated_bytes','allocated_peak_bytes',
                            'arena_bytes','arena_peak_bytes','allocator_observations')):
        raise RuntimeError('Unobserved allocator snapshot contains measurements')
    values.update(schema=1,method='newlib-mallinfo-at-unlock',
        status='partial' if partial else 'observed' if observed else 'not_observed',
        includes='allocator padding and metadata; excludes custom suballocators and static buffers',
        scope='completed allocator unlocks in matching package loads',
        counters_saturated=bool(flags&8),physical='not_tested')
    return values
