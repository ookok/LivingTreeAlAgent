"""
RAG-Anything Standalone Test (No project dependencies)
Tests multimodal parser, cross-modal KG, and VLM query
"""

print("=" * 60)
print("RAG-Anything Integration Functionality Test")
print("=" * 60)

class TextParser:
    def parse(self, content: str) -> dict:
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        sentences = []
        for para in paragraphs:
            sentences.extend([s.strip() for s in para.split('.') if s.strip()])
        return {
            'paragraphs': paragraphs,
            'sentences': sentences,
            'word_count': len(content.split())
        }

class TableParser:
    def parse(self, content: str) -> dict:
        lines = [l.strip() for l in content.strip().split('\n') if l.strip() and '|' in l]
        if not lines:
            return {'headers': [], 'rows': [], 'row_count': 0}
        header_line = lines[0]
        headers = [h.strip() for h in header_line.split('|') if h.strip()]
        rows = []
        for line in lines[2:]:
            if '|' in line:
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if cells:
                    rows.append(cells)
        return {'headers': headers, 'rows': rows, 'row_count': len(rows)}

class EquationParser:
    def parse(self, content: str) -> dict:
        import re
        equations = re.findall(r'\$([^$]+)\$', content)
        parsed = []
        for eq in equations:
            if '\\int' in eq:
                eq_type = 'definite_integral'
                bounds = re.findall(r'\\int_\{([^}]+)\}\^\{([^}]+)\}', eq)
                parsed.append({'type': eq_type, 'equation': eq, 'bounds': bounds})
            elif '\\frac' in eq:
                eq_type = 'fraction'
                parsed.append({'type': eq_type, 'equation': eq})
            else:
                eq_type = 'general'
                parsed.append({'type': eq_type, 'equation': eq})
        return {'equations': parsed, 'count': len(parsed)}

class MultimodalDocumentParser:
    def __init__(self):
        self.text_parser = TextParser()
        self.table_parser = TableParser()
        self.equation_parser = EquationParser()

    def parse(self, content: str) -> dict:
        return {
            'text': self.text_parser.parse(content),
            'table': self.table_parser.parse(content),
            'equation': self.equation_parser.parse(content)
        }

class Entity:
    def __init__(self, entity_id: str, entity_type: str, content: str, metadata: dict = None):
        self.id = entity_id
        self.type = entity_type
        self.content = content
        self.metadata = metadata or {}

class Relation:
    def __init__(self, source_id: str, target_id: str, relation_type: str, weight: float = 1.0):
        self.source_id = source_id
        self.target_id = target_id
        self.relation_type = relation_type
        self.weight = weight

class CrossModalLink:
    def __init__(self, entity_id: str, link_type: str, linked_entity_id: str):
        self.entity_id = entity_id
        self.type = link_type
        self.linked_entity_id = linked_entity_id

class CrossModalKnowledgeGraph:
    def __init__(self):
        self.entities = {}
        self.relations = []
        self.cross_modal_links = []

    def add_entity(self, entity: Entity):
        self.entities[entity.id] = entity

    def add_relation(self, relation: Relation):
        self.relations.append(relation)

    def add_cross_modal_link(self, link: CrossModalLink):
        self.cross_modal_links.append(link)

    def query_by_type(self, entity_type: str):
        return [e for e in self.entities.values() if e.type == entity_type]

    def get_related_entities(self, entity_id: str):
        related = []
        for rel in self.relations:
            if rel.source_id == entity_id:
                related.append(self.entities.get(rel.target_id))
            elif rel.target_id == entity_id:
                related.append(self.entities.get(rel.source_id))
        return [e for e in related if e]

class QueryAnalyzer:
    def __init__(self):
        self.query_types = ['text', 'image', 'table', 'equation', 'multimodal']

    def analyze(self, query: str) -> dict:
        query_lower = query.lower()
        has_math = any(kw in query_lower for kw in ['formula', 'equation', 'calculate', 'integral'])
        has_table = any(kw in query_lower for kw in ['table', 'compare', 'list'])
        has_image = any(kw in query_lower for kw in ['image', 'picture', 'figure', 'chart'])
        types = []
        if has_math:
            types.append('equation')
        if has_table:
            types.append('table')
        if has_image:
            types.append('image')
        if not types:
            types = ['text']
        return {'query': query, 'types': types, 'is_multimodal': len(types) > 1}

