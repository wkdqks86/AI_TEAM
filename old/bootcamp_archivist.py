"""Bootcamp Archivist v1.1.

녹취 날짜와 커리큘럼을 기준으로 관련 강의/실습 자료의 범위를 좁힌 뒤,
Claude에 전달할 ``claude_input.md`` 파일을 만드는 명령줄 프로그램입니다.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# 사용자 환경 설정
# ---------------------------------------------------------------------------

TRANSCRIPTS_DIR = Path(
    r"C:\Users\Peter\AppData\Local\LectureNotes\transcripts"
)
COURSE_ROOT = Path(r"C:\dev\course")
STUDY_ROOT = Path(r"C:\dev\study")
OUTPUT_FILE = Path("claude_input.md")

DATE_FORMAT = "%Y%m%d"
SEARCH_WINDOW_DAYS = 1
MAX_FILE_SIZE = 20 * 1024 * 1024  # 개별 자료 파일 최대 크기: 20MB
MAX_OUTPUT_SIZE = 10 * 1024 * 1024  # 최종 Markdown 최대 크기: 10MB
CSV_MAX_LINES = 100

ALLOWED_EXTENSIONS = {".txt", ".md", ".py", ".ipynb", ".csv"}
EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".ipynb_checkpoints",
    ".trash-0",
}


# 날짜별 과목과 세부 주제입니다.
# 새 일정이 생기면 같은 형식으로 한 줄씩 추가하면 됩니다.
CURRICULUM: dict[str, tuple[str, str]] = {
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


# 과목명과 실제 폴더 이름이 다를 수 있으므로 가능한 이름을 모아 둡니다.
FOLDER_KEYWORDS: dict[str, list[str]] = {
    "LLM": ["llm", "nlp", "language", "natural"],
    "딥러닝": ["deep_learning", "deep learning", "dl"],
    "머신러닝": ["machine_learning", "machine learning", "ml"],
    "데이터 분석": ["data_analysis", "data analysis"],
}


def is_raw_transcript(file: Path) -> bool:
    """파일 이름에 ``_raw``가 있으면 원본 녹취로 판단합니다."""

    return "_raw" in file.stem.casefold()


def extract_valid_date(file: Path) -> str | None:
    """``YYYYMMDD_이름.txt``에서 유효한 날짜 부분만 꺼냅니다."""

    date_text = file.stem.split("_", maxsplit=1)[0]

    try:
        datetime.strptime(date_text, DATE_FORMAT)
    except ValueError:
        return None

    return date_text


def find_transcript_dates(transcripts_dir: Path) -> list[str]:
    """raw 파일을 제외하고 정리할 수 있는 녹취 날짜를 찾습니다."""

    dates: set[str] = set()

    for file in transcripts_dir.glob("*.txt"):
        if is_raw_transcript(file):
            continue

        date_text = extract_valid_date(file)
        if date_text is not None:
            dates.add(date_text)

    return sorted(dates)


def choose_numbered_item(items: list[str], prompt: str) -> str:
    """번호 입력이 올바를 때까지 다시 묻고 선택한 항목을 돌려줍니다."""

    while True:
        choice = input(prompt).strip()

        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(items):
                return items[index]

        print(f"1부터 {len(items)} 사이의 번호를 입력해 주세요.")


def choose_transcript_date(dates: list[str]) -> str:
    """정리할 녹취 날짜를 사용자에게 선택받습니다."""

    print("\n정리할 날짜를 선택하세요.")
    for index, date_text in enumerate(dates, start=1):
        print(f"{index}. {date_text}")

    return choose_numbered_item(dates, "선택: ")


def get_curriculum(date_text: str) -> tuple[str, str] | None:
    """선택 날짜의 ``(과목, 세부 주제)``를 조회합니다."""

    return CURRICULUM.get(date_text)


def normalize_name(value: str) -> str:
    """폴더 이름 비교를 위해 구분 문자를 공백으로 통일합니다."""

    normalized = value.casefold()
    for separator in ("_", "-", "."):
        normalized = normalized.replace(separator, " ")
    return " ".join(normalized.split())


def folder_match_score(folder_name: str, keywords: list[str]) -> int:
    """폴더 이름이 키워드와 얼마나 잘 맞는지 점수로 계산합니다."""

    normalized_name = normalize_name(folder_name)
    name_words = set(normalized_name.split())
    best_score = 0

    for keyword in keywords:
        normalized_keyword = normalize_name(keyword)

        if normalized_name == normalized_keyword:
            score = 100
        elif normalized_keyword in name_words:
            score = 80
        elif len(normalized_keyword) > 2 and normalized_keyword in normalized_name:
            # dl, ml처럼 짧은 글자는 다른 단어에 우연히 포함될 수 있어
            # 부분 문자열 비교를 하지 않습니다.
            score = 50
        else:
            score = 0

        best_score = max(best_score, score)

    return best_score


def find_matching_folder(root: Path, subject: str) -> Path | None:
    """과목명과 키워드를 비교해 가장 점수가 높은 폴더를 찾습니다."""

    keywords = [subject, *FOLDER_KEYWORDS.get(subject, [])]
    matches: list[tuple[int, Path]] = []

    for folder in root.iterdir():
        if not folder.is_dir():
            continue

        score = folder_match_score(folder.name, keywords)
        if score > 0:
            matches.append((score, folder))

    if not matches:
        return None

    # 점수가 같으면 이름순으로 선택하여 실행할 때마다 결과가 같게 합니다.
    matches.sort(key=lambda item: (-item[0], item[1].name.casefold()))
    return matches[0][1]


def select_folder_from_root(root: Path, title: str) -> Path:
    """자동 매칭 실패 시 root 바로 아래 폴더 중 하나를 선택합니다."""

    folders = sorted(
        (folder for folder in root.iterdir() if folder.is_dir()),
        key=lambda folder: folder.name.casefold(),
    )

    if not folders:
        print(f"{title} 하위 폴더가 없어 root 폴더를 그대로 사용합니다: {root}")
        return root

    print(f"\n{title} 폴더를 자동으로 찾지 못했습니다.")
    print("아래 목록에서 사용할 폴더를 선택하세요.")
    for index, folder in enumerate(folders, start=1):
        print(f"{index}. {folder.name}")

    choices = [str(folder) for folder in folders]
    selected = choose_numbered_item(choices, "선택: ")
    return Path(selected)


def resolve_material_folder(root: Path, subject: str, title: str) -> Path:
    """먼저 자동 매칭하고, 실패한 경우에만 사용자에게 선택받습니다."""

    matched_folder = find_matching_folder(root, subject)

    if matched_folder is not None:
        print(f"{title} 자동 선택: {matched_folder}")
        return matched_folder

    return select_folder_from_root(root, title)


def has_excluded_directory(file: Path, search_root: Path) -> bool:
    """검색 root 아래 상대 경로에 제외 폴더가 있는지 확인합니다."""

    relative_parts = file.relative_to(search_root).parts[:-1]
    return any(part.casefold() in EXCLUDED_DIRS for part in relative_parts)


def find_recent_files(
    folder: Path,
    selected_date: str,
    window_days: int = SEARCH_WINDOW_DAYS,
) -> list[Path]:
    """선택 날짜 전후 ``window_days`` 안에 수정된 자료를 재귀 검색합니다."""

    target_date = datetime.strptime(selected_date, DATE_FORMAT)
    start_time = target_date - timedelta(days=window_days)
    # 마지막 날짜의 23:59:59까지 포함하기 위해 다음 날 00:00을 경계로 둡니다.
    end_time = target_date + timedelta(days=window_days + 1)
    candidates: list[tuple[float, Path]] = []

    for file in folder.rglob("*"):
        if not file.is_file():
            continue
        if has_excluded_directory(file, folder):
            continue
        if file.suffix.casefold() not in ALLOWED_EXTENSIONS:
            continue

        try:
            file_stat = file.stat()
        except OSError as error:
            print(f"파일 정보를 읽지 못해 건너뜀: {file} ({error})")
            continue

        if file_stat.st_size > MAX_FILE_SIZE:
            size_mb = file_stat.st_size / 1024 / 1024
            print(f"20MB 초과 파일 제외: {file} ({size_mb:.1f}MB)")
            continue

        modified_time = datetime.fromtimestamp(file_stat.st_mtime)
        if start_time <= modified_time < end_time:
            candidates.append((file_stat.st_mtime, file))

    candidates.sort(
        key=lambda item: (-item[0], str(item[1]).casefold())
    )
    return [file for _, file in candidates]


def choose_candidate_files(
    files: list[Path],
    root_folder: Path,
    title: str,
) -> list[Path]:
    """Enter=전체, 쉼표 번호=일부, n=없음 방식으로 자료를 확인합니다."""

    if not files:
        print(f"\n{title}: 선택 날짜 전후 ±{SEARCH_WINDOW_DAYS}일 후보가 없습니다.")
        return []

    print(f"\n{title} 후보")
    for index, file in enumerate(files, start=1):
        modified_time = datetime.fromtimestamp(file.stat().st_mtime)
        relative_path = file.relative_to(root_folder)
        print(
            f"{index}. {relative_path} "
            f"(수정: {modified_time:%Y-%m-%d %H:%M})"
        )

    print("\nEnter: 전체 사용 / 쉼표 숫자: 일부 선택 / n: 사용 안 함")

    while True:
        choice = input("선택 [Enter=전체]: ").strip().casefold()

        if choice == "":
            return files
        if choice == "n":
            return []

        selected_indices: list[int] = []
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

            if index not in selected_indices:
                selected_indices.append(index)

        if is_valid and selected_indices:
            return [files[index] for index in selected_indices]

        print("예: Enter, 1,3,5 또는 n 중 하나를 입력해 주세요.")


def read_notebook_content(file: Path) -> str:
    """Jupyter Notebook에서 markdown/code 셀의 내용만 추출합니다."""

    try:
        notebook = json.loads(file.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError as error:
        print(f"노트북 JSON 오류로 건너뜀: {file} ({error})")
        return ""
    except OSError as error:
        print(f"노트북을 읽지 못해 건너뜀: {file} ({error})")
        return ""

    parts: list[str] = []

    for cell in notebook.get("cells", []):
        cell_type = cell.get("cell_type")
        source_value = cell.get("source", [])

        if isinstance(source_value, list):
            source = "".join(str(line) for line in source_value)
        else:
            source = str(source_value)

        if cell_type == "markdown":
            parts.append(source)
        elif cell_type == "code":
            parts.append(f"```python\n{source}\n```")

    return "\n\n".join(parts)


def read_file_content(file: Path) -> str:
    """선택된 파일을 Claude에게 전달하기 좋은 텍스트로 읽습니다."""

    suffix = file.suffix.casefold()

    if suffix == ".ipynb":
        return read_notebook_content(file)

    try:
        content = file.read_text(encoding="utf-8", errors="ignore")
    except OSError as error:
        print(f"파일을 읽지 못해 건너뜀: {file} ({error})")
        return ""

    if suffix == ".csv":
        # 큰 CSV가 문서 대부분을 차지하지 않도록 미리보기만 포함합니다.
        return "\n".join(content.splitlines()[:CSV_MAX_LINES])

    return content


def collect_materials(files: list[Path], root_folder: Path) -> str:
    """최종 선택된 자료만 읽어 하나의 Markdown 문자열로 합칩니다."""

    sections: list[str] = []

    for file in files:
        content = read_file_content(file)
        if not content.strip():
            continue

        relative_path = file.relative_to(root_folder)
        sections.append(f"### {relative_path}\n\n{content.strip()}")

    if not sections:
        return "(선택한 자료 없음)"

    return "\n\n".join(sections)


def find_lecture_files(transcripts_dir: Path, selected_date: str) -> list[Path]:
    """선택 날짜의 녹취 파일을 찾되 raw 파일은 제외합니다."""

    return sorted(
        file
        for file in transcripts_dir.glob(f"{selected_date}_*.txt")
        if not is_raw_transcript(file)
    )


def collect_transcripts(lecture_files: list[Path]) -> str:
    """선택 날짜의 녹취 파일을 Markdown 섹션으로 합칩니다."""

    sections: list[str] = []

    for file in lecture_files:
        try:
            content = file.read_text(encoding="utf-8", errors="ignore")
        except OSError as error:
            print(f"녹취록을 읽지 못해 건너뜀: {file} ({error})")
            continue

        sections.append(f"### {file.name}\n\n{content.strip()}")

    return "\n\n".join(sections)


def build_claude_input(
    selected_date: str,
    subject: str,
    topic: str,
    course_folder: Path,
    study_folder: Path,
    transcript_text: str,
    course_materials: str,
    study_materials: str,
) -> str:
    """녹취록, 커리큘럼, 관련 자료를 최종 Markdown으로 조립합니다."""

    return f"""# 강의 정리 요청

