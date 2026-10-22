"""Build progressive decks by editing an isolated copy with native Anki APIs."""
from __future__ import annotations
import argparse
import collections
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

from german.vocab.pilot_build import CSS, FIELDS
from german.vocab.source import ENTRIES, ROOT, VOCAB, BUILD, connect
from german.vocab.content import LEVELS
from german.vocab.audio import DIRECTORY, MANIFEST, atomic_json
from german.vocab.pilot_validate import digest_rows

OUT = VOCAB / "out"
PROFILE = BUILD / "production-profile"
ARCHIVE = "Archive::Goethe duplicates · 2026-10-15"
FRONT_DE = '''<div class="wrap"><div class="eyebrow">{{Level}} · Deutsch → English</div>
<div class="word" lang="de">{{German}}</div>{{#CueDE}}<div class="cue">{{CueDE}}</div>{{/CueDE}}
{{Audio}}<div class="cue">Give the English meaning.</div></div>'''
FRONT_EN = '''<div class="wrap"><div class="eyebrow">{{Level}} · English → Deutsch</div>
<div class="word">{{English}}</div>{{#CueEN}}<div class="cue">{{CueEN}}</div>{{/CueEN}}
<div class="cue">Give the German word, including its article where applicable.</div></div>'''
BACK = '''<div class="wrap"><div class="eyebrow">{{Level}} · {{POS}}</div>
<div class="word" lang="de">{{German}}</div><div class="translation">{{English}}</div>{{Audio}}
<div class="section"><h3>Forms & grammar</h3>{{Grammar}}</div>
<div class="section"><h3>Meaning</h3>{{Meanings}}</div>
{{#Related}}<div class="section"><h3>Related words & contrasts</h3>{{Related}}</div>{{/Related}}
{{#Usage}}<div class="section"><h3>Usage & common mistakes</h3>{{Usage}}</div>{{/Usage}}
<div class="section"><h3>Examples</h3>{{Examples}}</div>
<div class="section"><h3>Your previous study history · import snapshot</h3>{{History}}</div>
<div class="source">{{Source}}</div></div>'''
STYLE = CSS + '''
.history-table {width:100%;border-collapse:collapse;font-size:14px;margin:8px 0 14px}
.history-table th,.history-table td {text-align:left;padding:5px;border-bottom:1px solid #d5ddd5}
.history-table th {font-weight:600}.replay-button {margin:4px 8px 4px 0}
details summary {cursor:pointer} .snapshot {font-size:14px;color:#68787a}
'''

IMPORT_INSTRUCTIONS = '''# German study kit — import instructions

These packages were built and native-import tested with Anki 26.9.3. Make a normal Anki backup and finish/sync reviews on other devices before importing.

## Recommended: complete migrated collection

1. In Anki, create a fresh profile for the migrated collection.
2. Choose **File → Import** and select `German-collection-cleaned-WITH-HISTORY.colpkg`.
3. Accept the collection replacement prompt for that fresh profile.
4. Sync only after checking the three `Goethe vocabulary` decks and deciding which side should overwrite AnkiWeb.

The COLPKG contains the complete original collection and media, the active A1/A2/B1 decks, and the suspended duplicate archive. Do not also import the APKG files into that profile.

## Alternative: vocabulary packages only

Import `Goethe-A1-WITH-HISTORY.apkg`, `Goethe-A2-WITH-HISTORY.apkg`, and `Goethe-B1-WITH-HISTORY.apkg` into a fresh profile or another carefully backed-up collection. Scheduling and deck configuration are included. Import `Goethe-duplicate-archive-WITH-HISTORY.apkg` only if you also want the redundant source notes and their independent histories; all archive cards are suspended.

On DE → EN cards the German word plays on the prompt. EN → DE prompts are silent. Both answers play the word followed by the three example sentences. The visible history section is explicitly the **15 October 2026 import snapshot**; use **Card Info** for live history after subsequent reviews.

Verify downloads against `SHA256SUMS` before import.
'''


def items(values):
    return "<ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in values) + "</ul>" if values else ""


