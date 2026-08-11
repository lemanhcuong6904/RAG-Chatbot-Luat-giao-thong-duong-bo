from __future__ import annotations
import re, json, csv, sqlite3, hashlib, unicodedata, shutil
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Any
import yaml

OUT = Path('/mnt/data/structured_sanction_layer')
OUT.mkdir(exist_ok=True)

SOURCES = {
 '35/2024/QH15': Path('/mnt/data/35-2024-QH15_Luat-Duong-bo.md'),
 '36/2024/QH15-P1': Path('/mnt/data/36-2024-QH15_Phan-1_Dieu-1-23.md'),
 '36/2024/QH15-P2': Path('/mnt/data/36-2024-QH15_Phan-2_Dieu-24-89.md'),
 '165/2024/NĐ-CP': Path('/mnt/data/165-2024-ND-CP_Huong-dan-Luat-Duong-bo.md'),
 '168/2024/NĐ-CP': Path('/mnt/data/168-2024-ND-CP_Xu-phat-TTATGT-Tru-diem-GPLX.md'),
 '238/2026/NĐ-CP': Path('/mnt/data/238-2026-ND-CP_Sua-doi-ND-168-2024.md'),
}

POINT_ORDER = ['a','b','c','d','đ','e','g','h','i','k','l','m','n','o','p','q','r','s','t','u','v','x','y']

ARTICLE_TAXONOMY = {
6: ('DRIVER',['CAR','FOUR_WHEEL_PASSENGER','FOUR_WHEEL_CARGO','CAR_SIMILAR']),
7: ('DRIVER',['MOTORCYCLE','MOPED','MOTORCYCLE_SIMILAR','MOPED_SIMILAR']),
8: ('DRIVER',['SPECIALIZED_MOTOR_VEHICLE']),
9: ('DRIVER',['BICYCLE','POWER_ASSISTED_BICYCLE','OTHER_NON_MOTORIZED']),
10: ('PEDESTRIAN',['PEDESTRIAN']),
11: ('ANIMAL_HANDLER',['ANIMAL','ANIMAL_DRAWN_VEHICLE']),
12: ('MIXED',[]),
13: ('DRIVER',['CAR','FOUR_WHEEL_PASSENGER','FOUR_WHEEL_CARGO','CAR_SIMILAR']),
14: ('DRIVER',['MOTORCYCLE','MOPED','MOTORCYCLE_SIMILAR','MOPED_SIMILAR']),
15: ('DRIVER',['NON_MOTORIZED']),
16: ('DRIVER',['SPECIALIZED_MOTOR_VEHICLE']),
17: ('DRIVER',['CAR','TRACTOR','CAR_SIMILAR']),
18: ('DRIVER',[]),
19: ('DRIVER',['SPECIALIZED_MOTOR_VEHICLE']),
20: ('DRIVER',['PASSENGER_CAR','CAR']),
21: ('DRIVER',['CARGO_CAR','TRACTOR','TRAILER','SEMI_TRAILER']),
22: ('DRIVER',['CAR']),
23: ('DRIVER',['CAR']),
24: ('DRIVER',['CAR']),
25: ('DRIVER',['SANITATION_CAR','WASTE_CAR']),
26: ('TRANSPORT_OPERATOR',[]),
27: ('DRIVER',['SCHOOL_TRANSPORT_CAR']),
28: ('DRIVER',['FOUR_WHEEL_PASSENGER','FOUR_WHEEL_CARGO']),
29: ('DRIVER',['ROAD_RESCUE_CAR']),
30: ('DRIVER',['AMBULANCE']),
31: ('MANUFACTURER_OR_SELLER',[]),
32: ('VEHICLE_OWNER',[]),
33: ('PASSENGER',[]),
34: ('DRIVER',['OVERSIZE_OR_OVERWEIGHT_VEHICLE']),
35: ('RACING_PARTICIPANT_OR_ORGANIZER',[]),
36: ('DRIVER',['MOTORCYCLE','MOPED','NON_MOTORIZED']),
37: ('DRIVER',['FOREIGN_PLATE_MOTOR_VEHICLE']),
38: ('DRIVER',['SPECIAL_ECONOMIC_ZONE_REGISTERED_VEHICLE']),
39: ('DRIVING_TRAINING_OR_TEST_ENTITY',[]),
40: ('VEHICLE_INSPECTION_ENTITY',[]),
}

def normalize_number_spaces(text:str)->str:
    # OCR/text-layer artifacts: stray vertical bar and wrapped thousand separators.
    text=text.replace('|',' ')
    return re.sub(r'(?<=\d)\.\s+(?=\d{3}(?:\.\d{3})*(?:\s|\.|đ|$))', '.', text)

def parse_frontmatter(text:str):
    if text.startswith('---'):
        m=re.match(r'^---\s*\n(.*?)\n---\s*\n',text,re.S)
        if m:
            try: meta=yaml.safe_load(m.group(1)) or {}
            except Exception: meta={}
            return meta,text[m.end():]
    return {},text

def slugify(s:str, maxlen=90):
    s=unicodedata.normalize('NFD',s)
    s=''.join(c for c in s if unicodedata.category(c)!='Mn').replace('đ','d').replace('Đ','D')
    s=re.sub(r'[^A-Za-z0-9]+','_',s).strip('_').upper()
    return s[:maxlen] or 'UNSPECIFIED'

def line_no(text:str, pos:int): return text.count('\n',0,pos)+1

def parse_articles(text:str):
    ms=list(re.finditer(r'^### Điều\s+(\d+)\.\s*(.*)$',text,re.M))
    out=[]
    for i,m in enumerate(ms):
        end=ms[i+1].start() if i+1<len(ms) else len(text)
        title=m.group(2).strip()
        body=text[m.end():end]
        # Repair title that wrapped onto next non-empty line before clause 1 (notably Điều 38).
        prefix=body.lstrip('\n')
        firstline=prefix.splitlines()[0].strip() if prefix.splitlines() else ''
        if firstline and not re.match(r'^\d+[a-z]?\.\s',firstline) and not firstline.startswith('#') and len(firstline)<180:
            title=(title+' '+firstline).strip()
            idx=body.find(firstline)
            body=body[:idx]+body[idx+len(firstline):]
        out.append({'article':int(m.group(1)),'title':title,'body':body.strip(),'start':m.start(),'end':end})
    return out

def split_clauses(body:str):
    # Sequential numbering avoids misreading wrapped money such as 1.000.000 as clause 1.
    lines=body.splitlines()
    clauses=[]; current=None; expected=1
    for ln in lines:
        raw=ln.rstrip()
        mm=re.match(r'^(\d+)([a-z]?)\.\s+(.*)$',raw)
        accept=False; key=None
        if mm:
            n=int(mm.group(1)); suff=mm.group(2)
            if n==expected and not suff:
                accept=True; expected+=1; key=str(n)
            elif n==expected-1 and suff: # e.g. 8a immediately after 8
                accept=True; key=f'{n}{suff}'
        if accept:
            if current: clauses.append(current)
            current={'clause':key,'text':raw[len(mm.group(1))+len(mm.group(2))+2:].strip(),'raw_lines':[raw]}
        else:
            if current:
                current['raw_lines'].append(raw)
                if raw.strip(): current['text'] += ('\n' if current['text'] else '') + raw.strip()
    if current: clauses.append(current)
    return clauses

def split_points(clause_text:str):
    # Repair inline OCR points such as '; 1) ...; m) ...' where '1)' is actually 'l)'.
    clause_text=re.sub(r'([:;])\s*\.?([a-zđA-ZĐ1])\)\s+', r'\1\n\2) ', clause_text)
    lines=clause_text.splitlines()
    points=[]; current=None; expected_idx=0; pre=[]
    for raw in lines:
        s=raw.strip()
        mm=re.match(r'^\.?([a-zđA-ZĐ1])\)\s+(.*)$',s)
        token=None
        if mm:
            token=mm.group(1).lower()
            if token in ('1','i') and expected_idx < len(POINT_ORDER) and POINT_ORDER[expected_idx]=='l': token='l'
        accept=False
        if token and expected_idx < len(POINT_ORDER) and token==POINT_ORDER[expected_idx]:
            accept=True; expected_idx+=1
        if accept:
            if current: points.append(current)
            current={'point':token,'text':mm.group(2).strip()}
        else:
            if current and s: current['text'] += ' '+s
            elif s: pre.append(s)
    if current: points.append(current)
    return ' '.join(pre).strip(), points

def money_values(text:str):
    vals=[]
    for m in re.finditer(r'(?<!\d)(\d{1,3}(?:\.\d{3})+|\d+)\s*đồng',normalize_number_spaces(text),re.I):
        vals.append(int(m.group(1).replace('.','')))
    return vals

def fine_ranges(text:str):
    t=normalize_number_spaces(text)
    pat=r'từ\s+(\d{1,3}(?:\.\d{3})+|\d+)\s*đồng\s+đến\s+(\d{1,3}(?:\.\d{3})+|\d+)\s*đồng'
    return [(int(a.replace('.','')),int(b.replace('.',''))) for a,b in re.findall(pat,t,re.I)]

