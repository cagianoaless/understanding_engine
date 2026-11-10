"""Frozen-protocol adapter/scorer. Prediction adaptation never reads references.

Docling items (not layout clusters, and not GT-selected panels) are prediction
units. Every native provenance box is retained. Multi-box items share traversal
position: no ordering between their boxes is invented. Paragraph's literal
coarse `text` rule does not relabel captions/headings as text.
"""

from collections import Counter, defaultdict
import hashlib
import json
import math


def sha(data):
    return hashlib.sha256(data).hexdigest()


def contains(box, point):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def center(box):
    return ((box[0]+box[2])/2, (box[1]+box[3])/2)


def validate_geometry(g):
    w, h = g['width'], g['height']
    if g['rotation'] != 0 or g['raw_rotation'] not in (None, 0) or g['user_unit'] != 1:
        raise ValueError('Unsupported original rotation/UserUnit')
    if any(g[k] != [0, 0, w, h] for k in ('bbox', 'mediabox', 'cropbox')):
        raise ValueError('Ambiguous crop/media transformation')
    if g['raw_cropbox'] is not None and g['raw_cropbox'] != [0, 0, w, h]:
        raise ValueError('Ambiguous raw crop')


def convert_box(native, geometry):
    validate_geometry(geometry)
    origin = native['coord_origin']
    if origin == 'BOTTOMLEFT':
        box = [native['l'], geometry['height']-native['t'],
               native['r'], geometry['height']-native['b']]
    elif origin == 'TOPLEFT':
        box = [native['l'], native['t'], native['r'], native['b']]
    else:
        raise ValueError('Unknown native coordinate origin')
    validate_box(box, geometry)
    return box


def validate_box(box, g):
    if (len(box) != 4 or not all(math.isfinite(x) for x in box)
            or not 0 <= box[0] < box[2] <= g['width']
            or not 0 <= box[1] < box[3] <= g['height']):
        raise ValueError('Malformed/out-of-page prediction geometry')


def adapt_docling(items, document, source_page, mapping):
    g = source_page['geometry']
    validate_geometry(g)
    number = source_page['page_number']
    pages = document['pages']
    native_page = pages.get(str(number), pages.get(number))
    if native_page is None or set(map(int, pages)) != {number}:
        raise ValueError('Native output page identity differs')
    size = native_page['size']
    # No rescaling or coordinate tolerance is used to make a mismatch disappear.
    if size['width'] != g['width'] or size['height'] != g['height']:
        raise ValueError('Native page size differs from original PDF')
    predictions, unsupported = [], []
    for item in items:
        if not item['provenance']:
            unsupported.append({'self_ref': item['self_ref'], 'reason': 'no native provenance box'})
        for i, prov in enumerate(item['provenance']):
            if prov['page_no'] != number:
                raise ValueError('Native item refers to another page')
            predictions.append({'id': item['self_ref']+':prov'+str(i), 'native_label': item['label'],
                'type': mapping.get(item['label'], 'unknown'), 'native_bbox': prov['bbox'],
                'bbox': convert_box(prov['bbox'], g), 'text': item['text'],
                'order_index': item['order_index'], 'native_source_character_ids': None})
    return {'engine': 'docling', 'regions': predictions, 'relations': None,
            'unsupported_items': unsupported, 'native_source_character_crosswalk': False}


def adapt_structure(native, source_page, mapping):
    page = native['pages'][0]
    if page['page_number'] != source_page['page_number']:
        raise ValueError('Structure page identity differs')
    validate_geometry(source_page['geometry'])
    predictions = []
    for region in page['regions']:
        validate_box(region['bbox'], source_page['geometry'])
        predictions.append({'id': region['id'], 'native_label': region['type'],
            'type': mapping.get(region['type'], 'unknown'), 'bbox': region['bbox'],
            'text': None, 'order_index': None,
            'native_source_character_ids': region['source_character_ids']})
    return {'engine': 'structure', 'regions': predictions, 'relations': page['relations'],
            'unsupported_items': [], 'native_source_character_crosswalk': True}


