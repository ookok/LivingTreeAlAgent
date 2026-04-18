"""
Writing Module Test Suite
Tests all core modules of the Writing Assistant
"""

import sys
from pathlib import Path


def test_imports():
    """Test module imports"""
    print("=" * 60)
    print("Test 1: Module Imports")
    print("=" * 60)

    modules = [
        ("IntentDetector", "writing.intent_detector"),
        ("LatexProcessor", "writing.latex_processor"),
        ("AIWriter", "writing.ai_writer"),
        ("OutlineGenerator", "writing.outline_generator"),
        ("CitationManager", "writing.citation_manager"),
    ]

    all_passed = True
    for name, module_path in modules:
        try:
            __import__(module_path)
            print(f"  [PASS] {name} ({module_path})")
        except ImportError as e:
            print(f"  [FAIL] {name}: {e}")
            all_passed = False

    return all_passed


def test_intent_detector():
    """Test IntentDetector"""
    print("\n" + "=" * 60)
    print("Test 2: IntentDetector - Intent Recognition")
    print("=" * 60)

    from writing.intent_detector import (
        IntentDetector, AnalysisContext, DocType, SubjectDomain
    )

    detector = IntentDetector()

    # Test: Academic paper content
    academic_content = """
    Abstract: This paper studies the application of deep learning in image recognition.
    1. Introduction
    Recently, CNNs have achieved breakthrough progress in computer vision [1].
    2. Methods
    We use ResNet-50 model for experiments.
    3. Conclusion
    Results show 95% accuracy.
    References:
    [1] LeCun et al., 2015, Nature
    """

    result = detector.detect(AnalysisContext(file_content=academic_content))

    print(f"  Doc Type: {result.doc_type.value}")
    print(f"  Subject: {result.subject.value}")
    print(f"  Confidence: {result.confidence:.0%}")
    print(f"  Format: {result.suggested_format.value}")
    print(f"  Language: {result.language}")
    print(f"  Skills: {result.suggested_skills}")

    passed = result.doc_type == DocType.ACADEMIC_PAPER
    print(f"  {'[PASS] Correctly identified as academic paper' if passed else '[FAIL] Recognition failed'}")
    return passed


def test_latex_processor():
    """Test LatexProcessor"""
    print("\n" + "=" * 60)
    print("Test 3: LatexProcessor - LaTeX Semantic Processing")
    print("=" * 60)

    from writing.latex_processor import LatexProcessor

    processor = LatexProcessor()

    # Test formula parsing
    formulas = [
        r"E = mc^2",
        r"$$\nabla \times \mathbf{E} = -\frac{\partial \mathbf{B}}{\partial t}$$",
        r"i\hbar\frac{\partial}{\partial t}\Psi = \hat{H}\Psi",
    ]

    all_passed = True
    for latex in formulas:
        parsed = processor.parse(latex)
        print(f"\n  Original: {latex}")
        print(f"  Standard: {parsed.latex}")
        print(f"  Operators: {parsed.operators}")
        print(f"  Variables: {parsed.variables}")
        print(f"  Semantic: {parsed.semantic_description}")

        if not parsed.latex:
            all_passed = False

    # Test formula transformation
    transform_test = r"\partial^2 \psi / \partial t^2"
    transformed = processor.transform(transform_test, "partial to derivative")
    print(f"\n  Transform test: {transform_test}")
    print(f"  Result: {transformed}")

    print(f"\n  {'[PASS] LaTeX processing OK' if all_passed else '[FAIL] LaTeX processing failed'}")
    return all_passed


def test_outline_generator():
    """Test OutlineGenerator"""
    print("\n" + "=" * 60)
    print("Test 4: OutlineGenerator - Smart Outline")
    print("=" * 60)

    from writing.outline_generator import OutlineGenerator, DocType
    from writing.intent_detector import SubjectDomain

    generator = OutlineGenerator()

    # Test paper outline
    paper_outline = generator.generate(
        "Deep Learning in Medical Imaging",
        DocType.ACADEMIC_PAPER,
        SubjectDomain.COMPUTER_SCIENCE
    )

    print(f"\n  Paper Outline ({len(paper_outline)} sections):")
    for i, section in enumerate(paper_outline[:5], 1):
        indent = "  " * (section.level - 1)
        print(f"    {indent}{i}. {section.title}")

    # Test business plan outline
    bp_outline = generator.generate(
        "AI Education Platform BP",
        DocType.BUSINESS_PLAN
    )

    print(f"\n  Business Plan Outline ({len(bp_outline)} sections):")
    for i, section in enumerate(bp_outline[:5], 1):
        indent = "  " * (section.level - 1)
        print(f"    {indent}{i}. {section.title}")

    # Test Markdown export
    md = generator.to_markdown(paper_outline[:3])
    print(f"\n  Markdown Export (first 100 chars):")
    print(f"    {md[:100]}...")

    passed = len(paper_outline) > 0 and len(bp_outline) > 0
    print(f"\n  {'[PASS] Outline generation OK' if passed else '[FAIL] Outline generation failed'}")
    return passed


