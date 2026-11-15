"""Conservative experimental LaTeX relationship comparison, not semantic proof.

No production AST, source alignment, correction, macro expansion or trusted syntax
validation. Unknown macros are retained; unsupported syntax is explicitly flagged.
Exact/normalized string comparison uses only the previously frozen formatting rule.
"""
from collections import Counter
import json
import re


def formatting(text):return text.replace('\r\n','\n').replace('\r','\n').strip()


def relationships(text):
    tokens=re.findall(r'\\[A-Za-z]+|\\.|[^\s]',text);index=0;features={k:[] for k in ['fractions','radicals','subscripts','superscripts','summation_limits','parentheses','operators']};warnings=[]
    def key(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'))
    def argument():
        nonlocal index
        if index>=len(tokens):raise ValueError('Missing command/script argument')
        if tokens[index]=='{':index+=1;return sequence('}')
        return [atom()]
    def atom():
        nonlocal index
        if index>=len(tokens):raise ValueError('Missing atom')
        t=tokens[index];index+=1
        if t in {'}',')',']'}:raise ValueError('Unexpected closing delimiter')
        if t in {r'\left',r'\right',r'\big',r'\Big',r'\bigl',r'\bigr'}:return atom()
        if t=='{':return sequence('}')
        if t in {'(', '['}:
            close=')' if t=='(' else ']';inside=sequence(close);features['parentheses'].append(key([t,inside,close]));return ['fence',t,inside,close]
        if t in {r'\frac',r'\dfrac',r'\tfrac'}:
            n,d=argument(),argument();features['fractions'].append(key([n,d]));return ['fraction',n,d]
        if t==r'\sqrt':
            degree=None
            if index<len(tokens) and tokens[index]=='[':index+=1;degree=sequence(']')
            inside=argument();features['radicals'].append(key([degree,inside]));return ['radical',degree,inside]
        if t in {r'\mathrm',r'\operatorname',r'\text',r'\mathbf',r'\mathcal',r'\boldsymbol'}:return [t,argument()]
        if t in {'=', '+', '-', '/', '*', '<', '>', r'\cdot',r'\times',r'\approx',r'\le',r'\ge',r'\sum',r'\prod',r'\int'}:features['operators'].append(t)
        return ['atom',t]
    def sequence(close=None):
        nonlocal index
        result=[]
        while index<len(tokens):
            if close and tokens[index]==close:index+=1;return result
            if tokens[index] in {'^','_'}:raise ValueError('Unattached script')
            node=atom();base=node;scripts={}
            while index<len(tokens) and tokens[index] in {'^','_'}:
                kind=tokens[index];index+=1
                if kind in scripts:raise ValueError('Duplicate script')
                value=argument();scripts[kind]=value
                features['subscripts' if kind=='_' else 'superscripts'].append(key([base,value]))
            if base==['atom',r'\sum']:features['summation_limits'].append(key([scripts.get('_'),scripts.get('^')]))
            if scripts:node=['scripts',base,scripts]
            result.append(node)
        if close:raise ValueError('Unclosed delimiter')
        return result
    try:tree=sequence()
    except ValueError as error:return dict(status='unsupported_or_malformed',reason=str(error),features=None,tree=None)
    return dict(status='diagnostic_parse_only',features=features,tree=tree,syntax_validity=None,
                caveat='Not a full TeX grammar/macro expander; unmatched feature keys are not proof of semantic error')


def counts(expected,predicted):
    a,b=Counter(expected),Counter(predicted);correct=sum((a&b).values());denominator=sum(a.values())
    return dict(correct=correct,incorrect_proposals=sum((b-a).values()),missing=sum((a-b).values()),ambiguous=0,
                reference_denominator=denominator,predicted_denominator=sum(b.values()),
                recall=correct/denominator if denominator else None)


def compare(reference,prediction):
    if prediction is None:return dict(status='no_prediction',exact=None,formatting_normalized=None,components=None,complete_expression_correct=None)
    a,b=relationships(reference),relationships(prediction)
    result=dict(status='diagnostic_comparison',exact=reference==prediction,formatting_normalized=formatting(reference)==formatting(prediction),
                reference_parse_status=a['status'],prediction_parse_status=b['status'],syntax_validity=None,
                complete_expression_correct=None,complete_expression_reason='Requires explicit source-checked adjudication; tree/string agreement is not semantic equivalence')
    if a['features'] is None or b['features'] is None:
        result.update(components=None,component_reason='Unsupported/malformed lightweight parse; not silently counted correct');return result
    result.update(components={k:counts(a['features'][k],b['features'][k]) for k in a['features']},strict_diagnostic_tree_equal=a['tree']==b['tree'])
    return result
