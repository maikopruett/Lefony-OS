# Licensing

Lefony OS is a collection of separately licensed components. There is no single
permissive license for the complete firmware. Existing file-level and upstream
notices take precedence over the directory defaults below.

| Material | License |
| --- | --- |
| Upsilon source and Lefony firmware adaptations under `ports/lefony-prime-g2/` | CC-BY-NC-SA-4.0, subject to existing component notices |
| Original Lefony standalone installer, host scripts and tests | GPL-3.0-or-later |
| QEMU models, QEMU patches and their adaptations | GPL-2.0-or-later, retaining individual upstream notices |
| U-Boot integrations, U-Boot patches and their adaptations | GPL-2.0-or-later, retaining individual upstream notices |
| Original Lefony boot capsule/recovery assembly and native layout tools without another notice | GPL-3.0-or-later |
| Original Lefony documentation and artwork | CC-BY-NC-SA-4.0 |

For the original Lefony material listed as GPL-3.0-or-later, permission is
granted to redistribute and/or modify it under the GNU General Public License
as published by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version. It is distributed without any warranty;
see [the full license](LICENSES/GPL-3.0-or-later.txt).

Original Lefony core adaptations, documentation and artwork are licensed under
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International](LICENSES/CC-BY-NC-SA-4.0.txt).
Copyright belongs to the respective Lefony contributors and upstream authors.

Preparation scripts are host tools, but strings/patches containing Upsilon
source adaptations retain CC-BY-NC-SA-4.0. The host-tool GPL grant does not
relicense those embedded fragments or the firmware they produce. Likewise,
reproduced upstream notices, third-party code, and assets retain their own
licenses. These directory defaults do not override an existing notice.

The noncommercial restriction means the complete OS does not meet the
[Open Source Definition](https://opensource.org/osd). Its source can be shared
and contributions accepted under the applicable terms; standalone GPL tools
are open source. Do not describe the whole firmware as GPL, MIT, or OSI-approved.

`LICENSES/` contains the principal license texts. `THIRD_PARTY_NOTICES.md` records
upstream sources and pins. Release distributions must also retain all component
notices from the actual pinned source trees and include the corresponding
source/build material required by their licenses. Proprietary HP firmware,
ROMs, vendor PDFs and private captures are not licensed or distributed here.
