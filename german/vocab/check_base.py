"""Native import checks for both directions, playback queues and review history."""
from __future__ import annotations
import argparse
import collections
import hashlib
import html
import json
from pathlib import Path
import tempfile

from anki.collection import Collection
from anki.import_export_pb2 import ImportAnkiPackageRequest,ImportAnkiPackageOptions
from german.vocab.build_base import OUT,PROFILE
from german.vocab.source import ENTRIES, VOCAB,BUILD,connect
from german.vocab.content import LEVELS
from german.vocab.audio import MANIFEST,atomic_json
from german.vocab.pilot_validate import digest_rows


def check_cards(col,entries,manifest):
    count=0
    for entry in entries:
        note=col.get_note(entry['source_note_id'])
        assert note['EntryID']==entry['id']
        cards=note.cards();assert len(cards)==2
        expected=[manifest[f"{entry['id']}:{s}"]['file'] for s in ['word','s1','s2','s3']]
        for card in cards:
            front=html.unescape(card.question());back=html.unescape(card.answer())
            assert not any(x in front for x in ['Forms & grammar','Your previous study history','<div class="example">'])
            assert '{{' not in front and '{{' not in back
            assert entry['german'] in (front if card.ord==0 else back)
            assert entry['english'] in (front if card.ord==1 else back)
            assert [x.filename for x in card.question_av_tags()]==(expected[:1] if card.ord==0 else [])
            assert [x.filename for x in card.answer_av_tags()]==expected
            assert '15 October 2026' in back and 'Card Info' in back
            assert '<li></li>' not in back
            for example in entry['examples']:
                assert example['de'] in back and example['en'] in back
            count+=1
    return count


def assert_card_rows(source, destination, where, source_today, destination_today):
    """Compare schedules, accounting for Anki's collection-day rebasing.

    Review-card ``due`` values are day numbers relative to the collection's
    creation date.  Native APKG import rebases those values when the target
    collection has a different creation date, while preserving the actual due
    day.  Every other identity/scheduling/FSRS field must remain byte-exact.
    """
    columns=[r[1] for r in source.execute('pragma table_info(cards)') if r[1] not in {'did','mod','usn','queue','due'}]
    assert digest_rows(source.execute(f'select {",".join(columns)} from cards where {where} order by id'))==digest_rows(destination.db.execute(f'select {",".join(columns)} from cards order by id'))
    source_due={row[0]:(row[1],row[2]) for row in source.execute(f'select id,type,due from cards where {where}')}
    destination_due={row[0]:(row[1],row[2]) for row in destination.db.execute('select id,type,due from cards')}
    assert source_due.keys()==destination_due.keys()
    for card_id,(card_type,due) in source_due.items():
        imported_type,imported_due=destination_due[card_id]
        assert imported_type==card_type
        if card_type==2:
            assert due-source_today==imported_due-destination_today
        else:
            assert due==imported_due


