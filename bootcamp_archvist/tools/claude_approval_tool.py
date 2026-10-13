from pathlib import Path
import re

DEFAULT_OUTPUT_DIR = Path("approval_output")
DEFAULT_PREVIEW_DIR = Path("notion_preview_output")


def read_markdown(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def split_sections(text: str) -> dict[str, str]:
    """Claude 결과의 A~G 블록을 분리합니다."""

    section_pattern = re.compile(
        r"(?m)^(#{1,4})\s*([A-G])(?:[.\s])+(.*)$"
    )
    summary_pattern = re.compile(
        r"(?m)^#{1,4}\s*요약\s*$"
    )

    matches = list(section_pattern.finditer(text))

    if not matches:
        return {}

    summary_match = summary_pattern.search(text)
    summary_start = summary_match.start() if summary_match else len(text)

    sections = {}

    for index, match in enumerate(matches):
        section_key = match.group(2)
        start = match.start()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = summary_start

        sections[section_key] = text[start:end].strip()

    return sections


def extract_summary(text: str) -> str:
    """A~G 뒤의 '# 요약' 섹션이 있으면 별도로 추출합니다."""

    summary_pattern = re.compile(
        r"(?m)^#{1,4}\s*요약\s*$"
    )

    match = summary_pattern.search(text)

    if not match:
        return ""

    return text[match.start():].strip()


def detect_material_status(text: str) -> str:
    """Claude 결과에서 자료 상태를 간단히 확인합니다."""

    if "중간 스냅샷" in text or "재검증 필요" in text:
        return "중간 스냅샷"

    if "최종 입력" in text:
        return "최종 입력"

    return "확인 필요"


def preview_section(label: str, content: str, page_chars: int = 1800):
    """내용을 생략하지 않고 페이지 단위로 끝까지 보여줍니다."""
    print()
    print("=" * 70)
    print(f"[{label}] 미리보기")
    print("=" * 70)

    if len(content) <= page_chars:
        print(content)
        return

    start = 0

    while start < len(content):
        end = min(start + page_chars, len(content))
        print(content[start:end])

        if end >= len(content):
            break

        print()
        answer = input("계속 보기 [Enter] / q 종료: ").strip().lower()

        if answer in {"q", "quit", "exit"}:
            raise SystemExit

        start = end

def ask_yes_no(message: str, default: bool = False) -> bool:
    while True:
        default_text = "Y/n" if default else "y/N"
        answer = input(f"{message} [{default_text}]: ").strip().lower()

        if not answer:
            return default

        if answer in {"y", "yes", "예", "ㅇ"}:
            return True

        if answer in {"n", "no", "아니오", "ㄴ"}:
            return False

        print("y 또는 n으로 입력해 주세요.")


def ask_decision(message: str) -> str:
    """승인/보류/제외/종료 중 하나를 받습니다."""
    while True:
        answer = input(
            f"{message} [y=승인 / s=보류 / n=제외 / q=종료]: "
        ).strip().lower()

        if answer in {"y", "yes", "예", "ㅇ"}:
            return "승인"
        if answer in {"s", "skip", "보류"}:
            return "보류"
        if answer in {"n", "no", "아니오", "ㄴ"}:
            return "제외"
        if answer in {"q", "quit", "exit"}:
            raise SystemExit

        print("y, s, n, q 중 하나를 입력해 주세요.")


def summarize_item_decisions(decisions: dict[str, str]) -> str:
    if not decisions:
        return "보류"

    values = set(decisions.values())

    if values == {"승인"}:
        return "승인"
    if "승인" in values:
        return "부분 승인"
    if "보류" in values:
        return "보류"
    return "제외"


def review_grouped_section(key: str, content: str) -> dict[str, str]:
    """C/D/G를 하위 항목별로 검토합니다."""
    prefix = key if key in {"C", "D"} else ""
    section_body = remove_first_heading(content)
    items = split_subsections(section_body, prefix)

    if not items:
        preview_section(key, content)
        return {key: ask_decision(f"{key} 블록을 어떻게 처리할까요?")}

    decisions = {}

    for title, body in items:
        preview_section(title, body)
        decisions[title] = ask_decision(f"{title} 항목을 어떻게 처리할까요?")

    return decisions


def review_e_section(content: str) -> dict[str, str]:
    """E 관련 노트를 연결별로 검토합니다."""
    rows = split_e_table_rows(content)

    if not rows:
        preview_section("E", content)
        return {"E": ask_decision("E 블록을 어떻게 처리할까요?")}

    decisions = {}

    for title, row in rows:
        preview_section(title, row)
        decisions[title] = ask_decision(f"{title} 연결을 어떻게 처리할까요?")

    return decisions


def approved_group_content(
    key: str,
    content: str,
    decisions: dict[str, str],
) -> str:
    prefix = key if key in {"C", "D"} else ""
    items = split_subsections(remove_first_heading(content), prefix)

    if not items:
        return content if decisions.get(key) == "승인" else ""

    approved = []

    for title, body in items:
        if decisions.get(title) == "승인":
            approved.append(body)

    return "\n\n".join(approved).strip()


def approved_e_content(
    content: str,
    decisions: dict[str, str],
) -> str:
    rows = split_e_table_rows(content)

    if not rows:
        return content if decisions.get("E") == "승인" else ""

    approved = [
        row
        for title, row in rows
        if decisions.get(title) == "승인"
    ]

    return "\n".join(approved).strip()



def split_b_property_rows(content: str) -> list[tuple[str, str]]:
    """B 블록의 DB 속성 표에서 주요 속성 행을 뽑습니다."""
    rows = []

    for line in content.splitlines():
        stripped = line.strip()

        if not stripped.startswith("|"):
            continue

        if "속성" in stripped and "값" in stripped:
            continue

        compact = stripped.replace(" ", "")
        if re.fullmatch(r"\|:?-+:?\|:?-+:?\|", compact):
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]

        if len(cells) < 2:
            continue

        key = re.sub(r"[*`]", "", cells[0]).strip()

        if key in {"제목", "날짜", "영역", "주제", "강의안"}:
            rows.append((key, stripped))

    return rows