def fine_caps(text:str):
    t=normalize_number_spaces(text)
    vals=[]
    for m in re.finditer(r'tổng mức phạt tiền tối đa không v[^\s]{0,6}\s+quá\s+(\d{1,3}(?:\.\d{3})+|\d+)\s*đồng',t,re.I):
        vals.append(int(m.group(1).replace('.','')))
    return vals

def infer_entity_variants(clause_text:str):
    t=' '.join(normalize_number_spaces(clause_text).split())
    low=t.lower().replace('đổi với','đối với')
    ranges=fine_ranges(t)
    caps=fine_caps(t)
    basis='PER_EXCESS_PERSON' if 'trên mỗi người vượt quá' in low else 'FLAT_RANGE'
    has_ind=bool(re.search(r'đối với\s+(?:chủ phương tiện là\s+)?cá nhân',low))
    has_org=bool(re.search(r'đối với\s+(?:chủ phương tiện là\s+)?tổ chức',low))
    if has_ind and has_org and len(ranges)>=2:
        return [('INDIVIDUAL',ranges[0][0],ranges[0][1],caps[0] if len(caps)>0 else None,basis),('ORGANIZATION',ranges[1][0],ranges[1][1],caps[1] if len(caps)>1 else None,basis)]
    if has_org and not has_ind and ranges:
        return [('ORGANIZATION',ranges[0][0],ranges[0][1],caps[0] if caps else None,basis)]
    if has_ind and not has_org and ranges:
        return [('INDIVIDUAL',ranges[0][0],ranges[0][1],caps[0] if caps else None,basis)]
    if ranges:
        return [('UNSPECIFIED',ranges[0][0],ranges[0][1],caps[0] if caps else None,basis)]
    return [('UNSPECIFIED',None,None,None,basis)]

def extract_behavior_no_points(clause_text:str,ptype:str):
    t=' '.join(normalize_number_spaces(clause_text).split()).strip()
    if ptype=='WARNING':
        return re.sub(r'^Phạt cảnh cáo\s*','',t,flags=re.I).strip(' ;.')
    if ptype=='CONFISCATION':
        return re.sub(r'^Tịch thu phương tiện\s+đối với\s*','',t,flags=re.I).strip(' ;.')
    # Fine: dual individual/organization ranges -> cut after second liable-entity marker.
    low=t.lower().replace('đổi với','đối với')
    org_matches=list(re.finditer(r'đối với\s+(?:chủ phương tiện là\s+)?tổ chức\s+',low))
    ind_matches=list(re.finditer(r'đối với\s+(?:chủ phương tiện là\s+)?cá nhân\s*[,;]?\s*',low))
    if ind_matches and org_matches:
        m=org_matches[0]
        return t[m.end():].strip(' ;.')
    # Otherwise cut after first liability marker, retaining actor wording that follows it.
    m=re.search(r'\bđ[ốổo]i\s+với\s+',t,re.I)
    if m:
        return t[m.end():].strip(' ;.')
    # Fallback removes only the range prefix.
    return re.sub(r'^Phạt tiền\s+từ\s+.*?đồng\s+đến\s+.*?đồng\s*','',t,flags=re.I).strip(' ;.')

def condition_tags(text:str):
    low=text.lower(); tags=[]
    patterns=[
      ('CAUSES_TRAFFIC_ACCIDENT','gây tai nạn giao thông'),('RECIDIVISM','tái phạm'),
      ('ALCOHOL','nồng độ cồn'),('DRUGS','chất ma túy'),('SPEED','quá tốc độ'),
      ('HIGHWAY','đường cao tốc'),('CHILD','trẻ em'),('NO_LICENSE','không có giấy phép'),
      ('EXCEPTION_PRESENT','trừ trường hợp'),('ENVIRONMENT','ô nhiễm môi trường'),
      ('DAMAGE_ROAD','gây hư hại cầu, đường')]
    for code,phrase in patterns:
        if phrase in low: tags.append(code)
    return tags

def rule_id(article,clause,point,entity,version='BASE'):
    return f'ND168_A{article:02d}_K{clause}_P{point or "_"}_{entity}_{version}'

def is_primary_clause(t:str):
    h=' '.join(t.split())[:220].lower()
    return h.startswith('phạt tiền từ ') or h.startswith('phạt cảnh cáo') or h.startswith('tịch thu phương tiện')

def parse_primary_rules(nd168_text:str):
    rows=[]; article_titles={}
    for art in parse_articles(nd168_text):
        a=art['article']; article_titles[a]=art['title']
        if not 6<=a<=40: continue
        actor,vehicles=ARTICLE_TAXONOMY.get(a,('UNSPECIFIED',[]))
        for cl in split_clauses(art['body']):
            ct=normalize_number_spaces(cl['text'])
            if not is_primary_clause(ct): continue
            head=' '.join(ct.split())
            if head.lower().startswith('phạt tiền từ'):
                ptype='FINE'; variants=infer_entity_variants(ct)
            elif head.lower().startswith('phạt cảnh cáo'):
                ptype='WARNING'; variants=[('UNSPECIFIED',None,None,None,None)]
            else:
                ptype='CONFISCATION'; variants=[('UNSPECIFIED',None,None,None,None)]
            pre,pts=split_points(ct)
            behaviors=pts if pts else [{'point':None,'text':extract_behavior_no_points(ct,ptype)}]
            # If no points, use full clause after sanction header to preserve meaning.
            for b in behaviors:
                btxt=' '.join(b['text'].split()).strip(' ;.')
                for ent,fmin,fmax,fcap,fbasis in variants:
                    rid=rule_id(a,cl['clause'],b['point'],ent)
                    rows.append({
                      'rule_id':rid,'document_number':'168/2024/NĐ-CP','article':str(a),'article_title':art['title'],
                      'clause':cl['clause'],'point':b['point'],'actor_code':actor,'vehicle_codes':vehicles,
                      'liable_entity_type':ent,'behavior_code':slugify(btxt),'behavior_text':btxt,
                      'conditions':condition_tags(btxt),'primary_sanction_type':ptype,
                      'fine_min':fmin,'fine_max':fmax,'fine_basis':fbasis if ptype=='FINE' else None,'fine_cap':fcap if ptype=='FINE' else None,'currency':'VND' if ptype=='FINE' else None,
                      'license_points_deducted':None,'license_suspension_min_months':None,'license_suspension_max_months':None,
                      'additional_sanctions':[],'remedial_measures':[],
                      'valid_from':'2025-01-01','valid_to':None,'deferred_effective_from':None,'deferred_scope_text':None,
                      'source_file':SOURCES['168/2024/NĐ-CP'].name,'source_chunk_id':f'ND168_A{a:02d}_K{cl["clause"]}_P{b["point"] or "_"}','amendment_source_chunk_id':None,
                      'source_location':f'Điều {a}, khoản {cl["clause"]}'+(f', điểm {b["point"]}' if b['point'] else ''),
                      'source_text':btxt,'parent_clause_text':' '.join(ct.split()),
                      'extraction_method':'DETERMINISTIC_RULE','validation_status':'PASS','confidence':0.98,
                      'amended_by':None,'base_rule_id':None,'notes':[]
                    })
    # Specific effectiveness under Article 53(2)
    for r in rows:
        if r['article']=='6' and r['clause']=='3' and r['point']=='m': r['valid_from']='2026-01-01'
        if r['article']=='26' and r['clause']=='4' and r['point']=='e': r['valid_from']='2026-01-01'
        if r['article']=='27' and r['clause']=='1' and r['point']=='b': r['valid_from']='2026-01-01'
        if r['article']=='32' and r['clause']=='1' and r['point']=='b':
            r['valid_from']=None; r['deferred_scope_text']='Có hiệu lực theo pháp luật bảo vệ môi trường về kiểm định khí thải xe mô tô, xe gắn máy.'; r['validation_status']='REVIEW'; r['confidence']=0.75
    return rows,article_titles

