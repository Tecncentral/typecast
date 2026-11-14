from agent import pipeline

SCENE = "INT. 1980s POLICE STATION, NIGHT. Big open room, drop ceiling. Parking for 3 trucks and 30 crew cars."
def test_parse():
    r = pipeline.parse_scene(SCENE)
    assert r["trucks"] == 3 and r["cars"] == 30 and r["year_max"] == 1992


