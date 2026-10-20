import csv, json, sqlite3, re, hashlib, collections, time
from pathlib import Path
from inspect_archive import entries, ROOT, ARCHIVE

OUT=ROOT/'batch_work'; OUT.mkdir(exist_ok=True)
db=sqlite3.connect(':memory:')
(OUT/'candidates').mkdir(exist_ok=True)
db.executescript('DROP TABLE IF EXISTS docs; CREATE TABLE docs(jid TEXT PRIMARY KEY,path TEXT,court TEXT,title TEXT,date TEXT,body TEXT,pdf TEXT,categories TEXT,scores TEXT,procedural INTEGER);')
deleted={}
with open(Path(__import__('os').environ['JUDICIAL_DELETIONS']),encoding='utf-8-sig') as f:
    deletion_rows=list(csv.DictReader(f))
for r in deletion_rows:
    deleted[r['裁判ID'].strip()]=r

rules={
 '繼承':[(r'分割遺產|遺產分割',12),(r'確認繼承權|返還遺產|遺囑無效|遺囑效力|遺贈',10),(r'借名.{0,20}(帳戶|存款)|剩餘財產分配|贈與歸扣',7),(r'遺產|繼承|遺囑',1)],
 '特留分':[(r'特留分',14),(r'扣減權|特種贈與|歸扣',5)],
 '保險與稅務':[(r'遺產稅|贈與稅|所得稅|基本稅額',5),(r'要保人|保險金|保單|保險費',4),(r'實質課稅|最低稅負|滿期金|解約金',5)],
 '台美傳承':[(r'美國|美籍|綠卡|IRS|3520|美金',2),(r'遺產稅|贈與稅|繼承|保單|遺囑|信託',5)],
 '職災與雇主責任':[(r'職業災害|職災',10),(r'勞動基準法第59條|勞基法第59條|職業災害補償',9),(r'雇主責任|僱主責任|通勤災害|職業病',8)],
 '車禍損害賠償':[(r'交通事故|車禍|肇事|強制汽車責任',5),(r'勞動能力.{0,8}(減損|減少|喪失)|減少勞動能力',9),(r'看護費|扶養費|過失相抵',4)],
 '保險給付爭議-保障型':[(r'給付保險金|保險金給付|保險契約|保險法第64條',10),(r'醫療保險|住院.{0,8}(必要|保險)|癌症|重大傷病|重大疾病|失能保險|長期照顧|傷害保險',7),(r'告知義務|除外責任|拒賠|必要性',3)],
 '保險給付爭議-身故傳承型':[(r'給付保險金|保險金給付|保險契約|保險法第64條',8),(r'身故保險金|死亡保險金|指定受益人|變更受益人|受益人變更|保險法第112條',10),(r'保險法第121條|自殺|復效|保單價值',3)]
}
counts=collections.Counter(); hits=collections.Counter(); rejected=[]; parse_errors=[]; duplicates=[]; monthly=collections.Counter(); types=collections.Counter(); seen=set(); metadata=[]
t0=time.time()
for name,size,data in entries(True):
    if not name.endswith('.json'):continue
    counts['json_entries']+=1
    try:d=json.loads(data.decode('utf-8-sig'))
    except Exception as e:parse_errors.append([name,str(e)]);continue
    jid=d.get('JID',''); title=d.get('JTITLE',''); body=d.get('JFULL','')
    if not isinstance(body,str):body=json.dumps(body,ensure_ascii=False)
    key=','.join(jid.split(',')[:5]); parts=jid.split(','); code=parts[0]
    types[code[-1:]]+=1; monthly[d.get('JDATE','')[:6]]+=1
    if jid in deleted or key in deleted:
        rejected.append({'jid':jid,'path':name,'reason':'匹配使用者提供的刪除清單'});counts['deleted_matches']+=1;continue
    if len(body.strip())==0:counts['empty_body']+=1
    court=Path(name).parent.name
    compact=re.sub(r'\s+','',body)
    proc= int(('裁定' in compact[:70] and '判決' not in compact[:70]) or bool(re.search(r'補[繳正].{0,15}(裁判費|訴之聲明)|應於本裁定送達',compact[:4000])))
    scores={}
    if code.endswith(('V','A')):
        for cat,rr in rules.items():
            score=sum(weight*min(3,len(re.findall(pat,compact))) for pat,weight in rr)
            if cat=='繼承' and not re.search(r'遺產|遺囑|借名|剩餘財產分配|贈與歸扣',title+compact):continue
            if cat=='特留分' and '特留分' not in compact:continue
            if cat=='保險與稅務' and not (re.search(r'遺產稅|贈與稅|所得稅|基本稅額',title+compact) and re.search(r'要保人|保險金|保單|保險費',compact)):continue
            if cat=='台美傳承' and not (re.search(r'美國|美籍|綠卡|IRS|3520',compact) and re.search(r'遺產|遺囑|保單|信託|贈與稅',compact)):continue
            if cat=='職災與雇主責任' and not re.search(r'職業災害|職災|職業病|雇主責任|僱主責任',compact):continue
            if cat=='車禍損害賠償' and not (re.search(r'交通事故|車禍|肇事|強制汽車責任',compact) and re.search(r'損害賠償|看護費|慰撫金|勞動能力',compact)):continue
            if cat.startswith('保險給付爭議'):
                if not re.search(r'給付保險金|保險金給付|保險契約|保險法第64條',title+compact):continue
                if cat.endswith('保障型') and not re.search(r'醫療|住院|癌症|重大傷病|重大疾病|失能|長期照顧|傷害保險',compact):continue
                if cat.endswith('身故傳承型') and not re.search(r'身故|死亡保險金|受益人|保險法第121條',compact):continue
            if score>=10:
                if re.search(r'分割遺產|遺囑|特留分',title) and cat in ['繼承','特留分']:score+=25
                if re.search(r'給付保險金|保險金給付',title) and cat.startswith('保險給付'):score+=25
                if re.search(r'職業災害|職災|補償',title) and cat=='職災與雇主責任':score+=25
                if code.endswith('A') and cat=='保險與稅務':score+=20
                if proc:score-=30
                if len(compact)<1500:score-=10
                scores[cat]=score
    if scores:counts['candidate_docs']+=1
    for c in scores:hits[c]+=1
    if jid in seen:duplicates.append(jid);continue
    seen.add(jid)
    if scores:
        db.execute('INSERT INTO docs VALUES(?,?,?,?,?,?,?,?,?,?)',(jid,name,court,title,d.get('JDATE'),body,d.get('JPDF'),json.dumps(list(scores),ensure_ascii=False),json.dumps(scores,ensure_ascii=False),proc))
        saved={**d,'archive_path':name,'court_folder':court,'keyword_scores':scores,'procedural_hint':proc}
        (OUT/'candidates'/(hashlib.sha256(jid.encode()).hexdigest()+'.json')).write_text(json.dumps(saved,ensure_ascii=False))
        metadata.append(dict(jid=jid,court=court,title=title,date=d.get('JDATE'),scores=scores,chars=len(body),procedural=proc))
    if counts['json_entries']%10000==0:
        db.commit();print('scanned',counts['json_entries'],'seconds',round(time.time()-t0),flush=True)