def extract_b_tag_candidates(content: str) -> list[str]:
    """B 블록의 신규 태그 후보 이름을 찾습니다."""
    candidates = []

    for line in content.splitlines():
        stripped = line.strip()

        if not stripped.startswith("|") or "신규 후보" not in stripped:
            continue

        match = re.match(r"^\|\s*`([^`]+)`\s*\|", stripped)

        if match:
            tag = match.group(1).strip()

            if tag not in candidates:
                candidates.append(tag)

    return candidates


def review_b_section(content: str) -> dict[str, str]:
    """B를 속성별 + 신규 태그별로 검토합니다."""
    decisions = {}

    rows = split_b_property_rows(content)

    if rows:
        for key, row in rows:
            preview_section(f"B-{key}", row)
            decisions[f"속성:{key}"] = ask_decision(
                f"B의 '{key}' 속성을 어떻게 처리할까요?"
            )
    else:
        preview_section("B", content)
        decisions["B"] = ask_decision("B 블록을 어떻게 처리할까요?")

    tags = extract_b_tag_candidates(content)

    if tags:
        print()
        print("=" * 70)
        print("[B] 신규 주제 태그 후보")
        print("=" * 70)

        for tag in tags:
            print(f"- {tag}")
            decisions[f"태그:{tag}"] = ask_decision(
                f"신규 태그 '{tag}'를 어떻게 처리할까요?"
            )

    return decisions


def build_b_decision_summary(decisions: dict[str, str]) -> list[str]:
    return [
        f"- {title}: **{decision}**"
        for title, decision in decisions.items()
    ]


