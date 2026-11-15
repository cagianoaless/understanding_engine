"""Small fallible geometric expression graph. No reference labels or PDF loading.

Inputs are positioned symbols and straight primitives in one verified TOPLEFT
frame. Width estimates are marked hints; missing glyph identities stay unknown.
This is deliberately not a TeX parser or a mathematical reading-order solver.
"""
from copy import deepcopy
import math
from statistics import median

CONFIG = {'fraction_band_em':2.5,'script_size_ratio':0.82,'script_dy_min_em':0.12,
          'script_dy_max_em':1.4,'script_x_gap_em':1.1,'script_tie_em':0.2,
          'baseline_tolerance_em':0.1,'run_gap_em':0.9,'number_gap_em':2.0,
          'number_min_page_fraction':0.65,'bar_max_slope':0.001}


def descendants(node):
    if node['kind'] in {'symbol','unresolved_symbol'}:return node['unit_ids'][:]
    return list(dict.fromkeys(x for c in node.get('children',[]) for x in descendants(c)))


def typed_tree(node):
    """Type only already predicted sequences; do not change geometric decisions.

    Explicit parentheses/operators can be typed. Implicit multiplication,
    function application, a conditional bar and unknown operators abstain.
    """
    if node['kind'] not in {'sequence','equality'}:
        return {**node,'children':[typed_tree(c) for c in node.get('children',[])]}
    original=node['children'];grouped=[];i=0
    while i<len(original):
        n=original[i]
        if n.get('text')=='(':
            level=1;j=i+1
            while j<len(original):
                if original[j].get('text')=='(':level+=1
                if original[j].get('text')==')':level-=1
                if level==0:break
                j+=1
            if level==0:
                grouped.append(dict(kind='group',children=[typed_tree(n),typed_tree(dict(kind='sequence',children=original[i+1:j])),typed_tree(original[j])]))
                i=j+1;continue
        grouped.append(typed_tree(n));i+=1
    if any(n.get('text') in {',',';','.'} for n in grouped):
        parts=[];current=[]
        for n in grouped:
            if n.get('text') in {',',';','.'}:
                if current:parts.append(typed_tree(dict(kind='sequence',children=current)));current=[]
                parts.append(n)
            else:current.append(n)
        if current:parts.append(typed_tree(dict(kind='sequence',children=current)))
        return dict(kind='multipart',punctuation_role='geometric separator hypothesis',children=parts)
    # Explicit low-precedence operators only. A sequence does not imply product.
    for symbols,kind in [({'='},'equality'),({'>','<'},'comparison'),({'+','−','-'},'arithmetic')]:
        positions=[i for i,n in enumerate(grouped) if n.get('text') in symbols]
        if positions and 0<positions[-1]<len(grouped)-1:
            i=positions[-1]
            return dict(kind=kind,operator=grouped[i]['text'],children=[typed_tree(dict(kind='sequence',children=grouped[:i])),grouped[i],typed_tree(dict(kind='sequence',children=grouped[i+1:]))])
    for i,n in enumerate(grouped):
        base=n['children'][0] if n['kind']=='indexed' else n
        if base.get('text')=='∑' and i<len(grouped)-1:
            return dict(kind='sequence',implicit_operations='unresolved',children=grouped[:i]+[
                dict(kind='summation',index_role='only attached script evidence; domain interpretation unresolved',children=[n,typed_tree(dict(kind='sequence',children=grouped[i+1:]))])])
    return dict(kind='sequence',implicit_operations='unresolved',children=grouped)