def test_citation_manager():
    """Test CitationManager"""
    print("\n" + "=" * 60)
    print("Test 5: CitationManager - Reference Management")
    print("=" * 60)

    from writing.citation_manager import CitationManager, Citation, CitationType, CitationStyle

    manager = CitationManager()

    # Add citation
    citation = Citation(
        citation_type=CitationType.ARTICLE,
        key="lecun2015",
        title="Deep Learning",
        authors=["Yann LeCun", "Yoshua Bengio", "Geoffrey Hinton"],
        year="2015",
        journal="Nature",
        volume="521",
        pages="436-444",
        doi="10.1038/nature14539"
    )

    key = manager.add(citation)
    print(f"  Added citation: {key}")

    # Test different formats
    print(f"\n  IEEE format:")
    print(f"    {manager.format_citation(key, CitationStyle.IEEE)}")

    print(f"\n  APA format:")
    print(f"    {manager.format_citation(key, CitationStyle.APA)}")

    # Test BibTeX generation
    bibtex = manager.generate_bibliography([key])
    print(f"\n  BibTeX:")
    print(f"    {bibtex[:100]}...")

    passed = key == "lecun2015"
    print(f"\n  {'[PASS] Citation management OK' if passed else '[FAIL] Citation management failed'}")
    return passed


def test_integration():
    """Integration test"""
    print("\n" + "=" * 60)
    print("Test 6: Integration Test - Complete Workflow")
    print("=" * 60)

    from writing.intent_detector import IntentDetector, AnalysisContext
    from writing.latex_processor import LatexProcessor
    from writing.outline_generator import OutlineGenerator
    from writing.ai_writer import AIWriter, WritingContext as WriterContext

    # Simulate academic paper writing workflow
    print("\n  Simulating academic paper workflow:")

    # 1. Intent recognition
    detector = IntentDetector()
    paper_content = """
    Deep Learning for Medical Image Diagnosis

    Abstract: This paper proposes a CNN-based method for medical image diagnosis...
    Keywords: deep learning, medical imaging, CNN

    1. Introduction
    Medical image diagnosis is important in clinical practice...
    $$f(x) = \frac{1}{1 + e^{-x}}$$
    """

    intent = detector.detect(AnalysisContext(file_content=paper_content))
    print(f"    1. Intent: {intent.doc_type.value}, confidence {intent.confidence:.0%}")

    # 2. Initialize writer
    writer = AIWriter()
    writer_context = WriterContext(
        doc_type=intent.doc_type,
        subject=intent.subject,
        target_format=intent.suggested_format,
        language=intent.language
    )
    writer.set_context(writer_context)
    print(f"    2. Context: {writer.current_context.target_format.value}")

    # 3. Generate outline
    generator = OutlineGenerator()
    outline = generator.generate("Deep Learning for Medical Diagnosis", intent.doc_type)
    print(f"    3. Outline: {len(outline)} sections")

    # 4. Formula processing
    processor = LatexProcessor()
    latex = r"\nabla \times \mathbf{E} = -\frac{\partial \mathbf{B}}{\partial t}"
    parsed = processor.parse(latex)
    print(f"    4. Formula: {parsed.semantic_description}")

    print("\n  [PASS] Complete workflow test passed")
    return True


def main():
    """Main function"""
    print("\n" + "=" * 60)
    print("  Writing Module Test Suite")
    print("=" * 60)

    results = []

    results.append(("Module Imports", test_imports()))
    results.append(("Intent Detection", test_intent_detector()))
    results.append(("LaTeX Processing", test_latex_processor()))
    results.append(("Outline Generation", test_outline_generator()))
    results.append(("Citation Management", test_citation_manager()))
    results.append(("Integration Test", test_integration()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    passed = 0
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} - {name}")
        if result:
            passed += 1

    print(f"\n  Total: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("\n  All tests passed!")
        return 0
    else:
        print(f"\n  {len(results) - passed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
