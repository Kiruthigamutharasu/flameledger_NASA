"""AI orchestration with a fake transport: verify, retry once, fail closed, cache, never raise."""
import json
from pathlib import Path

import pytest

from flameledger.config import ROOT, Settings
from flameledger.data import load_dataset
from flameledger.llm import FAILED_VERIFICATION, NOT_CONFIGURED, UNAVAILABLE, VERIFIED, Explainer
from flameledger.rules import Habitat, RulesEngine

DATA = Path(__file__).resolve().parent.parent / "data"
NO_KEY = Settings(data_dir=DATA, web_dir=ROOT / "web", gemini_api_key="", gemini_model="")


@pytest.fixture(scope="module")
def review():
    return RulesEngine(load_dataset(DATA)).review(Habitat(34, 8.2, 0.165), ["PMMA rod", "silicone"])


GOOD = json.dumps({
    "summary": "PMMA rod burned in microgravity at 13.6% O2, below this habitat's 34% O2. Silicone has no space data.",
    "per_material": [{"material_id": "pmma_rod", "explanation": "Published margin -2.4% O2 against the 1g blowoff limit."},
                     {"material_id": "silicone_mq", "explanation": "No space data. A reduced-gravity test is needed."}],
    "claims": [{"text": "PMMA burned at 13.6% O2", "value": 13.6, "unit": "pct_O2", "source_id": "E2"},
               {"text": "Habitat O2", "value": 34, "unit": "pct_O2", "source_id": "habitat"},
               {"text": "Published margin", "value": -2.4, "unit": "pct_O2", "source_id": "E3"}],
})
BAD = json.dumps({"summary": "PMMA will burn at 11% O2 on the Moon.", "per_material": [], "claims": []})


class Fake:
    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    def __call__(self, system, prompt, timeout):
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_not_configured(review):
    res = Explainer(NO_KEY).explain(review)
    assert res.ai is None and res.status == NOT_CONFIGURED


def test_verified_first_time(review):
    fake = Fake(GOOD)
    res = Explainer(NO_KEY, fake).explain(review)
    assert res.status == VERIFIED and res.ai["summary"].startswith("PMMA")
    assert len(fake.prompts) == 1


def test_retry_with_errors_then_pass(review):
    fake = Fake(BAD, GOOD)
    res = Explainer(NO_KEY, fake).explain(review)
    assert res.status == VERIFIED and len(fake.prompts) == 2
    assert "failed verification" in fake.prompts[1] and "11" in fake.prompts[1]


def test_fails_closed_after_one_retry(review):
    fake = Fake(BAD, BAD, GOOD)
    res = Explainer(NO_KEY, fake).explain(review)
    assert res.status == FAILED_VERIFICATION and res.ai is None and len(fake.prompts) == 2


def test_transport_error_is_retried_once_then_unavailable(review):
    fake = Fake(TimeoutError(), ConnectionError(), GOOD)
    res = Explainer(NO_KEY, fake).explain(review)
    assert res.status == UNAVAILABLE and res.ai is None and len(fake.prompts) == 2


def test_transport_error_then_success(review):
    assert Explainer(NO_KEY, Fake(TimeoutError(), GOOD)).explain(review).status == VERIFIED


def test_cache(review):
    fake = Fake(GOOD)
    ex = Explainer(NO_KEY, fake)
    assert ex.explain(review, cache_only=True).status == UNAVAILABLE
    assert ex.explain(review).status == VERIFIED
    assert ex.explain(review).status == VERIFIED
    assert ex.explain(review, cache_only=True).status == VERIFIED
    assert len(fake.prompts) == 1


def test_markdown_fenced_json_is_accepted(review):
    assert Explainer(NO_KEY, Fake("```json\n" + GOOD + "\n```")).explain(review).status == VERIFIED


def test_prompt_contains_only_given_evidence(review):
    fake = Fake(GOOD)
    Explainer(NO_KEY, fake).explain(review)
    payload = json.loads(fake.prompts[0].split("\n", 1)[1])
    ids = {e["id"] for e in payload["evidence"]}
    expected = {e["id"] for v in review["verdicts"] for e in v["evidence"]}
    assert ids == expected and "E14" not in ids
    assert {v["material_id"] for v in payload["verdict_table"]} == {"pmma_rod", "silicone_mq"}
