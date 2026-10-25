"""Batch vocabulary candidate review. Reads a worklist; never overwrites it.

Run from Jupyter with runpy.run_path(...)["run_batch"](mapping_file).
Only diagnosis code strings and public concept IDs are sent to OHDSI.
"""
import concurrent.futures
import csv
import datetime
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

BASE = 'https://atlas-demo.ohdsi.org/WebAPI/vocabulary/SYNPUF1K/'
MAP_RELATION = 'Non-standard to Standard map (OMOP)'
FIELDS = ['source_code','query_candidate','event_count','source_vocabulary',
          'source_concept_id','source_concept_name','source_validity',
          'target_concept_id','target_concept_name','target_vocabulary',
          'target_domain','target_standard_status','target_validity',
          'relationship','review_status','notes','source_evidence_url',
          'target_evidence_url','vocabulary_version','checked_at_utc']

def _get(path, cache):
    filename = cache / (hashlib.sha256(path.encode()).hexdigest() + '.json')
    if filename.exists():
        return json.loads(filename.read_text(encoding='utf-8'))
    last_error = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(BASE + path, headers={'Accept':'application/json'})
            with urllib.request.urlopen(req, timeout=20) as response:
                result = json.load(response)
            filename.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            return result
        except Exception as error:
            last_error = error
            if attempt == 0:
                time.sleep(1)
    raise last_error

def _save(path, rows, fields):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)

