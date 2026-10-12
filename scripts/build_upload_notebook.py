"""notebooks/upload_brain_colab.ipynb 만들기 · 게임에서 저장한 brain.json을 Hugging Face에 바로 올리기 (1분 · GPU 필요 없음)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import build_notebook as B

REPO = B.REPO
CELLS = [
    ("md", """# 내 RL 모델을 Hugging Face에 올리기 · 1분

**CONNECT AI LAB × AI CITY BUILDERS** · [CONNECT TYCOON](https://github.com/wonseokjung/connect-tycoon)

게임에서 **brain.json 저장**으로 내려받은 강화학습 모델을 내 Hugging Face 계정에 올립니다. GPU가 필요 없습니다.

1. https://huggingface.co/settings/tokens 에서 **Write** 토큰을 만듭니다.
2. Colab 왼쪽 🔑(보안 비밀)에 이름 `HF_TOKEN`, 값에 토큰을 넣고 노트북 액세스를 켭니다. 토큰은 코드에 적지 않습니다.
3. 아래 셀을 위에서부터 차례로 실행합니다.

업로드 이름은 `connectailab-rl-이름-버전-teacher` 입니다 (예: `connectailab-rl-jay-v2-teacher`). Qwen까지 학습해 올리려면 [Qwen 강화학습 Colab](https://colab.research.google.com/github/wonseokjung/connect-tycoon/blob/main/notebooks/rl_decision_model_qwen_colab.ipynb)을 쓰세요."""),
    ("code", f"""# 설치 (30초)
!pip -q install "connect-tycoon @ git+{REPO}" huggingface_hub
import connect_tycoon as ct
print("CONNECT TYCOON", ct.__version__)""", None),
    ("md", """## 1 · brain.json 고르기

실행하면 파일 선택 창이 뜹니다. 게임에서 저장한 파일(다운로드 폴더의 `회사이름-v2.json` 같은 이름)을 고르세요.
파일 없이 보기만 하려면 `USE_EXAMPLE`을 켜면 예시 모델을 씁니다."""),
    ("code", """USE_EXAMPLE = False                                   #@param {type:"boolean"}
if USE_EXAMPLE:
    ct.CompanyBrain.default().save("brain.json"); BRAIN = "brain.json"
else:
    from google.colab import files
    BRAIN = next(iter(files.upload()))
b = ct.CompanyBrain.from_file(BRAIN)
print("모델:", b.name, "· 회사의 가치", b.values, "· 기록된 성적", b.spec["company"].get("results"))""", None),
    ("md", """## 2 · 이름 · 나를 알리는 글 · 올리기

이름은 영문, 버전은 게임의 버전(v1, v2…)을 적습니다. 나를 알리는 글은 형식 없이 자유롭게 (무엇을 하는 사람인지 · 사업 · 서비스 · 채널 · 연락처). 모델 카드 맨 위 '만든 사람'에 그대로 들어가고, 비워 두면 빠집니다.

✅ 정상이면 · 1분 안팎 (모델 카드에 넣을 성적을 시험 달로 계산합니다) · 마지막에 내 모델 주소가 나옵니다"""),
    ("code", """from google.colab import userdata
from connect_tycoon.hub import push_brain
from connect_tycoon.llm.hub import make_author

try:
    HF_TOKEN = userdata.get("HF_TOKEN")
except Exception:
    HF_TOKEN = None
assert HF_TOKEN, "왼쪽 🔑에 HF_TOKEN(Write 권한)을 넣고 노트북 액세스를 켜 주세요"

NAME = "jay"                                         #@param {type:"string"}
VERSION = "v1"                                       #@param {type:"string"}

# 나를 알리는 글 · 따옴표 사이에 자유롭게
ABOUT_ME = '''
'''

url = push_brain(BRAIN, version=VERSION, name=NAME, author=make_author(ABOUT_ME), token=HF_TOKEN)
print("올라갔습니다 ·", url)""", None),
]


if __name__ == "__main__":
    B.CELLS = CELLS
    print(B.build(os.path.join(os.path.dirname(__file__), "..", "notebooks", "upload_brain_colab.ipynb")))