def build(units,shapes,page_width):
    units=deepcopy(units);shapes=deepcopy(shapes)
    assert all(u['anchor'] is not None and u['font_size']>0 and all(math.isfinite(v) for v in u['anchor']) for u in units)
    typical=median(u['font_size'] for u in units) if units else 10
    relations={'fractions':[],'indices':[],'summations':[],'delimiters':[],'operators':[],'expression_parts':[]}
    relations['operators']=[u['id'] for u in units if u['text'] in {'=','+','−','-','>','<'}]
    ambiguities=[]
    def leaf(u):
        x,y=u['anchor'];f=u['font_size'];width=u.get('width_hint',.55*f)
        return dict(kind='unresolved_symbol' if u['text']=='\ufffd' or u['text'].startswith('(cid:') else 'symbol',
                    text=u['text'],unit_ids=[u['id']],anchor=[x,y],size=f,right=x+width,children=[])
    leaves=[leaf(u) for u in units];number=[]
    # An isolated right-hand parenthesized integer is only a number hypothesis.
    ordered=sorted(leaves,key=lambda n:n['anchor'][0])
    for count in range(3,min(8,len(ordered))+1):
        group=ordered[-count:];text=''.join(n['text'] for n in group)
        if (text.startswith('(') and text.endswith(')') and text[1:-1].isdigit()
            and group[0]['anchor'][0]>page_width*CONFIG['number_min_page_fraction']
            and max(n['anchor'][1] for n in group)-min(n['anchor'][1] for n in group)<.2*typical
            and len(ordered)>count and group[0]['anchor'][0]-ordered[-count-1]['right']>CONFIG['number_gap_em']*typical):
            number=[x for n in group for x in descendants(n)];break
    leaves=[n for n in leaves if not set(n['unit_ids'])&set(number)]

    def sequence(nodes,bars,depth=0):
        if depth>8:
            ambiguities.append('Recursion bound');return dict(kind='unresolved_sequence',children=nodes)
        pool=nodes[:];fraction_nodes=[]
        for bar in sorted(bars,key=lambda s:(s['bbox'][2]-s['bbox'][0],s['id'])):
            x0,y0,x1,y1=bar['bbox'];width=x1-x0
            if width<=2 or abs(y1-y0)>CONFIG['bar_max_slope']*width:continue
            y=(y0+y1)/2
            above=[n for n in pool if x0-.1*typical<=n['anchor'][0]<=x1+.1*typical and y-CONFIG['fraction_band_em']*typical<n['anchor'][1]<y-.08*typical]
            below=[n for n in pool if x0-.1*typical<=n['anchor'][0]<=x1+.1*typical and y+.08*typical<n['anchor'][1]<y+CONFIG['fraction_band_em']*typical]
            if not above or not below:continue
            used=set(x for n in above+below for x in descendants(n));pool=[n for n in pool if not set(descendants(n))&used]
            rel=dict(kind='fraction',bar_id=bar['id'],bar_bbox=bar['bbox'],numerator=[x for n in above for x in descendants(n)],denominator=[x for n in below for x in descendants(n)])
            relations['fractions'].append(rel)
            fraction_nodes.append(dict(kind='fraction',bar_id=bar['id'],anchor=[x0,y+.25*typical],size=typical,right=x1,
                                       children=[sequence(above,[],depth+1),sequence(below,[],depth+1)]))
        # Lexical operator runs and equal-size script runs, using only geometry.
        grouped=[];consumed=set()
        for n in sorted(pool,key=lambda n:(n['anchor'][1],n['anchor'][0])):
            if id(n) in consumed:continue
            run=[n];consumed.add(id(n))
            for nxt in sorted(pool,key=lambda n:n['anchor'][0]):
                if id(nxt) in consumed or nxt['anchor'][0]<run[-1]['anchor'][0]:continue
                last=run[-1]
                if (abs(nxt['size']-n['size'])<.01*n['size'] and abs(nxt['anchor'][1]-n['anchor'][1])<CONFIG['baseline_tolerance_em']*n['size']
                    and -.1*n['size']<=nxt['anchor'][0]-last['right']<CONFIG['run_gap_em']*n['size']):
                    proposed=''.join(z.get('text','') for z in run+[nxt])
                    if n['size']<.85*typical or any(word.startswith(proposed) for word in ['max','min','lim']):run.append(nxt);consumed.add(id(nxt))
            if len(run)>1:grouped.append(dict(kind='symbol_run',text=''.join(z['text'] for z in run),anchor=n['anchor'],size=n['size'],right=run[-1]['right'],children=run))
            else:grouped.append(n)
        # Small scripts are associated before larger scripts, preserving nesting.
        parent={};attached={}
        for script in sorted(grouped,key=lambda n:(n['size'],n['anchor'][0])):
            candidates=[];sx,sy=script['anchor']
            for base in grouped:
                bx,by=base['anchor'];f=base['size'];dy=sy-by;gap=max(0,sx-base['right'])
                if (script is not base and script['size']<=CONFIG['script_size_ratio']*f and bx<=sx+.1*f
                    and sx-base['right']<=CONFIG['script_x_gap_em']*f
                    and CONFIG['script_dy_min_em']*f<=abs(dy)<=CONFIG['script_dy_max_em']*f):
                    candidates.append((gap+.1*abs(dy),base,'subscript' if dy>0 else 'superscript'))
            candidates.sort(key=lambda c:(c[0],c[1]['anchor'][0]))
            if not candidates:continue
            if len(candidates)>1 and candidates[1][0]-candidates[0][0]<CONFIG['script_tie_em']*candidates[0][1]['size']:
                ambiguities.append(dict(kind='script_candidates',script=descendants(script),bases=[descendants(c[1]) for c in candidates]));continue
            _,base,kind=candidates[0];parent[id(script)]=id(base);attached.setdefault(id(base),[]).append((script,kind))
        def with_scripts(n):
            children=attached.get(id(n),[])
            if not children:return n
            expanded=[with_scripts(c) for c,k in children]
            for (child,kind),expanded_child in zip(children,expanded):relations['indices'].append(dict(kind=kind,base=descendants(n),script=descendants(expanded_child)))
            return dict(kind='indexed',anchor=n['anchor'],size=n['size'],right=max([n['right']]+[c['right'] for c in expanded]),
                        children=[n]+expanded,script_kinds=[k for c,k in children])
        roots=sorted([with_scripts(n) for n in grouped if id(n) not in parent]+fraction_nodes,key=lambda n:n['anchor'][0])
        # Delimiters are hypotheses in the resulting horizontal sequence only.
        stack=[]
        for n in roots:
            if n.get('text')=='(':stack.append(n)
            if n.get('text')==')':
                if stack:relations['delimiters'].append(descendants(stack.pop())+descendants(n))
                else:ambiguities.append(dict(kind='unmatched_delimiter',units=descendants(n)))
        if stack:ambiguities.append(dict(kind='unmatched_delimiter',units=[x for n in stack for x in descendants(n)]))
        # Recognize summation only when a real Unicode sum is supplied. Never
        # reinterpret replacement/CID/font-family names as a summation operator.
        for i,n in enumerate(roots):
            base=n['children'][0] if n['kind']=='indexed' else n
            if base.get('text')=='∑':
                summand=[]
                for next_node in roots[i+1:]:
                    if next_node.get('text') in {'=',',',';'}:break
                    summand+=descendants(next_node)
                index=[x for c,k in zip(n.get('children',[])[1:],n.get('script_kinds',[])) if k=='subscript' for x in descendants(c)]
                relations['summations'].append(dict(operator=descendants(base),index=index,summand=summand))
        # Preserve equalities/arithmetic tokens in a sequence tree; precedence,
        # function application, unknown operators and true reading order abstain.
        return dict(kind='equality' if any(n.get('text')=='=' for n in roots) else 'sequence',
                    arithmetic_precedence='unresolved',children=roots)
    tree=sequence(leaves,[s for s in shapes if s['bbox'] is not None])
    parts=[];current=[]
    for n in tree['children']:
        if n.get('text') in {',',';','.'}:
            if current:parts.append(current);current=[]
        else:current+=descendants(n)
    if current:parts.append(current)
    relations['expression_parts']=parts
    return dict(schema_version='svg-math-prototype.1',configuration=CONFIG,tree=tree,expression_tree=typed_tree(tree),relations=relations,
                status='partial_unresolved' if ambiguities or any(u['text']=='\ufffd' or u['text'].startswith('(cid:') for u in units) else 'hypothesis_not_verified',
                equation_number_units=number,ambiguities=ambiguities,
                conserved_unit_ids=[x for n in tree['children'] for x in descendants(n)]+number,
                unresolved_symbol_ids=[u['id'] for u in units if u['text']=='\ufffd' or u['text'].startswith('(cid:')],
                warning='Geometry hypotheses only; no mathematically complete transcription or verified reading order')
