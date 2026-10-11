from engine.decision_risk import risk_adjusted_points

def test_risk_adjustment_preserves_raw_points():
    out=risk_adjusted_points({"predicted_points":10,"xmins":90,"availability":"AVAILABLE","rotation_risk":"LOW"})
    assert out["predicted_points"]==10 and out["risk_adjusted_points"]==10

def test_risk_adjustment_reduces_high_risk_score():
    safe=risk_adjusted_points({"predicted_points":10,"xmins":90,"availability":"AVAILABLE","rotation_risk":"LOW"})
    risky=risk_adjusted_points({"predicted_points":10,"xmins":45,"availability":"RISK","rotation_risk":"HIGH"})
    assert risky["risk_adjusted_points"] < safe["risk_adjusted_points"]
