from skillsync_ai.agents.rd_suggestion import (
    classify_evidence_signal,
    suggest_rd_rating,
    _clamp_upward_vs_zm,
    _reject_high_when_development_only,
    _evidence_summary,
)


def test_empty_tna_skill_tags_tagged_learning_need():
    row = {"source": "TNA", "label": "", "snippet": "Data & Analytics"}
    assert classify_evidence_signal(row) == "employee_learning_need"


def test_rm_skill_title_is_taxonomy_not_performance():
    row = {"source": "TNA", "label": "Reporting manager input 2", "snippet": "Data-Driven Planning"}
    assert classify_evidence_signal(row) == "skill_taxonomy_tag"


def test_appraisal_development_area_tagged():
    row = {
        "source": "Appraisal",
        "label": "What Are 2-3 Development Areas Or Skills That Your Team Member Needs To Develop, To Grow Further?",
        "snippet": "Use data to plan your discussions with hotel partners.",
    }
    assert classify_evidence_signal(row) == "appraisal_development_gap"


def test_development_only_rejects_proficient():
    evidence = [
        {"source": "TNA", "label": "Reporting manager input 2", "snippet": "Data-Driven Planning"},
        {"source": "TNA", "label": "", "snippet": "Data & Analytics"},
        {
            "source": "Appraisal",
            "label": "What Are 2-3 Development Areas Or Skills That Your Team Member Needs To Develop, To Grow Further?",
            "snippet": "Use data to plan your discussions with hotel partners.",
        },
    ]
    summary = _evidence_summary(evidence)
    assert summary["performance_count"] == 0
    assert summary["development_count"] >= 1
    assert _reject_high_when_development_only("Proficient", summary) == "Intermediate"


def test_clamp_allows_below_zm():
    assert _clamp_upward_vs_zm("Beginner", "Proficient") == "Beginner"
    assert _clamp_upward_vs_zm("Intermediate", "Proficient") == "Intermediate"


def test_suggest_fallback_development_only_without_llm(monkeypatch=None):
    # Direct unit of reject path used when LLM mirrors ZM.
    evidence = [
        {"source": "TNA", "label": "", "snippet": "Data & Analytics"},
        {
            "source": "Appraisal",
            "label": "development areas to grow further",
            "snippet": "Use data to plan.",
        },
    ]
    summary = _evidence_summary(evidence)
    assert _reject_high_when_development_only("Proficient", summary) == "Intermediate"
