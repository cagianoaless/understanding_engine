"""Offline experimental LaTeX-body grammar; no semantic inference or source alignment.

Offsets are half-open Python Unicode-string indices, not bytes or PDF positions.
Whitespace survives in the token stream and every original input is retained.
"""
from dataclasses import asdict, dataclass
import hashlib
import re

from .contracts import ExtractionError, json_bytes
from .formula_structure_contract import (FORMULA_STRUCTURE_VERSION, PARSER_VERSION,
                                         FormulaProvenance, FormulaStructure, validate_provenance)


@dataclass(frozen=True)
class ParseSettings:
    max_input_characters: int = 65536
    max_tokens: int = 4096
    max_nodes: int = 8192
    max_depth: int = 32
    max_diagnostics: int = 32
    repetition_limit: int = 8

    def __post_init__(self):
        ceilings = dict(max_input_characters=1048576, max_tokens=16384, max_nodes=32768,
                        max_depth=64, max_diagnostics=128, repetition_limit=64)
        for name, ceiling in ceilings.items():
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{name} must be an integer in [1,{ceiling}]")
        if self.repetition_limit < 3:
            raise ValueError("repetition_limit must be at least three")


_TOKEN = re.compile(r"(?P<space>\s+)|(?P<command>\\[A-Za-z]+|\\[\s\S])|(?P<number>[0-9]+(?:\.[0-9]+)?)|(?P<literal>[\s\S])")
_SYMBOLS = set(r"alpha beta gamma delta epsilon varepsilon theta vartheta lambda mu nu xi pi rho sigma tau phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Phi Psi Omega infty ell partial nabla star ast dots ldots cdots".split())
_NAMED = set("sin cos tan exp log ln max min lim".split())
_RELATIONS = {"=", "<", ">", r"\le", r"\leq", r"\ge", r"\geq", r"\ne", r"\neq", r"\approx", r"\equiv"}
_OPERATORS = {"+", "-", "/", "*", ",", ":", ";", "|", r"\mid", r"\colon", r"\cdot", r"\times", r"\in", r"\notin", r"\pm"}
_OPEN = {"(": ")", "[": "]", r"\{": r"\}", r"\langle": r"\rangle"}
_CLOSE = set(_OPEN.values()) | {"}", r"\right"}
_STYLES = {r"\mathrm", r"\mathbf", r"\mathcal", r"\mathit", r"\boldsymbol"}
_SPACING = {r"\,", r"\;", r"\!", r"\ ", r"\quad", r"\qquad", r"\:"}


class _Stop(Exception):
    def __init__(self, code, position):
        self.code, self.position = code, position


def _tokenize(text, settings):
    tokens = []
    for match in _TOKEN.finditer(text):
        if len(tokens) == settings.max_tokens:
            raise _Stop("token_limit", match.start())
        tokens.append(dict(kind=match.lastgroup, text=match.group(), start=match.start(), end=match.end()))
    return tokens


def _repetitive(tokens, limit):
    values = [t["text"] for t in tokens if t["kind"] != "space"]
    # Bounded exact repeated token blocks, not a semantic/prose classifier.
    for width in range(1, 9):
        run = width
        for i in range(width, len(values)):
            run = run + 1 if values[i] == values[i - width] else width
            if run >= width * limit:
                return True
    return False


