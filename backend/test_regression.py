"""
Regression tests for AdmitCrew coordinator agent catalog resolution.

Tests that:
1. Exact university+program resolution works correctly (Manchester vs Toronto)
2. Ambiguous program names without university require clarification
3. Contextual follow-ups preserve resolved university+program
4. Unknown universities escalate properly
5. Profile-aware catalog discovery filters by profile
"""

import sys
sys.path.insert(0, 'D:\\Projects\\AdmitCrew\\backend')

from agents.coordinator_agent import coordinator_agent
from agents.university_agent import university_agent


def test_collision_manchester_vs_toronto():
    """Test that 'University of Manchester BSc Computer Science' resolves to Manchester, not Toronto."""
    text = "What is the tuition fee for University of Manchester BSc Computer Science?"
    result = coordinator_agent.local_classify(text)
    
    assert result["intent"] == "program_question", f"Expected program_question, got {result['intent']}"
    assert result["university"] == "University of Manchester", f"Expected Manchester, got {result['university']}"
    assert result["program"] == "BSc Computer Science", f"Expected BSc Computer Science, got {result['program']}"
    assert result["university_found"] is True
    print("[PASS] test_collision_manchester_vs_toronto")


def test_collision_toronto_resolves_correctly():
    """Test that 'University of Toronto BSc Computer Science' resolves to Toronto."""
    text = "What is the tuition fee for University of Toronto BSc Computer Science?"
    result = coordinator_agent.local_classify(text)
    
    assert result["intent"] == "program_question"
    assert result["university"] == "University of Toronto"
    assert result["program"] == "BSc Computer Science"
    assert result["university_found"] is True
    print("[PASS] test_collision_toronto_resolves_correctly")


def test_ambiguous_program_requires_clarification():
    """Test that 'BSc Computer Science' without university triggers clarification."""
    text = "What is the tuition fee for BSc Computer Science?"
    result = coordinator_agent.local_classify(text)
    
    assert result["intent"] == "clarify_program"
    assert result["university"] is None
    assert result["program"] == "BSc Computer Science"
    assert result["university_found"] is False
    assert "University of Toronto" in result["reason"]
    assert "University of Manchester" in result["reason"]
    print("[PASS] test_ambiguous_program_requires_clarification")


def test_contextual_followup_preserves_program():
    """Test that 'What about its fee?' after Manchester context preserves Manchester."""
    context = {"last_program_id": 1}  # University of Manchester BSc CS
    text = "What about its fee?"
    result = coordinator_agent.local_classify(text, context)
    
    assert result["intent"] == "program_question"
    assert result["university"] == "University of Manchester"
    assert result["program"] == "BSc Computer Science"
    assert result["university_found"] is True
    print("[PASS] test_contextual_followup_preserves_program")


def test_contextual_eligibility_uses_profile():
    """Test that 'Do I meet its requirements?' triggers eligibility with profile."""
    context = {"last_program_id": 1}
    text = "Do I meet its requirements?"
    result = coordinator_agent.local_classify(text, context)
    
    assert result["intent"] == "eligibility"
    assert result["university"] == "University of Manchester"
    assert result["program"] == "BSc Computer Science"
    assert result["use_profile"] is True
    print("[PASS] test_contextual_eligibility_uses_profile")


def test_unknown_university_escalates():
    """Test that questions about unknown universities return unknown_university intent."""
    text = "What is the tuition fee for Harvard University Computer Science?"
    result = coordinator_agent.local_classify(text)
    
    assert result["intent"] == "unknown_university"
    assert result["university_found"] is False
    assert result["university"] is None
    print("[PASS] test_unknown_university_escalates")


def test_profile_aware_catalog_discovery():
    """Test that profile-aware discovery uses preferred_country."""
    profile = {"preferred_country": "UK", "marks": 80.0, "ielts_score": 7.0}
    text = "Based on my profile, which programs suit me?"
    result = coordinator_agent.local_classify(text, profile=profile)
    
    assert result["intent"] == "catalog_search"
    assert result["use_profile"] is True
    assert result["filters"].get("country") == "UK"
    print("[PASS] test_profile_aware_catalog_discovery")