def build_approval_result(
    source_file: Path,
    status: str,
    sections: dict[str, str],
    approvals: dict[str, bool],
    item_decisions: dict[str, dict[str, str]] | None = None,
    summary: str = "",
) -> str:
    item_decisions = item_decisions or {}

    labels = {
        "A": "날짜별 기술 페이지 본문",
        "B": "DB 속성",
        "C": "커리어 허브 반영분",
        "D": "상시 참고 페이지 반영분",
        "E": "관련 노트 후보",
        "F": "커버리지 검증 결과",
        "G": "작업 일지 기록",
    }

    lines = [
        "# Claude → Notion 승인 결과",
        "",
        f"- 원본: `{source_file}`",
        f"- 자료 상태: **{status}**",
        "",
        "## 승인 결과",
        "",
    ]

    for key in "ABCDEFG":
        if key == "F":
            decision = "검수용"
        elif key in item_decisions:
            decision = summarize_item_decisions(item_decisions[key])
        else:
            decision = "승인" if approvals.get(key, False) else "보류"

        lines.append(f"- {key}. {labels[key]}: **{decision}**")

    for key in ["B", "C", "D", "E", "G"]:
        decisions = item_decisions.get(key, {})
        if not decisions:
            continue

        lines.extend(["", f"### {key} 항목별 결정"])

        for title, decision in decisions.items():
            lines.append(f"- {title}: **{decision}**")

    lines.extend(["", "---", "", "## Notion 반영 대상", ""])

    if approvals.get("A", False) and "A" in sections:
        lines.append(strip_trailing_dividers(sections["A"]))
        lines.extend(["", "---", ""])

    if "B" in sections and "B" in item_decisions:
        lines.extend([
            "## B. DB 속성 — 사용자 세부 결정",
            "",
        ])
        lines.extend(build_b_decision_summary(item_decisions["B"]))
        lines.extend([
            "",
            "> 위 세부 결정이 아래 Claude 제안보다 우선한다. "
            "보류·제외된 속성 변경 또는 신규 태그는 실제 Notion에 반영하지 않는다.",
            "",
            strip_trailing_dividers(sections["B"]),
            "",
            "---",
            "",
        ])
    elif approvals.get("B", False) and "B" in sections:
        lines.append(strip_trailing_dividers(sections["B"]))
        lines.extend(["", "---", ""])

    for key in ["C", "D", "G"]:
        if key not in sections:
            continue

        approved = approved_group_content(
            key,
            sections[key],
            item_decisions.get(key, {}),
        )

        if approved:
            lines.append(approved)
            lines.extend(["", "---", ""])

    if "E" in sections:
        approved = approved_e_content(
            sections["E"],
            item_decisions.get("E", {}),
        )

        if approved:
            lines.extend([
                "## E. 관련 노트 — 승인된 연결",
                "",
                approved,
                "",
                "---",
                "",
            ])

    if "F" in sections:
        f_body = remove_first_heading(sections["F"])
        lines.extend([
            "## F. 커버리지 검증 결과 — 검수용",
            "",
            strip_trailing_dividers(f_body),
            "",
        ])

    if summary:
        lines.extend([
            "---",
            "",
            "## 최종 요약 — 검수 참고용",
            "",
            summary,
            "",
        ])

    return "\n".join(lines).strip() + "\n"

def strip_trailing_dividers(content: str) -> str:
    lines = content.rstrip().splitlines()

    while lines and lines[-1].strip() == "---":
        lines.pop()

    return "\n".join(lines).rstrip()


def remove_first_heading(content: str) -> str:
    lines = content.splitlines()

    if lines and re.match(r"^#{1,4}\s+", lines[0]):
        lines = lines[1:]

    return "\n".join(lines).lstrip()

def split_subsections(content: str, prefix: str) -> list[tuple[str, str]]:
    if prefix:
        pattern = re.compile(
            rf"(?m)^###\s+({re.escape(prefix)}-\d+\..*)$"
        )
    else:
        pattern = re.compile(r"(?m)^###\s+(\d+\..*)$")

    matches = list(pattern.finditer(content))
    items = []

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        items.append((match.group(1).strip(), content[start:end].strip()))

    return items

def needs_manual_review(text: str) -> bool:
    markers = [
        "판단 필요",
        "판단 보류",
        "⏸️",
        "약한 연결",
        "넣을지 판단 필요",
        "확인 필요",
    ]
    return any(marker in text for marker in markers)


def split_e_table_rows(content: str) -> list[tuple[str, str]]:
    rows = []

    for line in content.splitlines():
        stripped = line.strip()

        if not stripped.startswith("|"):
            continue

        if "연결 대상" in stripped:
            continue

        # Markdown 표 구분선 예: |---|---|---|
        compact = stripped.replace(" ", "")
        if re.fullmatch(r"\|:?-+:?\|:?-+:?\|:?-+:?\|", compact):
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]

        if len(cells) >= 3:
            rows.append((cells[0], stripped))

    return rows


