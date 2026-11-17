"""One prevalidated frozen formula graph; crop provenance, never glyph mapping."""
from copy import deepcopy

from .formula_structure_contract import validate_formula_structure
from .hybrid import _box, _docling_geometry
from .viewer_coordinates import require

MAX_GRAPH_BYTES = 1024**2


class FormulaDemo:
    def __init__(self, graph, source):
        validate_formula_structure(graph)
        provenance = graph['provenance']
        require(provenance['pdf_sha256'] == source['source_sha256'], 'Formula PDF identity differs')
        number = provenance['page_number']
        require(1 <= number <= source['page_count'], 'Formula page is absent')
        original = source['pages'][number-1]
        require(original['page_number'] == number, 'Formula/source page differs')
        geometry = original['geometry']
        _docling_geometry(geometry, {k: geometry[k] for k in ['width','height']})
        _box(provenance['bbox'], geometry)
        require(len(graph['nodes']) <= 2048, 'Formula demo node limit exceeded; nothing truncated')
        self.graph = deepcopy(graph)
        self.page_number = number
        self._nodes = {node['id']: node for node in self.graph['nodes']}

    def payload(self):
        return {'schema_version':'formula-explorer-demo.1', 'graph':deepcopy(self.graph),
                'pdf_overlay':'whole_formula_crop_only', 'symbol_pdf_alignment':'unavailable',
                'transcription_role':'unverified_model_hypothesis'}

    def node(self, identifier):
        require(isinstance(identifier,str) and identifier in self._nodes, 'Unknown formula node')
        node = self._nodes[identifier]
        start, end = node['character_span']
        text = self.graph['input']['latex'][start:end]
        require(text == node['source_text'], 'Formula node substring differs')
        a, b = node['token_span']
        return {'formula_id':self.graph['id'], 'node':deepcopy(node), 'latex_substring':text,
                'tokens':deepcopy(self.graph['tokens'][a:b]),
                'span_unit':'unicode_code_points_half_open', 'pdf_overlay':'whole_formula_crop_only',
                'symbol_pdf_alignment':'unavailable', 'whole_expression_status':deepcopy(self.graph['status'])}
