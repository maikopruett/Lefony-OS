#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Package public dual-boot assets. Never includes HP images or device NAND.

The signed manifest is a separate browser-development release contract. It does
not alter the installed layout digest or claim unperformed hardware tests.
"""
import argparse,base64,hashlib,json,shutil
from pathlib import Path
from prime_dual_boot_contract import canonical,verify_descriptor,require
from prime_g2_update_capsule import sign_prefix,verify_signature
from prime_g2_uboot_recovery import ram_capsule

def package(a):
 out=a.output.resolve();require(not out.exists(),'use a new release directory')
 names={'boot.imx':a.uboot,'boot.bin':a.uboot.with_suffix('.bin'),'recovery.imx':a.recovery,
        'recovery.bin':a.recovery.with_suffix('.bin'),'lefony.zImage':a.lefony,'lefony.dtb':a.dtb,'descriptor.bin':a.descriptor}
 descriptor=verify_descriptor(a.descriptor.read_bytes(),a.public_key)
 for field,path in [('lefony_image',a.lefony),('rescue',a.lefony),('lefony_dtb',a.dtb)]:
  require(descriptor['images'][field]==(path.stat().st_size,hashlib.sha256(path.read_bytes()).hexdigest()),'signed component mismatch')
 # Validate both paired IVTs before publication.
 import struct
 for p in (a.uboot,a.recovery):
  data=p.read_bytes();ivt=struct.unpack_from('<8I',data)
  require((ivt[0],ivt[1],ivt[5])==(0x402000d1,0x87800000,0x877ff400),'unsupported paired U-Boot IVT')
  binary=p.with_suffix('.bin').read_bytes();at=ivt[1]-ivt[5]
  require(data[at:at+len(binary)]==binary,'mismatched U-Boot pair')
 out.mkdir(parents=True)
 for name,p in names.items():shutil.copyfile(p,out/name)
 (out/'recovery.zImage').write_bytes(ram_capsule(a.recovery.with_suffix('.bin').read_bytes()))
 assets={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(out.iterdir())}
 payload={'schema':1,'kind':'lefony-browser-dual-development','release':descriptor['release'],
  'layout':5,'layoutSha256':'56ec2952e4bad8d3995dcb3b6cb1468976b4f0756fc5abb599841e2172655234',
  'hp':{'bytes':descriptor['images']['hp_image'][0],'sha256':descriptor['images']['hp_image'][1]},
  'assets':assets,'limits':['HP Prime G2 only','Exact HP V15751 image supplied locally','Development release; remaining power-loss and battery checks are not claimed','HP factory reset and official updates are blocked'],'sourceTag':a.source_tag}
 encoded=canonical(payload);signature=sign_prefix(encoded,a.private_key);verify_signature(encoded,signature,a.public_key)
 (out/'release.json').write_text(json.dumps({'payload':base64.b64encode(encoded).decode(),'signature':base64.b64encode(signature).decode()},indent=2)+'\n')
 (out/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in sorted(out.iterdir()) if p.is_file()))
 print(json.dumps({'release':descriptor['release'],'files':len(assets),'hp_included':False}))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('uboot','recovery','lefony','dtb','descriptor','public-key','private-key','output'):p.add_argument('--'+name,type=Path,required=True)
 p.add_argument('--source-tag',required=True);package(p.parse_args())