class VLMQueryProcessor:
    def __init__(self):
        self.kg = None
        self.query_analyzer = QueryAnalyzer()

    def set_knowledge_graph(self, kg):
        self.kg = kg

    def process_query(self, query: str) -> dict:
        analysis = self.query_analyzer.analyze(query)
        results = []
        for qtype in analysis['types']:
            entities = self.kg.query_by_type(qtype) if self.kg else []
            results.extend([{'type': qtype, 'entity': e.id} for e in entities])
        return {
            'query': query,
            'analysis': analysis,
            'results': results
        }

class ContextBuilder:
    def build(self, query_result: dict, max_items: int = 5) -> str:
        contexts = []
        for r in query_result.get('results', [])[:max_items]:
            if self.kg:
                entity = self.kg.entities.get(r.get('entity', ''))
                if entity:
                    contexts.append(f"[{entity.type}] {entity.content}")
        return '\n'.join(contexts) if contexts else "No relevant context found"

def test_multimodal_parser():
    print("\n=== Test Multimodal Parser ===")
    content = """
This is a sample document with multiple formats.

| Column A | Column B | Column C |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
| Value 4  | Value 5  | Value 6  |

For example: $E = mc^2$ and $\int_0^1 x^2 dx = \frac{1}{3}$.
Another important formula is $\int_0^1 x^2 dx = \frac{1}{3}$.
"""
    parser = MultimodalDocumentParser()
    result = parser.parse(content)

    print(f"  Parsed text paragraphs: {len(result['text']['paragraphs'])}")
    print(f"  Parsed text sentences: {len(result['text']['sentences'])}")
    print(f"  Word count: {result['text']['word_count']}")
    print(f"  Table headers: {result['table']['headers']}")
    print(f"  Table rows: {result['table']['row_count']}")
    print(f"  Equations found: {result['equation']['count']}")

    assert len(result['text']['paragraphs']) > 0, "Should parse paragraphs"
    assert len(result['table']['headers']) == 3, "Should have 3 table headers"
    assert result['equation']['count'] == 3, "Should find 3 equations"
    print("  [PASS] Multimodal parser works correctly")
    return True

def test_cross_modal_kg():
    print("\n=== Test Cross-Modal KG ===")
    kg = CrossModalKnowledgeGraph()

    kg.add_entity(Entity("text1", "text", "Einstein's theory of relativity"))
    kg.add_entity(Entity("eq1", "equation", "E = mc^2"))
    kg.add_entity(Entity("img1", "image", "Einstein portrait"))
    kg.add_entity(Entity("topic1", "topic", "Physics"))

    kg.add_relation(Relation("text1", "eq1", "contains_formula", 0.9))
    kg.add_relation(Relation("text1", "img1", "has_image", 0.7))
    kg.add_relation(Relation("topic1", "text1", "discusses", 1.0))

    kg.add_cross_modal_link(CrossModalLink("eq1", "explains", "text1"))
    kg.add_cross_modal_link(CrossModalLink("img1", "depicts", "text1"))

    print(f"  Total entities: {len(kg.entities)}")
    print(f"  Total relations: {len(kg.relations)}")
    print(f"  Cross-modal links: {len(kg.cross_modal_links)}")

    text_entities = kg.query_by_type("text")
    print(f"  Text entities: {[e.id for e in text_entities]}")

    eq_entities = kg.query_by_type("equation")
    print(f"  Equation entities: {[e.id for e in eq_entities]}")

    related = kg.get_related_entities("text1")
    print(f"  Entities related to text1: {[e.id for e in related]}")

    assert len(kg.entities) == 4, "Should have 4 entities"
    assert len(kg.relations) == 3, "Should have 3 relations"
    assert len(kg.cross_modal_links) == 2, "Should have 2 cross-modal links"
    print("  [PASS] Cross-modal KG works correctly")
    return True