def run_batch(worklist, workers=3):
    worklist = Path(worklist).expanduser().resolve()
    original_bytes = worklist.read_bytes()
    with worklist.open(encoding='utf-8-sig', newline='') as handle:
        items = list(csv.DictReader(handle))
    if len(items) != 72 or len({r['source_code'] for r in items}) != 72:
        raise ValueError('Expected the complete worklist of 72 unique source codes.')
    # Separate run folders preserve previous runs and the manual worklist.
    run_dir = worklist.parent / ('batch_review_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    run_dir.mkdir(parents=True)
    cache = worklist.parent / 'batch_vocabulary_cache'
    cache.mkdir(exist_ok=True)
    info = _get('info', cache)
    version = info.get('version', 'Unknown')
    checked = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (run_dir/'vocabulary_info.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    verified = [r for r in items if r.get('mapping_status','').startswith('Athena mapping verified')]
    pending = [r for r in items if r not in verified]
    rows, errors = [], []
    def base_row(item):
        row = dict.fromkeys(FIELDS, '')
        row.update(source_code=item['source_code'], event_count=item.get('event_count',''),
                   query_candidate=item.get('query_candidate',''), vocabulary_version=version,
                   checked_at_utc=checked)
        return row
    def query(item):
        code = item['source_code']
        query_code = '8550' if code == 'M85503' else item['query_candidate']
        results, failures = [], []
        row = base_row(item)
        try:
            found = _get('search/' + urllib.parse.quote(query_code, safe=''), cache)
            if not isinstance(found, list):
                raise ValueError('Unexpected search response format.')
            allowed = {'ICDO3'} if code == 'M85503' else {'ICD10','ICD10AM','ICD10CM'}
            expected = code[1:] if code == 'M85503' else code
            exact = [c for c in found if c.get('VOCABULARY_ID') in allowed
                     and str(c.get('CONCEPT_CODE','')).replace('.','').replace('/','') == expected]
            if not exact:
                results.append({**row, 'review_status':'manual_review_no_exact_source_candidate',
                                'notes':'No exact code candidate in the searched vocabularies. Do not truncate the code.'})
            for source in exact:
                source_id = source['CONCEPT_ID']
                sr = {**row, 'source_vocabulary':source['VOCABULARY_ID'],
                      'source_concept_id':source_id, 'source_concept_name':source['CONCEPT_NAME'],
                      'source_validity':source.get('INVALID_REASON_CAPTION', source.get('INVALID_REASON','')),
                      'source_evidence_url':BASE + f'concept/{source_id}/related'}
                try:
                    related = _get(f'concept/{source_id}/related', cache)
                    if not isinstance(related, list):
                        raise ValueError('Unexpected relationship response format.')
                    targets = [c for c in related if any(r.get('RELATIONSHIP_NAME') == MAP_RELATION
                               for r in c.get('RELATIONSHIPS',[]))]
                    if not targets:
                        results.append({**sr, 'review_status':'manual_review_no_maps_to',
                                        'notes':'Exact source candidate found but no standard mapping returned.'})
                    for target in targets:
                        standard = target.get('STANDARD_CONCEPT') == 'S'
                        valid = target.get('INVALID_REASON') in ('V', None, '')
                        results.append({**sr, 'target_concept_id':target['CONCEPT_ID'],
                            'target_concept_name':target['CONCEPT_NAME'],
                            'target_vocabulary':target.get('VOCABULARY_ID',''),
                            'target_domain':target.get('DOMAIN_ID',''),
                            'target_standard_status':'Standard' if standard else 'Not standard',
                            'target_validity':target.get('INVALID_REASON_CAPTION','Valid' if valid else 'Invalid'),
                            'relationship':'Maps to',
                            'review_status':'candidate_pending_local_source_confirmation' if standard and valid else 'manual_review_invalid_or_nonstandard_target',
                            'notes':'Demo snapshot candidate only; alternative source vocabularies must not be combined as approved mappings.',
                            'target_evidence_url':BASE + f"concept/{target['CONCEPT_ID']}"})
                except Exception as error:
                    message = type(error).__name__ + ': ' + str(error)
                    results.append({**sr, 'review_status':'relationship_query_failed', 'notes':message})
                    failures.append({'source_code':code,'stage':f'relationships:{source_id}','error':message})
        except Exception as error:
            message = type(error).__name__ + ': ' + str(error)
            results.append({**row, 'review_status':'search_query_failed','notes':message})
            failures.append({'source_code':code,'stage':'search','error':message})
        return results, failures
    print('Vocabulary snapshot:', version, flush=True)
    print('Previously verified codes preserved:', len(verified), flush=True)
    print('Codes to query:', len(pending), flush=True)
    for item in verified:
        r = base_row(item)
        for field in ('target_concept_id','target_concept_name','target_vocabulary','target_domain',
                      'target_standard_status','target_validity','source_evidence_url','target_evidence_url'):
            r[field] = item.get(field,'')
        r.update(source_vocabulary=item.get('evidence_source_vocabulary',''),
                 source_concept_id=item.get('evidence_source_concept_id',''),
                 review_status='previous_Athena_evidence_preserved',
                 vocabulary_version='See original Athena evidence; not the demo snapshot',
                 checked_at_utc=item.get('checked_date',''),
                 notes='Original manual evidence preserved; local source vocabulary remains pending.')
        rows.append(r)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1,min(int(workers),4))) as pool:
        jobs = {pool.submit(query,item):item['source_code'] for item in pending}
        for index, future in enumerate(concurrent.futures.as_completed(jobs),1):
            result, failures = future.result()
            rows.extend(result)
            errors.extend(failures)
            print(f'[{index}/{len(pending)}] {jobs[future]}: {len(result)} candidate/review rows; {len(failures)} query errors', flush=True)
    rows.sort(key=lambda r:(r['source_code'],str(r['source_vocabulary']),str(r['source_concept_id']),str(r['target_concept_id'])))
    assert {r['source_code'] for r in rows} == {r['source_code'] for r in items}
    assert worklist.read_bytes() == original_bytes, 'Manual worklist changed during the batch.'
    _save(run_dir/'batch_mapping_candidates.csv', rows, FIELDS)
    _save(run_dir/'query_errors.csv', errors, ['source_code','stage','error'])
    summary = {'source_codes_accounted_for':72, 'previous_Athena_codes_preserved':len(verified),
               'codes_queried':len(pending), 'candidate_or_review_rows':len(rows),
               'query_errors':len(errors),'original_worklist_unchanged':True,
               'vocabulary_snapshot':version,'status':'candidates_require_review'}
    (run_dir/'batch_summary.json').write_text(json.dumps(summary,indent=2), encoding='utf-8')
    print('\nBATCH FINISHED. These are review candidates, not approved mappings.', flush=True)
    print('Query errors:', len(errors), flush=True)
    print('Original worklist unchanged.', flush=True)
    print('Results saved to:', run_dir, flush=True)
    return run_dir

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--worklist', required=True)
    run_batch(parser.parse_args().worklist)