def main(args):
    entries=json.loads(ENTRIES.read_text())
    manifest=json.loads(MANIFEST.read_text())
    # A lexical headword must not be repeated *across levels*. Distinct senses
    # and parts of speech within one level are intentionally retained (for
    # example die Bank "bench" / "bank", or der Arm / arm).
    headword_levels=collections.defaultdict(set)
    german_entries=collections.defaultdict(list)
    for entry in entries:
        headword_levels[entry['headword'].casefold()].add(entry['level'])
        german_entries[entry['german'].casefold()].append(entry)
    assert all(len(levels)==1 for levels in headword_levels.values())
    # Identically displayed homonyms need visible disambiguation on both
    # directions, while capitalization-distinguished entries such as Sie/sie
    # remain independently identifiable.
    for duplicates in german_entries.values():
        if len(duplicates)>1 and len({entry['german'] for entry in duplicates})==1:
            assert all(entry.get('cue_de') and entry.get('cue_en') for entry in duplicates)
    assert {level:sum(entry['level']==level for entry in entries) for level in LEVELS}=={'A1':784,'A2':652,'B1':1481}
    source_probe=Collection(str(BUILD/'source.anki21'))
    source_today=source_probe.sched.today
    source_probe.close()
    source=connect(BUILD / 'source.anki21')
    from anki.import_export_pb2 import ImportAnkiPackageOptions
    options=ImportAnkiPackageOptions(with_scheduling=True)
    with tempfile.TemporaryDirectory(prefix='goethe-full-import-') as tmp:
        col=Collection(str(Path(tmp)/'collection.anki2'))
        try:
            for level in LEVELS:
                result=col.import_anki_package(ImportAnkiPackageRequest(package_path=str((OUT/f'Goethe-{level}-WITH-HISTORY.apkg').resolve()),options=options))
                print(f'Imported {level}: {len(result.log.new)} notes',flush=True)
            assert col.note_count()==len(entries) and col.card_count()==len(entries)*2
            rendered=check_cards(col,entries,manifest)
            ids=','.join(str(e['source_note_id']) for e in entries)
            assert_card_rows(source,col,f'nid in ({ids})',source_today,col.sched.today)
            actual_reviews=digest_rows(col.db.execute('select * from revlog order by id'))
            # Anki import assigns local update sequence numbers; actual review
            # values, IDs, timestamps and associations must remain identical.
            revcols=[r[1] for r in source.execute('pragma table_info(revlog)') if r[1]!='usn']
            assert digest_rows(source.execute(f'select {",".join(revcols)} from revlog where cid in (select id from cards where nid in ({ids})) order by id'))==digest_rows(col.db.execute(f'select {",".join(revcols)} from revlog order by id'))
            media=col.media.check();assert not media.missing,list(media.missing)
            assert col.db.scalar('select count(*) from cards where queue<0')==0
            for level in LEVELS:
                did=col.decks.id(f'Goethe vocabulary::{level}')
                assert col.decks.config_dict_for_deck_id(did)['autoplay'] is True
            report={'native_import':'passed','notes':len(entries),'cards_rendered':rendered,'progressive_level_counts':{'A1':784,'A2':652,'B1':1481},'unique_headwords_across_levels':True,'original_card_ids_and_schedules':'preserved','original_review_records':actual_reviews['rows'],'word_on_German_prompt_only':True,'answer_playback_order':['word','sentence 1','sentence 2','sentence 3'],'missing_media':list(media.missing),'unused_media':list(media.unused),'visible_history_is_labelled_snapshot':True}
        finally:col.close();source.close()

    source=connect(BUILD / 'source.anki21')
    source_notes=json.loads((BUILD/'source-notes.json').read_text())
    selected={entry['source_note_id'] for entry in entries}
    redundant=sorted({note['nid'] for note in source_notes}-selected)
    redundant_ids=','.join(map(str,redundant))
    with tempfile.TemporaryDirectory(prefix='goethe-archive-import-') as tmp:
        archive=Collection(str(Path(tmp)/'collection.anki2'))
        try:
            archive.import_anki_package(ImportAnkiPackageRequest(package_path=str((OUT/'Goethe-duplicate-archive-WITH-HISTORY.apkg').resolve()),options=options))
            assert archive.note_count()==len(redundant)
            assert archive.card_count()==len(redundant)*2
            assert archive.db.scalar('select count(*) from cards where queue!=-1')==0
            assert digest_rows(source.execute(f'select id,guid from notes where id in ({redundant_ids}) order by id'))==digest_rows(archive.db.execute('select id,guid from notes order by id'))
            assert_card_rows(source,archive,f'nid in ({redundant_ids})',source_today,archive.sched.today)
            revcols=[r[1] for r in source.execute('pragma table_info(revlog)') if r[1]!='usn']
            source_review=digest_rows(source.execute(f'select {",".join(revcols)} from revlog where cid in (select id from cards where nid in ({redundant_ids})) order by id'))
            archive_review=digest_rows(archive.db.execute(f'select {",".join(revcols)} from revlog order by id'))
            assert source_review==archive_review
            report['duplicate_archive']={'native_import':'passed','notes':len(redundant),'cards':len(redundant)*2,'all_cards_suspended':True,'original_note_and_card_identities':'preserved','original_schedules_and_fsrs_data':'preserved','original_review_records':archive_review['rows']}
        finally:archive.close();source.close()

    from anki._backend import RustBackend
    source=connect(BUILD/'source.anki21')
    selected_ids=','.join(map(str,sorted(selected)))
    with tempfile.TemporaryDirectory(prefix='goethe-colpkg-import-',dir=BUILD) as tmp:
        root=Path(tmp); col_path=root/'collection.anki2'; media_dir=root/'collection.media'; media_db=root/'collection.media.db2'
        RustBackend().import_collection_package(col_path=str(col_path),backup_path=str((OUT/'German-collection-cleaned-WITH-HISTORY.colpkg').resolve()),media_folder=str(media_dir),media_db=str(media_db))
        full=Collection(str(col_path))
        try:
            assert full.note_count()==197231 and full.card_count()==245305
            assert digest_rows(source.execute('select id,guid from notes order by id'))==digest_rows(full.db.execute('select id,guid from notes order by id'))
            full_cardcols=[r[1] for r in source.execute('pragma table_info(cards)') if r[1] not in {'did','mod','usn','queue'}]
            assert digest_rows(source.execute(f'select {",".join(full_cardcols)} from cards order by id'))==digest_rows(full.db.execute(f'select {",".join(full_cardcols)} from cards order by id'))
            full_revcols=[r[1] for r in source.execute('pragma table_info(revlog)') if r[1]!='usn']
            assert digest_rows(source.execute(f'select {",".join(full_revcols)} from revlog order by id'))==digest_rows(full.db.execute(f'select {",".join(full_revcols)} from revlog order by id'))
            assert full.db.scalar(f'select count(*) from cards where nid in ({selected_ids}) and queue<0')==0
            assert full.db.scalar(f'select count(*) from cards where nid in ({redundant_ids}) and queue!=-1')==0
            unique_media={record['file']:record['sha256'] for record in manifest.values()}
            for name,digest in unique_media.items():
                path=media_dir/name
                assert path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==digest
            report['complete_collection']={'native_import':'passed','notes':full.note_count(),'cards':full.card_count(),'original_note_and_card_identities':'preserved','original_schedules_and_fsrs_data':'preserved','all_review_records':'preserved','active_cards_available':True,'duplicate_cards_suspended':True,'goethe_media_checksums_verified':len(unique_media)}
        finally:full.close();source.close()
    atomic_json(OUT/'package-validation.json',report)
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    main(p.parse_args())