## 날짜

{selected_date}

## 커리큘럼

- 과목: {subject}
- 세부 주제: {topic}

## 강의자료 폴더

{course_folder}

## 실습/개인노트 폴더

{study_folder}

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


def save_output(content: str, output_file: Path) -> bool:
    """10MB를 넘지 않을 때만 결과를 저장하고 성공 여부를 반환합니다."""

    output_size = len(content.encode("utf-8"))

    if output_size > MAX_OUTPUT_SIZE:
        size_mb = output_size / 1024 / 1024
        print(f"\n저장 중단: 최종 파일 크기가 {size_mb:.2f}MB입니다.")
        print("10MB 이하가 되도록 선택한 자료 수를 줄여 주세요.")
        return False

    try:
        output_file.write_text(content, encoding="utf-8")
    except OSError as error:
        print(f"\n파일 저장 실패: {output_file} ({error})")
        return False

    print(f"\n생성 완료: {output_file.resolve()}")
    print(f"파일 크기: {output_size / 1024 / 1024:.2f}MB")
    return True


def validate_required_directories(directories: list[Path]) -> bool:
    """실행에 필요한 폴더가 모두 존재하는지 먼저 확인합니다."""

    missing_directories = [path for path in directories if not path.is_dir()]

    if not missing_directories:
        return True

    print("다음 필수 폴더를 찾지 못했습니다.")
    for directory in missing_directories:
        print(f"- {directory}")
    print("파일 위쪽의 경로 설정을 현재 컴퓨터 환경에 맞게 수정해 주세요.")
    return False


