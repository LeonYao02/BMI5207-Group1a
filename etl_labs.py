"""Person 3 lab ETL. Run from repository root with PYTHONPATH=src.
Example: PYTHONPATH=src python person3/etl_labs.py --input-dir private/raw_labs --key private/group_key.hex --mapping person3/labs_mapping.csv
Do not publish raw input, private key, or output with raw identifiers.
"""
import argparse,csv,re,sys
from pathlib import Path
from collections import Counter
from datetime import datetime
from openpyxl import load_workbook
from bmi5207.shared import load_key, person_id, shift_datetime, digest, ID_MAX

FIELDS=['measurement_id','person_id','measurement_concept_id','measurement_date','measurement_datetime','measurement_time','measurement_type_concept_id','operator_concept_id','value_as_number','value_as_concept_id','unit_concept_id','range_low','range_high','provider_id','visit_occurrence_id','visit_detail_id','measurement_source_value','measurement_source_concept_id','unit_source_value','unit_source_concept_id','value_source_value','measurement_event_id','meas_event_field_concept_id']

def txt(x): return '' if x is None else str(x).strip()
def number(x):
    s=txt(x)
    if not s:return ''
    try:return float(s)
    except ValueError:return ''
def parse_result(raw):
    """Return numeric value, OMOP operator ID, or text for review.
    Athena standard operator concepts: < 4171756, <= 4171754, > 4172703, >= 4171755.
    These are verified at runtime against CONCEPT.csv when provided.
    """
    raw=txt(raw)
    m=re.fullmatch(r'\s*(<=|>=|<|>|≤|≥)\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*',raw)
    if m:
        op={'<':'<','>':'>','<=':'<=','>=':'>=','≤':'<=','≥':'>='}[m.group(1)]
        return float(m.group(2)),op,'INEQUALITY'
    n=number(raw)
    return n,'','NUMERIC' if n!='' else ('MISSING' if not raw else 'TEXT')

def rows_from_files(folder):
    for file in sorted(folder.glob('lab results_patient *.xlsx')):
        wb=load_workbook(file,read_only=True,data_only=True)
        for sh in wb:
            it=iter(sh.values); header=next(it); keys=[txt(x) for x in header]
            for i,row in enumerate(it,2):
                r=dict(zip(keys,row))
                if not txt(r.get('Test_Code')):continue
                yield file.name,sh.title,i,r
        wb.close()