db.commit()
summary={'archive':ARCHIVE.name,'archive_sha256':hashlib.file_digest(open(ARCHIVE,'rb'),'sha256').hexdigest(),'deletion_file':Path(__import__('os').environ['JUDICIAL_DELETIONS']).name,'deletion_sha256':hashlib.file_digest(open(Path(__import__('os').environ['JUDICIAL_DELETIONS']),'rb'),'sha256').hexdigest(),'deletion_rows':len(deletion_rows),'deletion_unique_ids':len(deleted),'counts':dict(counts),'topic_keyword_hits':dict(hits),'date_months':dict(monthly),'types':dict(types),'parse_errors':parse_errors,'duplicate_jids':duplicates,'excluded_deleted':rejected,'elapsed_seconds':round(time.time()-t0)}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
ranked={}
for cat in rules:
    candidates=[]
    for row in db.execute('SELECT jid,court,title,date,scores,length(body),procedural FROM docs WHERE categories LIKE ?',('%'+cat+'%',)):
        jid,court,title,date,ss,n,proc=row;score=json.loads(ss)[cat]
        candidates.append(dict(jid=jid,court=court,title=title,date=date,score=score,chars=n,procedural=proc))
    ranked[cat]=sorted(candidates,key=lambda x:(-x['score'],-x['chars']))[:25]
(OUT/'ranked.json').write_text(json.dumps(ranked,ensure_ascii=False,indent=2))
(OUT/'candidate_metadata.json').write_text(json.dumps(metadata,ensure_ascii=False))
print(json.dumps(summary,ensure_ascii=False),flush=True)
