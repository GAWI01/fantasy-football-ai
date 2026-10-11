from engine.decision_risk import player_risk, squad_health
def test_unavailable_is_very_high():
    assert player_risk({"xmins":0,"start_probability":0,"availability":"UNAVAILABLE","rotation_risk":"OUT"})["label"]=="VERY_HIGH"
def test_healthy():
    players=[{"player_id":i,"name":str(i),"xmins":90,"start_probability":1,"availability":"AVAILABLE","rotation_risk":"LOW"} for i in range(15)]
    assert squad_health(players)["status"]=="HEALTHY"