def extract_ref_locations(stmt:str,current_article:int):
    # Return list of (article,clause,point|None). Handles standardized "quy định tại ... Điều này" references.
    low=stmt.lower()
    idx=low.find('quy định tại')
    if idx<0: return []
    ref=stmt[idx+len('quy định tại'):]
    # Cut at sanction action markers.
    cuts=[]
    for pat in [r'\bbị tr[ừuùử]',r'\bcòn bị',r'\bbuộc ',r'\bbị tước',r'\bbị thu hồi',r'\btịch thu']:
        mm=re.search(pat,ref,re.I)
        if mm: cuts.append(mm.start())
    if cuts: ref=ref[:min(cuts)]
    refs=[]
    # split segments ending in Điều X/Điều này
    pos=0; segs=[]
    for m in re.finditer(r'Điều\s+(này|\d+)',ref,re.I):
        segs.append((ref[pos:m.start()], current_article if m.group(1).lower()=='này' else int(m.group(1))))
        pos=m.end()
    if not segs: segs=[(ref,current_article)]
    elif ref[pos:].strip(): segs.append((ref[pos:],current_article))
    for seg,art in segs:
        # point groups + clause
        consumed=[]
        for pm in re.finditer(r'((?:điểm\s+[a-zđl1i](?:\s*,\s*)?)+(?:\s*(?:và|,)?\s*điểm\s+[a-zđl1i])*)\s+khoản\s+(\d+[a-z]?)',seg,re.I):
            ptxt=pm.group(1)
            pts=re.findall(r'điểm\s+([a-zđl1i])',ptxt,re.I)
            pts=[('l' if x.lower()=='1' else x.lower()) for x in pts]
            for p in pts: refs.append((art,pm.group(2),p))
            consumed.append((pm.start(),pm.end()))
        # remove consumed spans, parse standalone clauses
        arr=list(seg)
        for s,e in consumed:
            for k in range(s,e): arr[k]=' '
        rest=''.join(arr)
        for cm in re.finditer(r'khoản\s+(\d+[a-z]?)',rest,re.I): refs.append((art,cm.group(1),None))
    # dedupe
    seen=set(); out=[]
    for x in refs:
        if x not in seen: seen.add(x); out.append(x)
    return out

def action_statements(clause_text:str):
    pre,pts=split_points(clause_text)
    return [p['text'] for p in pts] if pts else [' '.join(clause_text.split())]

def apply_secondary_actions(rows,nd168_text):
    byloc={}
    for r in rows: byloc.setdefault((int(r['article']),r['clause'],r['point']),[]).append(r)
    unmatched=[]; edges=[]
    for art in parse_articles(nd168_text):
        a=art['article']
        if not 6<=a<=40: continue
        for cl in split_clauses(art['body']):
            ct=normalize_number_spaces(cl['text'])
            low=' '.join(ct.split()).lower()
            if is_primary_clause(ct): continue
            kind=None
            if 'trừ điểm giấy phép lái xe' in low or 'trù điểm giấy phép lái xe' in low or 'trử điểm giấy phép lái xe' in low:
                kind='POINTS'
            elif 'tước quyền sử dụng' in low or 'hình thức xử phạt bổ sung' in low or 'tịch thu' in low:
                kind='ADDITIONAL'
            elif 'biện pháp khắc phục hậu quả' in low or 'buộc ' in low or 'thu hồi' in low:
                kind='REMEDIAL'
            if not kind: continue
            for stmt in action_statements(ct):
                refs=extract_ref_locations(stmt,a)
                matched=[]
                for ra,rc,rp in refs:
                    if rp is None:
                        for (aa,cc,pp),lst in byloc.items():
                            if aa==ra and cc==rc: matched.extend(lst)
                    else: matched.extend(byloc.get((ra,rc,rp),[]))
                # If standard clause says "quy định tại khoản ..." but parser fails, keep review.
                if not matched:
                    unmatched.append({'document_number':'168/2024/NĐ-CP','article':a,'clause':cl['clause'],'action_kind':kind,'statement':stmt,'parsed_refs':refs,'reason':'NO_TARGET_MATCH'})
                    continue
                if kind=='POINTS':
                    nums=[int(x) for x in re.findall(r'(\d{1,2})\s*đi[ểề]m',stmt,re.I)]
                    pts=nums[-1] if nums else None
                    for r in matched:
                        if pts is not None: r['license_points_deducted']=pts
                        else:
                            r['validation_status']='REVIEW'; r['notes'].append('Không parse được số điểm trừ từ secondary action.')
                elif kind=='ADDITIONAL':
                    dur=re.search(r'tước quyền sử dụng giấy phép lái xe\s+từ\s+(\d+)\s*tháng\s+đến\s+(\d+)\s*tháng',stmt,re.I)
                    for r in matched:
                        if dur:
                            r['license_suspension_min_months']=int(dur.group(1)); r['license_suspension_max_months']=int(dur.group(2))
                        if stmt not in r['additional_sanctions']: r['additional_sanctions'].append(stmt)
                else:
                    for r in matched:
                        if stmt not in r['remedial_measures']: r['remedial_measures'].append(stmt)
                for r in matched:
                    edges.append({'source_document':'168/2024/NĐ-CP','source_article':str(a),'source_clause':cl['clause'],'action_kind':kind,'target_rule_id':r['rule_id'],'statement':stmt})
    return unmatched,edges

def find_rows(rows,a,c,p=None):
    return [r for r in rows if r['article']==str(a) and r['clause']==str(c) and (p is None or r['point']==p) and r['valid_to'] is None]

def clone_amended(r,new_text,effective='2026-08-15',amend_art=None,version='A238'):
    oldid=r['rule_id']; r['valid_to']=effective; r['amended_by']='238/2026/NĐ-CP'
    nr=json.loads(json.dumps(r,ensure_ascii=False)); nr['base_rule_id']=oldid; nr['rule_id']=oldid.rsplit('_',1)[0]+'_'+version; nr['behavior_text']=' '.join(new_text.split()).strip(' ;."'); nr['behavior_code']=slugify(nr['behavior_text']); nr['source_text']=nr['behavior_text']; nr['valid_from']=effective; nr['valid_to']=None; nr['document_number']='168/2024/NĐ-CP'; nr['amended_by']='238/2026/NĐ-CP'; nr['source_file']=SOURCES['238/2026/NĐ-CP'].name; nr['amendment_source_chunk_id']=f'ND238_A{amend_art}' if amend_art else None; nr['source_location']=(nr['source_location']+f' (được sửa bởi Điều {amend_art} NĐ 238/2026/NĐ-CP)' if amend_art else nr['source_location']); nr['extraction_method']='BASE_PLUS_AMENDMENT_OVERLAY'; nr['confidence']=0.99
    return nr

def add_rule(rows,a,c,p,behavior,ptype='FINE',fine=None,entity='UNSPECIFIED',points=None,effective='2026-08-15',amend_art=None,deferred=None,deferred_scope=None,actor=None,vehicles=None,fine_basis='FLAT_RANGE',fine_cap=None):
    if actor is None or vehicles is None:
        actor0,vehicles0=ARTICLE_TAXONOMY.get(a,('UNSPECIFIED',[])); actor=actor or actor0; vehicles=vehicles if vehicles is not None else vehicles0
    fmin,fmax=(fine if fine else (None,None))
    rid=rule_id(a,c,p,entity,'A238')
    r={'rule_id':rid,'document_number':'168/2024/NĐ-CP','article':str(a),'article_title':'','clause':str(c),'point':p,
       'actor_code':actor,'vehicle_codes':vehicles,'liable_entity_type':entity,'behavior_code':slugify(behavior),'behavior_text':' '.join(behavior.split()).strip(' ;."'),
       'conditions':condition_tags(behavior),'primary_sanction_type':ptype,'fine_min':fmin,'fine_max':fmax,'fine_basis':fine_basis if ptype=='FINE' else None,'fine_cap':fine_cap if ptype=='FINE' else None,'currency':'VND' if ptype=='FINE' else None,
       'license_points_deducted':points,'license_suspension_min_months':None,'license_suspension_max_months':None,'additional_sanctions':[],'remedial_measures':[],
       'valid_from':effective,'valid_to':None,'deferred_effective_from':deferred,'deferred_scope_text':deferred_scope,
       'source_file':SOURCES['238/2026/NĐ-CP'].name,'source_chunk_id':f'ND168_A{a:02d}_K{c}_P{p or "_"}','amendment_source_chunk_id':f'ND238_A{amend_art}' if amend_art else None,'source_location':f'Điều {a}, khoản {c}'+(f', điểm {p}' if p else '')+f' (bổ sung bởi Điều {amend_art} NĐ 238/2026/NĐ-CP)',
       'source_text':' '.join(behavior.split()),'parent_clause_text':'','extraction_method':'AMENDMENT_OVERLAY','validation_status':'PASS','confidence':0.99,'amended_by':'238/2026/NĐ-CP','base_rule_id':None,'notes':[]}
    rows.append(r); return r