def ground(adapted, source_page):
    """Geometry ownership is an association, never a manufactured glyph alignment."""
    chars = source_page['characters']
    by_id = {c['id']: c for c in chars}
    owners = defaultdict(list)
    contradictory = set()
    native_owners = defaultdict(list)
    for region in adapted['regions']:
        ids = [c['id'] for c in chars if contains(region['bbox'], center(c['bbox']))]
        region['source_character_ids'] = ids
        region['source_unicode_backend_order'] = ''.join(by_id[c]['text'] for c in ids)
        region['native_text_equals_source_backend_order'] = (
            None if region['text'] is None else region['text'] == region['source_unicode_backend_order'])
        for ref in ids:
            owners[ref].append(region['id'])
        native = region['native_source_character_ids']
        if native is not None:
            for ref in native:
                native_owners[ref].append(region['id'])
                if ref not in by_id or ref not in ids:
                    contradictory.add(ref)
            region['native_geometry_disagreements'] = sorted(set(native) ^ set(ids))
    states = []
    for c in chars:
        refs = owners[c['id']]
        status = ('contradictory' if c['id'] in contradictory else
                  'valid' if len(refs) == 1 else 'ambiguous' if refs else 'unmatched')
        states.append({'source_character_id': c['id'], 'status': status, 'prediction_ids': refs})
    adapted['grounding'] = {'characters': states, 'status_counts': dict(Counter(s['status'] for s in states)),
        'source_characters': len(chars), 'foreign_native_ids': sorted(contradictory-set(by_id)),
        'native_ids_once': (all(len(native_owners[c['id']]) == 1 for c in chars)
                            and set(native_owners) == set(by_id)) if adapted['engine'] == 'structure' else None,
        'native_crosswalk_reason': None if adapted['engine'] == 'structure' else
            'Docling charspan indexes its own text; bbox associations are not native character provenance'}
    return adapted


def iou(a, b):
    area = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-area
    return area / union if union else 0


def match(predictions, truth, windows):
    eligible = [p for p in predictions if any(contains(w, center(p['bbox'])) for w in windows)]
    edges = sorted((-iou(t['bbox'], p['bbox']), t['id'], p['id'])
                   for t in truth for p in eligible if iou(t['bbox'], p['bbox']) >= .5)
    used_truth, used_pred, decisions = set(), set(), []
    for negative, t, p in edges:
        if t not in used_truth and p not in used_pred:
            used_truth.add(t); used_pred.add(p)
            decisions.append({'truth_id': t, 'prediction_id': p, 'iou': -negative})
    return eligible, decisions


def prf(tp, fp, fn):
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision_numerator': tp, 'precision_denominator': tp+fp,
        'recall_numerator': tp, 'recall_denominator': tp+fn,
        'precision': tp/(tp+fp) if tp+fp else None, 'recall': tp/(tp+fn) if tp+fn else None,
        'f1_numerator': 2*tp, 'f1_denominator': 2*tp+fp+fn,
        'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        'undefined_reason': 'zero denominator for corresponding measure' if not (tp+fp and tp+fn) else None}


def coarse(label):
    return 'text' if label == 'reference' else label


def relation_status(adapted, before, after):
    regions = {r['id']: r for r in adapted['regions']}
    if adapted['engine'] == 'docling':
        a, b = regions[before]['order_index'], regions[after]['order_index']
        return 'correct' if a < b else 'inversion' if a > b else 'abstention'
    edges = defaultdict(set)
    for edge in adapted['relations']:
        edges[edge['before']].add(edge['after'])

    def reachable(a, b):
        seen, pending = set(), [a]
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            if b in edges[node]:
                return True
            pending.extend(edges[node]-seen)
        return False
    # Any cyclic graph invalidates assertions, including cycles off this pair.
    if any(reachable(r, r) for r in regions):
        return 'abstention'
    return 'correct' if reachable(before, after) else 'inversion' if reachable(after, before) else 'abstention'


def strip_owner(group, predictions, source):
    by_id = {c['id']: c for c in source['characters']}
    candidates = []
    for p in predictions:
        if coarse(p['type']) != 'text':
            continue
        covered = sum(contains(p['bbox'], center(by_id[ref]['bbox'])) for ref in group)
        if covered * 2 >= len(group):
            candidates.append({'prediction_id': p['id'], 'covered': covered, 'denominator': len(group)})
    # Unique means unique qualifying region, not a best-score guess among ties.
    return {'owner': candidates[0]['prediction_id'] if len(candidates) == 1 else None,
            'status': 'valid' if len(candidates) == 1 else 'ambiguous' if candidates else 'unmatched',
            'candidates': candidates}


