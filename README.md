# AI_TEAM — Bootcamp Archivist

부트캠프 수업의 **녹취록, 강의자료, 실습 노트**를 한데 모아 Claude가 검토할 수 있는 Markdown으로 만들고, 사용자가 승인한 내용만 Notion에 반영하도록 돕는 개인 학습 아카이브 도구입니다.

> 현재 핵심 버전: Bootcamp Archivist **v1.9** / Claude → Notion 승인 도구 **v0.3.4**

## 왜 만들었나요?

하루 수업 자료는 여러 위치에 흩어져 있고, 녹취에는 음성 인식 오류가 섞일 수 있습니다. 이 프로젝트는 자료를 자동으로 모으는 데서 끝나지 않고 다음 두 판단을 분리합니다.

- **오늘 어디까지 배웠는가?** → 녹취록을 우선해 실제 수업 범위를 판단합니다.
- **배운 내용이 정확히 무엇인가?** → 실행 코드, 실습 노트, 강의안을 대조해 검증합니다.

또한 AI가 제안한 내용을 Notion에 바로 쓰지 않고, 사용자가 `승인 / 보류 / 제외`를 결정하는 검토 단계를 둡니다.

## 전체 작업 흐름

```text
LectureNotes 녹취록 + 강의자료 + 실습 노트
                    ↓
          Bootcamp Archivist v1.9
                    ↓
       claude_input_YYYYMMDD.md 생성
                    ↓
             Claude가 자료 검수
                    ↓
      claude_output_YYYYMMDD.md 생성
                    ↓
       Claude → Notion 승인 도구 v0.3.4
                    ↓
       항목별 승인 / 보류 / 제외 결정
                    ↓
   *_approval.md + *_notion_preview.md 생성
                    ↓
       승인된 내용만 Claude가 Notion 반영
                    ↓
            실제 Notion 결과 확인
```

핵심 안전장치는 **AI가 만든 결과와 실제 Notion 반영 사이에 사람의 승인 단계를 두는 것**입니다.

## 주요 기능

### 1. Bootcamp Archivist v1.9

- LectureNotes 녹취 파일에서 정리할 날짜 선택
- 날짜별 커리큘럼과 과목 폴더 자동 연결
- 자동 연결 실패 시 폴더를 직접 선택하는 대체 흐름 제공
- 경로·주제 키워드로 강의자료 후보 검색
- 선택 날짜 전후의 실습/개인 노트 검색
- 여러 강의자료 및 실습 폴더에서 필요한 파일만 선택
- `.txt`, `.md`, `.py`, `.ipynb`, `.csv` 내용 수집
- Notebook의 Markdown/코드 셀 추출 및 Base64 이미지 제거
- 개별 파일 20MB, 최종 출력 10MB 제한
- Claude 전달 규칙과 자료 출처를 포함한 Markdown 생성

### 2. Claude → Notion 승인 도구 v0.3.4

- Claude 결과에서 A~G 섹션 자동 분리
- A 본문 승인 여부 확인
- B의 DB 속성과 신규 태그 후보를 각각 검토
- C/D/E/G 후보를 항목별로 `승인 / 보류 / 제외`
- F 커버리지 결과는 검수 전용으로 분리
- 기존 승인 파일을 다시 열어 보류 항목 검토 가능
- 승인 결과와 Notion 반영 미리보기를 별도 파일로 생성

## A~G 결과 블록

| 블록 | 의미 | 처리 원칙 |
|---|---|---|
| A | 날짜별 기술 페이지 본문 | 사용자 확인 후 반영 |
| B | DB 속성 | 속성·신규 태그별 세부 확인 |
| C | 커리어 허브 반영분 | 항목별 승인 필요 |
| D | 상시 참고 페이지 반영분 | 기존 페이지를 먼저 확인한 뒤 승인 |
| E | 관련 노트 후보 | 연결 방향까지 확인 후 승인 |
| F | 녹취 커버리지 검증 | 검수용이며 자동 반영하지 않음 |
| G | 작업 일지 기록 | 실제 새 규칙·예외만 승인 |

## 프로젝트 구조

```text
AI_TEAM/
├─ agents/
│  └─ claude_knowledge_manager_prompt_v1.md
├─ bootcamp_archvist/
│  ├─ bootcamp_archivist.py          # 자료 수집 및 Claude 입력 생성
│  ├─ config/
│  │  ├─ NOTION_정리_규칙.md          # 최상위 운영 규칙(Source of Truth)
│  │  ├─ NOTION_정리_기준서.md        # 판단 근거와 예외 기록
│  │  └─ claude_notion_knowledge_manager.md
│  ├─ output/                        # 로컬 생성 파일(Git 제외)
│  └─ tools/
│     ├─ claude_approval_tool.py     # 승인·미리보기 생성 도구
│     ├─ approval_output/            # 로컬 승인 결과(Git 제외)
│     └─ notion_preview_output/      # 로컬 미리보기(Git 제외)
├─ old/                              # 이전 Archivist 버전 보관
├─ peter_coding_style_v1.md          # 학습용 코드 작성 원칙
└─ pyproject.toml
```

현재 폴더명 `bootcamp_archvist`에는 `archivist`의 `i`가 하나 빠져 있지만, 기존 로컬 작업 경로와의 호환성을 위해 그대로 유지하고 있습니다.

## 실행 환경

- Windows 11 / PowerShell
- Python 3.13 이상
- 외부 Python 패키지 없음(표준 라이브러리만 사용)

