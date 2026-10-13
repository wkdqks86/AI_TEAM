"""Bootcamp Archivist v1.9

녹취 날짜를 선택하면 커리큘럼과 폴더 매핑을 기준으로
관련 강의/실습 자료를 찾고 Claude 입력용 Markdown을 만듭니다.
"""

from datetime import datetime, timedelta
from pathlib import Path
import json
import re


# ------------------------------------------------------------
# 사용자 환경 설정
# ------------------------------------------------------------

TRANSCRIPTS_DIR = Path(
    r"C:\Users\Peter\AppData\Local\LectureNotes\transcripts"
)
COURSE_ROOT = Path(r"C:\dev\course")
STUDY_ROOT = Path(r"C:\dev\study")
OUTPUT_DIR = Path("output")

SEARCH_WINDOW_DAYS = 1
MAX_FILE_SIZE = 20 * 1024 * 1024       # 개별 파일 20MB
MAX_OUTPUT_SIZE = 10 * 1024 * 1024     # 최종 파일 10MB
CSV_MAX_LINES = 100


CLAUDE_HANDOFF = """## Claude Desktop 전달 안내

이 파일만으로 Notion 정리 규칙 전체를 대체하지 않는다.

Claude Desktop에 아래 파일을 함께 전달한다.

### 필수
1. `NOTION_정리_규칙.md`
2. 이 `claude_input_YYYYMMDD.md`

### 권장
3. `claude_notion_knowledge_manager_v1.md`

### 필요할 때만
4. `NOTION_정리_기준서.md`

우선순위:
`NOTION_정리_규칙.md`
→ `claude_notion_knowledge_manager_v1.md`
→ 해당 날짜 `claude_input`
→ 판단 근거가 필요할 때 `NOTION_정리_기준서.md`

`NOTION_정리_기준서.md`는 매번 전부 읽는 규칙 문서가 아니라
기존 판단의 배경과 예외 사례가 필요할 때 참고하는 작업 일지다.

최종 결과는 다음을 분리해서 작성한다.

### 실제 수업 범위 판정 규칙
- 날짜별 정리 범위는 **녹취록을 최우선 기준**으로 판단한다.
- 강의자료와 실습/개인노트는 녹취 내용을 보완·검증하기 위한 근거 자료다.
- 강의자료에 다음 진도 내용이 포함되어 있어도, **녹취에서 실제로 다루지 않은 내용은 날짜별 기술 페이지에 포함하지 않는다.**
- 녹취에서 설명이 짧더라도 실제 코드 실행, 실습 흔적, 화면 결과가 확인되면 포함할 수 있다.
- 녹취와 강의자료의 범위가 다르면 커리큘럼보다 **실제 녹취된 수업 진도**를 우선한다.
- 커리큘럼은 자료 후보를 찾는 기준일 뿐, 실제 수업 범위를 확정하는 기준이 아니다.
- 실제 수업에서 다루지 않은 후속 내용은 필요하면 "다음 진도 후보"로만 구분하고 본문 정리에는 섞지 않는다.

A. 날짜별 기술 페이지 본문
B. DB 속성
C. 커리어 허브 반영분
D. 상시 참고 페이지 반영분
E. 관련 노트 후보
F. 녹취 커버리지 검증 결과
G. 작업 일지 기록
"""

ALLOWED_EXTENSIONS = {".txt", ".md", ".py", ".ipynb", ".csv"}
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".ipynb_checkpoints",
    ".trash-0",
}


def is_exit_choice(choice: str) -> bool:
    """대화형 선택에서 종료 명령인지 확인합니다."""
    return choice.strip().lower() in {"q", "quit", "exit"}


# ------------------------------------------------------------
# 커리큘럼
# ------------------------------------------------------------