class _Parser:
    def __init__(self, text, tokens, settings, identity):
        self.text, self.tokens, self.settings, self.identity = text, tokens, settings, identity
        self.sig = [i for i, t in enumerate(tokens) if t["kind"] != "space"]
        self.sigpos = {token: i for i, token in enumerate(self.sig)}
        self.pos = 0
        self.nodes, self.diagnostics = [], []
        self.by_id = {}
        self.diagnostics_bounded = False

    def peek(self):
        return self.tokens[self.sig[self.pos]]["text"] if self.pos < len(self.sig) else None

    def offset(self):
        return self.tokens[self.sig[self.pos]]["start"] if self.pos < len(self.sig) else len(self.text)

    def diagnostic(self, code, start, end=None, *, critical=False):
        value = {"code": code, "character_span": [start, start if end is None else end]}
        if len(self.diagnostics) < self.settings.max_diagnostics:
            self.diagnostics.append(value)
        else:
            self.diagnostics_bounded = True
            if critical:
                self.diagnostics[-1] = value
        return value

    def add(self, kind, start, end, children=(), *, attributes=None, status=None, codes=(), whole=False, reserved=False):
        if not reserved and len(self.nodes) >= self.settings.max_nodes:
            raise _Stop("node_limit", self.offset())
        a = self.sig[start] if start < len(self.sig) else len(self.tokens)
        b = self.sig[end - 1] + 1 if end > start else a
        left = self.tokens[a]["start"] if a < len(self.tokens) else len(self.text)
        right = self.tokens[b - 1]["end"] if b > a else left
        if whole:
            a, b, left, right = 0, len(self.tokens), 0, len(self.text)
        status = status or ("unresolved" if any(n[1]["status"] == "unresolved" for n in children) else
                            "ambiguous" if any(n[1]["status"] == "ambiguous" for n in children) else "supported")
        node = dict(id=f"{self.identity}:n{len(self.nodes)}", type=kind,
                    token_span=[a, b], character_span=[left, right], token_span_complete=True,
                    source_text=self.text[left:right], children=[{"role": role, "node_id": n["id"]} for role, n in children],
                    status=status, attributes=attributes or {},
                    diagnostics=[self.diagnostic(c, left, right) for c in codes])
        self.nodes.append(node)
        self.by_id[node['id']] = node
        return node

    def expect(self, value):
        if self.peek() != value:
            raise _Stop("expected_" + value if value in {"}", ")", "]"} else "missing_delimiter_or_argument", self.offset())
        self.pos += 1

    def sequence(self, depth, stops=()):
        if depth > self.settings.max_depth:
            raise _Stop("depth_limit", self.offset())
        start = self.pos
        items = []
        while self.peek() is not None and self.peek() not in stops:
            if self.peek() in _CLOSE:
                raise _Stop("unexpected_closing_delimiter", self.offset())
            items.append(self.atom_with_scripts(depth))
        if not items:
            return self.add("unknown", start, self.pos, status="unresolved", codes=["empty_expression"])
        # Only local well-formedness, never arithmetic precedence or implicit
        # multiplication. A bare star remains a glyph (e.g. a superscript).
        infix = {'+', '-', '/', r'\cdot', r'\times', r'\mid', '|', r'\in', r'\notin', r'\colon'}
        for i, item in enumerate(items):
            if item['type'] == 'operator' and item['source_text'] in infix:
                unary = i == 0 and item['source_text'] in {'+', '-'}
                if i == len(items) - 1 or (i == 0 and not unary) or (
                        i and items[i-1]['type'] == 'operator') or items[i+1]['type'] == 'operator':
                    raise _Stop('unsupported_operator_sequence', item['character_span'][0])
        # A bare-letter/number run is NOT silently joined into a name or numeral.
        run = []
        for item in items + [None]:
            leaf = item
            while leaf and leaf["type"] in {"superscript", "subscript"}:
                leaf = self.by_id[leaf["children"][0]["node_id"]]
            if leaf and leaf["type"] in {"symbol", "number"} and not leaf["source_text"].startswith("\\"):
                run.append(item)
            else:
                if len(run) > 1:
                    self.diagnostic("ambiguous_identifier_or_numeric_sequence", run[0]["character_span"][0], run[-1]["character_span"][1])
                    for n in run:
                        if n["status"] == "supported":
                            n["status"] = "ambiguous"
                run = []
        if any(n['type'] == 'layout_marker' and n['source_text'] == r'\\' for n in items):
            return self.add('sequence', start, self.pos, [('item', n) for n in items],
                            status='unresolved' if any(n['status'] == 'unresolved' for n in items) else 'ambiguous',
                            attributes={'relation_scope': 'not_inferred_across_layout_breaks'},
                            codes=['layout_break_relation_scope_unresolved'])
        relations = [i for i, n in enumerate(items) if n["type"] == "operator" and n["attributes"].get("relation")]
        if relations:
            if relations[0] == 0 or relations[-1] == len(items) - 1 or any(b == a + 1 for a, b in zip(relations, relations[1:])):
                raise _Stop("missing_relation_operand", self.offset())
            children, begin = [], 0
            for i in relations + [len(items)]:
                part = items[begin:i]
                # Spans refer to exact original tokens, not a reconstructed string.
                lo = self.sigpos[part[0]["token_span"][0]]
                hi = self.sigpos[part[-1]["token_span"][1] - 1] + 1
                operand = self.add("sequence", lo, hi, [("item", n) for n in part])
                children.append(("operand", operand))
                if i < len(items):
                    children.append(("relation_operator", items[i]))
                begin = i + 1
            return self.add("relation", start, self.pos, children, attributes={"semantics": "not_inferred"})
        return self.add("sequence", start, self.pos, [("item", n) for n in items])

    def argument(self, depth, *, braced=False):
        if self.peek() == "{":
            return self.group(depth + 1, "{", "}", "group")
        value = self.peek()
        if braced or value is None or value in {"^", "_"} or value in _CLOSE:
            raise _Stop("explicit_braced_argument_required", self.offset())
        # TeX unbraced arguments consume one token, not an entire digit string.
        if (value.startswith("\\") and value[1:] not in _SYMBOLS) or (not value.startswith("\\") and (len(value) != 1 or not value.isalnum())):
            raise _Stop("unsupported_unbraced_argument", self.offset())
        return self.atom(depth + 1)

    def group(self, depth, opener, closer, kind):
        start = self.pos
        self.expect(opener)
        body = self.sequence(depth, (closer,))
        self.expect(closer)
        return self.add(kind, start, self.pos, [("body", body)], attributes={"open": opener, "close": closer})

    def atom(self, depth):
        if depth > self.settings.max_depth:
            raise _Stop("depth_limit", self.offset())
        start, value = self.pos, self.peek()
        if value in {None, "^", "_"}:
            raise _Stop("missing_base_or_argument", self.offset())
        if value == "{":
            return self.group(depth + 1, "{", "}", "group")
        if value in _OPEN:
            return self.group(depth + 1, value, _OPEN[value], "delimited_group")
        self.pos += 1
        if value == r"\left":
            opener = self.peek()
            if opener not in _OPEN:
                raise _Stop("unsupported_sized_delimiter", self.offset())
            self.pos += 1
            body = self.sequence(depth + 1, (r"\right",))
            self.expect(r"\right")
            self.expect(_OPEN[opener])
            return self.add("delimited_group", start, self.pos, [("body", body)], attributes={"open": opener, "close": _OPEN[opener], "sized": True})
        if value in {r"\frac", r"\dfrac", r"\tfrac"}:
            numerator = self.argument(depth, braced=True)
            denominator = self.argument(depth, braced=True)
            return self.add("fraction", start, self.pos, [("numerator", numerator), ("denominator", denominator)])
        if value == r"\sqrt":
            children = []
            if self.peek() == "[":
                children.append(("degree", self.group(depth + 1, "[", "]", "group")))
            children.append(("radicand", self.argument(depth, braced=True)))
            return self.add("radical", start, self.pos, children)
        if value in _STYLES or value == r"\operatorname":
            starred = value == r"\operatorname" and self.peek() == "*"
            if starred:
                self.pos += 1
            body = self.argument(depth, braced=True)
            return self.add("operator_group" if value == r"\operatorname" else "typography_group", start, self.pos, [("body", body)],
                            attributes={"command": value, "starred": starred, "semantic_identity": "not_inferred"})
        if value == r"\text":
            self.expect("{")
            begin = self.pos
            while self.peek() not in {None, "}", "{"}:
                self.pos += 1
            body = self.add("literal_text", begin, self.pos, attributes={"semantic_identity": "not_inferred"})
            self.expect("}")
            supported = bool(re.fullmatch(r"\s*[A-Za-z]+\s*", body["source_text"]))
            return self.add("text_group", start, self.pos, [("body", body)], status="ambiguous" if supported else "unresolved",
                            codes=["text_name_not_verified_identifier" if supported else "unsupported_prose_or_text_group"])
        if value in _RELATIONS | _OPERATORS or value == r"\sum":
            return self.add("operator", start, self.pos, attributes={"relation": value in _RELATIONS, "semantic_identity": "not_inferred"})
        if value.startswith("\\"):
            command = value[1:]
            if command in _SYMBOLS:
                return self.add("symbol", start, self.pos)
            if command in _NAMED:
                return self.add("operator_group", start, self.pos, attributes={"command": value, "semantic_identity": "not_inferred"})
            if value in _SPACING or value == r"\\":
                return self.add("layout_marker", start, self.pos, attributes={"command": value})
            raise _Stop("unsupported_command", self.tokens[self.sig[start]]["start"])
        if value == "&":
            return self.add("layout_marker", start, self.pos, attributes={"kind": "alignment_tab"})
        token = self.tokens[self.sig[start]]
        if token["kind"] == "number":
            return self.add("number", start, self.pos)
        if value.isalpha():
            return self.add("symbol", start, self.pos)
        if value == ".":
            return self.add("punctuation", start, self.pos)
        raise _Stop("unsupported_literal", token["start"])

    def atom_with_scripts(self, depth):
        start = self.pos
        base = self.atom(depth)
        summation = base["source_text"] == r"\sum" and base["type"] == "operator"
        seen, limits = set(), [("operator", base)]
        while self.peek() in {"^", "_"}:
            kind = self.peek()
            if kind in seen:
                raise _Stop("duplicate_script", self.offset())
            seen.add(kind)
            self.pos += 1
            argument = self.argument(depth)
            if summation:
                limits.append(("upper_limit" if kind == "^" else "lower_limit", argument))
            else:
                base = self.add("superscript" if kind == "^" else "subscript", start, self.pos,
                                [("base", base), ("script", argument)])
        if summation:
            return self.add("summation", start, self.pos, limits, attributes={"summand_scope": "not_inferred", "variable_binding": "not_inferred"})
        return base


