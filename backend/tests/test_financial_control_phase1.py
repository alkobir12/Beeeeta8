"""
Tests for Financial Control Layer — Phase 1
  • Approval Engine classification + workflow + four-eyes
  • Findings Engine lifecycle
  • Audit Rules detection
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from financial_control.approval_engine import ApprovalEngine
from financial_control.audit_rules import AuditRulesEngine
from financial_control.findings_engine import FindingsEngine
from financial_control.four_eyes import FourEyesValidator, FourEyesViolation
from financial_control.models import ApprovalLevel, FindingStatus


# ============== Approval Engine ==============

def test_classify_auto():
    eng = ApprovalEngine(db=None)
    assert eng.classify(0) == ApprovalLevel.AUTO
    assert eng.classify(500) == ApprovalLevel.AUTO
    assert eng.classify(1000) == ApprovalLevel.AUTO


def test_classify_manager():
    eng = ApprovalEngine(db=None)
    assert eng.classify(1000.01) == ApprovalLevel.MANAGER
    assert eng.classify(5000) == ApprovalLevel.MANAGER
    assert eng.classify(10000) == ApprovalLevel.MANAGER


def test_classify_senior_manager():
    eng = ApprovalEngine(db=None)
    assert eng.classify(10000.01) == ApprovalLevel.SENIOR_MANAGER
    assert eng.classify(25000) == ApprovalLevel.SENIOR_MANAGER
    assert eng.classify(50000) == ApprovalLevel.SENIOR_MANAGER


def test_classify_director():
    eng = ApprovalEngine(db=None)
    assert eng.classify(50000.01) == ApprovalLevel.DIRECTOR
    assert eng.classify(1_000_000) == ApprovalLevel.DIRECTOR


def test_role_can_approve():
    eng = ApprovalEngine(db=None)
    # admin can always approve
    assert eng.role_can_approve("admin", ApprovalLevel.DIRECTOR) is True
    # manager can approve manager level
    assert eng.role_can_approve("manager", ApprovalLevel.MANAGER) is True
    # manager cannot approve senior_manager level
    assert eng.role_can_approve("manager", ApprovalLevel.SENIOR_MANAGER) is False
    # clerk cannot approve anything but auto
    assert eng.role_can_approve("clerk", ApprovalLevel.MANAGER) is False
    assert eng.role_can_approve("clerk", ApprovalLevel.AUTO) is True  # 'any' role allowed


# ============== Four Eyes ==============

def test_four_eyes_clean():
    FourEyesValidator.check(creator="a", reviewer="b", approver="c")  # no raise


def test_four_eyes_creator_eq_reviewer():
    with pytest.raises(FourEyesViolation) as exc:
        FourEyesValidator.check(creator="a", reviewer="a", approver="b")
    assert "creator_equals_reviewer" in str(exc.value)


def test_four_eyes_creator_eq_approver():
    with pytest.raises(FourEyesViolation) as exc:
        FourEyesValidator.check(creator="a", approver="a")
    assert "creator_equals_approver" in str(exc.value)


def test_four_eyes_reviewer_eq_approver():
    with pytest.raises(FourEyesViolation) as exc:
        FourEyesValidator.check(creator="a", reviewer="b", approver="b")
    assert "reviewer_equals_approver" in str(exc.value)


def test_four_eyes_admin_override():
    # admin can hold both roles
    FourEyesValidator.check(creator="a", approver="a", allow_admin_override=True, actor_role="admin")
    FourEyesValidator.check(creator="a", reviewer="b", approver="b", allow_admin_override=True, actor_role="admin")


# ============== Audit Rules ==============

def test_rule_duplicate_payments():
    eng = AuditRulesEngine(workshop_id="t1")
    journals = [
        {"id": "j1", "source": "operation_payment", "reference_id": "op1", "total": 100},
        {"id": "j2", "source": "operation_payment", "reference_id": "op1", "total": 100},
        {"id": "j3", "source": "operation_payment", "reference_id": "op2", "total": 50},
    ]
    findings = eng.rule_duplicate_payments(journals)
    assert len(findings) == 1
    assert findings[0].rule_code == "duplicate_payment"
    assert findings[0].entity_id == "op1"
    assert findings[0].financial_impact == 200.0


def test_rule_negative_inventory():
    eng = AuditRulesEngine(workshop_id="t1")
    parts = [
        {"id": "p1", "name": "فلتر", "stock": 5, "cost": 20},
        {"id": "p2", "name": "زيت", "stock": -3, "cost": 50},
        {"id": "p3", "name": "بطارية", "stock": 0, "cost": 100},
    ]
    findings = eng.rule_negative_inventory(parts)
    assert len(findings) == 1
    assert findings[0].entity_id == "p2"
    assert findings[0].financial_impact == 150.0  # 3 * 50


def test_rule_unbalanced_journal():
    eng = AuditRulesEngine(workshop_id="t1")
    journals = [
        {"id": "j1", "lines": [{"debit": 100, "credit": 0}, {"debit": 0, "credit": 100}]},  # balanced
        {"id": "j2", "lines": [{"debit": 100, "credit": 0}, {"debit": 0, "credit": 80}]},   # drift 20
    ]
    findings = eng.rule_unbalanced_journal(journals)
    assert len(findings) == 1
    assert findings[0].entity_id == "j2"
    assert findings[0].financial_impact == 20.0


def test_rule_future_dated():
    eng = AuditRulesEngine(workshop_id="t1")
    operations = [
        {"id": "o1", "date": "2030-01-01T00:00:00", "total": 500},  # future
        {"id": "o2", "date": "2024-01-01T00:00:00", "total": 300},  # past
    ]
    findings = eng.rule_future_dated(operations)
    assert len(findings) == 1
    assert findings[0].entity_id == "o1"


def test_rule_missing_reference():
    eng = AuditRulesEngine(workshop_id="t1")
    operations = [
        {"id": "op1", "type": "sale", "total": 100},
        {"id": "op2", "type": "service", "total": 200},
        {"id": "op3", "type": "draft", "total": 50},  # should be skipped
    ]
    journals = [
        {"id": "j1", "reference_id": "op1"},
    ]
    findings = eng.rule_missing_reference(operations, journals)
    assert len(findings) == 1
    assert findings[0].entity_id == "op2"


def test_run_all_returns_list():
    eng = AuditRulesEngine(workshop_id="t1")
    ctx = {"journals": [], "operations": [], "parts": [], "invoices": []}
    findings = eng.run_all(ctx)
    assert isinstance(findings, list)
    assert len(findings) == 0


# ============== Signatures stable ==============

def test_signature_deterministic():
    from financial_control.findings_engine import make_signature
    s1 = make_signature(rule_code="duplicate_payment", entity_type="operation", entity_id="op1")
    s2 = make_signature(rule_code="duplicate_payment", entity_type="operation", entity_id="op1")
    assert s1 == s2
    s3 = make_signature(rule_code="duplicate_payment", entity_type="operation", entity_id="op2")
    assert s1 != s3