CURRICULUM = {
    "20261001": ("LLM", "자연어 데이터 준비"),
    "20261002": ("LLM", "자연어 데이터 준비"),

    "20261006": ("LLM", "자연어 딥러닝"),
    "20261007": ("LLM", "자연어 딥러닝"),
    "20261008": ("LLM", "자연어 딥러닝"),
    "20261012": ("LLM", "자연어 딥러닝"),
    "20261013": ("LLM", "자연어 딥러닝"),

    "20261014": ("LLM", "LLM"),
    "20261015": ("LLM", "LLM"),
    "20261016": ("LLM", "LLM"),

    "20261019": ("LLM", "프롬프트 엔지니어링"),
    "20261020": ("LLM", "프롬프트 엔지니어링"),
    "20261021": ("LLM", "프롬프트 엔지니어링"),
    "20261022": ("LLM", "프롬프트 엔지니어링"),
    "20261023": ("LLM", "프롬프트 엔지니어링"),
    "20261026": ("LLM", "프롬프트 엔지니어링"),
    "20261027": ("LLM", "프롬프트 엔지니어링"),
    "20261028": ("LLM", "프롬프트 엔지니어링"),
    "20261029": ("LLM", "프롬프트 엔지니어링"),
    "20261030": ("LLM", "프롬프트 엔지니어링"),

    "20261102": ("LLM", "파인튜닝"),
    "20261103": ("LLM", "파인튜닝"),
    "20261104": ("LLM", "파인튜닝"),
    "20261105": ("LLM", "파인튜닝"),

    "20261106": ("LLM", "자연어-이미지 멀티모달"),
    "20261109": ("LLM", "자연어-이미지 멀티모달"),
    "20261110": ("LLM", "자연어-이미지 멀티모달"),

    "20261111": ("LLM", "단위 프로젝트"),
    "20261112": ("LLM", "단위 프로젝트"),
}


# ------------------------------------------------------------
# 과목 ↔ 실제 폴더 매핑
# ------------------------------------------------------------
# 현재 실제 폴더 구조를 기준으로 둡니다.
# 폴더가 바뀌면 여기만 수정하면 됩니다.

SUBJECT_FOLDERS = {
    "LLM": {
        "course": "course_Deep_Learning",
        "study": "dl",
    },
    "딥러닝": {
        "course": "course_Deep_Learning",
        "study": "dl",
    },
    "머신러닝": {
        "course": "course_Machine_Learning",
        "study": "ml",
    },
    "데이터 분석": {
        "course": "course_Data_Analysis",
        "study": "data analysis",
    },
}


TOPIC_KEYWORDS = {
    "자연어 데이터 준비": [
        "nlp",
        "text",
        "token",
        "tokenizer",
        "vocab",
        "vocabulary",
        "padding",
        "embedding",
        "sentiment",
        "cnn 1d",
        "natural language",
    ],
    "자연어 딥러닝": [
        "nlp",
        "rnn",
        "lstm",
        "gru",
        "cnn 1d",
        "embedding",
        "sequence",
        "attention",
        "transformer",
    ],
    "LLM": [
        "llm",
        "transformer",
        "attention",
        "language model",
        "huggingface",
        "tokenizer",
    ],
    "프롬프트 엔지니어링": [
        "prompt",
        "prompt engineering",
        "few shot",
        "few-shot",
        "zero shot",
        "zero-shot",
        "chain of thought",
    ],
    "파인튜닝": [
        "fine tuning",
        "fine-tuning",
        "finetuning",
        "peft",
        "lora",
        "qlora",
        "trainer",
    ],
    "자연어-이미지 멀티모달": [
        "multimodal",
        "multi modal",
        "vision language",
        "vlm",
        "clip",
        "image text",
    ],
    "단위 프로젝트": [
        "project",
        "mini project",
        "unit project",
    ],
}


def choose_transcript_date() -> str:
    """raw 파일을 제외한 녹취 날짜를 보여주고 하나를 선택합니다."""

    dates = set()

    for file in TRANSCRIPTS_DIR.glob("*.txt"):
        if "_raw" in file.stem.lower():
            continue

        date_text = file.stem.split("_", 1)[0]

        try:
            datetime.strptime(date_text, "%Y%m%d")
        except ValueError:
            continue

        dates.add(date_text)

    sorted_dates = sorted(dates)

    if not sorted_dates:
        raise RuntimeError("정리할 수 있는 녹취 날짜가 없습니다.")

    print("\n정리할 날짜를 선택하세요.")

    for index, date_text in enumerate(sorted_dates, start=1):
        print(f"{index}. {date_text}")

    print("q. 종료")

    while True:
        choice = input("선택: ").strip()

        if is_exit_choice(choice):
            raise SystemExit

        if choice.isdigit():
            index = int(choice) - 1

            if 0 <= index < len(sorted_dates):
                return sorted_dates[index]

        print(f"1부터 {len(sorted_dates)} 사이의 번호 또는 q를 입력해 주세요.")