### 1. 저장소 받기

```powershell
git clone https://github.com/wkdqks86/AI_TEAM.git
cd AI_TEAM
```

### 2. 가상환경 만들기

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

가상환경은 이 프로젝트만 사용하는 독립된 Python 작업 공간입니다. 현재는 외부 패키지가 없지만, 나중에 패키지가 추가되어도 컴퓨터 전체 환경과 섞이지 않게 해 줍니다.

## 사용 방법

### 1단계: 로컬 경로 확인

[`bootcamp_archivist.py`](bootcamp_archvist/bootcamp_archivist.py) 위쪽의 다음 값을 자신의 폴더 구조에 맞게 확인합니다.

```python
TRANSCRIPTS_DIR = Path(r"C:\Users\...\LectureNotes\transcripts")
COURSE_ROOT = Path(r"C:\dev\course")
STUDY_ROOT = Path(r"C:\dev\study")
```

이 값들은 각각 녹취록, 강의자료, 개인 실습 자료가 있는 시작 폴더입니다.

### 2단계: Claude 입력 파일 만들기

상대 경로로 지정된 `output` 폴더에 결과가 생기도록 프로그램 폴더에서 실행합니다.

```powershell
cd bootcamp_archvist
python bootcamp_archivist.py
```

화면 안내에 따라 날짜와 자료를 선택하면 다음 파일이 만들어집니다.

```text
output/claude_input_YYYYMMDD.md
```

### 3단계: Claude에서 검수 결과 만들기

Claude Desktop에 다음 파일을 함께 전달합니다.

1. `config/NOTION_정리_규칙.md`
2. 생성된 `output/claude_input_YYYYMMDD.md`
3. `config/claude_notion_knowledge_manager.md`
4. 판단 근거가 필요할 때만 `config/NOTION_정리_기준서.md`

규칙의 우선순위는 아래와 같습니다.

```text
NOTION_정리_규칙.md
→ claude_notion_knowledge_manager.md
→ 해당 날짜 claude_input
→ 필요할 때 NOTION_정리_기준서.md
```

### 4단계: Claude 결과 승인하기

Claude가 만든 `claude_output_YYYYMMDD.md`를 `bootcamp_archvist/output`에 저장한 뒤 실행합니다.

```powershell
cd tools
python claude_approval_tool.py
```

파일 경로 대신 `..\output` 폴더를 입력하면 그 안의 결과 목록에서 선택할 수 있습니다. 검토가 끝나면 다음 두 파일이 생성됩니다.

```text
approval_output/*_approval.md
notion_preview_output/*_notion_preview.md
```

### 5단계: 승인된 내용만 Notion에 반영

원본 Claude 결과가 아니라 `*_notion_preview.md`를 Claude에 전달합니다. Claude에는 다음 원칙을 함께 명시합니다.

> 승인된 항목만 실제 Notion에 반영하고, 보류·제외된 내용은 반영하지 않는다. B의 속성·신규 태그도 세부 승인 결과를 우선한다.

## 자료 보호와 Git 정책

이 저장소는 공개 저장소입니다. 다음 파일에는 전체 녹취, 로컬 경로, 수업 자료가 포함될 수 있어 `.gitignore`로 Git 업로드를 막습니다.

- `bootcamp_archvist/output/`
- `bootcamp_archvist/tools/approval_output/`
- `bootcamp_archvist/tools/notion_preview_output/`
- 도구 폴더에 임시 저장한 `claude_output_*_approval.md`, `claude_output_*_notion_preview*.md`

파일은 로컬에서 삭제되지 않습니다. 공유가 필요할 때는 개인정보·비밀값·저작권이 있는 수업 자료가 없는지 먼저 확인한 뒤 별도로 추가하세요.

## 현재 상태와 다음 개선 후보

- [x] Archivist v1.9 자료 수집 흐름
- [x] 실제 수업 범위와 내용 정확성 판단 기준 분리
- [x] 승인 도구 v0.3.4의 B 세부 승인
- [x] C/D/E/G 항목별 승인·보류·제외
- [x] 승인 결과와 Notion 미리보기 분리
- [ ] 사용자별 로컬 경로를 설정 파일이나 환경 변수로 분리
- [ ] 자동화 테스트 추가
- [ ] `bootcamp_archvist` 폴더명 오타를 안전하게 마이그레이션
- [ ] Claude/Notion 반영 완료 후 녹취 보관 절차 자동화

## 학습 포인트

이 프로젝트에서 살펴볼 수 있는 Python 개념은 다음과 같습니다.

- `pathlib.Path`: 운영체제 경로를 읽기 쉽게 다루기
- 함수 분리: 날짜 선택, 파일 검색, 내용 읽기처럼 역할별로 나누기
- 타입 힌트: 함수가 받는 값과 돌려주는 값을 명확히 표현하기
- 예외 처리: 파일이 없거나 JSON이 손상된 경우 안전하게 건너뛰기
- 정규식: Markdown 섹션과 승인 상태 찾기
- 상수: 파일 크기 제한처럼 바뀔 수 있는 값을 한곳에서 관리하기

처음 코드를 읽는다면 `main()`에서 시작해 호출되는 함수를 하나씩 따라가는 방법을 추천합니다. `main()`은 프로그램의 **목차**, 각 함수는 목차의 한 항목을 담당하는 **작은 작업자**라고 생각하면 이해하기 쉽습니다.