def main():
    p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,required=True);p.add_argument('--key',type=Path,required=True);p.add_argument('--mapping',type=Path,required=True);p.add_argument('--output-dir',type=Path,default=Path('private/person3_output'));p.add_argument('--strict',action='store_true');p.add_argument('--vocabulary',type=Path,help='Athena CONCEPT.csv for runtime ID validation');a=p.parse_args()
    key=load_key(a.key)
    with a.mapping.open(encoding='utf-8-sig',newline='') as f: mappings={r['source_test_code']:r for r in csv.DictReader(f)}
    output=[];issues=[];used=set();persons=set();counts=Counter();unresolved=Counter(); kinds=Counter()
    verified={}
    value_concepts={}
    if a.vocabulary:
        with a.vocabulary.open(encoding='utf-8') as vf:
            for v in csv.DictReader(vf,delimiter='\t'):
                if v['concept_id'] in {txt(x.get('measurement_concept_id')) for x in mappings.values()}:
                    verified[v['concept_id']]=v
                if v['concept_id'] in ('45878244','45884084','4305306') and v['standard_concept']=='S' and not v['invalid_reason'] and v['domain_id']=='Meas Value':
                    value_concepts[v['concept_id']]=v
    type_valid=False
    if a.vocabulary:
        with a.vocabulary.open(encoding='utf-8') as vf:
            type_valid=any(v['concept_id']=='32856' and v['concept_name']=='Lab' and v['domain_id']=='Type Concept' and v['standard_concept']=='S' and not v['invalid_reason'] for v in csv.DictReader(vf,delimiter='	'))
    operator_ids={'<':'4171756','<=':'4171754','>':'4172704','>=':'4171755'}
    if a.vocabulary:
        with a.vocabulary.open(encoding='utf-8') as vf:
            found={v['concept_id']:v for v in csv.DictReader(vf,delimiter='\t') if v['concept_id'] in operator_ids.values()}
        operator_ids={k:(v if v in found and found[v]['standard_concept']=='S' and not found[v]['invalid_reason'] else '') for k,v in operator_ids.items()}
    else:operator_ids={k:'' for k in operator_ids}
    for file,sheet,rowno,r in rows_from_files(a.input_dir):
        pn=txt(r.get('Patient_No'));code=txt(r.get('Test_Code'));m=mappings.get(code,{})
        if not pn:raise ValueError(f'Missing patient number at {file}:{rowno}')
        pid=person_id(key,pn);persons.add(pid)
        shifted=shift_datetime(key,pn,r['Result_Test_Date'])
        # Event IDs deterministic per source filename, sheet, and row; no source identifiers exported.
        id_seed=digest(key,'lab-event',pn,file,sheet,str(rowno))
        mid=int.from_bytes(id_seed[:8],'big')%ID_MAX+1
        if mid in used:raise ValueError('Measurement ID collision')
        used.add(mid)
        cid=txt(m.get('measurement_concept_id'))
        if cid and (txt(m.get('mapping_status')).lower()!='confirmed' or cid!=txt(m.get('strict_measurement_concept_id'))):
            issues.append((code,'Non-confirmed candidate cannot be promoted'));cid=''
        if cid and not a.vocabulary:
            issues.append((code,'Vocabulary verification required for promoted mapping'));cid=''
        if cid and a.vocabulary:
            v=verified.get(cid)
            if not v or v['domain_id']!='Measurement' or v['standard_concept']!='S' or v['invalid_reason']:
                issues.append((code,'Invalid nonstandard or non-Measurement concept ID rejected'));cid=''
        if not cid or cid=='0':unresolved[code]+=1;issues.append((code,'Missing verified standard measurement concept'))
        raw=txt(r.get('Test_Result'));v,op,kind=parse_result(raw);kinds[kind]+=1
        # OMOP CDM 5.4 MEASUREMENT.value_source_value is VARCHAR(50).
        # Preserve full source only in private input; flag any truncation.
        if len(raw)>50: issues.append((code,'Source result exceeds OMOP VARCHAR(50); value_source_value truncated to 50 characters'))
        operator=operator_ids.get(op,'')
        if op and not operator:issues.append((code,'Operator concept unavailable or unverified; original inequality retained'))
        value_cid=''
        # Source meaning checked against official Athena Meas Value concepts; never infer from free text alone.
        if kind=='TEXT':
            result_map={('ABO','B'):'45878244',('RH','positive'):'45884084',('BSAG','non-reactive'):'4305306'}
            proposed=result_map.get((code,raw if code=='ABO' else raw.lower()))
            if proposed and proposed in value_concepts and cid: value_cid=proposed
            else: issues.append((code,'Qualitative result not standardized; source text retained'))
        unit=txt(m.get('unit_concept_id')) if txt(m.get('unit_verified'))=='YES' else ''
        if not unit:issues.append((code,'Unit not verified; left null'))
        output.append(dict(measurement_id=mid,person_id=pid,measurement_concept_id=cid or '0',measurement_date=shifted.date().isoformat(),measurement_datetime=shifted.isoformat(sep=' '),measurement_time=shifted.strftime('%H:%M:%S'),measurement_type_concept_id='32856' if a.vocabulary and type_valid else '0',operator_concept_id=operator,value_as_number=v,value_as_concept_id=value_cid,unit_concept_id=unit,range_low=number(r.get('Minimum_Range')),range_high=number(r.get('Maximum_Range')),provider_id='',visit_occurrence_id='',visit_detail_id='',measurement_source_value=code,measurement_source_concept_id='0',unit_source_value=txt(m.get('unit_source_value')) if txt(m.get('unit_verified'))=='YES' else '',unit_source_concept_id='0',value_source_value=raw[:50],measurement_event_id='',meas_event_field_concept_id=''))
        counts[code]+=1
    a.output_dir.mkdir(parents=True,exist_ok=True)
    with (a.output_dir/'MEASUREMENT.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(output)
    with (a.output_dir/'lab_quality_report.txt').open('w',encoding='utf-8') as f:
        f.write(f'Rows: {len(output)}\nDistinct patients: {len(persons)}\nDistinct test codes: {len(counts)}\nUnmapped rows: {sum(unresolved.values())}\nResult types: {dict(kinds)}\n')
        f.write('All visit_occurrence_id values intentionally blank: no exact source visit linkage.\n')
        f.write('measurement_type_concept_id=32856 (Lab) when verified against Athena; otherwise 0 placeholder.\n')
        f.write('Source data has no explicit unit field.\n')
        for code,count in sorted(unresolved.items()):f.write(f'UNMAPPED {code}: {count}\n')
        for code,note in sorted(set(issues)):f.write(f'REVIEW {code}: {note}\n')
    print(f'Processed {len(output)} rows, {len(persons)} patients, {len(counts)} test codes; {sum(unresolved.values())} rows without verified concepts.')
    if a.strict and (unresolved or any(k in ('TEXT','INEQUALITY') for k in kinds) or any(not txt(x.get('unit_verified'))=='YES' for x in mappings.values())):
        sys.exit('Strict validation failed: resolve mapping and result review flags before final submission.')
if __name__=='__main__':main()