def choose_folder(root: Path, title: str) -> Path:
    """폴더를 직접 선택합니다."""

    folders = sorted(
        [folder for folder in root.iterdir() if folder.is_dir()],
        key=lambda folder: folder.name.lower(),
    )

    if not folders:
        return root

    print(f"\n{title} 폴더를 선택하세요.")

    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder.name}")

    print("q. 종료")

    while True:
        choice = input("선택: ").strip()

        if is_exit_choice(choice):
            raise SystemExit

        if choice.isdigit():
            index = int(choice) - 1

            if 0 <= index < len(folders):
                return folders[index]

        print(f"1부터 {len(folders)} 사이의 번호 또는 q를 입력해 주세요.")

def get_material_folder(
    root: Path,
    subject: str,
    folder_type: str,
    title: str,
) -> Path:
    """과목 매핑으로 폴더를 찾고, 없으면 직접 선택합니다."""

    folder_name = SUBJECT_FOLDERS.get(subject, {}).get(folder_type)

    if folder_name:
        folder = root / folder_name

        if folder.is_dir():
            print(f"{title} 자동 선택: {folder}")
            return folder

    print(f"{title} 자동 선택 실패")
    return choose_folder(root, title)



def find_course_files(
    folder: Path,
    subject: str,
    topic: str,
    limit: int = 20,
) -> list[Path]:
    """수정일이 아니라 주제/경로 키워드로 강의자료 후보를 찾습니다."""

    keywords = [subject, topic, *TOPIC_KEYWORDS.get(topic, [])]
    keywords = [keyword.lower() for keyword in keywords]

    scored_files = []
    fallback_files = []

    for file in folder.rglob("*"):
        if not file.is_file():
            continue

        relative_parts = [
            part.lower()
            for part in file.relative_to(folder).parts[:-1]
        ]

        if any(part in EXCLUDED_DIRS for part in relative_parts):
            continue

        if file.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        try:
            file_stat = file.stat()
        except OSError:
            print(f"파일 정보 확인 실패: {file}")
            continue

        if file_stat.st_size > MAX_FILE_SIZE:
            print(f"20MB 초과 파일 제외: {file}")
            continue

        fallback_files.append(
            (file_stat.st_mtime, file)
        )

        relative_path = str(
            file.relative_to(folder)
        ).lower()

        score = 0

        for keyword in keywords:
            if keyword in relative_path:
                score += 1

        if score > 0:
            scored_files.append(
                (score, file_stat.st_mtime, file)
            )

    if scored_files:
        scored_files.sort(
            key=lambda item: (
                -item[0],
                -item[1],
                str(item[2]).lower(),
            )
        )
        return [
            file
            for _, _, file in scored_files[:limit]
        ]

    fallback_files.sort(
        key=lambda item: (
            -item[0],
            str(item[1]).lower(),
        )
    )

    return [
        file
        for _, file in fallback_files[:limit]
    ]


def find_recent_files(folder: Path, selected_date: str) -> list[Path]:
    """선택 날짜 전후에 수정된 관련 자료 파일을 찾습니다."""

    target_date = datetime.strptime(selected_date, "%Y%m%d")
    start_time = target_date - timedelta(days=SEARCH_WINDOW_DAYS)
    end_time = target_date + timedelta(days=SEARCH_WINDOW_DAYS + 1)

    files = []

    for file in folder.rglob("*"):
        if not file.is_file():
            continue

        relative_parts = [
            part.lower()
            for part in file.relative_to(folder).parts[:-1]
        ]

        if any(part in EXCLUDED_DIRS for part in relative_parts):
            continue

        if file.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        try:
            file_stat = file.stat()
        except OSError:
            print(f"파일 정보 확인 실패: {file}")
            continue

        if file_stat.st_size > MAX_FILE_SIZE:
            print(f"20MB 초과 파일 제외: {file}")
            continue

        modified_time = datetime.fromtimestamp(file_stat.st_mtime)

        if start_time <= modified_time < end_time:
            files.append(file)

    return sorted(
        files,
        key=lambda file: file.stat().st_mtime,
        reverse=True,
    )


