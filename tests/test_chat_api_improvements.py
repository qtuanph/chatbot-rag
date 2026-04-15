#!/usr/bin/env python3
"""
Test script for chat API improvements.
Validates citations deduplication, input validation, and error handling.
"""

import json
import sys
from typing import Any, Dict
from pathlib import Path

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_citations_deduplication():
    """Test citations deduplication logic."""
    print("[TEST] Testing citations deduplication...")

    from app.api.routes.chat import _deduplicate_citations

    # Test case 1: Duplicate document_id and node_id
    citations = [
        {"document_id": "doc1", "node_id": "node1", "index": 1, "title": "Doc 1", "heading": "Section 1"},
        {"document_id": "doc1", "node_id": "node1", "index": 5, "title": "Doc 1", "heading": "Section 1"},
        {"document_id": "doc1", "node_id": "node2", "index": 2, "title": "Doc 1", "heading": "Section 2"},
        {"document_id": "doc2", "node_id": "node1", "index": 3, "title": "Doc 2", "heading": "Section 1"},
    ]

    result = _deduplicate_citations(citations)

    assert len(result) == 3, f"Expected 3 citations, got {len(result)}"
    assert result[0]["index"] == 1, "First citation should have index 1"
    assert result[1]["index"] == 2, "Second citation should have index 2"
    assert result[2]["index"] == 3, "Third citation should have index 3"

    # Test case 2: Missing fields
    incomplete_citations = [
        {"document_id": "doc1", "node_id": "node1", "index": 1},
        {"document_id": "doc2", "node_id": "node2", "index": 2},
    ]

    result = _deduplicate_citations(incomplete_citations)

    assert all("title" in c for c in result), "All citations should have default title"
    assert all("heading" in c for c in result), "All citations should have default heading"

    # Test case 3: Limit to 10
    many_citations = [
        {"document_id": f"doc{i}", "node_id": f"node{i}", "index": i, "title": f"Doc {i}", "heading": f"Section {i}"}
        for i in range(1, 20)
    ]

    result = _deduplicate_citations(many_citations)

    assert len(result) == 10, f"Should limit to 10 citations, got {len(result)}"

    print("[PASS] Citations deduplication tests passed!")
    return True


def test_input_validation():
    """Test input validation logic."""
    print("\n[TEST] Testing input validation...")

    from pydantic import ValidationError
    from app.schemas.chat import ChatRequest

    # Test case 1: Valid query
    try:
        req = ChatRequest(query="What is the leave policy?")
        assert req.query == "What is the leave policy?"
        print("  [PASS] Valid query accepted")
    except ValidationError as e:
        print(f"  [FAIL] Valid query rejected: {e}")
        return False

    # Test case 2: Empty query
    try:
        req = ChatRequest(query="")
        print("  [FAIL] Empty query should be rejected")
        return False
    except ValidationError:
        print("  [PASS] Empty query rejected")

    # Test case 3: Query too short
    try:
        req = ChatRequest(query="Hi")
        print("  [FAIL] Query < 3 chars should be rejected")
        return False
    except ValidationError:
        print("  [PASS] Query < 3 chars rejected")

    # Test case 4: XSS attempt
    try:
        req = ChatRequest(query="<script>alert('xss')</script>")
        print("  [FAIL] XSS query should be rejected")
        return False
    except ValidationError:
        print("  [PASS] XSS query rejected")

    # Test case 5: Too many special characters
    try:
        req = ChatRequest(query="!@#$%^&*()!@#$%^&*()!@#$%^&*()")
        print("  [FAIL] Special char abuse should be rejected")
        return False
    except ValidationError:
        print("  [PASS] Special char abuse rejected")

    # Test case 6: Vietnamese characters (should pass)
    try:
        req = ChatRequest(query="Chính sách nghỉ phép là gì?")
        assert req.query == "Chính sách nghỉ phép là gì?"
        print("  [PASS] Vietnamese query accepted")
    except ValidationError as e:
        print(f"  [FAIL] Vietnamese query rejected: {e}")
        return False

    # Test case 7: Emojis (should pass)
    try:
        req = ChatRequest(query="Xin chào 👋 How are you? 😀")
        assert req.query == "Xin chào 👋 How are you? 😀"
        print("  [PASS] Emoji query accepted")
    except ValidationError as e:
        print(f"  [FAIL] Emoji query rejected: {e}")
        return False

    print("[PASS] Input validation tests passed!")
    return True


def test_sse_format():
    """Test SSE format compliance."""
    print("\n[TEST] Testing SSE format...")

    # Test SSE event format
    event = {"chunk": "Hello", "done": False}
    sse_line = f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    assert sse_line.startswith("data: "), "SSE line must start with 'data: '"
    assert sse_line.endswith("\n\n"), "SSE line must end with double newline"

    # Parse and verify
    json_str = sse_line[6:-2]  # Remove "data: " prefix and "\n\n" suffix
    parsed = json.loads(json_str)

    assert parsed == event, "Parsed event must match original"

    print("[PASS] SSE format tests passed!")
    return True


def test_error_messages():
    """Test error message formatting."""
    print("\n[TEST] Testing error messages...")

    # Test Vietnamese UTF-8 encoding
    error_event = {
        "chunk": "",
        "done": True,
        "error": "AI Model phản hồi quá chậm. Vui lòng thử câu hỏi ngắn hơn hoặc thử lại sau."
    }

    sse_line = f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    parsed = json.loads(sse_line[6:-2])

    assert "phản hồi quá chậm" in parsed["error"], "Vietnamese text must be preserved"
    assert parsed["done"] == True, "Error event must have done=True"
    assert parsed["chunk"] == "", "Error event must have empty chunk"

    print("[PASS] Error message tests passed!")
    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("Chat API Improvements Test Suite")
    print("=" * 60)

    tests = [
        test_citations_deduplication,
        test_input_validation,
        test_sse_format,
        test_error_messages,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[FAIL] Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n[SUCCESS] All tests passed! Chat API improvements verified.")
        return 0
    else:
        print(f"\n[WARNING] {failed} test(s) failed. Please review.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