def parse_formula(latex: str, provenance: FormulaProvenance, *, raw_model_output: str | None = None,
                  termination: str = "unknown", settings: ParseSettings | None = None) -> FormulaStructure:
    """Build a navigable syntax hypothesis without consulting references or a PDF.

    `termination` is an observed caller-supplied model fact: complete/incomplete/
    unknown. It is not inferred from balanced braces or plausible mathematics.
    Invalid input identity raises ExtractionError; bad LaTeX returns diagnostics.
    """
    if not isinstance(latex, str) or (raw_model_output is not None and not isinstance(raw_model_output, str)):
        raise TypeError("LaTeX/raw output must be strings")
    if termination not in {"complete", "incomplete", "unknown"}:
        raise ValueError("Invalid observed model termination")
    validate_provenance(provenance)
    settings = ParseSettings() if settings is None else settings
    if not isinstance(settings, ParseSettings):
        raise TypeError('settings must be ParseSettings, not an implicit or partial configuration')
    algorithm = {"name": PARSER_VERSION, "settings": asdict(settings)}
    original = dict(latex=latex, raw_model_output=raw_model_output, termination=termination,
                    latex_sha256=hashlib.sha256(latex.encode()).hexdigest(),
                    raw_model_output_sha256=hashlib.sha256(raw_model_output.encode()).hexdigest() if raw_model_output is not None else None)
    identity = hashlib.sha256(json_bytes({"parser": algorithm, "provenance": provenance, "input": original})).hexdigest()
    guarded, tokens = None, []
    try:
        if len(latex) > settings.max_input_characters:
            raise _Stop("input_character_limit", 0)
        tokens = _tokenize(latex, settings)
        if _repetitive(tokens, settings.repetition_limit):
            guarded = _Stop("excessive_repetition", 0)
    except _Stop as stop:
        guarded = stop
        tokens = []
    parser = _Parser(latex, tokens, settings, identity)
    failure, root = guarded, None
    if not guarded:
        try:
            root = parser.sequence(0)
        except _Stop as stop:
            failure = stop
    if failure:
        parser.diagnostic(failure.code, failure.position, critical=True)
        # Keep already parsed fragments reachable, explicitly inside an
        # unresolved whole-input wrapper. Never label a prefix as full success.
        referenced = {c["node_id"] for n in parser.nodes for c in n["children"]}
        fragments = [n for n in parser.nodes if n["id"] not in referenced]
        # Reserve the final wrapper independently of the normal node budget.
        root = parser.add("unknown", 0, len(parser.sig), [("parsed_fragment", n) for n in fragments], status="unresolved", whole=True, reserved=True)
        root["token_span_complete"] = bool(tokens) or not latex
    elif root:
        # Include leading/trailing whitespace without rewriting child spans.
        root = parser.add("sequence", 0, len(parser.sig), [("body", root)], whole=True, reserved=True)
    has_support = any(n["type"] not in {"unknown", "sequence", "layout_marker", "literal_text"} for n in parser.nodes)
    unresolved = any(n["status"] == "unresolved" for n in parser.nodes)
    if termination != "complete":
        parser.diagnostic("incomplete_model_generation" if termination == "incomplete" else "model_termination_unknown", 0, len(latex), critical=not failure)
    if termination == 'incomplete' and root['status'] != 'unresolved':
        root['status'] = 'unresolved'
        root['diagnostics'].append({'code': 'incomplete_model_generation', 'character_span': [0, len(latex)]})
    partial = unresolved or failure is not None or termination == "incomplete"
    ambiguous = any(n["status"] == "ambiguous" for n in parser.nodes)
    result = dict(formula_structure_version=FORMULA_STRUCTURE_VERSION, id=identity, parser=algorithm,
                  provenance={**provenance, "bbox": list(provenance["bbox"])}, input=original,
                  evidence_status={"text_role": "model_transcription_hypothesis", "source_alignment": "formula_crop_only",
                                   "mathematical_correctness": "unverified", "source_validation": "provenance_recorded_not_verified"},
                  tokens=tokens, nodes=parser.nodes, root_id=root["id"],
                  status={"parsing": "partial" if partial and has_support else "rejected" if partial else "parsed",
                          "syntax": "not_parsed" if guarded else "unsupported_or_malformed" if failure or unresolved else "complete_for_v0_grammar",
                          "structural_support": "partial" if partial and has_support else "unresolved" if partial else "ambiguous" if ambiguous else "supported",
                          "acceptance": "reject" if partial else "inspect_with_ambiguities" if ambiguous or termination == "unknown" else "inspect_syntax_only",
                          "diagnostics": "bounded" if parser.diagnostics_bounded else "complete"},
                  diagnostics=parser.diagnostics)
    return result
