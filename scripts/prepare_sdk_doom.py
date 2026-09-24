#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare the pinned Doom engine and notices for ARM SDK qualification.

The app uses the scoped MIT alternative for its Lefony runtime inputs. Release
qualification and the complete corresponding-source audit remain separate.
Embedded Doom source adaptations retain GPL-2.0-or-later, matching the emitted
engine notices; the standalone host tool remains GPL-3.0-or-later.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def digest(data):return hashlib.sha256(data).hexdigest()


def prepare(destination,checkout,arguments=None):
    pin=json.loads((ROOT/'sdk/ports/doom/source.json').read_text())
    source=checkout/pin['directory'];contents={}
    if destination.exists():raise ValueError('Existing project was preserved; choose a new destination')
    for name,expected in pin['source_files'].items():
        data=(source/name).read_bytes()
        if digest(data)!=expected:raise ValueError('Pinned source differs: '+name)
        contents[name]=data
    license_data=(checkout/pin['license']['path']).read_bytes()
    if digest(license_data)!=pin['license']['sha256']:raise ValueError('Pinned Doom license differs')
    changes=[]
    def edit(name,before,after,reason):
        text=contents[name].decode()
        if text.count(before)!=1:raise ValueError('Unexpected Doom source context: '+name+': '+before[:70])
        contents[name]=text.replace(before,after).encode();changes.append({'file':name,'reason':reason})
    edit('doomgeneric.c','#include "m_argv.h"','#include "m_argv.h"\n#include "i_system.h"',
         'Declare the existing engine allocation-error handler')
    edit('doomgeneric.c','\tDG_Init();','''    /* Lefony qualification: checked allocation before platform use. */
    if (DG_ScreenBuffer == NULL) I_Error("Screen buffer allocation failed");
\tDG_Init();''','Reject failed screen allocation before use')
    edit('i_system.c','#include "i_system.h"','#include "i_system.h"\n#include "doomgeneric.h"',
         'Declare the platform display hook used for fatal errors')
    edit('i_system.c','    entry = malloc(sizeof(*entry));','''    entry = malloc(sizeof(*entry));
    if (entry == NULL) I_Error("Cannot allocate exit handler");''',
         'Report exhausted exit-handler allocation before dereferencing it')
    edit('i_system.c','''        fprintf(stderr, "Warning: recursive call to I_Error detected.\\n");
#if ORIGCODE
        exit(-1);
#endif''','''        fprintf(stderr, "Warning: recursive call to I_Error detected.\\n");
        /* Keep the first error visible and run the registered output discard. */
        exit(-1);''','Restore bounded recursive-error exit independently of the SDL platform')
    edit('i_system.c','    // Shutdown. Here might be other errors.',
         '''    /* Lefony qualification: retain the actual error in the app frame. */
    DG_SetWindowTitle(msgbuf);

    // Shutdown. Here might be other errors.''','Expose the actual fatal message through the public display adapter')
    edit('i_system.c','''    exit(0);
#endif
}''','''#endif
    /* Lefony qualification: a normal Quit always completes main cleanup. */
    exit(0);
}''','Restore successful Quit when the SDL-specific ORIGCODE backend is disabled')
    edit('g_game.c','#include "doomdef.h"','#include "doomdef.h"\n#include "output.h"',
         'Use the public SDK transaction adapter for game saves')
    original=contents['g_game.c'].decode()
    start=original.index('void G_DoSaveGame (void)')
    end=original.index('// G_InitNew',start)
    before=original[start:end]
    edit('g_game.c',before,'''void G_DoSaveGame (void)
{
    /* The OS stages a direct replacement. A second named copy would need
     * additional logical quota even when replacing a same-sized save. */
    char *savegame_file = P_SaveGameFile(savegameslot);
    savegame_error = false;
    save_stream = DG_OpenOutput(savegame_file);
    if (save_stream == NULL)
    {
        savegame_error = true;
    }
    else
    {
        long size;
        P_WriteSaveGameHeader(savedescription);
        P_ArchivePlayers();
        P_ArchiveWorld();
        P_ArchiveThinkers();
        P_ArchiveSpecials();
        P_WriteSaveGameEOF();
        size = ftell(save_stream);
        if (size < 0 || (vanilla_savegame_limit && size > SAVEGAMESIZE))
            savegame_error = true;
        if (DG_FinishOutput(save_stream, !savegame_error) != 0)
            savegame_error = true;
        save_stream = NULL;
    }
    gameaction = ga_nothing;
    M_StringCopy(savedescription, "", sizeof(savedescription));
    players[consoleplayer].message = savegame_error
        ? "SAVE UNCONFIRMED: LOAD TO CHECK"
        : DEH_String(GGSAVED);
    R_FillBackScreen();
}

//
''','Stage direct game saves, discard processing failures and keep gameplay available for retry')
    edit('m_config.c','#include "m_misc.h"','#include "m_misc.h"\n#include "output.h"',
         'Use checked configuration streams through the public SDK')
    edit('m_config.c','''                intparm = scantokey[intparm];
            }
            else''','''                intparm = scantokey[intparm];
            }
            else if (intparm == KEY_STRAFE_L || intparm == KEY_STRAFE_R
                  || intparm == KEY_USE || intparm == KEY_FIRE)
            {
                /* Doomgeneric writes these four unmapped virtual keys as
                 * raw values. They are outside the DOS scan-code range. */
            }
            else''','Round-trip Doomgeneric virtual action keys without changing DOS scan-code bindings')
    edit('m_config.c','''static void SaveDefaultCollection(default_collection_t *collection)
{
#if ORIGCODE''','''static void SaveDefaultCollection(default_collection_t *collection)
{''','Enable the portable configuration writer independently of the SDL platform')
    edit('m_config.c','''    f = fopen (collection->filename, "w");
    if (!f)
\treturn; // can't write the file, but don't complain''','''    f = DG_OpenOutput(collection->filename);
    if (!f) I_Error("Cannot open configuration for saving: %s", collection->filename);''',
         'Surface configuration open errors without truncating prior data')
    edit('m_config.c','''    fclose (f);
#endif
}

// Parses integer''','''    if (DG_FinishOutput(f, !ferror(f)) != 0)
        I_Error("Configuration save unconfirmed: %s", collection->filename);
}

// Parses integer''','Commit complete configuration output and report failed saves')
    edit('m_config.c','''static void LoadDefaultCollection(default_collection_t *collection)
{
#if ORIGCODE''','''static void LoadDefaultCollection(default_collection_t *collection)
{''','Enable the portable configuration reader independently of the SDL platform')
    edit('m_config.c','    f = fopen(collection->filename, "r");','    f = DG_OpenConfigInput(collection->filename);',
         'Bound configuration inputs to 64 KiB')
    edit('m_config.c','''        // File not opened, but don't complain.\x20
        // It's probably just the first time they ran the game.

        return;''','''        if (errno != ENOENT) I_Error("Cannot read configuration: %s", collection->filename);
        return;''','Treat only an absent configuration as first-run defaults')
    edit('m_config.c','    while (!feof(f))','    while (!feof(f) && !ferror(f))',
         'Stop bounded configuration parsing after a read error')
    edit('m_config.c','''    fclose (f);
#endif
}

// Set the default''','''    if (ferror(f)) { fclose(f); I_Error("Configuration read failed: %s", collection->filename); }
    if (fclose(f)) I_Error("Configuration close failed: %s", collection->filename);
}

// Set the default''','Report read/close errors before continuing with partially read settings')
    edit('m_config.c','''            * (char **) def->location = strdup(value);''','''            {
                char *copy = strdup(value);
                if (copy == NULL) I_Error("Cannot allocate configuration string");
                * (char **) def->location = copy;
            }''','Reject failed configuration allocation before publishing a null setting')
    for setting in ('default_main_config','default_extra_config'):
        edit('m_config.c','M_StringJoin(configdir, '+setting+', NULL)',
             'M_StringJoin(configdir, configdir[0] && configdir[strlen(configdir)-1] != DIR_SEPARATOR ? DIR_SEPARATOR_S : "", '+setting+', NULL)',
             'Separate the configuration directory from '+setting+' without changing saved-game paths')
    edit('m_config.c','    char *result = (char *)malloc(2);','''    char *result = (char *)malloc(2);
    if (result == NULL) I_Error("Cannot allocate configuration directory");''',
         'Reject exhausted configuration-directory allocation before writing it')
    edit('p_saveg.c','        filename = malloc(filename_size);','''        filename = malloc(filename_size);
        if (filename == NULL) I_Error("Cannot allocate savegame filename");''',
         'Report exhausted save-path allocation before formatting into it')
    destination.mkdir(parents=True)
    for name,data in contents.items():
        target=destination/'src/doomgeneric'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    shutil.copyfile(ROOT/'sdk/ports/doom/platform.c',destination/'src/platform.c')
    for name in ('output.h','output.c'):
        shutil.copyfile(ROOT/'sdk/ports/doom'/name,destination/'src'/name)
    (destination/'notices').mkdir();(destination/'notices/doomgeneric.txt').write_bytes(license_data)
    shutil.copyfile(ROOT/'LICENSES/MIT.txt',destination/'notices/lefony-runtime-MIT.txt')
    shutil.copyfile(ROOT/'LICENSE.md',destination/'notices/lefony-license-scope.md')
    shutil.copyfile(ROOT/'sdk/ports/doom/THIRD_PARTY_NOTICES.md',destination/'THIRD_PARTY_NOTICES.md')
    metadata={'abi':1,'id':'doom-proof','name':'Doom qualification','version':'0.2.3',
              'license':'GPL-2.0-or-later','schema':1,'minimum_api':12,
              'required_capabilities':8252,'optional_capabilities':0,'data_schema':0}
    config={'schema':2,'runtime':'foreground-newlib-1',
            'sources':['src/doomgeneric/'+p for p in pin['portable_sources']]+['src/platform.c','src/output.c'],
            'include_dirs':['src','src/doomgeneric'],'defines':pin['defines'],
            'c_flags':['-fwrapv','-fno-strict-aliasing','-Wno-error'],
            'arguments':arguments if arguments is not None else ['-iwad','freedoom1.wad','-warp','1','1','-skill','2','-nosound','-nogui']}
    for name,value in [('app.json',metadata),('project.json',config)]:
        (destination/name).write_text(json.dumps(value,indent=2)+'\n')
    (destination/'notices/port.txt').write_text(json.dumps({'upstream_commit':pin['commit'],'changes':changes,
        'prepared_sources':{name:digest(data) for name,data in contents.items()},
        'platform_sha256':digest((destination/'src/platform.c').read_bytes()),
        'output_sha256':{name:digest((destination/'src'/name).read_bytes()) for name in ('output.c','output.h')},
        'lefony_runtime_license':'MIT alternative; scope and complete notice included',
        'distribution':'development candidate; final linked-input and corresponding-source audit required'},indent=2)+'\n')
    (destination/'README.md').write_text('''# Local Doom qualification project

This uses the public foreground, input, pixel and file APIs. Game data is the
separately pinned Freedoom Phase 1 WAD, stored as app-private `freedoom1.wad`.
It is not embedded or supplied by the source bundle. No sound backend is enabled.

The prepared engine retains its GPL notices. The approved conventional SDK
startup/interfaces/adapters offer an MIT alternative; its scope and full notice
are included. Other components retain their own terms; see THIRD_PARTY_NOTICES.md.
The app manifest describes the project license, not release qualification.
`notices/port.txt` records every checked change and prepared-source hash.

Build and test using the ordinary SDK project commands. The repository's
`vm/test-sdk-doom-gameplay.py` covers gameplay and saved-state restoration;
`vm/test-sdk-doom-storage.py` covers settings and full-quota saves. The error
and resource harnesses extend these with failed writes, retry and exhaustion.

Import the permitted WAD with the app closed, after installation/upgrade acceptance:

```sh
lefony-sdk files import doom-proof freedoom1.wad ./freedoom1.wad
```

Named saves live in `.savegame/`; configuration
files are `default.cfg` and `doomgenericdoom.cfg`. Configuration input is bounded
to 64 KiB per file. Ordinary Quit saves settings; OS-owned Home can force exit
without running the engine's settings writer.

This recipe requires API 12 writer cancellation (capability mask 8252). Saves
stage a direct replacement, crediting the existing file against the logical
quota. Processing failures discard the staged writer. A failed final commit
is unconfirmed: inspect the previous or complete new file before retrying.
''')
    return config