def choose_files(
    files: list[Path],
    root: Path,
    title: str,
) -> list[Path]:
    """Enter=전체, 번호=일부, n=사용 안 함, q=종료."""

    if not files:
        print(f"\n{title}: 날짜 기준 후보 파일이 없습니다.")
        return []

    print(f"\n{title} 후보")

    for index, file in enumerate(files, start=1):
        modified_time = datetime.fromtimestamp(file.stat().st_mtime)
        relative_path = file.relative_to(root)

        print(
            f"{index}. {relative_path} "
            f"(수정: {modified_time:%Y-%m-%d %H:%M})"
        )

    print("\nEnter: 전체 사용 / 예: 1,3 / n: 사용 안 함 / q: 종료")

    while True:
        choice = input("선택 [Enter=전체]: ").strip().lower()

        if is_exit_choice(choice):
            raise SystemExit

        if choice == "":
            return files

        if choice == "n":
            return []

        selected = []
        is_valid = True

        for value in choice.split(","):
            value = value.strip()

            if not value.isdigit():
                is_valid = False
                break

            index = int(value) - 1

            if not 0 <= index < len(files):
                is_valid = False
                break

            if files[index] not in selected:
                selected.append(files[index])

        if is_valid and selected:
            return selected

        print("Enter, 1,3, n 또는 q 형식으로 입력해 주세요.")


def choose_course_files(
    initial_folder: Path,
    subject: str,
    topic: str,
) -> tuple[list[Path], list[Path]]:
    """
    강의자료를 하나 이상의 course 폴더에서 선택합니다.

    예:
    - 1~7교시: 커리큘럼 기준 폴더
    - 8교시: 진도가 빨라져 다른 강의 폴더

    첫 폴더에서 필요한 파일을 고른 뒤
    a를 눌러 다른 폴더의 자료를 추가할 수 있습니다.
    """

    selected_folders = []
    selected_files = []
    current_folder = initial_folder

    while True:
        candidates = find_course_files(
            current_folder,
            subject,
            topic,
        )

        print(f"\n현재 강의자료 폴더: {current_folder}")

        if not candidates:
            print("강의자료 후보가 없습니다.")
        else:
            print("\n강의자료 후보")

            for index, file in enumerate(candidates, start=1):
                modified_time = datetime.fromtimestamp(file.stat().st_mtime)
                relative_path = file.relative_to(current_folder)

                print(
                    f"{index}. {relative_path} "
                    f"(수정: {modified_time:%Y-%m-%d %H:%M})"
                )

        print(
            "\nEnter: 전체 사용 / 예: 1,3 / n: 이 폴더 사용 안 함 "
            "/ a: 다른 강의자료 폴더도 추가 / q: 종료"
        )

        choice = input("선택 [Enter=전체]: ").strip().lower()

        if is_exit_choice(choice):
            raise SystemExit

        folder_files = []

        if choice == "":
            folder_files = candidates

        elif choice == "n":
            folder_files = []

        elif choice == "a":
            current_folder = choose_folder(
                COURSE_ROOT,
                "추가 강의자료",
            )
            continue

        else:
            is_valid = True

            for value in choice.split(","):
                value = value.strip()

                if not value.isdigit():
                    is_valid = False
                    break

                index = int(value) - 1

                if not 0 <= index < len(candidates):
                    is_valid = False
                    break

                file = candidates[index]

                if file not in folder_files:
                    folder_files.append(file)

            if not is_valid or not folder_files:
                print("Enter, 1,3, n, a 또는 q 형식으로 입력해 주세요.")
                continue

        if folder_files:
            if current_folder not in selected_folders:
                selected_folders.append(current_folder)

            for file in folder_files:
                if file not in selected_files:
                    selected_files.append(file)

        print()
        print("현재까지 선택한 강의자료:")

        if selected_files:
            for file in selected_files:
                print(f"- {file.relative_to(COURSE_ROOT)}")
        else:
            print("- 없음")

        while True:
            next_choice = input(
                "\nEnter: 선택 완료 / a: 다른 폴더 자료 추가 / q: 종료: "
            ).strip().lower()

            if is_exit_choice(next_choice):
                raise SystemExit

            if next_choice == "":
                return selected_folders, selected_files

            if next_choice == "a":
                current_folder = choose_folder(
                    COURSE_ROOT,
                    "추가 강의자료",
                )
                break

            print("Enter, a 또는 q를 입력해 주세요.")

