"""Person 3 lab ETL. Run from repository root with PYTHONPATH=src.
Example: PYTHONPATH=src python person3_labs/etl_labs.py --input-dir private/raw_labs --key private/group_key.hex --mapping person3_labs/labs_mapping.csv
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
    p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,required=True);p.add_argument('--key',type=Path,required=True);p.add_argument('--mapping',type=Path,required=True);p.add_argument('--output-dir',type=Path,default=Path('private/person3_output'));p.add_argument('--strict',action='store_true');a=p.parse_args()
    key=load_key(a.key)
    with a.mapping.open(encoding='utf-8-sig',newline='') as f: mappings={r['source_test_code']:r for r in csv.DictReader(f)}
    output=[];issues=[];used=set();persons=set();counts=Counter();unresolved=Counter()
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
        if not cid or cid=='0':unresolved[code]+=1;issues.append((code,'Missing verified standard measurement concept'))
        raw=txt(r.get('Test_Result'));v=number(raw);operator=''
        if raw.startswith(('<','>','<=' ,'>=')):
            # preserve inequality in source value; no invented operator ID
            v=number(re.sub(r'^[<>]=?','',raw));issues.append((code,'Inequality operator requires Athena concept verification'))
        elif raw and v=='':issues.append((code,'Categorical result requires value_as_concept_id mapping'))
        unit=txt(m.get('unit_concept_id'))
        if not unit:issues.append((code,'Unit absent in source; leave blank'))
        output.append(dict(measurement_id=mid,person_id=pid,measurement_concept_id=cid or '0',measurement_date=shifted.date().isoformat(),measurement_datetime=shifted.isoformat(sep=' '),measurement_time=shifted.strftime('%H:%M:%S'),measurement_type_concept_id='0',operator_concept_id=operator,value_as_number=v,value_as_concept_id='',unit_concept_id=unit,range_low=number(r.get('Minimum_Range')),range_high=number(r.get('Maximum_Range')),provider_id='',visit_occurrence_id='',visit_detail_id='',measurement_source_value=code,measurement_source_concept_id='0',unit_source_value='',unit_source_concept_id='0',value_source_value=raw,measurement_event_id='',meas_event_field_concept_id=''))
        counts[code]+=1
    a.output_dir.mkdir(parents=True,exist_ok=True)
    with (a.output_dir/'MEASUREMENT.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(output)
    with (a.output_dir/'lab_quality_report.txt').open('w',encoding='utf-8') as f:
        f.write(f'Rows: {len(output)}\nDistinct patients: {len(persons)}\nDistinct test codes: {len(counts)}\nUnmapped rows: {sum(unresolved.values())}\n')
        f.write('All visit_occurrence_id values intentionally blank: no exact source visit linkage.\n')
        f.write('measurement_type_concept_id=0 is a PLACEHOLDER, not a validated final OMOP type.\n')
        f.write('Source data has no explicit unit field.\n')
        for code,count in sorted(unresolved.items()):f.write(f'UNMAPPED {code}: {count}\n')
        for code,note in sorted(set(issues)):f.write(f'REVIEW {code}: {note}\n')
    print(f'Processed {len(output)} rows, {len(persons)} patients, {len(counts)} test codes; {sum(unresolved.values())} rows without verified concepts.')
    if a.strict and (unresolved or any('Categorical' in n or 'Inequality' in n for _,n in issues)):
        sys.exit('Strict validation failed: resolve mapping and result review flags before final submission.')
if __name__=='__main__':main()