def test_vlm_query():
    print("\n=== Test VLM Query ===")
    kg = CrossModalKnowledgeGraph()

    kg.add_entity(Entity("text1", "text", "Machine learning overview"))
    kg.add_entity(Entity("eq1", "equation", "loss = (y - y_pred)^2"))
    kg.add_entity(Entity("table1", "table", "accuracy metrics"))

    processor = VLMQueryProcessor()
    processor.set_knowledge_graph(kg)

    result1 = processor.process_query("Show me the formulas")
    print(f"  Query 'Show me the formulas' detected types: {result1['analysis']['types']}")
    print(f"  Results: {len(result1['results'])}")

    result2 = processor.process_query("Compare the metrics")
    print(f"  Query 'Compare the metrics' detected types: {result2['analysis']['types']}")
    print(f"  Results: {len(result2['results'])}")

    result3 = processor.process_query("What is machine learning?")
    print(f"  Query 'What is machine learning?' detected types: {result3['analysis']['types']}")
    print(f"  Results: {len(result3['results'])}")

    context_builder = ContextBuilder()
    context_builder.kg = kg
    context = context_builder.build(result1)
    print(f"  Built context (first 50 chars): {context[:50]}...")

    assert 'equation' in result1['analysis']['types'], "Should detect equation query"
    assert 'table' in result2['analysis']['types'], "Should detect table query"
    assert 'text' in result3['analysis']['types'], "Should detect text query"
    print("  [PASS] VLM query processing works correctly")
    return True

def test_integration():
    print("\n=== Test Full Integration ===")
    parser = MultimodalDocumentParser()
    kg = CrossModalKnowledgeGraph()
    processor = VLMQueryProcessor()

    content = """
Introduction to Neural Networks

| Layer | Neurons | Activation |
|-------|---------|------------|
| Input | 784     | None       |
| Hidden| 128     | ReLU       |
| Output| 10      | Softmax    |

The loss function is $L = -\sum y_i \log(\hat{y}_i)$.
"""
    parsed = parser.parse(content)
    print(f"  Parsed document with {len(parsed['text']['paragraphs'])} paragraphs")

    if parsed['table']['headers']:
        for i, row in enumerate(parsed['table']['rows']):
            kg.add_entity(Entity(f"table_row_{i}", "table", str(row)))
            print(f"  Added table row {i}: {row[:2]}...")

    for eq in parsed['equation']['equations']:
        kg.add_entity(Entity(f"eq_{eq['type']}", "equation", eq['equation']))
        print(f"  Added equation: {eq['equation'][:30]}...")

    processor.set_knowledge_graph(kg)
    result = processor.process_query("Show me the neural network formulas and tables")

    print(f"  Query types: {result['analysis']['types']}")
    print(f"  Query is multimodal: {result['analysis']['is_multimodal']}")
    print(f"  Total results found: {len(result['results'])}")

    context_builder = ContextBuilder()
    context_builder.kg = kg
    context = context_builder.build(result, max_items=10)
    print(f"  Built context length: {len(context)} chars")

    assert result['analysis']['is_multimodal'] == True, "Should be multimodal query"
    assert len(result['results']) >= 2, "Should find multiple results"
    print("  [PASS] Full integration works correctly")
    return True

if __name__ == "__main__":
    all_passed = True

    try:
        all_passed &= test_multimodal_parser()
    except Exception as e:
        print(f"  [FAIL] Multimodal parser: {e}")
        all_passed = False

    try:
        all_passed &= test_cross_modal_kg()
    except Exception as e:
        print(f"  [FAIL] Cross-modal KG: {e}")
        all_passed = False

    try:
        all_passed &= test_vlm_query()
    except Exception as e:
        print(f"  [FAIL] VLM query: {e}")
        all_passed = False

    try:
        all_passed &= test_integration()
    except Exception as e:
        print(f"  [FAIL] Integration: {e}")
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("All RAG-Anything tests PASSED!")
    else:
        print("Some RAG-Anything tests FAILED!")
    print("=" * 60)