def main() -> None:
    """Bootcamp Archivist v1.1의 전체 실행 순서를 관리합니다."""

    print("=== Bootcamp Archivist v1.1 ===")

    if not validate_required_directories(
        [TRANSCRIPTS_DIR, COURSE_ROOT, STUDY_ROOT]
    ):
        return

    # 1. raw 파일을 뺀 녹취 날짜 중 하나를 먼저 선택합니다.
    transcript_dates = find_transcript_dates(TRANSCRIPTS_DIR)
    if not transcript_dates:
        print("정리할 수 있는 녹취 날짜가 없습니다.")
        return

    selected_date = choose_transcript_date(transcript_dates)

    # 2. 날짜가 정해진 뒤에 커리큘럼을 조회해야 selected_date 오류가 없습니다.
    curriculum = get_curriculum(selected_date)
    if curriculum is None:
        print(f"\n{selected_date}의 커리큘럼 정보를 찾지 못했습니다.")
        print("CURRICULUM에 해당 날짜를 추가한 뒤 다시 실행해 주세요.")
        return

    subject, topic = curriculum
    print("\n커리큘럼")
    print(f"- 과목: {subject}")
    print(f"- 세부 주제: {topic}")

    # 3. 과목명으로 자동 매칭하고 실패한 root만 사용자에게 선택받습니다.
    print("\n관련 폴더를 찾는 중...")
    course_folder = resolve_material_folder(COURSE_ROOT, subject, "강의자료")
    study_folder = resolve_material_folder(STUDY_ROOT, subject, "실습/개인노트")

    # 4. 아직 내용은 읽지 않고, 날짜/확장자/크기 조건에 맞는 경로만 찾습니다.
    course_candidates = find_recent_files(course_folder, selected_date)
    study_candidates = find_recent_files(study_folder, selected_date)

    # 5. Enter를 누르면 후보 전체를 기본값으로 사용합니다.
    selected_course_files = choose_candidate_files(
        course_candidates,
        course_folder,
        "강의자료",
    )
    selected_study_files = choose_candidate_files(
        study_candidates,
        study_folder,
        "실습/개인노트",
    )

    # 6. 이 시점부터 사용자가 확정한 파일만 실제로 읽습니다.
    lecture_files = find_lecture_files(TRANSCRIPTS_DIR, selected_date)
    transcript_text = collect_transcripts(lecture_files)
    course_materials = collect_materials(selected_course_files, course_folder)
    study_materials = collect_materials(selected_study_files, study_folder)

    # 7. 모든 내용을 합치고, 10MB 안전장치를 통과할 때만 저장합니다.
    claude_input = build_claude_input(
        selected_date=selected_date,
        subject=subject,
        topic=topic,
        course_folder=course_folder,
        study_folder=study_folder,
        transcript_text=transcript_text,
        course_materials=course_materials,
        study_materials=study_materials,
    )
    save_output(claude_input, OUTPUT_FILE)


if __name__ == "__main__":
    main()