def apply_nd238(rows,nd238_text,article_titles):
    events=[]; review=[]
    def event(op,a,c=None,p=None,art238=None,text=None,notes=None):
        events.append({'amending_document':'238/2026/NĐ-CP','amending_article':str(art238) if art238 else None,'operation':op,'target_document':'168/2024/NĐ-CP','target_article':str(a) if a else None,'target_clause':str(c) if c else None,'target_point':p,'effective_from':'2026-08-15','replacement_or_added_text':text,'notes':notes})
    # Explicit replacement texts from supplied NĐ238.
    repl={
      (6,'3','m',2): 'Chở trẻ em dưới 10 tuổi và chiều cao dưới 1,35 mét trên xe ô tô ngồi cùng hàng ghế với người lái xe (trừ xe ô tô chỉ có một hàng ghế)',
      (13,'8','b',3): 'Điều khiển xe không gắn đủ biển số hoặc gắn biển số không đúng vị trí, không đúng quy cách theo quy định; gắn biển số không rõ chữ, số hoặc sơn, dán lên chữ, số của biển số xe; gắn biển số bị bẻ cong, che lấp, làm thay đổi chữ, số, màu sắc (của chữ, số, nền biển số xe), hình dạng, kích thước của biển số xe; sử dụng chất liệu, vật liệu, thiết bị làm thay đổi khả năng nhận diện thông tin biển số xe của phương tiện, thiết bị kỹ thuật nghiệp vụ (kể cả rơ moóc và sơ mi rơ moóc)',
      (14,'3','b',4): 'Điều khiển xe gắn biển số không đúng vị trí, không đúng quy cách theo quy định; gắn biển số không rõ chữ, số hoặc sơn, dán lên chữ, số của biển số xe; gắn biển số bị bẻ cong, che lấp, làm thay đổi chữ, số, màu sắc (của chữ, số, nền biển số xe), hình dạng, kích thước của biển số xe; sử dụng chất liệu, vật liệu, thiết bị làm thay đổi khả năng nhận diện thông tin biển số xe của phương tiện, thiết bị kỹ thuật nghiệp vụ',
      (17,'2','a',5): 'Chở vật liệu xây dựng, đất đá, phế thải, hàng rời mà không che đậy; làm rơi vãi hàng hóa, vật liệu xây dựng, đất đá, phế thải, bùn, hàng rời xuống đường; chở hàng hoặc chất thải để nước chảy xuống đường',
      (18,'4','a',6): 'Người từ đủ 16 tuổi đến dưới 18 tuổi điều khiển xe mô tô và các loại xe tương tự xe mô tô',
      (20,'5','đ',7): 'Điều khiển xe vận tải hành khách theo hợp đồng sử dụng hợp đồng bằng văn bản giấy mà không có hợp đồng vận tải, danh sách hành khách theo quy định; có hợp đồng vận tải nhưng không đúng theo quy định; đón khách, chở người không có tên trong danh sách hành khách theo hợp đồng đã ký',
      (20,'5','g',7): 'Điều khiển xe vận chuyển hành khách theo hợp đồng mà đón, trả khách tại trụ sở chính, trụ sở chi nhánh, văn phòng đại diện hoặc tại một địa điểm cố định khác do đơn vị kinh doanh vận tải thuê, hợp tác kinh doanh, trên các tuyến đường phố; đón, trả hành khách, cán bộ, công chức, viên chức, công nhân không đúng địa điểm được ghi trong hợp đồng vận tải đã ký, trừ hành vi vi phạm quy định tại khoản 8 Điều này; vận chuyển không đúng đối tượng theo quy định (áp dụng đối với xe kinh doanh vận tải hành khách theo hợp đồng vận chuyển trẻ em mầm non, học sinh, sinh viên, cán bộ, công chức, viên chức, công nhân)',
      (20,'5','l',7): 'Điều khiển xe kinh doanh vận tải hành khách, xe vận tải nội bộ không lắp thiết bị ghi nhận hình ảnh người lái xe hoặc có lắp thiết bị ghi nhận hình ảnh người lái xe nhưng không có tác dụng trong quá trình xe tham gia giao thông theo quy định hoặc làm sai lệch dữ liệu của thiết bị ghi nhận hình ảnh người lái xe lắp trên xe ô tô',
      (20,'5','m',7): 'Điều khiển xe vận tải hành khách theo hợp đồng sử dụng hợp đồng điện tử không có thiết bị do đơn vị kinh doanh vận tải cung cấp để truy cập được nội dung của hợp đồng điện tử, danh sách hành khách hoặc có thiết bị do đơn vị kinh doanh vận tải cung cấp nhưng không truy cập được nội dung của hợp đồng điện tử, danh sách hành khách; có hợp đồng điện tử nhưng không đúng theo quy định hoặc tự ý thay đổi thông tin của hợp đồng điện tử, danh sách hành khách đã ký; đón khách, chở người không có tên trong danh sách hành khách theo hợp đồng đã ký',
      (20,'6','đ',7): 'Điều khiển xe kinh doanh vận tải hành khách, xe vận tải nội bộ không lắp thiết bị giám sát hành trình của xe theo quy định hoặc có lắp thiết bị giám sát hành trình của xe nhưng thiết bị không hoạt động theo quy định hoặc làm sai lệch dữ liệu của thiết bị giám sát hành trình của xe ô tô',
      (21,'2','b',8): 'Chở hàng trên nóc thùng xe; chở hàng vượt quá bề rộng thùng xe (kể cả bề rộng rơ moóc và sơ mi rơ moóc); chở hàng vượt phía trước, phía sau thùng xe (kể cả rơ moóc và sơ mi rơ moóc) trên 10% chiều dài toàn bộ của xe theo thiết kế được ghi trong chứng nhận kiểm định an toàn kỹ thuật và bảo vệ môi trường của xe, trừ hành vi vi phạm quy định tại điểm d khoản 8 Điều 21 Nghị định này',
      (21,'3','b',8): 'Điều khiển xe ô tô kinh doanh vận tải, xe ô tô đầu kéo, xe vận tải nội bộ không lắp thiết bị ghi nhận hình ảnh người lái xe hoặc có lắp thiết bị ghi nhận hình ảnh người lái xe nhưng không có tác dụng trong quá trình xe tham gia giao thông theo quy định hoặc làm sai lệch dữ liệu của thiết bị ghi nhận hình ảnh người lái xe lắp trên xe ô tô',
      (21,'5','c',8): 'Điều khiển xe ô tô kinh doanh vận tải, xe ô tô đầu kéo, xe vận tải nội bộ không lắp thiết bị giám sát hành trình hoặc có lắp thiết bị giám sát hành trình nhưng không có tác dụng trong quá trình xe tham gia giao thông theo quy định hoặc làm sai lệch dữ liệu của thiết bị giám sát hành trình lắp trên xe ô tô',
      (21,'8','d',8): 'Chở thiết bị có hình dạng thùng hoặc có hình dạng như công-ten-nơ (không phải công-ten-nơ) vượt quá chiều dài toàn bộ được ghi trong chứng nhận kiểm định an toàn kỹ thuật và bảo vệ môi trường của rơ moóc, sơ mi rơ moóc; chở loại hàng không đúng với thông tin ghi trong chứng nhận kiểm định an toàn kỹ thuật và bảo vệ môi trường của rơ moóc, sơ mi rơ moóc',
      (21,'8','đ',8): 'Vận chuyển hàng trên xe không chằng buộc hoặc có chằng buộc nhưng không bảo đảm an toàn, trừ hành vi vi phạm quy định tại khoản 10 Điều này; vận chuyển hàng rời, vật liệu xây dựng trên xe mà xe không có thành thùng',
      (26,'7','e',9): 'Sử dụng xe kinh doanh vận tải hành khách theo hợp đồng mà trên xe không có hợp đồng vận tải, danh sách hành khách; không có thiết bị để truy cập nội dung hợp đồng điện tử, danh sách hành khách theo quy định; có hợp đồng nhưng không đúng theo quy định; tự ý thay đổi thông tin của hợp đồng điện tử, danh sách hành khách đã ký; đón khách, chở người không có tên trong danh sách hành khách theo hợp đồng đã ký; đón, trả khách tại trụ sở chính, trụ sở chi nhánh, văn phòng đại diện hoặc tại một địa điểm cố định khác do đơn vị kinh doanh vận tải thuê, hợp tác kinh doanh, trên các tuyến đường phố; vận chuyển không đúng đối tượng theo quy định (áp dụng đối với xe kinh doanh vận tải hành khách theo hợp đồng vận chuyển trẻ em mầm non, học sinh, sinh viên, cán bộ, công chức, viên chức, công nhân)',
    }
    newrows=[]
    for (a,c,p,art238),txt in repl.items():
        targets=find_rows(rows,a,c,p)
        if not targets:
            review.append({'type':'AMENDMENT_TARGET_MISSING','target':f'A{a} K{c} P{p}','amending_article':art238,'text':txt})
        for r in targets:
            nr=clone_amended(r,txt,amend_art=art238); nr['article_title']=article_titles.get(a,r['article_title']); newrows.append(nr)
            if (a,c,p)==(20,'5','l'):
                nr['deferred_effective_from']='2028-01-01'; nr['deferred_scope_text']='Đối với xe ô tô kinh doanh vận tải hành khách dưới 08 chỗ, xe ô tô kinh doanh vận tải hàng hóa (trừ xe ô tô đầu kéo), xe vận tải nội bộ: hiệu lực từ 2028-01-01 theo khoản 3 Điều 53 sau sửa đổi.'
        event('REPLACE',a,c,p,art238,txt)
    rows.extend(newrows)
    # Additions: A6 K1a warning
    add_rule(rows,6,'1a',None,'Người điều khiển xe ô tô chở trẻ em dưới 10 tuổi và chiều cao dưới 1,35 mét trên xe mà không sử dụng thiết bị an toàn phù hợp cho trẻ em theo quy định (trừ xe ô tô kinh doanh vận tải hành khách)',ptype='WARNING',effective='2026-08-15',amend_art=2,actor='DRIVER',vehicles=['CAR'])
    event('ADD',6,'1a',None,2,'Phạt cảnh cáo ... không sử dụng thiết bị an toàn phù hợp cho trẻ em.')
    # A20 K5 n inherits fine from K5; defer 2029
    parent=find_rows(rows,20,'5')
    fine=(parent[0]['fine_min'],parent[0]['fine_max']) if parent else (None,None)
    add_rule(rows,20,'5','n','Điều khiển xe ô tô kinh doanh vận tải hành khách từ 08 chỗ trở lên (không kể chỗ của người lái xe) không lắp thiết bị ghi nhận hình ảnh khoang chở khách hoặc có lắp thiết bị ghi nhận hình ảnh khoang chở khách nhưng không có tác dụng trong quá trình xe tham gia giao thông theo quy định hoặc làm sai lệch dữ liệu của thiết bị ghi nhận hình ảnh khoang chở khách lắp trên xe ô tô',fine=fine,effective='2026-08-15',deferred='2029-01-01',deferred_scope='Quy định xử phạt liên quan thiết bị ghi nhận hình ảnh khoang chở khách có hiệu lực từ 2029-01-01 và theo pháp luật liên quan.',amend_art=7)
    event('ADD',20,'5','n',7,'Thiết bị ghi nhận hình ảnh khoang chở khách',notes='deferred 2029-01-01')
    # A20 K8a + 6 points
    add_rule(rows,20,'8a',None,'Người điều khiển xe ô tô không kinh doanh vận tải hành khách nhưng chở người có thu tiền hoặc ký hợp đồng, nhận đặt chỗ để chở người trên xe',fine=(12000000,14000000),points=6,amend_art=7)
    event('ADD',20,'8a',None,7,'Phạt tiền 12-14 triệu; trừ 06 điểm.')
    # A21 K8 e inherits K8
    parent=find_rows(rows,21,'8'); fine=(parent[0]['fine_min'],parent[0]['fine_max']) if parent else (None,None)
    add_rule(rows,21,'8','e','Điều khiển xe ô tô không kinh doanh vận tải hàng hóa nhưng chở hàng hóa trên xe có thu tiền',fine=fine,amend_art=8)
    event('ADD',21,'8','e',8,'Xe ô tô không kinh doanh vận tải hàng hóa nhưng chở hàng có thu tiền.')
    # A26 K7 k,l inherit K7 and defer 2029
    parent=find_rows(rows,26,'7');
    # pick organization and individual variants if dual ranges; add same entity variants
    variants={r['liable_entity_type']:(r['fine_min'],r['fine_max']) for r in parent}
    for ent,fr in variants.items() or {'UNSPECIFIED':(None,None)}.items():
        add_rule(rows,26,'7','k','Sử dụng xe ô tô kinh doanh vận tải hành khách từ 08 chỗ trở lên (không kể chỗ của người lái xe) không lắp thiết bị ghi nhận hình ảnh khoang chở khách theo quy định hoặc có lắp nhưng không ghi, không lưu trữ được dữ liệu trên xe trong quá trình xe tham gia giao thông theo quy định hoặc làm sai lệch dữ liệu của thiết bị ghi nhận hình ảnh khoang chở khách trên xe ô tô',fine=fr,entity=ent,amend_art=9,deferred='2029-01-01',deferred_scope='Hiệu lực từ 2029-01-01 và theo pháp luật về thiết bị ghi nhận hình ảnh khoang chở khách.')
        add_rule(rows,26,'7','l','Không thực hiện việc cung cấp, cập nhật, truyền dẫn, lưu trữ, quản lý thông tin, dữ liệu thu thập từ thiết bị ghi nhận hình ảnh khoang chở khách lắp trên xe ô tô theo quy định',fine=fr,entity=ent,amend_art=9,deferred='2029-01-01',deferred_scope='Hiệu lực từ 2029-01-01 và theo pháp luật về thiết bị ghi nhận hình ảnh khoang chở khách.')
    event('ADD',26,'7','k',9,'Vi phạm thiết bị ghi nhận hình ảnh khoang chở khách',notes='deferred 2029'); event('ADD',26,'7','l',9,'Không cung cấp/cập nhật/truyền dẫn/lưu trữ dữ liệu khoang chở khách',notes='deferred 2029')
    # A26 K8 d inherits K8
    parent=find_rows(rows,26,'8'); variants={r['liable_entity_type']:(r['fine_min'],r['fine_max']) for r in parent}
    for ent,fr in variants.items() or {'UNSPECIFIED':(None,None)}.items():
        add_rule(rows,26,'8','d','Sử dụng xe ô tô kinh doanh vận tải hành khách theo hợp đồng mà xác nhận đặt chỗ cho từng hành khách đi xe ngoài hợp đồng đã ký kết hoặc bán vé, thu tiền ngoài hợp đồng đã ký kết; ấn định hành trình, lịch trình cố định để phục vụ cho nhiều hành khách hoặc nhiều người thuê vận tải khác nhau',fine=fr,entity=ent,amend_art=9)
    event('ADD',26,'8','d',9,'Hợp đồng nhưng xác nhận đặt chỗ/bán vé/ấn định hành trình cố định.')
    # A29 K3a two behaviors + points 2
    for p,txt in [('a','Điều khiển xe ô tô cứu hộ giao thông đường bộ chở xe được cứu hộ mà vượt quá khối lượng cho phép chuyên chở của xe cứu hộ; kéo theo xe được cứu hộ mà vượt quá khối lượng cho phép kéo theo của xe cứu hộ được ghi trong chứng nhận kiểm định an toàn kỹ thuật và bảo vệ môi trường của xe'),('b','Điều khiển xe ô tô cứu hộ giao thông đường bộ kéo theo xe không đúng đối tượng được cứu hộ theo quy định tại khoản 1 Điều 54 Luật Trật tự, an toàn giao thông đường bộ')]:
        add_rule(rows,29,'3a',p,txt,fine=(5000000,10000000),points=2,amend_art=10)
        event('ADD',29,'3a',p,10,txt)
    # A32 K9a: dual entity, b deferred 2028 scoped
    for p,txt in [('a','Đưa xe không lắp thiết bị giám sát hành trình của xe hoặc có lắp thiết bị giám sát hành trình nhưng không hoạt động, không đúng quy chuẩn theo quy định hoặc làm sai lệch dữ liệu của thiết bị giám sát hành trình của xe ô tô'),('b','Đưa xe không lắp thiết bị ghi nhận hình ảnh người lái xe hoặc có lắp thiết bị ghi nhận hình ảnh người lái xe nhưng không ghi, không lưu trữ được dữ liệu theo quy định hoặc làm sai lệch dữ liệu của thiết bị ghi nhận hình ảnh người lái xe lắp trên xe ô tô')]:
        for ent,fr in [('INDIVIDUAL',(5000000,6000000)),('ORGANIZATION',(10000000,12000000))]:
            add_rule(rows,32,'9a',p,txt,fine=fr,entity=ent,amend_art=11,deferred='2028-01-01' if p=='b' else None,deferred_scope='Đối với một số nhóm xe nêu tại khoản 3 Điều 53 sau sửa đổi, hiệu lực từ 2028-01-01.' if p=='b' else None)
        event('ADD',32,'9a',p,11,txt,notes='p=b has deferred scope to 2028')
    # A32 K11e inherits K11, A32 K13e inherits K13 and K21(c) says owner-driver deduction 4 for point e K13.
    for c,p,txt,pts in [
      ('11','e','Giao phương tiện hoặc để cho người làm công, người điều khiển phương tiện thực hiện hành vi vi phạm quy định tại khoản 8a Điều 20 của Nghị định này',None),
      ('13','e','Giao phương tiện hoặc để cho người làm công, người đại diện điều khiển phương tiện thực hiện hành vi vi phạm quy định tại điểm c, điểm d, điểm e khoản 8 Điều 21 của Nghị định này hoặc trực tiếp điều khiển phương tiện thực hiện hành vi vi phạm quy định tại điểm c, điểm d, điểm e khoản 8 Điều 21 của Nghị định này',4)]:
        parent=find_rows(rows,32,c); variants={r['liable_entity_type']:(r['fine_min'],r['fine_max']) for r in parent}
        for ent,fr in variants.items() or {'UNSPECIFIED':(None,None)}.items(): add_rule(rows,32,c,p,txt,fine=fr,entity=ent,points=pts,amend_art=11)
        event('ADD',32,c,p,11,txt)
    # NĐ 238 Điều 19: patch các sửa đổi làm thay đổi trực tiếp phạm vi hành vi.
    text_ops=[
      (6,'3','h','APPEND_AFTER','xe được kéo khi kéo nhau',', trừ hành vi vi phạm quy định tại điểm b khoản 3a Điều 29 của Nghị định này','Bổ sung ngoại lệ liên quan điểm b khoản 3a Điều 29'),
      (6,'2','a','APPEND_AFTER','chỉ được phép chuyển sang một làn đường liền kể',' hoặc chuyển làn đường không bảo đảm khoảng cách an toàn với xe phía trước, xe phía sau, xe hai bên','Bổ sung điều kiện khoảng cách khi chuyển làn'),
      (6,'5','g','APPEND_AFTER','chỉ được phép chuyền sang một làn đường liền kể',' hoặc chuyển làn đường không bảo đảm khoảng cách an toàn với xe phía trước, xe phía sau, xe hai bên','Bổ sung điều kiện khoảng cách khi chuyển làn'),
      (7,'1','e','APPEND_AFTER','chỉ được phép chuyển sang một làn đường liền kề',' hoặc chuyển làn đường không bảo đảm khoảng cách an toàn với xe phía trước, xe phía sau, xe hai bên','Bổ sung điều kiện khoảng cách khi chuyển làn'),
      (8,'6','h','APPEND_AFTER','chỉ được phép chuyển sang một làn đường liền kề',' hoặc chuyển làn đường không bảo đảm khoảng cách an toàn với xe phía trước, xe phía sau, xe hai bên','Bổ sung điều kiện khoảng cách khi chuyển làn'),
      (6,'5','i','APPEND_AFTER','đối với loại phương tiện đang điều khiển',' hoặc có quy định cấm của cấp có thẩm quyền đối với loại phương tiện đang điều khiển','Bổ sung trường hợp có quy định cấm của cấp có thẩm quyền'),
      (7,'6','b','APPEND_AFTER','đối với loại phương tiện đang điều khiển',' hoặc có quy định cấm của cấp có thẩm quyền đối với loại phương tiện đang điều khiển','Bổ sung trường hợp có quy định cấm của cấp có thẩm quyền'),
      (8,'6','d','APPEND_AFTER','đối với loại phương tiện đang điều khiến',' hoặc có quy định cấm của cấp có thẩm quyền đối với loại phương tiện đang điều khiển','Bổ sung trường hợp có quy định cấm của cấp có thẩm quyền'),
      (6,'7','c','REPLACE','làn dừng xe khẩn cấp','làn dừng xe khẩn cấp hoặc dải dừng xe khẩn cấp','Bổ sung dải dừng xe khẩn cấp'),
      (8,'6','b','REPLACE','làn dừng xe khẩn cấp','làn dừng xe khẩn cấp hoặc dải dừng xe khẩn cấp','Bổ sung dải dừng xe khẩn cấp'),
      (6,'5','p','REPLACE','chở người trên nóc xe; để người đu bám ở cửa xe, bên ngoài thành xe khi xe đang chạy','để người nằm, ngồi, đu bám bên ngoài xe khi xe đang chạy','Thay thế mô tả hành vi người ở bên ngoài xe'),
      (20,'6','d','REPLACE','xe ô tô kinh doanh vận tải','xe ô tô kinh doanh vận tải, xe vận tải nội bộ','Bổ sung xe vận tải nội bộ'),
      (21,'5','b','REPLACE','xe ô tô kinh doanh vận tải','xe ô tô kinh doanh vận tải, xe vận tải nội bộ','Bổ sung xe vận tải nội bộ'),
      (26,'11',None,'APPEND_AFTER','điểm a, điểm h khoản 7','điểm a, điểm h, điểm l khoản 7','Bổ sung điểm l khoản 7 vào trường hợp tái phạm'),
      (32,'7','b','REMOVE','; giấy chứng nhận kiểm định an toàn kỹ thuật và bảo vệ môi trường','','Bỏ cụm từ giấy chứng nhận kiểm định an toàn kỹ thuật và bảo vệ môi trường'),
      (32,'7','d','REMOVE',', giấy chứng nhận kiểm định an toàn kỹ thuật và bảo vệ môi trường','','Bỏ cụm từ giấy chứng nhận kiểm định an toàn kỹ thuật và bảo vệ môi trường'),
    ]
    for a,c,p,op,needle,repltxt,desc in text_ops:
        targets=find_rows(rows,a,c,p)
        if not targets:
            review.append({'type':'AMENDMENT_TARGET_MISSING','target':f'A{a} K{c} P{p}','amending_article':19,'instruction':desc})
            event(op,a,c,p,19,desc)
            continue
        for r in list(targets):
            old=r['behavior_text']; newtxt=old
            if op=='APPEND_AFTER':
                # For item 7, replacement text already contains the full desired phrase.
                if a==26 and c=='11': newtxt=old.replace(needle,repltxt,1)
                elif needle in old: newtxt=old.replace(needle,needle+repltxt,1)
                else: review.append({'type':'AMENDMENT_TEXT_NEEDLE_MISSING','rule_id':r['rule_id'],'needle':needle,'instruction':desc}); continue
            elif op=='REPLACE':
                if needle in old: newtxt=old.replace(needle,repltxt,1)
                else: review.append({'type':'AMENDMENT_TEXT_NEEDLE_MISSING','rule_id':r['rule_id'],'needle':needle,'instruction':desc}); continue
            elif op=='REMOVE':
                if needle in old: newtxt=old.replace(needle,repltxt,1)
                else: review.append({'type':'AMENDMENT_TEXT_NEEDLE_MISSING','rule_id':r['rule_id'],'needle':needle,'instruction':desc}); continue
            nr=clone_amended(r,newtxt,amend_art=19,version='A238D19')
            nr['article_title']=article_titles.get(a,r.get('article_title',''))
            if a==26 and c=='11':
                nr['deferred_effective_from']='2029-01-01'; nr['deferred_scope_text']='Phần tái phạm liên quan điểm l khoản 7 chỉ phát sinh khi quy định về thiết bị ghi nhận hình ảnh khoang chở khách có hiệu lực từ 2029-01-01.'
            rows.append(nr)
        event(op,a,c,p,19,desc)

    # Điều 19 khoản 5 mở rộng biện pháp khắc phục ở điểm a khoản 6 Điều 14:
    # từ điểm đ khoản 2 -> khoản 1; điểm d, điểm đ khoản 2.
    remedy14='Buộc thay thế thiết bị đủ tiêu chuẩn an toàn kỹ thuật hoặc khôi phục tính năng kỹ thuật của thiết bị theo quy định.'
    for target_clause,target_point in [('1',None),('2','d')]:
        for r in list(find_rows(rows,14,target_clause,target_point)):
            nr=clone_amended(r,r['behavior_text'],amend_art=19,version='A238D19R')
            if remedy14 not in nr['remedial_measures']: nr['remedial_measures'].append(remedy14)
            nr['article_title']=article_titles.get(14,r.get('article_title','')); rows.append(nr)
    event('EXPAND_REMEDY_REFERENCE',14,'6','a',19,'Biện pháp khắc phục áp dụng thêm khoản 1 và điểm d khoản 2 Điều 14.')

    # Các biện pháp khắc phục được sửa/bổ sung trực tiếp bởi NĐ 238.
    remedy26k='Buộc lắp đặt thiết bị giám sát hành trình, thiết bị ghi nhận hình ảnh người lái xe, thiết bị ghi nhận hình ảnh khoang chở khách, dây đai an toàn, ghế ngồi cho trẻ em mầm non, học sinh tiểu học trên xe theo đúng quy định.'
    remedy26l='Buộc cung cấp, cập nhật, truyền dẫn, lưu trữ, quản lý thông tin, dữ liệu thu thập từ thiết bị giám sát hành trình, thiết bị ghi nhận hình ảnh người lái xe, thiết bị ghi nhận hình ảnh khoang chở khách lắp trên xe ô tô theo quy định.'
    for r in find_rows(rows,26,'7','k'):
        if remedy26k not in r['remedial_measures']: r['remedial_measures'].append(remedy26k)
    for r in find_rows(rows,26,'7','l'):
        if remedy26l not in r['remedial_measures']: r['remedial_measures'].append(remedy26l)
    remedy32='Buộc lắp đặt dụng cụ, thiết bị chuyên dùng để cứu hộ, hỗ trợ cứu hộ, thiết bị giám sát hành trình, thiết bị ghi nhận hình ảnh người lái xe trên xe theo đúng quy định.'
    for p9a in ['a','b']:
        for r in find_rows(rows,32,'9a',p9a):
            if remedy32 not in r['remedial_measures']: r['remedial_measures'].append(remedy32)
    event('UPDATE_REMEDY_REFERENCE',26,'13',None,9,'Cập nhật biện pháp khắc phục cho thiết bị hình ảnh người lái/khoang chở khách.')
    event('UPDATE_REMEDY_REFERENCE',32,'19','l',11,'Khoản 9a được bổ sung vào phạm vi buộc lắp thiết bị.')
    # Bãi bỏ A32 K17 points d, đ, e, g from 2026-08-15
    for p in ['d','đ','e','g']:
        targets=find_rows(rows,32,'17',p)
        for r in targets: r['valid_to']='2026-08-15'; r['amended_by']='238/2026/NĐ-CP'; r['notes'].append('Bãi bỏ bởi khoản 17 Điều 19 NĐ 238/2026/NĐ-CP.')
        event('REPEAL',32,'17',p,19,'Bãi bỏ điểm này.')
    return events,review

