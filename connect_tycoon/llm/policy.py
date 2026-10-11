"""④ 채점 · 언어 모델을 회사 사장 자리에 앉힙니다. Scorer(MLX · PyTorch)의 보기 확률로 판단하고, JEV 모양으로도 답합니다."""
from .. import jev as J
from ..company import DEPTS
from .format import task


class LLMPolicy:
    def __init__(self, scorer, values=None, name=None):
        self.scorer, self.values = scorer, values
        self.name = name or getattr(scorer, "name", "llm")

    def probs(self, dept, ev):
        return self.scorer.probs(task(dept, ev, self.values))

    def act(self, dept, obs, ev):
        p = self.probs(dept, ev)
        return DEPTS[dept]["actions"][max(range(len(p)), key=lambda i: p[i])]

    def jev(self, dept, ev):
        """같은 판단을 JEV 응답(choice · probabilities · confidence)으로."""
        return J.answer(dept, self.probs(dept, ev), model=self.name)


def report(policy, company, months=3, card=True, demand_months=2):
    """시뮬레이터 처음 보는 달 + 실제 데이터 시험. 언어 모델은 느리므로 달 수를 작게 둡니다."""
    from .. import backtest
    from ..train import evaluate
    ev = evaluate(company, policy, seeds=range(7000, 7000 + months))
    out = {"profit": ev["profit"], "sat": ev["sat"], "incidents": ev["incidents"], "months": months}
    if card:
        c = backtest.card(policy, company)
        out["card"] = {"caught": c["caught"], "fraud": c["fraud"], "saved": c["saved"], "cases": c["cases"]}
    if demand_months:
        out["demand_profit"] = backtest.demand(policy, company, months=demand_months)["profit"]
    return out
