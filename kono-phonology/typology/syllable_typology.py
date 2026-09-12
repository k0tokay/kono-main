"""Syllable-shape transitions and PMI. Run from kono-phonology:
python typology/syllable_typology.py --permutations 200
Requires numpy, matplotlib; epitran only when refreshing TXT IPA caches.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import sys
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from syllable_shapes import prepare,learn_onsets,syllabify

NAMES={'jpn':'Japanese','cmn':'Mandarin','ita':'Italian','ekk':'Estonian','hrv':'Croatian','khk':'Mongolian','rus':'Russian'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def entropy(c):
    t=sum(c.values());return -sum(n/t*math.log2(n/t) for n in c.values()) if t else 0.
def stats(words,boundary=False):
    pairs=Counter()
    for w in words:
        s=['BOS']+w+['EOS'] if boundary else w
        pairs.update(zip(s,s[1:]))
    row=Counter();col=Counter()
    for (a,b),n in pairs.items():row[a]+=n;col[b]+=n
    total=sum(pairs.values())
    mi=sum(n/total*math.log2(n*total/(row[a]*col[b])) for (a,b),n in pairs.items()) if total else None
    hc=sum(n/total*math.log2(row[a]/n) for (a,b),n in pairs.items()) if total else None
    return dict(pairs=pairs,row=row,col=col,total=total,mi=mi,h_cond=hc)
def js(p,q):
    if not sum(p.values()) or not sum(q.values()):return None
    ps=sum(p.values());qs=sum(q.values());v=0
    for k in p.keys()|q.keys():
        a=p[k]/ps;b=q[k]/qs;m=(a+b)/2
        if a:v+=a*math.log2(a/m)/2
        if b:v+=b*math.log2(b/m)/2
    return v

def null_mi(words,draws,rng):
    groups=defaultdict(list)
    for w in words:groups[len(w)].append(w)
    mats=[np.array(v,dtype=object) for k,v in groups.items() if k>1]
    vals=[]
    for _ in range(draws):
        ws=[]
        for mat in mats:
            x=mat.copy()
            for j in range(x.shape[1]):x[:,j]=rng.permutation(x[:,j])
            ws.extend(x.tolist())
        vals.append(stats(ws)['mi'])
    return np.array(vals,dtype=float)

def natural_dataset(name,lang,records,rejected):
    parsed=[];seen=set();duplicates=0
    for rid,form,tokens in records:
        key=tuple(tokens)
        if key in seen:
            duplicates+=1;continue
        seen.add(key)
        try:
            segs,notes=prepare(tokens,lang)
            alt,_=prepare(tokens,lang,False)
            parsed.append((rid,form,tokens,segs,alt,notes))
        except ValueError as e:rejected.append(dict(id=rid,word=form,reason=str(e)))
    onsets=learn_onsets([x[3] for x in parsed]);alt_onsets=learn_onsets([x[4] for x in parsed])
    rows=[]
    for rid,form,tokens,segs,alt,notes in parsed:
        primary=syllabify(segs,lang,onsets)
        single=syllabify(segs,lang,onsets,True)
        split=syllabify(alt,lang,alt_onsets)
        if lang=='cmn':
            nch=sum('\u4e00'<=x<='\u9fff' for x in form)
            if nch and nch!=len(primary):
                rejected.append(dict(id=rid,word=form,reason='Han character / inferred syllable count mismatch (hiatus, erhua, or transcription)',ipa=' '.join(tokens),inferred=[x[0] for x in primary]));continue
        rows.append(dict(id=rid,word=form,ipa=' '.join(tokens),syllables=[x[1] for x in primary],
                         shapes=[x[0] for x in primary],singleton=[x[0] for x in single],
                         split_vowels=[x[0] for x in split],notes=notes))
    return dict(name=name,lang=lang,rows=rows,rejected=rejected,duplicates=duplicates,input_rows=len(records)+sum(x['reason']=='multiword/boundary entry' for x in rejected),onsets=[list(x) for x in sorted(onsets)])

def restricted_kono_word(w):
    """Analysis-only hard onset restriction, including relaxed fallback."""
    from konophon import Word
    from konophon.syllable import Syllabifier
    class NoNasalLOnset(Syllabifier):
        def legal_onset(self, seq):
            if tuple(p.spell for p in seq) in {('n','l'),('m','l')}:
                return False
            return super().legal_onset(seq)
    return Word(w.seq, syllabifier=NoNasalLOnset(w.inv))

def load_all(project,out):
    sys.path.insert(0,str(project));from konophon.corpus import autoload
    sys.path.insert(0,str(project/'typology'));from kono_ipa import CONSONANT_IPA,VOWEL_IPA
    ipa={**CONSONANT_IPA,**VOWEL_IPA}; manifest={};ds=[]
    kp=project.parent/'kono-dictionary-editor/src/data/konomeno-v5.json'
    corpus=autoload(kp);manifest[str(kp.relative_to(project.parent))]=sha(kp)
    rows=[];seen=set()
    for w in corpus:
        if w.spell in seen:continue
        seen.add(w.spell)
        sylls=w.syllables
        if w.notes:
            # Preserve explicit corpus parser warnings in audit, rather than treating fallback as certain.
            notes=list(w.notes)
        else:notes=[]
        shapes=[s.shape for s in sylls]
        rows.append(dict(id=w.spell,word=w.spell,ipa=' '.join(ipa[p.spell] for p in w.seq),
                         syllables=[s.spell for s in sylls],shapes=shapes,singleton=shapes,
                         split_vowels=shapes,notes=notes))
    baseline=rows; rows=[]; changes=[]
    by_word={w.spell:w for w in corpus}
    for old in baseline:
        w=restricted_kono_word(by_word[old['word']])
        shapes=[s.shape for s in w.syllables]
        row=dict(old,syllables=[s.spell for s in w.syllables],shapes=shapes,
                 singleton=shapes,split_vowels=shapes,notes=list(w.notes))
        assert ''.join(row['syllables'])==''.join(old['syllables'])
        assert not any(tuple(p.spell for p in s.onset) in {('n','l'),('m','l')} for s in w.syllables)
        rows.append(row)
        if row['syllables']!=old['syllables']:
            changes.append(dict(word=w.spell,before=old['syllables'],after=row['syllables'],
                                shapes_before=old['shapes'],shapes_after=shapes,notes=row['notes']))
    dump(out/'konomeno_mop_changes.json',changes)
    ds.append(dict(name='Konomeno',lang='kono',condition='No nl/ml onsets, including fallback',rows=rows,rejected=corpus.rejected,onsets=[]))
    ds.append(dict(name='Konomeno_original_MOP',lang='kono',rows=baseline,rejected=corpus.rejected,onsets=[]))
    fp=project/'typology/raw/northeuralex-forms.csv';manifest['typology/raw/northeuralex-forms.csv']=sha(fp)
    allrows=list(csv.DictReader(fp.open()))
    for lang,name in NAMES.items():
        records=[];reject=[]
        for r in allrows:
            if r['Language_ID']!=lang:continue
            tokens=r['Segments'].split()
            if '+' in tokens or '_' in tokens:
                reject.append(dict(id=r['ID'],word=r['Value'],reason='multiword/boundary entry'));continue
            records.append((r['ID'],r['Value'],tokens))
        ds.append(natural_dataset(name+'_NE',lang,records,reject))
    for lang,stem,code in [('ekk','estonian','est-Latn'),('hrv','croatian','hrv-Latn')]:
        fp=project/f'typology/wordlists/{stem}.txt';manifest[f'typology/wordlists/{stem}.txt']=sha(fp)
        cache=out/f'{stem}_ipa_cache.json'
        old=json.loads(cache.read_text()) if cache.exists() else {}
        if old.get('sha256')==sha(fp):recs=old['records']
        else:
            import epitran
            import importlib.metadata
            epi=epitran.Epitran(code)
            forms=list(dict.fromkeys(x.strip() for x in fp.read_text().splitlines() if x.strip()))
            recs=[(str(i+1),w,epi.trans_list(w)) for i,w in enumerate(forms)]
            dump(cache,dict(sha256=sha(fp),epitran_version=importlib.metadata.version('epitran'),records=recs))
        ds.append(natural_dataset(NAMES[lang]+'_TXT',lang,recs,[]))
    # Same words / paired observations: a direct view of effects of lengthening and gemination.
    fp=project/'out/stimuli/stimuli_blind.tsv';manifest['out/stimuli/stimuli_blind.tsv']=sha(fp)
    sys.path.insert(0,str(project/'scripts'));from compare_weight_scales import underlying_syllables
    from konophon import Word
    under=[];surface=[]
    for r in csv.DictReader(fp.open(),delimiter='\t'):
        u,_,_=underlying_syllables(r['単語'],r['音節化・長短'])
        for dest,spelling in [(under,'.'.join(u)),(surface,r['音節化・長短'])]:
            w=Word(spelling);shapes=[s.shape for s in w.syllables]
            dest.append(dict(id=r['順'],word=r['単語'],ipa='',syllables=[s.spell for s in w.syllables],
                             shapes=shapes,singleton=shapes,split_vowels=shapes,notes=list(w.notes)))
    for name,rows in [('Kono_stimuli_base',under),('Kono_stimuli_surface',surface)]:
        ds.append(dict(name=name,lang='kono',rows=rows,rejected=[],onsets=[]))
    return ds,manifest

def export(ds,out,labels,draws,seed,min_count):
    summaries=[];rng=np.random.default_rng(seed)
    for d in ds:
        name=d['name'];words=[r['shapes'] for r in d['rows']];freq=Counter(s for w in words for s in w)
        n=len(words);nt=sum(freq.values());inside=stats(words);edge=stats(words,True)
        null=null_mi(words,draws,rng)
        summary=dict(name=name,words=n,syllables=nt,types=len(freq),internal_pairs=inside['total'],
                     monosyllabic=sum(len(w)==1 for w in words)/n,closed=sum(v for k,v in freq.items() if k.endswith('C'))/nt,
                     complex_onset=sum(v for k,v in freq.items() if k.startswith('CC'))/nt,
                     long_nucleus=sum(v for k,v in freq.items() if 'VV' in k)/nt,
                     H=entropy(freq),MI_internal=inside['mi'],MI_boundaries=edge['mi'],H_cond_internal=inside['h_cond'],
                     null_mean=float(null.mean()),null_low=float(np.quantile(null,.025)),null_high=float(np.quantile(null,.975)),
                     permutation_p=float((1+sum(null>=inside['mi']))/(draws+1)),
                     rejected=len(d['rejected']),flagged=sum(bool(r['notes']) for r in d['rows']),
                     MI_singleton=stats([r['singleton'] for r in d['rows']])['mi'],
                     MI_split_vowels=stats([r['split_vowels'] for r in d['rows']])['mi'],
                     singleton_changed=sum(r['shapes']!=r['singleton'] for r in d['rows']),
                     vowel_split_changed=sum(r['shapes']!=r['split_vowels'] for r in d['rows']))
        summaries.append(summary)
        dump(out/f'audit_{name}.json',d)
        dump(out/f'frequencies_{name}.json',freq)
        for scope,bound in [('internal',False),('boundaries',True)]:
            st=stats(words,bound);labs=(['BOS'] if bound else [])+labels+(['EOS'] if bound else [])
            p=np.full((len(labs),len(labs)),np.nan);mi=p.copy();count=np.zeros_like(p,dtype=int)
            records=[]
            for i,a in enumerate(labs):
                for j,b in enumerate(labs):
                    c=st['pairs'][a,b];count[i,j]=c
                    if st['row'][a]:p[i,j]=c/st['row'][a]
                    val=math.log2(c*st['total']/(st['row'][a]*st['col'][b])) if c else None
                    if c>=min_count:mi[i,j]=val
                    if c:
                        examples=[r['word'] for r in d['rows'] if (a,b) in list(zip((['BOS']+r['shapes'] if bound else r['shapes']), (r['shapes']+['EOS'] if bound else r['shapes'][1:])))]
                        records.append(dict(prev=a,next=b,count=c,transition=p[i,j],pmi=val,shown=c>=min_count,examples=list(dict.fromkeys(examples))[:5]))
            dump(out/f'pairs_{name}_{scope}.json',records)
            for tag,array in [('counts',count),('transition',p),('pmi',mi)]:
                with (out/f'{tag}_{name}_{scope}.csv').open('w') as f:
                    writer=csv.writer(f);writer.writerow(['prev/next']+labs)
                    for lab,row in zip(labs,array):writer.writerow([lab]+['' if isinstance(x,(float,np.floating)) and np.isnan(x) else x for x in row])
            plot_matrix(p,labs,name,scope,'transition',out,min_count)
            plot_matrix(mi,labs,name,scope,'pmi',out,min_count)
    dump(out/'summary.json',summaries)
    return summaries

def plot_matrix(arr,labels,name,scope,kind,out,min_count):
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(10,8))
    cmap=plt.get_cmap('RdBu_r' if kind=='pmi' else 'YlOrRd').copy();cmap.set_bad('#d9d9d9')
    im=ax.imshow(np.ma.masked_invalid(arr),cmap=cmap,vmin=-4 if kind=='pmi' else 0,vmax=4 if kind=='pmi' else 1)
    ax.set_xticks(range(len(labels)),labels,rotation=60,ha='right',fontsize=7)
    ax.set_yticks(range(len(labels)),labels,fontsize=7)
    ax.set_xlabel('Next syllable shape');ax.set_ylabel('Previous syllable shape')
    ax.set_title(f'{name}: {kind} ({scope})\n'+(f'PMI bits, count >= {min_count}; gray = unestimated; colors clipped at +/-4' if kind=='pmi' else 'Row-normalized probability; gray = no outgoing observations'))
    fig.colorbar(im,ax=ax,shrink=.75);fig.tight_layout();fig.savefig(out/f'{kind}_{name}_{scope}.png',dpi=140);plt.close(fig)

def write_report(ds,summary,out,draws):
    uni={d['name']:Counter(s for r in d['rows'] for s in r['shapes']) for d in ds}
    pair={d['name']:stats([r['shapes'] for r in d['rows']])['pairs'] for d in ds}
    lines=['# 音節構造の遷移・PMI：コノメノとの比較','',
           '語彙タイプをほぼ一票として数えた記述比較。音声の時間・強勢・高低は測定していない。NEはNorthEuraLex，TXTは既存.txtのEpitran転写。自然言語の音節境界は近似推定。','',
           '| 資料 | 語数 | 音節数 | 語内隣接数 | 単音節語% | 閉音節% | CC開始% | 長・複合核% | 語内MI | 境界込みMI |','|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:
        lines.append(f'| {s["name"]} | {s["words"]} | {s["syllables"]} | {s["internal_pairs"]} | {100*s["monosyllabic"]:.1f} | {100*s["closed"]:.1f} | {100*s["complex_onset"]:.1f} | {100*s["long_nucleus"]:.1f} | {s["MI_internal"]:.3f} | {s["MI_boundaries"]:.3f} |')
    lines+=['','## コノメノのMOP変更','',
            '`Konomeno` は nl・ml をオンセットとして許さず再音節化した辞書。`Konomeno_original_MOP` は変更前。自然言語との距離は変更後を基準とする。刺激語の2資料は記録された境界を保持した参考資料で，この制約を適用していない。','',
            '| 語 | 変更前 | 変更後 |','|---|---|---|']
    for r in json.loads((out/'konomeno_mop_changes.json').read_text()):
        lines.append('| '+r['word']+' | '+'.'.join(r['before'])+' | '+'.'.join(r['after'])+' |')
    lines+=['','## コノメノとの分布差','', 'Jensen–Shannon divergence（bits，0は同じ，1は支持が重ならない）。語内bigramの差には音節型の出現率自体の差も含まれる。近さはかっこよさ・リズム全体の近さではない。','',
            '| 資料 | 音節型JS | 語内bigram JS | 長さを潰した型JS |','|---|---:|---:|---:|']
    def short(c):
        out=Counter()
        for k,v in c.items():out[k.replace('VV','V')]+=v
        return out
    for d in ds[1:]:
        name=d['name'];lines.append(f'| {name} | {js(uni["Konomeno"],uni[name]):.3f} | {js(pair["Konomeno"],pair[name]):.3f} | {js(short(uni["Konomeno"]),short(uni[name])):.3f} |')
    lines+=['','## 語長・位置を保ったシャッフルとの比較','',
            f'同じ音節数の語どうしで，各位置の音節型を独立に交換する（seed固定，{draws}回）。語長と位置別の周辺分布は保つ。単なる語頭/語末の型の偏りを超えた語内の組合せがあるかを見る。区間は帰無分布の95%範囲であり推定量の信頼区間ではない。p値は探索的・多重比較未補正。','',
            '| 資料 | 観測MI | 帰無平均 | 帰無95%範囲 | 観測−帰無平均 | p |','|---|---:|---:|---|---:|---:|']
    for s in summary:
        lines.append(f'| {s["name"]} | {s["MI_internal"]:.3f} | {s["null_mean"]:.3f} | {s["null_low"]:.3f}–{s["null_high"]:.3f} | {s["MI_internal"]-s["null_mean"]:+.3f} | {s["permutation_p"]:.3f} |')
    lines+=['','## 音節化の感度','', '単子音オンセット優先への変更と，別々の母音トークンを統合しない場合を比較。これは音節化の不確かさの全範囲ではない。コノメノは体系の音節化を固定しているためこの2項目は0。','',
            '| 資料 | 単子音優先で変わる語 | 母音非統合で変わる語 | MI（単子音優先） | MI（母音非統合） | 除外行 |','|---|---:|---:|---:|---:|---:|']
    for s in summary:lines.append(f'| {s["name"]} | {s["singleton_changed"]} | {s["vowel_split_changed"]} | {s["MI_singleton"]:.3f} | {s["MI_split_vowels"]:.3f} | {s["rejected"]} |')
    for d in ds:
        name=d['name'];lines+=['',f'## {name}','', '型の頻度：'+', '.join(f'{k} {100*v/sum(uni[name].values()):.1f}%' for k,v in uni[name].most_common(8)), '',
            f'![語内遷移](transition_{name}_internal.png)',f'![語内PMI](pmi_{name}_internal.png)','',
            '| 前 → 次 | 件数 | 遷移確率 | PMI | 例 |','|---|---:|---:|---:|---|']
        recs=json.loads((out/f'pairs_{name}_internal.json').read_text())
        for r in sorted((r for r in recs if r['shown']),key=lambda r:-r['pmi'])[:8]:
            lines.append(f'| {r["prev"]} → {r["next"]} | {r["count"]} | {r["transition"]:.3f} | {r["pmi"]:+.3f} | {", ".join(r["examples"])} |')
    lines+=['','各行の入力・推定境界・注記は `audit_*.json`，全組合せの度数・遷移・PMIは同名のCSV/JSON。境界込みの図は `*_boundaries.png`。PMIを色付けする最小度数はmanifest.jsonのmin_count（既定5），0件と閾値未満を0 PMIに置き換えない。']
    (out/'comparison.md').write_text('\n'.join(lines)+'\n')
    import matplotlib.pyplot as plt
    core=[s for s in summary if s['name'] not in ('Estonian_NE','Croatian_NE','Kono_stimuli_base','Kono_stimuli_surface','Konomeno_original_MOP')]
    fig,axes=plt.subplots(1,3,figsize=(16,5))
    for ax,key,title in zip(axes,['closed','complex_onset','long_nucleus'],['Closed syllables','Complex onsets','Long/complex nuclei']):
        ax.barh([s['name'] for s in core],[100*s[key] for s in core]);ax.invert_yaxis();ax.set_xlim(0,100);ax.set_title(title);ax.set_xlabel('% of syllables')
    fig.tight_layout();fig.savefig(out/'overview.png',dpi=150);plt.close(fig)

def plot_panels(summary,out):
    import matplotlib.pyplot as plt
    names=['Konomeno','Japanese_NE','Mandarin_NE','Italian_NE','Estonian_TXT','Croatian_TXT','Mongolian_NE','Russian_NE']
    for kind in ['transition','pmi']:
        fig,axes=plt.subplots(2,4,figsize=(32,17))
        cmap=plt.get_cmap('RdBu_r' if kind=='pmi' else 'YlOrRd').copy();cmap.set_bad('#d9d9d9')
        for ax,name in zip(axes.flat,names):
            with (out/f'{kind}_{name}_internal.csv').open() as f:rows=list(csv.reader(f))
            labels=rows[0][1:];arr=np.array([[float(x) if x else np.nan for x in r[1:]] for r in rows[1:]])
            im=ax.imshow(np.ma.masked_invalid(arr),cmap=cmap,vmin=-4 if kind=='pmi' else 0,vmax=4 if kind=='pmi' else 1)
            ax.set_xticks(range(len(labels)),labels,rotation=70,ha='right',fontsize=7)
            ax.set_yticks(range(len(labels)),labels,fontsize=7);ax.set_title(name)
        fig.suptitle(f'Syllable shape {kind}: within-word pairs; same axes and color scale\nGray = unavailable / below threshold; columns = next, rows = previous',fontsize=18)
        fig.tight_layout(rect=(0,0,.95,.95));cax=fig.add_axes([.965,.2,.012,.6]);fig.colorbar(im,cax=cax)
        fig.savefig(out/f'comparison_{kind}.png',dpi=140);plt.close(fig)


def main():
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,default=Path(__file__).resolve().parent.parent)
    p.add_argument('--out',type=Path);p.add_argument('--permutations',type=int,default=200);p.add_argument('--seed',type=int,default=20260911);p.add_argument('--min-count',type=int,default=5)
    a=p.parse_args()
    if a.permutations<1 or a.min_count<1:p.error('permutations and min-count must be positive')
    project=a.project.resolve();out=a.out or project/'typology/output/syllable';out.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR','/tmp/kono-syllable-mpl')
    import matplotlib;matplotlib.use('Agg')
    ds,manifest=load_all(project,out)
    dump(out/'manifest.json',dict(inputs=manifest,seed=a.seed,permutations=a.permutations,python=sys.version,min_count=a.min_count,code={p.name:sha(p) for p in (Path(__file__),Path(__file__).with_name('syllable_shapes.py'))}))
    labels=sorted({s for d in ds for r in d['rows'] for s in r['shapes']},key=lambda s:(len(s),s))
    print('datasets',[(d['name'],len(d['rows'])) for d in ds],flush=True)
    summary=export(ds,out,labels,a.permutations,a.seed,a.min_count)
    write_report(ds,summary,out,a.permutations)
    plot_panels(summary,out)
    print('wrote',out,flush=True)
if __name__=='__main__':main()