def bundle_game_data(destination, cache):
    """Distribute only the verified public Freedoom release and its notices."""
    pin=json.loads((ROOT/'sdk/ports/doom/assets.json').read_text())
    files=[];payload=bytearray()
    data_directory=destination/'data';data_directory.mkdir()
    for name,expected in pin['files'].items():
        data=(cache/name).read_bytes()
        if len(data)!=expected['bytes'] or digest(data)!=expected['sha256']:
            raise ValueError('Pinned Freedoom input differs: '+name)
        target=name if name.endswith('.wad') else 'Freedoom-'+name
        (data_directory/target).write_bytes(data)
        if name.endswith('.txt'):(destination/'notices'/target).write_bytes(data)
        files.append({'path':target,'offset':len(payload),'bytes':len(data),'sha256':digest(data)})
        payload.extend(data)
    descriptor={'schema':1,'encoding':'gzip','bytes':len(payload),'sha256':digest(payload),'files':files}
    (destination/'notices/bundled-data.txt').write_text(json.dumps(descriptor,indent=2)+'\n')
    shutil.copyfile(ROOT/'sdk/ports/doom/assets.json',destination/'notices/freedoom-inputs.txt')
    manifest=json.loads((destination/'app.json').read_text())
    manifest.update(name='Doom',version='0.2.3')
    (destination/'app.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (destination/'README.md').write_text("""# Doom with Freedoom Phase 1

The store installation includes the unmodified Freedoom 0.13.0 WAD and its
license/credits. No separate download or terminal import is needed. Use the
current SDK source CLI with bundled-data support to publish this project.
`notices/bundled-data.txt` pins each file; `data/` holds the public inputs.
The source download retains the descriptor, provenance and all license notices.
For offline source rebuilds, the engine needs no data. For publication/replay,
retrieve the release data alongside the source and place it in `data/`.

Controls: arrows move/turn; XNT fires; Space uses; Shift runs; Alpha strafes;
Back/Menu opens the menu; OK confirms; Num/Symb save/load; Plot/View quick
save/load; Toolbox quits. Quit saves settings; Home returns to Lefony.
Requires API 12. No sound or multiplayer. Physical qualification remains open.
""")


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--source',type=Path,default=ROOT/'build/sdk-1.0-upstream/doomgeneric')
    parser.add_argument('--bundle-data',action='store_true',help='Include pinned Freedoom data for automatic store installation')
    parser.add_argument('--assets',type=Path,default=ROOT/'build/sdk-1.0-upstream')
    args=parser.parse_args();prepare(args.project.resolve(),args.source.resolve())
    if args.bundle_data:bundle_game_data(args.project.resolve(),args.assets.resolve())
    print(args.project.resolve())
