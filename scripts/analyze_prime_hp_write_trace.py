#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check observed NAND attempts AND committed overlay records, never filter writes."""
import argparse,collections,json,struct
from pathlib import Path
from analyze_hp_prime_compatibility import require,private_output
from prime_hp_confinement import FIRST_BLOCK,LAST_BLOCK,BBT_FIRST,BBT_LAST


def region(event):
    block=event['block']
    if FIRST_BLOCK<=block<=LAST_BLOCK:return 'hp-filesystem'
    if BBT_FIRST<=block<=BBT_LAST and (event['operation']=='erase' or event.get('page',-1)%64 in (0,4)):
        return 'hp-bad-block-metadata'
    return 'protected'


def analyze(log: Path, overlay: Path):
    attempts=[]
    for line in log.read_text().splitlines():
        if line.startswith('prime-nand-write: '):
            event=json.loads(line.split(': ',1)[1])
            require(event['operation'] in ('program','erase'),'unknown trace operation')
            require(event['page']//64==event['block'],'inconsistent trace address')
            attempts.append(event)
    require(attempts,'missing NAND write attempts; empty trace is not confinement evidence')
    data=overlay.read_bytes();require(data[:8]==b'PG2RAW1\n','physical overlay required')
    at=8;commits=[]
    while at<len(data):
        require(at+8<=len(data),'torn overlay header')
        op,index=struct.unpack_from('<B3xI',data,at);at+=8
        require(op in (1,2),'unknown overlay operation')
        if op==1:
            require(at+2112<=len(data),'torn overlay payload');at+=2112
        commits.append({'operation':'program' if op==1 else 'erase','block':index//64 if op==1 else index,
                        'page':index if op==1 else index*64})
    escaped=[e for e in attempts if region(e)=='protected']
    committed_escaped=[e for e in commits if region(e)=='protected']
    return {'attempt_count':len(attempts),'commit_count':len(commits),
            'attempt_operations':dict(collections.Counter(e['operation'] for e in attempts)),
            'attempt_regions':dict(collections.Counter(region(e) for e in attempts)),
            'attempt_block_bounds':[min(e['block'] for e in attempts),max(e['block'] for e in attempts)],
            'escaped_attempts':escaped,'escaped_commits':committed_escaped,
            'result':'PASS observed write confinement' if not escaped and not committed_escaped else 'FAIL writes escape declared regions',
            'limits':['Only recorded execution paths; not exhaustive reachability proof','Overlay may include seed records supplied by the caller']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--log',type=Path,required=True);p.add_argument('--overlay',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=analyze(a.log,a.overlay)
    with private_output(a.output).open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(result['result'],result['attempt_count'],'attempts')
    raise SystemExit(bool(result['escaped_attempts'] or result['escaped_commits']))