def choose_study_files(
    initial_folder: Path,
    selected_date: str,
) -> tuple[list[Path], list[Path]]:
    """
    실습/개인노트를 하나 이상의 study 폴더에서 선택합니다.

    첫 폴더에서 필요한 파일을 고른 뒤
    a를 눌러 다른 폴더의 자료를 추가할 수 있습니다.
    """

    selected_folders = []
    selected_files = []
    current_folder = initial_folder

    while True:
        candidates = find_recent_files(
            current_folder,
            selected_date,
        )

        print(f"\n현재 실습/개인노트 폴더: {current_folder}")

        if not candidates:
            print("날짜 기준 후보 파일이 없습니다.")
        else:
            print("\n실습/개인노트 후보")

            for index, file in enumerate(candidates, start=1):
                modified_time = datetime.fromtimestamp(file.stat().st_mtime)
                relative_path = file.relative_to(current_folder)

                print(
                    f"{index}. {relative_path} "
                    f"(수정: {modified_time:%Y-%m-%d %H:%M})"
                )

        print(
            "\nEnter: 전체 사용 / 예: 1,3 / n: 이 폴더 사용 안 함 "
            "/ a: 다른 실습/개인노트 폴더도 추가 / q: 종료"
        )

        choice = input("선택 [Enter=전체]: ").strip().lower()

        if is_exit_choice(choice):
            raise SystemExit

        folder_files = []

        if choice == "":
            folder_files = candidates

        elif choice == "n":
            folder_files = []

        elif choice == "a":
            current_folder = choose_folder(
                STUDY_ROOT,
                "추가 실습/개인노트",
            )
            continue

        else:
            is_valid = True

            for value in choice.split(","):
                value = value.strip()

                if not value.isdigit():
                    is_valid = False
                    break

                index = int(value) - 1

                if not 0 <= index < len(candidates):
                    is_valid = False
                    break

                file = candidates[index]

                if file not in folder_files:
                    folder_files.append(file)

            if not is_valid or not folder_files:
                print("Enter, 1,3, n, a 또는 q 형식으로 입력해 주세요.")
                continue

        if folder_files:
            if current_folder not in selected_folders:
                selected_folders.append(current_folder)

            for file in folder_files:
                if file not in selected_files:
                    selected_files.append(file)

        print()
        print("현재까지 선택한 실습/개인노트:")

        if selected_files:
            for file in selected_files:
                print(f"- {file.relative_to(STUDY_ROOT)}")
        else:
            print("- 없음")

        while True:
            next_choice = input(
                "\nEnter: 선택 완료 / a: 다른 폴더 자료 추가 / q: 종료: "
            ).strip().lower()

            if is_exit_choice(next_choice):
                raise SystemExit

            if next_choice == "":
                return selected_folders, selected_files

            if next_choice == "a":
                current_folder = choose_folder(
                    STUDY_ROOT,
                    "추가 실습/개인노트",
                )
                break

            print("Enter, a 또는 q를 입력해 주세요.")