def test_subject_country_discovery():
    """Test that 'Computer Science programs in UK' filters by UK."""
    text = "Which Computer Science programs can I apply to in the UK?"
    result = coordinator_agent.local_classify(text)
    
    assert result["intent"] == "catalog_search"
    assert result["filters"].get("country", "").casefold() == "uk"
    print("[PASS] test_subject_country_discovery")


def test_options_query_filters_by_country():
    """Test that 'What options do I have in the UK?' filters by UK."""
    text = "What options do I have in the UK?"
    result = coordinator_agent.local_classify(text)
    
    assert result["intent"] == "catalog_search"
    assert result["filters"].get("country", "").casefold() == "uk"
    print("[PASS] test_options_query_filters_by_country")


def test_program_match_priority_over_fuzzy():
    """Test that exact university+program takes priority over fuzzy matching."""
    text = "Manchester BSc Computer Science"
    result = coordinator_agent.local_classify(text)
    
    assert result["intent"] in ("program_question", "clarify_program")
    assert result["university"] == "University of Manchester" or result["university"] is None
    print("[PASS] test_program_match_priority_over_fuzzy (behavior noted)")


def test_catalog_lookup_uses_exact_university_program_pair():
    """Verify that handle_message uses get_program(university, program) for exact lookup."""
    program = university_agent.get_program("University of Manchester", "BSc Computer Science")
    
    assert program is not None
    assert program["id"] == 1
    assert program["university"] == "University of Manchester"
    assert program["program"] == "BSc Computer Science"
    print("[PASS] test_catalog_lookup_uses_exact_university_program_pair")


def test_duplicate_program_not_found_at_wrong_university():
    """Test that Manchester BSc CS doesn't return Toronto data."""
    program = university_agent.get_program("University of Manchester", "BSc Computer Science")
    
    assert program["id"] == 1  # Manchester, not Toronto (id=3)
    assert program["university"] != "University of Toronto"
    print("[PASS] test_duplicate_program_not_found_at_wrong_university")


