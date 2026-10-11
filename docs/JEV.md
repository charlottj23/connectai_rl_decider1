# JEV 형식

회사의 모든 판단은 JEV(OpenRouter Decisions API의 `typesafe/jev-1.13`)와 같은 모양으로 오갑니다.

```
요청  {"model", "state": {...}, "questions": {"decision": {"type": "choice", "instructions", "criteria": {key: 설명}}}}
응답  {"model", "answers": {"decision": {"type": "choice", "choice": key, "probabilities": {key: p}, "confidence": p}}}
```

`connect-tycoon demo --dept 부서`로 언제든 실제 요청과 응답을 볼 수 있습니다.

## 예시 · 환불

```json
{
  "model": "typesafe/jev-1.13",
  "state": {
    "department": "refund",
    "department_name": "환불",
    "company_name": "CONNECT 상회",
    "company": {"day": 0, "weekday": "월", "sat": 0.709, "stock": 150.0, "incoming": 0.0, "ad": 0.5,
                "human_left": 0.667, "human_seats_left": 2, "human_seats": 3, "time": 0.231, "days": 20},
    "reason": "불량", "tier": "신규", "amount": 6.0, "fraud_score": 0.111, "billing_left": 1.0
  },
  "questions": {
    "decision": {
      "type": "choice",
      "instructions": "환불 요청을 어떻게 처리할지 고르세요. 악용이면 돈을 잃고, 정상 고객을 거절하면 만족이 떨어집니다. 회사의 가치 — 이익 1 · 고객 만족 1 · 위험 회피 1.",
      "criteria": {"full": "전액 환불", "partial": "부분 환불 (절반)", "deny": "거절",
                   "human": "사람 확인 · 악용이면 사람이 거절합니다 · 건당 0.8만원"}
    }
  }
}
```

```json
{
  "model": "connect-company/jay-company",
  "answers": {
    "decision": {"type": "choice", "choice": "full",
                 "probabilities": {"full": 0.9921, "partial": 0.0003, "deny": 0.0003, "human": 0.0074},
                 "confidence": 0.9921, "reason": "강화학습 정책"}
  }
}
```

(문서에서는 숫자를 줄였습니다. 실제 요청은 반올림하지 않습니다.)

## 부서별 state

| 부서 (`department`) | 부서별 필드 | criteria key |
|---|---|---|
| `staffing` 인력 배치 | `yesterday_cs_overflow` · `yesterday_refunds` · `yesterday_security` · `yesterday_human_overflow` | balanced · cs_focus · billing_focus · review_focus |
| `inventory` 재고 발주 | `recent_sales` · `stockout_yesterday` | none · small · large |
| `marketing` 마케팅 | `recent_sales` · `profit_yesterday` | stop · keep · boost |
| `cs` 고객센터 | `message` · `industry` · `urgent_left` · `billing_left` | urgent · normal · billing · human |
| `refund` 환불 | `reason` · `tier` · `amount` · `fraud_score` · `billing_left` | full · partial · deny · human |
| `security` 보안 | `amount` · `fraud_score` · `new_device` · `overseas` · `velocity` | allow · block · human |

`company`는 모든 부서에 공통입니다: `day` · `weekday` · `sat`(고객 만족) · `stock` · `incoming` · `ad` · `human_left`(남은 사람 확인 비율) · `human_seats_left` · `human_seats` · `time`(낮 시간 0~1) · `days`.

## 아무 JEV 모델이나 사장 자리에

```python
import connect_tycoon as ct

def my_model(request):                      # JEV 요청 → JEV 응답
    keys = list(request["questions"]["decision"]["criteria"])
    return {"answers": {"decision": {"type": "choice", "choice": keys[0]}}}

company = ct.make_company()
policy = ct.jev.JevPolicy(my_model)         # 응답 모양을 검사하고 모든 요청/응답을 policy.log에 남깁니다
log, days = company.run_month(7000, policy)
rows = ct.jev.dataset(policy.log, log, seed=7000)
ct.jev.write_jsonl(rows, "my_model_month.jsonl")
```

`probabilities`와 `confidence`는 없어도 됩니다. 있으면 게임 패널에 막대로 그립니다.

## 학습 데이터 한 줄

```json
{"env": "connect-company/1", "seed": 7000, "day": 0, "department": "refund",
 "request": {...}, "response": {...},
 "reward": 0.1, "day_reward": 4.2,
 "outcome": {"truth": "정상", "effective": "전액 환불", "overflow": false, "money": -6.0, "dsat": 0.01, "incidents": 0}}
```

- `reward` · 그 판단의 즉시 보상 (회사의 가치로 계산)
- `day_reward` · 그날 하루 보상의 합 (아침 판단처럼 결과가 늦게 오는 판단에 씁니다)
- `outcome.truth` · 판단할 때는 보이지 않던 진실 (악용 · 사기 · 문의의 진짜 유형)

게임에서 사람이 내린 지시도 같은 모양으로 저장됩니다 (`response.model = "connect-tycoon/owner"`).