def score(adapted, truth_page, source_page):
    predictions, matches = match(adapted['regions'], truth_page['regions'], truth_page['windows'])
    pred = {r['id']: r for r in predictions}
    truth = {r['id']: r for r in truth_page['regions']}
    by_truth = {m['truth_id']: m['prediction_id'] for m in matches}
    matched_predictions = set(by_truth.values())
    types = sorted(set(map(coarse, [t['type'] for t in truth.values() if t['classification_scoreable']])) |
                   set(map(coarse, [p['type'] for p in predictions])) | {'heading', 'caption', 'figure', 'table', 'equation'})
    confusion = Counter()
    ignored_predictions = {by_truth[t['id']] for t in truth.values()
                           if not t['classification_scoreable'] and t['id'] in by_truth}
    type_counts = {label: dict(tp=0, fp=0, fn=0) for label in types}
    false_math_headings = 0
    category_counts = {}
    for t in truth.values():
        category_counts.setdefault(t['category'], {'truth': 0, 'localized': 0, 'classified_correct': 0,
                                                  'classification_denominator': 0})
        c = category_counts[t['category']]; c['truth'] += 1
        p = pred.get(by_truth.get(t['id']))
        c['localized'] += p is not None
        if not t['classification_scoreable']:
            continue
        c['classification_denominator'] += 1
        a, b = coarse(t['type']), coarse(p['type']) if p else '__missing__'
        confusion[a+' -> '+b] += 1
        if a == b:
            type_counts[a]['tp'] += 1; c['classified_correct'] += 1
        else:
            type_counts[a]['fn'] += 1
            if p:
                type_counts[b]['fp'] += 1
        if p and b == 'heading' and t['category'] in ('display_math', 'inline_math'):
            false_math_headings += 1
    for p in predictions:
        if p['id'] not in matched_predictions and p['id'] not in ignored_predictions:
            type_counts[coarse(p['type'])]['fp'] += 1
            confusion['__unmatched__ -> '+coarse(p['type'])] += 1
    order = []
    for pair in truth_page['order_pairs']:
        a, b = by_truth.get(pair['before']), by_truth.get(pair['after'])
        status = relation_status(adapted, a, b) if a and b else 'unscoreable'
        order.append(dict(pair, prediction_before=a, prediction_after=b, status=status))
    paragraphs = []
    for decision in truth_page['paragraph_decisions']:
        probes = [strip_owner(group, adapted['regions'], source_page) for group in decision['source_character_ids']]
        actual = probes[0]['owner'] == probes[1]['owner'] if all(p['owner'] for p in probes) else None
        paragraphs.append({'id': decision['id'], 'expected': 'join' if decision['same_paragraph'] else 'break',
            'predicted': None if actual is None else 'join' if actual else 'break', 'probes': probes,
            'correct': actual == decision['same_paragraph'] if actual is not None else False})
    pc = Counter(p['expected']+' -> '+(p['predicted'] or 'unscoreable') for p in paragraphs)
    oc = Counter(p['status'] for p in order)
    all_ground = adapted.get('grounding', {})
    scoped_ids = {c['id'] for c in source_page['characters']
                  if any(contains(w, center(c['bbox'])) for w in truth_page['windows'])}
    scoped_ground = Counter(c['status'] for c in all_ground.get('characters', []) if c['source_character_id'] in scoped_ids)
    # An absent prediction output leaves every original character unmatched.
    if not all_ground:
        scoped_ground['unmatched'] = len(scoped_ids)
    return {'page_id': truth_page['id'], 'document_id': truth_page['document_id'],
        'layout': truth_page['layout'], 'engine': adapted['engine'], 'provisional': True,
        'localization': prf(len(matches), len(predictions)-len(matches), len(truth)-len(matches)),
        'classification': {k: prf(**v) for k, v in type_counts.items()},
        'classification_truth_denominator': sum(t['classification_scoreable'] for t in truth.values()),
        'classification_excluded_truth_ids': [t['id'] for t in truth.values() if not t['classification_scoreable']],
        'confusion': dict(confusion), 'false_headings_on_math': false_math_headings,
        'category_counts': category_counts, 'order': {k: oc[k] for k in ['correct', 'inversion', 'abstention', 'unscoreable']},
        'order_denominator': len(order), 'paragraph_confusion': dict(pc),
        'paragraph_correct': sum(p['correct'] for p in paragraphs),
        'paragraph_scoreable': sum(p['predicted'] is not None for p in paragraphs),
        'paragraph_denominator': len(paragraphs), 'grounding_window_characters': len(scoped_ids),
        'grounding_window_counts': {s: scoped_ground[s] for s in ['valid', 'ambiguous', 'unmatched', 'contradictory']},
        'grounding_whole_page': {k: v for k, v in all_ground.items() if k != 'characters'},
        'decisions': {'matches': matches, 'order': order, 'paragraph': paragraphs,
            'unmatched_truth': sorted(set(truth)-set(by_truth)),
            'unmatched_predictions': sorted(set(pred)-matched_predictions)},
        'localization_by_type': {label: prf(
            sum(t['id'] in by_truth for t in truth.values() if coarse(t['type']) == label),
            sum(coarse(p['type']) == label and p['id'] not in matched_predictions for p in predictions),
            sum(t['id'] not in by_truth for t in truth.values() if coarse(t['type']) == label))
            for label in ['figure', 'table', 'equation']},
        'math_content_reconstruction': {'value': None, 'reason': 'Not defined or authorized by frozen protocol'}}


