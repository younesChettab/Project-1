from amin.engine.normalize import contains_ar, normalize_ar
from amin.engine.pipeline import apply_corrections, run

AR_YAD = "إن الذين يبايعونك إنما يبايعون الله ﴿يَدُ اللَّهِ فَوْقَ أَيْدِيهِمْ﴾."


def rules(result):
    return [f["rule"] for f in result["findings"]]


def test_normalize_strips_tashkeel_and_alef():
    assert normalize_ar("أَوْلِيَاءَ اللَّهِ") == "اولياء الله"


def test_arabic_prefixes_match():
    assert contains_ar(normalize_ar("ولا يجوز قتال الكافرين"), ["كافر"])
    assert contains_ar(normalize_ar("وأقيموا الصلاة"), ["صلاة"])


def test_tawil_of_hand_is_flagged_en():
    r = run(AR_YAD, "Those who pledge to you pledge to Allah; Allah's power is over their hands.", "en", use_llm=False)
    assert "tawil:sifah-yad" in rules(r)
    f = next(f for f in r["findings"] if f["rule"] == "tawil:sifah-yad")
    assert f["severity"] == "high" and f["suggestion"] == "the Hand of Allah"


def test_approved_hand_translation_not_flagged():
    r = run(AR_YAD, 'Those who pledge to you pledge to Allah: "The Hand of Allah is over their hands" [48:10].', "en", use_llm=False)
    assert not any(x.startswith(("tawil", "ayah")) for x in rules(r))


def test_istiwa_french():
    r = run("ثم استوى على العرش.", "Puis Il a pris le contrôle du Trône.", "fr", use_llm=False)
    assert "tawil:sifah-istiwa" in rules(r)


def test_offensive_term_is_global():
    r = run("ندعوهم إلى الإسلام.", "We call the infidels to Islam.", "en", use_llm=False)
    assert "forbidden:kafir" in rules(r)


def test_golden_rule_gloss_inside_parentheses_ok():
    r = run("الشهداء أحياء.", "The Shuhada (Martyrs) are alive.", "en", use_llm=False)
    assert "forbidden:shaheed" not in rules(r)


def test_negation_dropped():
    r = run("ولا يجوز الاعتداء.", "It is permitted to attack.", "en", use_llm=False)
    assert "omission:negation" in rules(r)


def test_negation_kept():
    r = run("ولا يجوز الاعتداء.", "It is not permitted to attack.", "en", use_llm=False)
    assert "omission:negation" not in rules(r)


def test_hadith_attribution_and_salawat():
    r = run("قال رسول الله صلى الله عليه وسلم: «ينزل ربنا» متفق عليه.", 'The Messenger said: "Our Lord descends."', "en", use_llm=False)
    assert "hadith:no-source" in rules(r)
    assert "hadith:salawat" in rules(r)


def test_apply_corrections():
    t = "The martyrs are alive."
    r = run("الشهداء أحياء.", t, "en", use_llm=False)
    ids = [f["id"] for f in r["findings"] if f["replace"]]
    assert apply_corrections(t, r["findings"], set(ids)) == "The Shaheed (Martyr) are alive."


def test_clean_samples_have_no_errors():
    import yaml
    from pathlib import Path
    data = yaml.safe_load(open(Path(__file__).parent.parent / "samples" / "samples.yaml", encoding="utf-8"))
    for s in data["samples"]:
        if s["id"].endswith("clean"):
            r = run(s["arabic"], s["translation"], s["lang"], s["audience"], use_llm=False)
            assert [f for f in r["findings"] if f["type"] != 7] == [], s["id"]
