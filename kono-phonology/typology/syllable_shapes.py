"""Auditable, approximate IPA syllabification for typological structure counts.

No claim of phonological ground truth. See output/syllable/README.md.
"""
from collections import Counter
from dataclasses import dataclass
import unicodedata as ud

VOWELS = set('aeiouyæøœɑɐɒɔəɘɛɜɞɤɨɪɯɵɶʉʊʌʏ')
CONS = set('pbtdkgqɢʔɖʈɟcɡmnŋɲɳɴɱlrɻɾɽɭʎʟɫɮɬʀʁjwʋɥɰfvszʃʒɕʑʂʐθðxɣχhɦçʝɸβ')
MOD = set('ˑːʲˠʰʷˀ˞ˤˈˌʼ’')

def base(s):
    return ''.join(ch for ch in ud.normalize('NFD',s) if ud.category(ch)!='Mn' and ch not in MOD)

@dataclass
class Segment:
    ipa: str
    nucleus: bool
    long: bool = False


def prepare(tokens, lang, merge_vowels=True):
    out=[]; notes=[]
    for token_index,tok in enumerate(tokens):
        if tok in ('+','_','-'): raise ValueError('multiword/boundary entry')
        if all(c.isnumeric() or c in '˥˦˧˨˩' for c in tok):
            # Remove tone as a feature; it is NOT reliably a syllable delimiter in this source.
            continue
        b=base(tok)
        if not b: continue
        vowel=all(c in VOWELS for c in b) or '\u0329' in ud.normalize('NFD',tok) or (lang=='hrv' and b=='r' and 'ː' in tok)
        if not vowel and not all(c in CONS for c in b): raise ValueError('unknown IPA token '+tok)
        if vowel:
            out.append(Segment(tok,True,'ː' in tok or len(b)>1))
        elif 'ː' in tok and any(all(c in VOWELS for c in base(t)) for t in tokens[:token_index] if base(t)) and any(all(c in VOWELS for c in base(t)) for t in tokens[token_index+1:] if base(t)):
            out.extend([Segment(tok.replace('ː',''),False),Segment(tok.replace('ː',''),False)])
            notes.append('geminate expanded')
        else:
            out.append(Segment(tok,False))
            if 'ː' in tok:notes.append('edge long consonant: one C slot')
    # Japanese C+j represents a palatalized onset, not a two-C cluster.
    if lang=='jpn':
        combined=[]
        for x in out:
            if combined and base(x.ipa)=='s' and combined[-1].ipa=='t':
                combined[-1].ipa='ts';notes.append('split Japanese affricate normalized')
            elif base(x.ipa)=='j' and combined and not combined[-1].nucleus:
                combined[-1].ipa += 'ʲ';notes.append('C+j palatalized onset normalized')
            else:combined.append(x)
        out=combined
    # Croatian unmarked syllabic r (also used by Epitran); explicit r̩ already handled.
    if lang=='hrv':
        for i,x in enumerate(out):
            if base(x.ipa)=='r' and not x.nucleus and (i==0 or not out[i-1].nucleus) and (i+1==len(out) or not out[i+1].nucleus):
                x.nucleus=True;notes.append('syllabic r inferred')
    # Mandarin adjacent vowel tokens constitute a rime; rare hiatus is flagged by Han-count audit.
    # Epitran Estonian writes adjacent vowels separately: treat runs as one nucleus, including long vowels.
    # Italian pre-vocalic i/u in the same uninterrupted vowel run are grouped (hiatus ambiguous).
    merged=[]
    for x in out:
        join=(merged and x.nucleus and merged[-1].nucleus and merge_vowels and
              (lang in ('cmn','ekk') or (lang=='ita' and base(merged[-1].ipa) in ('i','u'))))
        if join:
            merged[-1]=Segment(merged[-1].ipa+'~'+x.ipa,True,True)
            notes.append('vowel run merged')
        else: merged.append(x)
    if not any(x.nucleus for x in merged): raise ValueError('no nucleus')
    return merged,sorted(set(notes))


def learn_onsets(words):
    counts=Counter()
    for word in words:
        onset=[]
        for x in word:
            if x.nucleus: break
            onset.append(base(x.ipa))
        if onset:counts[tuple(onset)]+=1
    return {k for k,v in counts.items() if v>=2}


def syllabify(word,lang,onsets,singleton=False):
    nuclei=[i for i,x in enumerate(word) if x.nucleus]
    starts=[0]
    for a,b in zip(nuclei,nuclei[1:]):
        cluster=word[a+1:b]
        keys=tuple(base(x.ipa) for x in cluster)
        allowed=1 if singleton or lang=='jpn' else len(cluster)
        cut=len(cluster)
        for k in range(len(cluster)+1):
            tail=keys[k:]
            if len(tail)>allowed:continue
            # Mandarin nasal/rhotic finals cannot begin a new syllable here except n.
            if lang=='cmn' and tail and tail[0] in ('ŋ','ɻ'):continue
            if lang=='jpn' and tail and tail[0]=='ɴ':continue
            if not tail or len(tail)==1 or tail in onsets:
                # A geminate may not be wholly in an onset.
                if any(tail[j]==tail[j+1] for j in range(len(tail)-1)):continue
                cut=k;break
        starts.append(a+1+cut)
    ends=starts[1:]+[len(word)]
    result=[]
    for start,end in zip(starts,ends):
        s=word[start:end];ns=[i for i,x in enumerate(s) if x.nucleus]
        assert len(ns)==1
        i=ns[0]
        shape='C'*i+('VV' if s[i].long else 'V')+'C'*(len(s)-i-1)
        result.append((shape,' '.join(x.ipa for x in s)))
    return result