def extract_provisions():
    # Registry is logical-document based. Luật 36 is physically split into two files,
    # but both parts share one document_key/document_number for retrieval and citation.
    recs=[]; regmap={}
    for key,p in SOURCES.items():
        text=p.read_text(encoding='utf-8'); meta,body=parse_frontmatter(text); body=normalize_number_spaces(body)
        docnum=meta.get('so_ky_hieu') or key.split('-P')[0]
        logical_key=docnum
        part_id=None
        if key.endswith('-P1'): part_id='PART_01'
        elif key.endswith('-P2'): part_id='PART_02'
        if logical_key not in regmap:
            regmap[logical_key]={
              'document_key':logical_key,'document_number':docnum,'title':meta.get('title'),
              'effective_date':str(meta.get('ngay_co_hieu_luc')) if meta.get('ngay_co_hieu_luc') else None,
              'source_files':[],'parts':[],'document_type':meta.get('loai_van_ban'),
              'issuer':meta.get('co_quan_ban_hanh'),'summary':meta.get('trich_yeu')
            }
        regmap[logical_key]['source_files'].append(p.name)
        if part_id: regmap[logical_key]['parts'].append({'part_id':part_id,'source_file':p.name,'scope':meta.get('pham_vi_dieu')})
        for art in parse_articles(body):
            recs.append({'document_key':logical_key,'document_number':docnum,'part_id':part_id,
                         'article':str(art['article']),'article_title':art['title'],
                         'text':' '.join(art['body'].split()),'source_file':p.name})
    return list(regmap.values()),recs

