"""두뇌 키우기 · 규칙 사장을 따라 배우고(지도학습) → 보상으로 고칩니다(PPO) → brain.json."""
import connect_tycoon as ct

values = {"이익": 2.0, "고객 만족": 1.0, "위험": 1.0}        # 이익을 두 배로 중요하게
company = ct.make_company(values=values)
policy, history = ct.grow_brain(company, ct.RulePolicy(), iterations=20, months_per_iter=12, imitate_months=20)

mine, rule = ct.evaluate(company, policy), ct.evaluate(company, ct.RulePolicy())
print(f"처음 보는 40개월 · 내 두뇌 {mine['profit']:.0f}만원/달 · 규칙 사장 {rule['profit']:.0f}만원/달")

spec = ct.CompanyBrain.make_spec(ct.CompanyBrain.default().spec, policy, name="my-ceo", values=values, researcher="나")
ct.CompanyBrain(spec).save("my-ceo.json")
print("저장 → my-ceo.json   ·   connect-tycoon play --brain my-ceo.json")