def remove_base64_images(text: str) -> str:
    """Notebook Markdown의 base64 이미지 데이터는 Claude 입력에서 제거합니다."""

    pattern = r'!\[([^\]]*)\]\(data:image/[^;]+;base64,[^)]+\)'

    def replace_image(match):
        alt_text = match.group(1).strip()
        image_name = alt_text if alt_text else "이미지"
        return f"[노트북 이미지 생략: {image_name}]"

    return re.sub(
        pattern,
        replace_image,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def read_file(file: Path) -> str:
    """Claude 입력용 텍스트로 파일 내용을 읽습니다."""

    if file.suffix.lower() == ".ipynb":
        try:
            notebook = json.loads(
                file.read_text(encoding="utf-8", errors="ignore")
            )
        except (json.JSONDecodeError, OSError):
            print(f"노트북 읽기 실패: {file}")
            return ""

        parts = []

        for cell in notebook.get("cells", []):
            source = "".join(cell.get("source", []))

            if cell.get("cell_type") == "markdown":
                source = remove_base64_images(source)
                parts.append(source)

            elif cell.get("cell_type") == "code":
                parts.append(f"```python\n{source}\n```")

        return "\n\n".join(parts)

    try:
        content = file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        print(f"파일 읽기 실패: {file}")
        return ""

    if file.suffix.lower() == ".csv":
        return "\n".join(content.splitlines()[:CSV_MAX_LINES])

    return content


def collect_files(files: list[Path], root: Path) -> str:
    """선택한 자료 파일을 Markdown으로 합칩니다."""

    sections = []

    for file in files:
        content = read_file(file)

        if not content.strip():
            continue

        relative_path = file.relative_to(root)
        sections.append(
            f"### {relative_path}\n\n{content.strip()}"
        )

    return "\n\n".join(sections) if sections else "(선택한 자료 없음)"


def collect_transcripts(selected_date: str) -> str:
    """선택한 날짜의 일반 txt 녹취만 합칩니다."""

    sections = []

    for file in sorted(
        TRANSCRIPTS_DIR.glob(f"{selected_date}_*.txt")
    ):
        if "_raw" in file.stem.lower():
            continue

        try:
            content = file.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            print(f"녹취록 읽기 실패: {file}")
            continue

        sections.append(
            f"### {file.name}\n\n{content.strip()}"
        )

    return "\n\n".join(sections)


def main() -> None:
    print("=== Bootcamp Archivist v1.9 ===")

    # 1. 필수 폴더 확인
    for directory in [TRANSCRIPTS_DIR, COURSE_ROOT, STUDY_ROOT]:
        if not directory.is_dir():
            print(f"폴더를 찾지 못했습니다: {directory}")
            return

    # 2. 녹취 날짜 선택
    try:
        selected_date = choose_transcript_date()
    except RuntimeError as error:
        print(error)
        return

    # 3. 커리큘럼 확인
    curriculum = CURRICULUM.get(selected_date)

    if curriculum is None:
        print(f"{selected_date}의 커리큘럼 정보가 없습니다.")
        return

    subject, topic = curriculum

    print("\n커리큘럼")
    print(f"- 과목: {subject}")
    print(f"- 세부 주제: {topic}")

    # 4. 과목에 맞는 폴더 결정
    print("\n관련 폴더를 찾는 중...")

    course_folder = get_material_folder(
        COURSE_ROOT,
        subject,
        "course",
        "강의자료",
    )

    study_folder = get_material_folder(
        STUDY_ROOT,
        subject,
        "study",
        "실습/개인노트",
    )

    # 5. 강의자료는 주제 기준, study는 수정일 기준으로 후보 찾기
    #    실제 진도가 커리큘럼보다 빠르면 강의자료 선택 화면에서
    #    다른 course 폴더로 이동할 수 있습니다.
    course_folders, course_files = choose_course_files(
        course_folder,
        subject,
        topic,
    )

    # 6. 실습/개인노트도 여러 study 폴더에서 누적 선택할 수 있습니다.
    study_folders, study_files = choose_study_files(
        study_folder,
        selected_date,
    )

    # 7. 필요한 파일만 읽기
    transcript_text = collect_transcripts(selected_date)
    course_materials = collect_files(
        course_files,
        COURSE_ROOT,
    )
    study_materials = collect_files(
        study_files,
        STUDY_ROOT,
    )

    # 8. Claude 입력 만들기
    claude_input = f"""# 강의 정리 요청

{CLAUDE_HANDOFF}

---

## 날짜

{selected_date}

## 커리큘럼

- 과목: {subject}
- 세부 주제: {topic}

## 강의자료 폴더

{chr(10).join(f"- {folder}" for folder in course_folders) if course_folders else "(선택한 강의자료 폴더 없음)"}

## 실습/개인노트 폴더

{chr(10).join(f"- {folder}" for folder in study_folders) if study_folders else "(선택한 실습/개인노트 폴더 없음)"}

---

## 녹취록

{transcript_text}

---

## 강의자료

{course_materials}

---

## 실습/개인노트

{study_materials}
"""

    # 9. 크기 확인 후 저장
    output_size = len(claude_input.encode("utf-8"))

    if output_size > MAX_OUTPUT_SIZE:
        size_mb = output_size / 1024 / 1024
        print(f"\n저장 중단: {size_mb:.2f}MB")
        print("선택한 자료 수를 줄여 주세요.")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = OUTPUT_DIR / f"claude_input_{selected_date}.md"

    try:
        output_file.write_text(
            claude_input,
            encoding="utf-8",
        )
    except OSError as error:
        print(f"파일 저장 실패: {error}")
        return

    print(f"\n생성 완료: {output_file.resolve()}")
    print(
        f"파일 크기: "
        f"{output_size / 1024 / 1024:.2f}MB"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n사용자가 작업을 취소했습니다.")
    except SystemExit:
        print("\nBootcamp Archivist를 종료합니다.")
