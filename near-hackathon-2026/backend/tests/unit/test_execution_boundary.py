from app.foundation.execution_boundary import SimulatedSigner, enforce_before_signing


def test_block_and_error_never_call_signer():
    signer = SimulatedSigner()
    assert enforce_before_signing("BLOCK", {}, signer.sign)["signer_invoked"] is False
    assert enforce_before_signing("ERROR", {}, signer.sign)["signer_invoked"] is False
    assert signer.calls == []


def test_review_warns_until_explicit_human_approval():
    signer = SimulatedSigner()
    result = enforce_before_signing("REVIEW", {"amount_near": 7}, signer.sign)
    assert result == {"outcome": "WARN", "signer_invoked": False, "approval_required": True}
    assert signer.calls == []
    approved = enforce_before_signing("REVIEW", {"amount_near": 7}, signer.sign, human_approved=True)
    assert approved["outcome"] == "ALLOW"
    assert approved["signer_invoked"] is True
    assert approved["signer_result"] == {"simulated": True, "broadcast": False}


def test_allow_uses_only_simulated_signer_and_fails_closed_on_unknown_decision():
    signer = SimulatedSigner()
    result = enforce_before_signing("APPROVE", {"amount_near": 1}, signer.sign)
    assert result["outcome"] == "ALLOW" and result["signer_invoked"] is True
    assert enforce_before_signing("MAYBE", {}, signer.sign)["outcome"] == "ERROR"
    assert len(signer.calls) == 1