def build_notion_preview(
    source_file: Path,
    sections: dict[str, str],
    approvals: dict[str, bool],
    item_decisions: dict[str, dict[str, str]] | None = None,
    summary: str = "",
) -> str:
    item_decisions = item_decisions or {}

    lines = [
        "# Notion 반영 미리보기",
        "",
        f"- 원본: `{source_file}`",
        "- 목적: 실제 Notion 수정 전 최종 반영 범위 확인",
        "",
        "## 반영 요약",
        "",
    ]

    for key in ["A", "B", "C", "D", "E", "G"]:
        if key in item_decisions:
            status = summarize_item_decisions(item_decisions[key])
        else:
            status = "승인" if approvals.get(key, False) else "보류"

        lines.append(f"- {key}: **{status}**")

    lines.extend([
        "- F: 검수용 — Notion 반영 제외",
        "",
        "---",
        "",
    ])

    if approvals.get("A") and "A" in sections:
        lines.extend([
            "## A. 날짜별 기술 페이지 — 반영 준비",
            "",
            strip_trailing_dividers(remove_first_heading(sections["A"])),
            "",
            "---",
            "",
        ])

    if "B" in sections and "B" in item_decisions:
        lines.extend([
            "## B. DB 속성 — 세부 승인 결과",
            "",
        ])
        lines.extend(build_b_decision_summary(item_decisions["B"]))
        lines.extend([
            "",
            "> 위 세부 결정이 아래 Claude 제안보다 우선한다. "
            "보류·제외된 속성 변경 또는 신규 태그는 실제 Notion에 반영하지 않는다.",
            "",
            strip_trailing_dividers(remove_first_heading(sections["B"])),
            "",
            "---",
            "",
        ])
    elif approvals.get("B") and "B" in sections:
        lines.extend([
            "## B. DB 속성 — 반영 준비",
            "",
            strip_trailing_dividers(remove_first_heading(sections["B"])),
            "",
            "---",
            "",
        ])

    for key, label in [
        ("C", "커리어 허브"),
        ("D", "상시 참고 페이지"),
        ("G", "기준서 업데이트"),
    ]:
        if key not in sections:
            continue

        section_body = remove_first_heading(sections[key])
        prefix = key if key in {"C", "D"} else ""
        items = split_subsections(section_body, prefix)

        lines.extend([
            f"## {key}. {label} — 항목별 미리보기",
            "",
        ])

        if not items:
            decision = item_decisions.get(key, {}).get(key, "보류")
            lines.append(f"> 최종 결정: **{decision}**")
            lines.append("")
            lines.append(strip_trailing_dividers(section_body))
        else:
            decisions = item_decisions.get(key, {})

            for title, body in items:
                decision = decisions.get(title, "보류")
                icon = {
                    "승인": "✅ 승인",
                    "보류": "⏸️ 보류",
                    "제외": "❌ 제외",
                }.get(decision, "⚠️ 확인")

                lines.append(f"### {title} — {icon}")
                lines.append("")
                lines.append(remove_first_heading(body))
                lines.append("")

        lines.extend(["", "---", ""])

    if "E" in sections:
        rows = split_e_table_rows(sections["E"])

        lines.extend([
            "## E. 관련 노트 — 연결별 미리보기",
            "",
        ])

        if rows:
            decisions = item_decisions.get("E", {})

            for title, row in rows:
                decision = decisions.get(title, "보류")
                icon = {
                    "승인": "✅ 승인",
                    "보류": "⏸️ 보류",
                    "제외": "❌ 제외",
                }.get(decision, "⚠️ 확인")

                lines.append(f"- {icon} — {title}")
                lines.append(f"  - 원본 행: {row}")
        else:
            decision = item_decisions.get("E", {}).get("E", "보류")
            lines.append(f"> 최종 결정: **{decision}**")
            lines.append("")
            lines.append(
                strip_trailing_dividers(
                    remove_first_heading(sections["E"])
                )
            )

        lines.extend(["", "---", ""])

    if summary:
        lines.extend([
            "## 최종 요약 — 참고용",
            "",
            remove_first_heading(summary),
            "",
        ])

    return "\n".join(lines).strip() + "\n"