def file_sha256(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(8*1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def history_html(entry, notes):
    sections = ['<p class="snapshot">Snapshot: 15 October 2026. Current reviews and scheduling update automatically in Anki; open Card Info for your live history.</p>']
    canonical = notes[entry["source_note_id"]]
    ratings = {1:"Again",2:"Hard",3:"Good",4:"Easy"}
    for card in canonical["cards"]:
        direction = "DE → EN" if card["ord"]==0 else "EN → DE"
        records = [r for r in canonical["reviews"] if r["cid"]==card["id"]]
        reviews = [r for r in records if r["ease"] in ratings and r["type"] != 4]
        interval = f"{card['ivl']} days" if card["type"]==2 else "not in review"
        sections.append(f"<p><strong>{direction}</strong>: {card['reps']} repetitions · interval {interval} · {len(reviews)} rated reviews · {len(records)} total history records</p>")
        if reviews:
            rows = []
            for r in reviews[-5:][::-1]:
                date = datetime.fromtimestamp(r["id"]/1000,ZoneInfo("Europe/Zurich")).strftime("%d %b %Y %H:%M")
                ivl = f"{r['ivl']} d" if r["ivl"]>=0 else f"{-r['ivl']} s"
                rows.append(f"<tr><td>{date}</td><td>{ratings[r['ease']]}</td><td>{ivl}</td></tr>")
            sections.append('<details><summary>Recent reviews</summary><table class="history-table"><thead><tr><th>Date (Zurich)</th><th>Rating</th><th>Interval</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></details>')
        else: sections.append("<p>No rated reviews in the source collection.</p>")
    duplicates = [notes[nid] for nid in entry["source_note_ids"] if nid!=entry["source_note_id"]]
    if duplicates:
        rows=[]
        for n in duplicates:
            rated=sum(r["ease"] in ratings and r["type"]!=4 for r in n["reviews"])
            rows.append(f"<tr><td>{n['nid']}</td><td>{n['level']}</td><td>{sum(c['reps'] for c in n['cards'])}</td><td>{rated}</td></tr>")
        sections.append('<details><summary>History retained from duplicate source cards</summary><p>These independent schedules remain in the suspended archive. The active cards retain the schedule shown above.</p><table class="history-table"><thead><tr><th>Original note</th><th>Level</th><th>Repetitions</th><th>Rated reviews</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></details>')
    sections.append(f'<p class="snapshot">Original note {entry["source_note_id"]} · original card IDs '+', '.join(str(c["id"]) for c in canonical["cards"])+'. Full review records are retained.</p>')
    return ''.join(sections)


def field_values(entry, manifest, notes, verify=True):
    media=[]
    def sound(slot,text):
        record=manifest.get(f"{entry['id']}:{slot}")
        if not record: raise ValueError(f"Missing audio {entry['id']}:{slot}")
        if record["settings"]["text"]!=text: raise ValueError(f"Stale audio: {entry['id']}:{slot}")
        path=DIRECTORY / record["file"]
        if not path.exists(): raise ValueError(f"Missing media: {path}")
        if verify and hashlib.sha256(path.read_bytes()).hexdigest()!=record["sha256"]: raise ValueError(f"Bad audio checksum: {path}")
        media.append(path)
        return f"[sound:{path.name}]"
    examples=''.join(f'<div class="example"><div lang="de">{html.escape(e["de"])}</div><div class="en">{html.escape(e["en"])}</div>{sound(f"s{i}",e["de"])}</div>' for i,e in enumerate(entry["examples"],1))
    fields={"EntryID":entry["id"],"German":entry["german"],"English":entry["english"],"CueDE":entry["cue_de"],"CueEN":entry["cue_en"],"Level":entry["level"],"POS":entry["pos"],"Grammar":entry["grammar"],"Usage":entry["usage"]}
    fields={k:html.escape(v) for k,v in fields.items()}
    from urllib.parse import quote
    source=f'Goethe {entry["level"]} source vocabulary; examples from your collection with editorial additions. Definitions/inflections adapted from <a href="https://en.wiktionary.org/wiki/{quote(entry["headword"])}#German">Wiktionary contributors</a> via Kaikki/Wiktextract, <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>. Qwen3-TTS synthetic German audio.'
    fields.update(Meanings=items(entry["meanings"]),Related=items(entry["related"]),Examples=examples,Audio=sound("word",entry["german"]),History=history_html(entry,notes),Source=source)
    assert set(fields)==set(FIELDS)
    return fields,media


def baseline(db,source_ids):
    ids=','.join(map(str,source_ids))
    columns=[r[1] for r in db.execute('pragma table_info(cards)') if r[1] not in {'did','mod','usn','queue'}]
    return {"review_log":digest_rows(db.execute('select * from revlog order by id')),
        "other_notes":digest_rows(db.execute(f'select * from notes where id not in ({ids}) order by id')),
        "other_cards":digest_rows(db.execute(f'select * from cards where nid not in ({ids}) order by id')),
        "goethe_card_scheduling":digest_rows(db.execute(f'select {",".join(columns)} from cards where nid in ({ids}) order by id')),
        "note_identities":digest_rows(db.execute('select id,guid from notes order by id')),
        "card_columns":columns}


def build(args):
    from anki.collection import Collection,NoteIdsLimit
    from anki.import_export_pb2 import ExportAnkiPackageOptions
    entries=json.loads(ENTRIES.read_text())
    groups=json.loads((BUILD / 'groups.json').read_text())
    if len(entries)!=len(groups): raise ValueError(f"Only {len(entries)}/{len(groups)} entries ready")
    if any(len(e['examples'])!=3 for e in entries): raise ValueError('Each entry must have three examples')
    notes={n['nid']:n for n in json.loads((BUILD / 'source-notes.json').read_text())}
    selected={e['source_note_id'] for e in entries}
    allids=set(notes)
    redundant=allids-selected
    manifest=json.loads(MANIFEST.read_text())
    # Validate every input before changing the isolated profile.
    fields={}; media=set()
    for e in entries:
        data,files=field_values(e,manifest,notes)
        fields[e['source_note_id']]=data;media.update(files)
    source=connect(BUILD / 'source.anki21')
    before=baseline(source,allids)
    OUT.mkdir(exist_ok=True)
    col=Collection(str((PROFILE / 'collection.anki2').resolve()))
    try:
        # Reruns update the same note type and original note/card identities.
        model=col.models.by_name('Goethe vocabulary · progressive 2026')
        if model is None:
            model=col.models.new('Goethe vocabulary · progressive 2026')
            for name in FIELDS: col.models.add_field(model,col.models.new_field(name))
            for name,front in [('DE → EN',FRONT_DE),('EN → DE',FRONT_EN)]:
                template=col.models.new_template(name);template.update(qfmt=front,afmt=BACK);col.models.add_template(model,template)
            model['css']=STYLE;col.models.add(model)
        else:
            for t,front in zip(model['tmpls'],[FRONT_DE,FRONT_EN]):t.update(qfmt=front,afmt=BACK)
            model['css']=STYLE;col.models.update(model)
        by_mid=collections.defaultdict(list)
        for nid in selected: by_mid[col.get_note(nid).mid].append(nid)
        for mid,nids in by_mid.items():
            if mid==model['id']:continue
            old=col.models.get(mid)
            old_fields={f['name']:f['ord'] for f in old['flds']}
            de,en=('de_word','en_word') if 'de_word' in old_fields else (('Wort_DE','Wort_EN') if 'Wort_DE' in old_fields else ('base_d','base_e'))
            request=col.models.change_notetype_info(old_notetype_id=mid,new_notetype_id=model['id']).input
            request.note_ids.extend(nids);request.new_templates[:]=[0,1];request.new_fields[:]=[-1]*len(FIELDS)
            request.new_fields[FIELDS.index('German')]=old_fields[de];request.new_fields[FIELDS.index('English')]=old_fields[en]
            col.models.change_notetype_of_notes(request)
        decks={level:col.decks.id(f'Goethe vocabulary::{level}') for level in LEVELS}
        source_config=col.decks.config_dict_for_deck_id(next(iter(notes.values()))['deck_id'])
        config=next((c for c in col.decks.all_config() if c['name']=='Goethe vocabulary · audio'),None)
        if config is None:config=col.decks.add_config('Goethe vocabulary · audio',clone_from=source_config)
        config['autoplay']=True;config['replayq']=False;col.decks.update_config(config)
        for did in decks.values():
            deck=col.decks.get(did);deck['conf']=config['id'];col.decks.update(deck)
        for index,e in enumerate(entries,1):
            note=col.get_note(e['source_note_id'])
            for name,value in fields[note.id].items():note[name]=value
            note.add_tag('goethe_clean_2026');note.add_tag(e['level'].lower());col.update_note(note)
            col.set_deck([c.id for c in note.cards()],decks[e['level']])
            if index%500==0:print(f'Updated {index}/{len(entries)} notes',flush=True)
        for path in sorted(media):col.media.write_data(path.name,path.read_bytes())
        active_cards=[c['id'] for n in notes.values() if n['nid'] in selected for c in n['cards']]
        suspended_active=[c['id'] for n in notes.values() if n['nid'] in selected for c in n['cards'] if c['queue']<0]
        if suspended_active:col.sched.unsuspend_cards(suspended_active)
        archive_cards=[c['id'] for nid in redundant for c in notes[nid]['cards']]
        col.set_deck(archive_cards,col.decks.id(ARCHIVE));col.sched.suspend_cards(archive_cards)
        after=baseline(col.db,allids)
        checks={key:before[key]==after[key] for key in before if key!='card_columns'}
        checks['all_archive_cards_suspended']=col.db.scalar(f'select count(*) from cards where nid in ({",".join(map(str,redundant))}) and queue!=-1')==0
        checks['all_active_cards_available']=col.db.scalar(f'select count(*) from cards where nid in ({",".join(map(str,selected))}) and queue<0')==0
        checks['all_original_note_and_card_counts_preserved']=col.note_count()==197231 and col.card_count()==245305
        checks['original_duplicate_notes_unchanged']=digest_rows(source.execute(f'select * from notes where id in ({",".join(map(str,redundant))}) order by id'))==digest_rows(col.db.execute(f'select * from notes where id in ({",".join(map(str,redundant))}) order by id'))
        if not all(checks.values()):raise AssertionError(json.dumps(checks))
        report={'notes':len(entries),'cards':len(active_cards),'levels':dict(collections.Counter(e['level'] for e in entries)), 'archived_notes':len(redundant),'archived_cards':len(archive_cards),'retained_cards_unsuspended':len(suspended_active),'media_files':len(media),'all_collection_review_records':before['review_log'],'checks':checks,'checked_card_columns':before['card_columns']}
        atomic_json(OUT / 'migration-validation.json',report)
        print(json.dumps(report,indent=2),flush=True)
        options=ExportAnkiPackageOptions(with_scheduling=True,with_media=True,with_deck_configs=True)
        for level in LEVELS:
            package=OUT / f'Goethe-{level}-WITH-HISTORY.apkg'
            col.export_anki_package(out_path=str(package.resolve()),options=options,limit=NoteIdsLimit(note_ids=[e['source_note_id'] for e in entries if e['level']==level]))
            print(f'Exported {package}',flush=True)
        col.export_anki_package(out_path=str((OUT / 'Goethe-duplicate-archive-WITH-HISTORY.apkg').resolve()),options=options,limit=NoteIdsLimit(note_ids=list(redundant)))
        if not args.skip_collection:
            col.export_collection_package(out_path=str((OUT / 'German-collection-cleaned-WITH-HISTORY.colpkg').resolve()),include_media=True,legacy=False)
            print('Exported complete migrated collection with all original decks and media',flush=True)
        (OUT/'IMPORT-INSTRUCTIONS.md').write_text(IMPORT_INSTRUCTIONS)
        packages=sorted(path for path in OUT.iterdir() if path.suffix in {'.apkg','.colpkg'})
        (OUT/'SHA256SUMS').write_text(''.join(f'{file_sha256(path)}  {path.name}\n' for path in packages))
    finally:
        col.close();source.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-collection',action='store_true')
    build(parser.parse_args())
