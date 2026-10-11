"""한 달을 세 사장으로 운영해 보고 비교합니다."""
import connect_tycoon as ct

company = ct.make_company()                      # 강의 Colab과 같은 회사
brain = ct.CompanyBrain.default()                # 예시 AI 사장 (jay-company)

for name, ceo in [("무작위", ct.RandomPolicy(0)), ("규칙 사장", ct.RulePolicy()), ("AI 사장", brain)]:
    log, days = company.run_month(7000, ceo)
    profit = sum(d["profit"] for d in days)
    print(f"{name:8s} 한 달 이익 {profit:7.0f}만원 · 월말 고객 만족 {days[-1]['sat']:.0%} · 위험 사고 {sum(d['incidents'] for d in days)}건")