def write_jsonl(path,rows):
    with open(path,'w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False)+'\n')

def write_csv(path,rows):
    if not rows: return
    # flatten list fields/json fields
    keys=[]
    for r in rows:
        for k in r:
            if k not in keys: keys.append(k)
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys); w.writeheader()
        for r in rows:
            rr={k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v) for k,v in r.items()}; w.writerow(rr)

def build_sqlite(dbpath,registry,provisions,rules,events,edges,review):
    if dbpath.exists(): dbpath.unlink()
    con=sqlite3.connect(dbpath)
    cur=con.cursor()
    cur.executescript('''
    CREATE TABLE sanction_rules(
      rule_id TEXT PRIMARY KEY, document_number TEXT, article TEXT, clause TEXT, point TEXT,
      actor_code TEXT, vehicle_codes_json TEXT, liable_entity_type TEXT,
      behavior_code TEXT, behavior_text TEXT, conditions_json TEXT,
      primary_sanction_type TEXT, fine_min INTEGER, fine_max INTEGER, currency TEXT,
      license_points_deducted INTEGER, license_suspension_min_months INTEGER, license_suspension_max_months INTEGER,
      additional_sanctions_json TEXT, remedial_measures_json TEXT,
      valid_from TEXT, valid_to TEXT, deferred_effective_from TEXT, deferred_scope_text TEXT,
      source_file TEXT, source_location TEXT, source_text TEXT,
      extraction_method TEXT, validation_status TEXT, confidence REAL, amended_by TEXT, base_rule_id TEXT, notes_json TEXT
    );
    CREATE INDEX idx_rule_lookup ON sanction_rules(article,clause,point);
    CREATE INDEX idx_rule_behavior ON sanction_rules(behavior_code);
    CREATE INDEX idx_rule_temporal ON sanction_rules(valid_from,valid_to);
    CREATE INDEX idx_rule_vehicle ON sanction_rules(actor_code);
    CREATE TABLE sanction_amendments(amending_document TEXT, amending_article TEXT, operation TEXT,target_document TEXT,target_article TEXT,target_clause TEXT,target_point TEXT,effective_from TEXT,replacement_or_added_text TEXT,notes TEXT);
    CREATE TABLE sanction_crossrefs(source_document TEXT,source_article TEXT,source_clause TEXT,action_kind TEXT,target_rule_id TEXT,statement TEXT);
    CREATE TABLE review_queue(payload_json TEXT);
    CREATE TABLE source_registry(payload_json TEXT);
    CREATE TABLE legal_provisions(payload_json TEXT);
    ''')
    for r in rules:
        cur.execute('''INSERT INTO sanction_rules VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(
          r['rule_id'],r['document_number'],r['article'],r['clause'],r['point'],r['actor_code'],json.dumps(r['vehicle_codes'],ensure_ascii=False),r['liable_entity_type'],r['behavior_code'],r['behavior_text'],json.dumps(r['conditions'],ensure_ascii=False),r['primary_sanction_type'],r['fine_min'],r['fine_max'],r['currency'],r['license_points_deducted'],r['license_suspension_min_months'],r['license_suspension_max_months'],json.dumps(r['additional_sanctions'],ensure_ascii=False),json.dumps(r['remedial_measures'],ensure_ascii=False),r['valid_from'],r['valid_to'],r['deferred_effective_from'],r['deferred_scope_text'],r['source_file'],r['source_location'],r['source_text'],r['extraction_method'],r['validation_status'],r['confidence'],r['amended_by'],r['base_rule_id'],json.dumps(r['notes'],ensure_ascii=False),r.get('article_title','')
        ))
    # column count hack: article_title wasn't in schema; migration below not possible here
    con.rollback(); con.close()

def build_sqlite2(dbpath,registry,provisions,rules,events,edges,review):
    if dbpath.exists(): dbpath.unlink()
    con=sqlite3.connect(dbpath); cur=con.cursor()
    cur.execute('''CREATE TABLE sanction_rules(
      rule_id TEXT PRIMARY KEY, document_number TEXT, article TEXT, article_title TEXT, clause TEXT, point TEXT,
      actor_code TEXT, vehicle_codes_json TEXT, liable_entity_type TEXT, behavior_code TEXT, behavior_text TEXT, conditions_json TEXT,
      primary_sanction_type TEXT, fine_min INTEGER, fine_max INTEGER, fine_basis TEXT, fine_cap INTEGER, currency TEXT, license_points_deducted INTEGER,
      license_suspension_min_months INTEGER, license_suspension_max_months INTEGER, additional_sanctions_json TEXT, remedial_measures_json TEXT,
      valid_from TEXT, valid_to TEXT, deferred_effective_from TEXT, deferred_scope_text TEXT, source_file TEXT, source_chunk_id TEXT, amendment_source_chunk_id TEXT, source_location TEXT, source_text TEXT,
      parent_clause_text TEXT, extraction_method TEXT, validation_status TEXT, confidence REAL, amended_by TEXT, base_rule_id TEXT, notes_json TEXT)''')
    cur.execute('CREATE INDEX idx_rule_lookup ON sanction_rules(article,clause,point)'); cur.execute('CREATE INDEX idx_rule_behavior ON sanction_rules(behavior_code)'); cur.execute('CREATE INDEX idx_rule_temporal ON sanction_rules(valid_from,valid_to)')
    cols=['rule_id','document_number','article','article_title','clause','point','actor_code','vehicle_codes','liable_entity_type','behavior_code','behavior_text','conditions','primary_sanction_type','fine_min','fine_max','fine_basis','fine_cap','currency','license_points_deducted','license_suspension_min_months','license_suspension_max_months','additional_sanctions','remedial_measures','valid_from','valid_to','deferred_effective_from','deferred_scope_text','source_file','source_chunk_id','amendment_source_chunk_id','source_location','source_text','parent_clause_text','extraction_method','validation_status','confidence','amended_by','base_rule_id','notes']
    q='INSERT INTO sanction_rules VALUES ('+','.join('?'*len(cols))+')'
    for r in rules:
        vals=[]
        for c in cols:
            v=r.get(c)
            if isinstance(v,(list,dict)): v=json.dumps(v,ensure_ascii=False)
            vals.append(v)
        cur.execute(q,vals)
    cur.execute('''CREATE TABLE sanction_amendments(amending_document TEXT,amending_article TEXT,operation TEXT,target_document TEXT,target_article TEXT,target_clause TEXT,target_point TEXT,effective_from TEXT,replacement_or_added_text TEXT,notes TEXT)''')
    for e in events: cur.execute('INSERT INTO sanction_amendments VALUES (?,?,?,?,?,?,?,?,?,?)',[e.get(k) for k in ['amending_document','amending_article','operation','target_document','target_article','target_clause','target_point','effective_from','replacement_or_added_text','notes']])
    cur.execute('''CREATE TABLE sanction_crossrefs(source_document TEXT,source_article TEXT,source_clause TEXT,action_kind TEXT,target_rule_id TEXT,statement TEXT)''')
    for e in edges: cur.execute('INSERT INTO sanction_crossrefs VALUES (?,?,?,?,?,?)',[e.get(k) for k in ['source_document','source_article','source_clause','action_kind','target_rule_id','statement']])
    cur.execute('CREATE TABLE review_queue(payload_json TEXT)'); [cur.execute('INSERT INTO review_queue VALUES (?)',(json.dumps(x,ensure_ascii=False),)) for x in review]
    cur.execute('CREATE TABLE source_registry(payload_json TEXT)'); [cur.execute('INSERT INTO source_registry VALUES (?)',(json.dumps(x,ensure_ascii=False),)) for x in registry]
    cur.execute('CREATE TABLE legal_provisions(payload_json TEXT)'); [cur.execute('INSERT INTO legal_provisions VALUES (?)',(json.dumps(x,ensure_ascii=False),)) for x in provisions]
    con.commit(); con.close()

def main():
    registry,provisions=extract_provisions()
    raw168=SOURCES['168/2024/NĐ-CP'].read_text(encoding='utf-8'); _,body168=parse_frontmatter(raw168); body168=normalize_number_spaces(body168)
    rules,titles=parse_primary_rules(body168)
    unmatched,edges=apply_secondary_actions(rules,body168)
    raw238=SOURCES['238/2026/NĐ-CP'].read_text(encoding='utf-8'); _,body238=parse_frontmatter(raw238); body238=normalize_number_spaces(body238)
    events,amend_review=apply_nd238(rules,body238,titles)
    # fill titles for additions
    for r in rules: r['article_title']=titles.get(int(r['article']),r.get('article_title',''))
    # Validate basic monetary rows
    review=list(unmatched)+amend_review
    for r in rules:
        if r['primary_sanction_type']=='FINE' and (r['fine_min'] is None or r['fine_max'] is None):
            r['validation_status']='REVIEW'; r['confidence']=min(r['confidence'],0.6); review.append({'type':'MISSING_FINE','rule_id':r['rule_id'],'source_location':r['source_location'],'text':r['parent_clause_text'][:500]})
        if r['fine_min'] is not None and r['fine_max'] is not None and r['fine_min']>r['fine_max']:
            r['validation_status']='REVIEW'; review.append({'type':'INVALID_FINE_RANGE','rule_id':r['rule_id']})
    # Any rule explicitly marked REVIEW must be visible in the review queue.
    queued_rule_ids={x.get('rule_id') for x in review if isinstance(x,dict)}
    for r in rules:
        if r.get('validation_status')=='REVIEW' and r.get('rule_id') not in queued_rule_ids:
            reason='REQUIRES_EXTERNAL_EFFECTIVE_DATE' if r.get('valid_from') is None and r.get('deferred_scope_text') else 'RULE_REQUIRES_REVIEW'
            review.append({'type':reason,'rule_id':r['rule_id'],'source_location':r.get('source_location'),
                           'deferred_scope_text':r.get('deferred_scope_text'),'text':r.get('source_text','')[:500]})
            queued_rule_ids.add(r['rule_id'])
    # dedupe rules by id (amendment additions could collide if parent variants weird)
    uniq={}
    for r in rules:
        if r['rule_id'] in uniq:
            # preserve with suffix hash
            r['rule_id'] += '_'+hashlib.md5((r['behavior_text']+r['liable_entity_type']).encode()).hexdigest()[:6]
        uniq[r['rule_id']]=r
    rules=list(uniq.values())
    # JSONL/CSV
    write_jsonl(OUT/'source_registry.jsonl',registry); write_jsonl(OUT/'legal_provisions.jsonl',provisions)
    write_jsonl(OUT/'sanction_rules.jsonl',rules); write_csv(OUT/'sanction_rules.csv',rules)
    write_jsonl(OUT/'sanction_amendments.jsonl',events); write_jsonl(OUT/'sanction_crossrefs.jsonl',edges); write_jsonl(OUT/'review_queue.jsonl',review)
    build_sqlite2(OUT/'sanctions.sqlite',registry,provisions,rules,events,edges,review)
    # schema
    schema={
      'rule_id':'stable versioned identifier','actor_code':'canonical liable actor category','vehicle_codes':'canonical vehicle categories','liable_entity_type':'INDIVIDUAL/ORGANIZATION/UNSPECIFIED',
      'behavior_code':'auto-normalized canonical-like behavior key; keep behavior_text as legal wording','behavior_text':'legal behavior wording from source/amendment',
      'primary_sanction_type':'FINE/WARNING/CONFISCATION','fine_min':'VND integer','fine_max':'VND integer','fine_basis':'FLAT_RANGE or PER_EXCESS_PERSON','fine_cap':'maximum total fine when source specifies a cap','license_points_deducted':'GPLX points',
      'license_suspension_min_months':'months','license_suspension_max_months':'months','additional_sanctions':'secondary sanctions joined from cross references','remedial_measures':'remedies joined from cross references',
      'valid_from':'inclusive effective date of this version','valid_to':'exclusive end date','deferred_effective_from':'special future effectiveness for a scoped subset','deferred_scope_text':'scope of special future effectiveness',
      'source_chunk_id':'stable target provision id','amendment_source_chunk_id':'NĐ238 amendment evidence id when applicable','source_location':'Điều/Khoản/Điểm','base_rule_id':'previous version when amended','validation_status':'PASS/REVIEW','notes':'QA/amendment notes'
    }
    (OUT/'schema.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')
    # metrics
    metrics={
      'source_files':len(SOURCES),'logical_documents':len(registry),'legal_provisions':len(provisions),'sanction_rule_versions':len(rules),
      'fine_rules':sum(r['primary_sanction_type']=='FINE' for r in rules),'warning_rules':sum(r['primary_sanction_type']=='WARNING' for r in rules),'confiscation_rules':sum(r['primary_sanction_type']=='CONFISCATION' for r in rules),
      'rules_with_points':sum(r['license_points_deducted'] is not None for r in rules),'rules_with_suspension':sum(r['license_suspension_min_months'] is not None for r in rules),
      'amendment_events':len(events),'crossref_edges':len(edges),'review_items':len(review),'pass_rules':sum(r['validation_status']=='PASS' for r in rules),'review_rules':sum(r['validation_status']=='REVIEW' for r in rules),
      'effective_on_2026_08_11':sum((r['valid_from'] is None or r['valid_from']<='2026-08-11') and (r['valid_to'] is None or '2026-08-11'<r['valid_to']) and (r['deferred_effective_from'] is None or r['deferred_effective_from']<='2026-08-11') for r in rules),
      'effective_on_2026_08_15_without_deferred_scope':sum((r['valid_from'] is None or r['valid_from']<='2026-08-15') and (r['valid_to'] is None or '2026-08-15'<r['valid_to']) and r['deferred_effective_from'] is None for r in rules)
    }
    (OUT/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    # README
    readme=f'''# Structured Sanction Layer – Luật giao thông đường bộ\n\nGenerated from the supplied Markdown files only.\n\n## Scope\n\n- Luật 35/2024/QH15, Luật 36/2024/QH15 (2 source files nhưng 1 logical document), NĐ 165/2024/NĐ-CP: indexed into `legal_provisions.jsonl` as legal context/definitions.\n- NĐ 168/2024/NĐ-CP: primary sanction source; rules extracted from Articles 6–40.\n- NĐ 238/2026/NĐ-CP: amendment overlay with versioned rules and amendment events. Its general effective date is **2026-08-15**, so on **2026-08-11** the amended versions are future rules.\n\n## Outputs\n\n- `sanction_rules.jsonl` / `sanction_rules.csv`: versioned structured sanction rules.\n- `sanctions.sqlite`: query-ready database.\n- `sanction_amendments.jsonl`: amendment/repeal/addition operations from NĐ 238.\n- `sanction_crossrefs.jsonl`: edges that join fine behaviors to point deduction/additional/remedial clauses.\n- `review_queue.jsonl`: cases that should not be silently trusted.\n- `source_registry.jsonl`, `legal_provisions.jsonl`, `schema.json`, `metrics.json`.\n\n## Metrics\n\n```json\n{json.dumps(metrics,ensure_ascii=False,indent=2)}\n```\n\n## Temporal lookup\n\nUse event date, not detection date. NĐ 238 Article 21 states violations occurring and ending before 2026-08-15 are handled under the decree effective at the time of the violation.\n\n```sql\nSELECT * FROM sanction_rules\nWHERE behavior_code = ?\n  AND (valid_from IS NULL OR valid_from <= :event_date)\n  AND (valid_to IS NULL OR :event_date < valid_to);\n```\n\nThen enforce `deferred_effective_from`/`deferred_scope_text` for special 2028/2029 provisions.\n\n## Important QA note\n\n`behavior_code` is generated deterministically from legal wording; it is not yet a hand-curated semantic ontology. For production, maintain a separate alias/catalog layer mapping user phrases such as “vượt đèn đỏ” to the stable rule/behavior codes.\n'''
    (OUT/'README.md').write_text(readme,encoding='utf-8')
    # copy builder
    shutil.copy2(Path(__file__),OUT/'build_sanction_layer.py')
    print(json.dumps(metrics,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