def aggregate(rows):
    total = lambda field: sum(r[field] for r in rows)
    localization = prf(*(sum(r['localization'][k] for r in rows) for k in ['tp', 'fp', 'fn']))
    classes = sorted({k for r in rows for k in r['classification']})
    classification = {k: prf(*(sum(r['classification'].get(k, {}).get(v, 0) for r in rows)
                              for v in ['tp', 'fp', 'fn'])) for k in classes}
    order = {k: sum(r['order'][k] for r in rows) for k in ['correct', 'inversion', 'abstention', 'unscoreable']}
    od, pd = total('order_denominator'), total('paragraph_denominator')
    gc = {k: sum(r['grounding_window_counts'][k] for r in rows)
          for k in ['valid', 'ambiguous', 'unmatched', 'contradictory']}
    combine = lambda key: dict(sum((Counter(r[key]) for r in rows), Counter()))
    cats = {}
    for r in rows:
        for cat, counts in r['category_counts'].items():
            cats.setdefault(cat, Counter()).update(counts)
    return {'pages': len(rows), 'localization': localization, 'classification': classification,
        'confusion': combine('confusion'), 'category_counts': {k: dict(v) for k, v in cats.items()},
        'false_headings_on_math': total('false_headings_on_math'), 'order': order, 'order_denominator': od,
        'order_correct_fraction': order['correct']/od if od else None,
        'order_undefined_reason': 'No frozen known order pairs' if not od else None,
        'paragraph_confusion': combine('paragraph_confusion'), 'paragraph_correct': total('paragraph_correct'),
        'paragraph_scoreable': total('paragraph_scoreable'), 'paragraph_denominator': pd,
        'paragraph_accuracy': total('paragraph_correct')/pd if pd else None,
        'paragraph_coverage': total('paragraph_scoreable')/pd if pd else None,
        'grounding_window_characters': total('grounding_window_characters'), 'grounding_window_counts': gc,
        'localization_by_type': {label: prf(*(sum(r['localization_by_type'][label][k] for r in rows)
                                            for k in ['tp', 'fp', 'fn']))
                                 for label in ['figure', 'table', 'equation']}}


def semantic_structure(native):
    """Equivalence probe only; never rewrite native outputs or source IDs.

    Structure IDs include validator version in their identity hash. Compare the
    complete pages after replacing only declared structure IDs with list-index
    tokens; all source character IDs, Unicode, boxes and decisions stay exact.
    """
    identities = {}
    for page in native['pages']:
        for collection in ['regions', 'lines', 'columns']:
            for i, value in enumerate(page[collection]):
                identities[value['id']] = f'p{page["page_number"]}:{collection}:{i}'

    def replace(value):
        if isinstance(value, dict):
            return {k: replace(v) for k, v in value.items()}
        if isinstance(value, list):
            return [replace(v) for v in value]
        return identities.get(value, value) if isinstance(value, str) else value
    return replace(native['pages'])