def choose_source_file(source_input: str):
    source_path = Path(source_input)

    if source_path.is_file():
        return source_path

    if not source_path.is_dir():
        print(f"경로를 찾을 수 없습니다: {source_path}")
        return None

    candidates = list(source_path.glob("claude_output_*.md"))
    candidates += list(source_path.glob("*_approval.md"))

    candidates = sorted(
        set(candidates),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    if not candidates:
        print("처리할 Claude output 또는 approval 파일이 없습니다.")
        print("Claude 작업이 끝난 뒤 다시 실행해 주세요.")
        return None

    print()
    print("Claude output 또는 approval 파일을 선택하세요.")

    for index, path in enumerate(candidates, start=1):
        print(f"{index}. {path.name}")

    while True:
        answer = input("번호를 입력하세요 (q: 종료): ").strip().lower()

        if answer in {"q", "quit", "exit"}:
            raise SystemExit

        try:
            selected_index = int(answer) - 1
        except ValueError:
            print("숫자로 입력해 주세요.")
            continue

        if 0 <= selected_index < len(candidates):
            return candidates[selected_index]

        print("목록에 있는 번호를 입력해 주세요.")



def parse_existing_approvals(text: str) -> dict[str, bool]:
    """기존 approval.md의 승인/보류 상태를 읽습니다."""

    approvals = {}

    pattern = re.compile(
        r"(?m)^-\s*([A-G])\.[^:]+:\s*\*\*(승인|보류|검수용)\*\*"
    )

    for match in pattern.finditer(text):
        key = match.group(1)
        status = match.group(2)

        if status == "승인":
            approvals[key] = True
        elif status == "보류":
            approvals[key] = False

    return approvals


def extract_original_source_from_approval(text: str):
    """approval.md 안의 원본 Claude output 경로를 찾습니다."""

    match = re.search(
        r"(?m)^-\s*원본:\s*`([^`]+)`\s*$",
        text,
    )

    if not match:
        return None

    return Path(match.group(1))


def is_approval_file(path: Path) -> bool:
    return path.name.endswith("_approval.md")


def load_source_and_existing_approvals(selected_file: Path):
    """
    claude_output_*.md 또는 *_approval.md 둘 다 받을 수 있게 합니다.

    approval 파일이면:
    - 기존 승인 상태를 읽고
    - 원본 Claude output 파일을 찾아 다시 로드합니다.
    """

    if not is_approval_file(selected_file):
        return selected_file, {}, False

    approval_text = read_markdown(selected_file)
    existing_approvals = parse_existing_approvals(approval_text)
    original_source = extract_original_source_from_approval(approval_text)

    if original_source is None:
        print("approval 파일에서 원본 경로를 찾지 못했습니다.")
        return None, {}, True

    if not original_source.exists():
        print(f"원본 Claude output 파일을 찾을 수 없습니다: {original_source}")
        return None, {}, True

    return original_source, existing_approvals, True


def review_only_pending_sections(
    sections: dict[str, str],
    existing_approvals: dict[str, bool],
) -> dict[str, bool]:
    """
    기존 approval 파일에서 보류된 항목만 다시 확인합니다.
    기존 승인 항목은 그대로 유지하고 다시 묻지 않습니다.
    """

    approvals = dict(existing_approvals)

    pending_keys = [
        key
        for key in ["A", "B", "C", "D", "E", "G"]
        if key in sections and existing_approvals.get(key) is False
    ]

    if not pending_keys:
        print()
        print("다시 승인할 보류 항목이 없습니다.")
        return approvals

    print()
    print("보류된 항목만 다시 확인합니다:", ", ".join(pending_keys))

    for key in pending_keys:
        preview_section(key, sections[key])

        if key in {"A", "B"}:
            message = f"{key} 블록을 최종 반영 대상으로 승인할까요?"
        else:
            message = f"{key} 후보를 다음 Notion 반영 단계로 넘길까요?"

        answer = ask_yes_no(
            message,
            default=False,
        )

        # y일 때만 보류 -> 승인으로 변경합니다.
        # Enter/N이면 기존 보류 상태를 그대로 유지합니다.
        if answer:
            approvals[key] = True

    return approvals


def show_final_approval_status(approvals: dict[str, bool]) -> None:
    """저장 직전 최종 승인 상태를 한 번에 보여줍니다."""

    labels = {
        "A": "날짜별 기술 페이지 본문",
        "B": "DB 속성",
        "C": "커리어 허브 반영분",
        "D": "상시 참고 페이지 반영분",
        "E": "관련 노트 후보",
        "G": "작업 일지 기록",
    }

    print()
    print("=" * 70)
    print("최종 승인 상태")
    print("=" * 70)

    for key in ["A", "B", "C", "D", "E", "G"]:
        status = "승인" if approvals.get(key, False) else "보류"
        print(f"{key}. {labels[key]}: {status}")

    print("F. 커버리지 검증 결과: 검수용")
    print("=" * 70)


def confirm_save_final_status() -> bool:
    """최종 상태를 실제 파일로 저장할지 마지막으로 확인합니다."""

    return ask_yes_no(
        "이 상태로 승인 결과와 Notion 미리보기를 저장할까요?",
        default=False,
    )


def main():
    print("=== Claude → Notion 승인 도구 v0.3.4 ===")
    print()

    source_input = input(
        "Claude 결과 Markdown 파일 경로를 입력하세요: "
    ).strip().strip('"')

    if not source_input:
        print("파일 경로가 없습니다.")
        return

    if source_input.lower() in {"q", "quit", "exit"}:
        raise SystemExit

    selected_file = choose_source_file(source_input)

    if selected_file is None:
        return

    source_file, existing_approvals, resumed_from_approval = (
        load_source_and_existing_approvals(selected_file)
    )

    if source_file is None:
        return

    text = read_markdown(source_file)
    sections = split_sections(text)
    summary = extract_summary(text)

    if not sections:
        print("A~G 섹션을 찾지 못했습니다.")
        print("Claude 결과 제목이 '# A. ...' 형태인지 확인해 주세요.")
        return

    print()
    print("발견한 섹션:", ", ".join(sorted(sections.keys())))

    if summary:
        print("최종 요약 섹션: 별도 감지됨")

    status = detect_material_status(text)
    print(f"자료 상태 감지: {status}")

    if status != "최종 입력":
        print()
        print("주의: 최종 입력으로 확정되지 않았습니다.")

        proceed = ask_yes_no(
            "그래도 승인 검토를 계속할까요?",
            default=False,
        )

        if not proceed:
            print("검토를 종료합니다.")
            return

    item_decisions = {}

    if resumed_from_approval:
        approvals = dict(existing_approvals)

        if "A" in sections and existing_approvals.get("A") is False:
            preview_section("A", sections["A"])
            approvals["A"] = ask_yes_no(
                "A 블록을 최종 반영 대상으로 승인할까요?",
                default=False,
            )

        if "B" in sections and existing_approvals.get("B") is False:
            decisions = review_b_section(sections["B"])
            item_decisions["B"] = decisions
            approvals["B"] = any(
                decision == "승인"
                for decision in decisions.values()
            )

        for key in ["C", "D", "E", "G"]:
            if key not in sections:
                continue

            if existing_approvals.get(key) is True:
                approvals[key] = True
                continue

            if key == "E":
                decisions = review_e_section(sections[key])
            else:
                decisions = review_grouped_section(key, sections[key])

            item_decisions[key] = decisions
            approvals[key] = any(
                decision == "승인"
                for decision in decisions.values()
            )
    else:
        approvals = {}

        if "A" in sections:
            preview_section("A", sections["A"])
            approvals["A"] = ask_yes_no(
                "A 블록을 최종 반영 대상으로 승인할까요?",
                default=False,
            )

        if "B" in sections:
            decisions = review_b_section(sections["B"])
            item_decisions["B"] = decisions
            approvals["B"] = any(
                decision == "승인"
                for decision in decisions.values()
            )

        for key in ["C", "D", "E", "G"]:
            if key not in sections:
                continue

            if key == "E":
                decisions = review_e_section(sections[key])
            else:
                decisions = review_grouped_section(key, sections[key])

            item_decisions[key] = decisions
            approvals[key] = any(
                decision == "승인"
                for decision in decisions.values()
            )

    if "F" in sections:
        preview_section("F", sections["F"])
        print()
        print("F는 검수용이므로 Notion 본문 자동 반영 대상에서 제외합니다.")

    if summary:
        preview_section("요약", summary)
        print()
        print("요약은 검수 참고용이며 G 작업 일지에 포함하지 않습니다.")

    show_final_approval_status(approvals)

    if not confirm_save_final_status():
        print()
        print("저장하지 않고 종료합니다. 기존 파일은 변경하지 않았습니다.")
        return

    DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)

    output_file = DEFAULT_OUTPUT_DIR / f"{source_file.stem}_approval.md"

    result = build_approval_result(
        source_file=source_file,
        status=status,
        sections=sections,
        approvals=approvals,
        item_decisions=item_decisions,
        summary=summary,
    )

    output_file.write_text(result, encoding="utf-8")

    DEFAULT_PREVIEW_DIR.mkdir(exist_ok=True)

    preview_file = DEFAULT_PREVIEW_DIR / f"{source_file.stem}_notion_preview.md"

    preview = build_notion_preview(
        source_file=source_file,
        sections=sections,
        approvals=approvals,
        item_decisions=item_decisions,
        summary=summary,
    )

    preview_file.write_text(preview, encoding="utf-8")

    print()
    print("=" * 70)
    print("승인 결과 저장 완료")
    print(output_file.resolve())
    print()
    print("Notion 반영 미리보기 저장 완료")
    print(preview_file.resolve())
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n사용자가 작업을 취소했습니다.")
    except SystemExit:
        print("\n승인 도구를 종료합니다.")