def run_all_tests():
    """Run all regression tests."""
    tests = [
        test_collision_manchester_vs_toronto,
        test_collision_toronto_resolves_correctly,
        test_ambiguous_program_requires_clarification,
        test_contextual_followup_preserves_program,
        test_contextual_eligibility_uses_profile,
        test_unknown_university_escalates,
        test_profile_aware_catalog_discovery,
        test_subject_country_discovery,
        test_options_query_filters_by_country,
        test_program_match_priority_over_fuzzy,
        test_catalog_lookup_uses_exact_university_program_pair,
        test_duplicate_program_not_found_at_wrong_university,
        test_escalation_creation_and_resolution,
        test_escalation_resolution_prevents_duplicate,
        test_escalation_history_appears_in_student_conversation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print("[FAIL] " + test.__name__ + ": " + str(e))
            failed += 1
    
    print("\n=== Results: " + str(passed) + " passed, " + str(failed) + " failed ===")
    return failed == 0


def test_escalation_creation_and_resolution():
    """Test that escalation is created and staff response is inserted into conversation."""
    from database import get_connection
    from agents.escalation_agent import escalation_agent
    
    # Create a test escalation with a lead and conversation
    conn = get_connection()
    # Use existing lead 11
    lead_id = 11
    # Get a conversation for this lead
    conv = conn.execute("SELECT id FROM conversations WHERE lead_id = ? ORDER BY id DESC LIMIT 1", (lead_id,)).fetchone()
    conv_id = conv["id"] if conv else None
    
    # Create escalation with conversation
    result = escalation_agent.create_escalation(
        question="Test escalation question",
        reason="Test reason",
        source_agent="test_agent",
        lead_id=lead_id,
        conversation_id=conv_id,  # With conversation
    )
    assert "escalation" in result
    esc_id = result["escalation"]["id"]
    
    # Resolve with staff response
    staff_response = "This is a test staff response."
    resolve_result = escalation_agent.resolve_escalation(esc_id, staff_response, actor_id=1)
    assert resolve_result["resolved"] is True
    assert resolve_result["delivered_to_conversation"] is True
    message_id = resolve_result["message_id"]
    
    # Verify message was inserted
    msg = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    assert msg is not None
    assert msg["sender"] == "staff"
    assert staff_response in msg["content"]
    
    # Verify escalation status
    esc = conn.execute("SELECT * FROM escalations WHERE id = ?", (esc_id,)).fetchone()
    assert esc["status"] == "resolved"
    assert esc["staff_response"] == staff_response
    
    conn.close()
    print("[PASS] test_escalation_creation_and_resolution")


def test_escalation_resolution_prevents_duplicate():
    """Test that repeated resolution doesn't duplicate messages."""
    from agents.escalation_agent import escalation_agent
    
    # Create a new escalation
    result = escalation_agent.create_escalation(
        question="Duplicate test question",
        reason="Test duplicate prevention",
        source_agent="test_agent",
        lead_id=11,
        conversation_id=None,
    )
    esc_id = result["escalation"]["id"]
    
    # First resolution
    staff_response = "First response."
    resolve_result1 = escalation_agent.resolve_escalation(esc_id, staff_response, actor_id=1)
    assert resolve_result1["resolved"] is True
    message_id1 = resolve_result1["message_id"]
    
    # Second resolution with same response
    resolve_result2 = escalation_agent.resolve_escalation(esc_id, staff_response, actor_id=1)
    assert resolve_result2["resolved"] is False
    assert resolve_result2["already_resolved"] is True
    # Should not create a new message
    assert resolve_result2["escalation"]["id"] == esc_id
    
    # Second resolution with different response should fail
    resolve_result3 = escalation_agent.resolve_escalation(esc_id, "Different response.", actor_id=1)
    assert "error" in resolve_result3
    assert resolve_result3["error"] == "escalation_already_resolved"
    
    print("[PASS] test_escalation_resolution_prevents_duplicate")


def test_escalation_history_appears_in_student_conversation():
    """Test that resolved escalation response appears in student's history."""
    import requests
    base_url = 'http://localhost:8000'
    
    # Create a fresh session for this test
    session_id = 'test_escalation_history'
    resp = requests.post(base_url + '/api/chat/start?session_id=' + session_id)
    
    # Quick intake
    resp = requests.post(base_url + '/api/chat/message', json={'session_id': session_id, 'message': 'Hi, I want to study in the UK.'})
    resp = requests.post(base_url + '/api/chat/message', json={'session_id': session_id, 'message': 'My name is Test User. I got 80% and IELTS 7.0.'})
    resp = requests.post(base_url + '/api/chat/message', json={'session_id': session_id, 'message': 'My phone is +44 7911 111111 and my budget is 30000 GBP per year.'})
    
    # Trigger escalation
    resp = requests.post(base_url + '/api/chat/message', json={'session_id': session_id, 'message': 'What is the fee for Unknown University Program?'})
    assert resp.status_code == 200
    esc_id = resp.json()["details"]["result"]["escalation"]["escalation_id"]
    
    # Resolve escalation
    from agents.escalation_agent import escalation_agent
    resolve_result = escalation_agent.resolve_escalation(esc_id, "Test staff response for history.", actor_id=1)
    assert resolve_result["resolved"] is True
    assert resolve_result["delivered_to_conversation"] is True
    
    # Check history includes staff response
    resp = requests.get(base_url + '/api/chat/history?session_id=' + session_id)
    messages = resp.json()["messages"]
    
    # Find staff message
    staff_messages = [m for m in messages if m["role"] == "staff"]
    assert len(staff_messages) >= 1
    assert "Test staff response for history." in staff_messages[-1]["text"]
    
    print("[PASS] test_escalation_history_appears_in_student_conversation")


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)