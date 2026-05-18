import argparse
import html
import getpass
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


BASE_URL = "http://10.11.219.21"
API_URL = f"{BASE_URL}/api"
TYPE_NAMES = {
    "0": "编程题",
    "1": "选择题",
    "2": "填空题",
    "3": "问答题",
    "4": "代码填空题",
}


def current_semester_start(now: datetime | None = None) -> str:
    now = now or datetime.now()
    if now.month >= 8:
        return f"{now.year}-08-01"
    if now.month >= 2:
        return f"{now.year}-02-01"
    return f"{now.year - 1}-08-01"


def html_to_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", value)
    text = re.sub(r"(?i)</\s*(p|div|li|tr|h[1-6]|table|ul|ol|pre)\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def compact(value: Any) -> str:
    text = html_to_text(value)
    return re.sub(r"[ \t]+", " ", text).strip()


def request_json(session: requests.Session, method: str, path: str, **kwargs: Any) -> Any:
    url = path if path.startswith("http") else f"{API_URL}/{path.lstrip('/')}"
    response = session.request(method, url, timeout=20, **kwargs)
    try:
        data = response.json()
    except ValueError:
        data = response.text
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {url} failed: {response.status_code} {data}")
    return data


def fetch_captcha(session: requests.Session, tmp_dir: Path) -> tuple[str, Path]:
    data = request_json(session, "POST", "captcha/")
    captcha_key = data["captcha_key"]
    image_bytes = __import__("base64").b64decode(data["captcha_image"])
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / "captcha.png"
    path.write_bytes(image_bytes)
    return captcha_key, path


def cleanup_auth_files(tmp_dir: Path) -> None:
    for name in ("captcha.png", "captcha.json", "captcha_key.txt"):
        path = tmp_dir / name
        if path.exists():
            path.unlink()


def login(session: requests.Session, username: str, password: str, captcha_key: str, captcha_value: str) -> dict[str, Any]:
    payload = {
        "username": username,
        "password": password,
        "captcha_key": captcha_key,
        "captcha_value": captcha_value,
    }
    return request_json(session, "POST", "user/login/", json=payload)


def fetch_contests(session: requests.Session, group: int, limit: int = 50) -> list[dict[str, Any]]:
    contests: list[dict[str, Any]] = []
    offset = 0
    while True:
        data = request_json(session, "GET", "contests/", params={"group": group, "offset": offset, "limit": limit})
        results = data.get("results", [])
        contests.extend(results)
        if offset + limit >= data.get("count", len(contests)):
            return contests
        offset += limit


def iter_problems(contest_detail: dict[str, Any]) -> list[dict[str, Any]]:
    problem_json = contest_detail.get("problem_json") or {}
    problem_score = contest_detail.get("problem_score") or {}
    rows: list[dict[str, Any]] = []
    for type_id, problems in problem_json.items():
        if not isinstance(problems, list):
            continue
        for index, problem in enumerate(problems, start=1):
            if problem.get("deleted"):
                continue
            problem_id = str(problem.get("id", ""))
            item = dict(problem)
            item["_type_id"] = str(type_id)
            item["_type_name"] = TYPE_NAMES.get(str(type_id), f"类型{type_id}")
            item["_index"] = index
            item["_score"] = (problem_score.get(str(type_id)) or {}).get(problem_id)
            rows.append(item)
    return rows


def problem_to_markdown(problem: dict[str, Any]) -> str:
    lines = [
        f"### {problem['_type_name']} {problem['_index']}: ID {problem.get('id', '')}",
    ]
    if problem.get("_score") is not None:
        lines.append(f"分值: {problem['_score']}")
    title = compact(problem.get("title") or problem.get("name"))
    if title:
        lines.append(f"标题: {title}")
    description = html_to_text(problem.get("description"))
    if description:
        lines.extend(["", description])

    choices = problem.get("choices") or problem.get("options") or problem.get("choice")
    if isinstance(choices, list) and choices:
        lines.append("")
        lines.append("选项:")
        for idx, choice in enumerate(choices, start=1):
            label = chr(ord("A") + idx - 1)
            lines.append(f"- {label}. {compact(choice)}")

    for key, label in [
        ("input_description", "输入说明"),
        ("output_description", "输出说明"),
        ("sample_input", "样例输入"),
        ("sample_output", "样例输出"),
        ("hint", "提示"),
        ("template", "代码模板"),
    ]:
        value = problem.get(key)
        if value:
            lines.extend(["", f"{label}:", html_to_text(value)])
    return "\n".join(lines).strip()


def export(
    group: int,
    since: str,
    username: str,
    password: str,
    captcha_value: str | None,
    captcha_key: str | None = None,
) -> tuple[Path, Path, int, int]:
    tmp_dir = Path("tmp")
    out_dir = Path("exports")
    out_dir.mkdir(exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": f"{BASE_URL}/"})

    captcha_path: Path | None = None
    try:
        if captcha_key is None:
            captcha_key, captcha_path = fetch_captcha(session, tmp_dir)
        if captcha_value is None:
            if captcha_path is None:
                raise RuntimeError("captcha_value is required when captcha_key is provided")
            print(f"验证码图片: {captcha_path.resolve()}")
            captcha_value = input("请输入验证码: ").strip()
        login(session, username, password, captcha_key, captcha_value)

        contests = fetch_contests(session, group)
        filtered = [
            contest for contest in contests
            if str(contest.get("begin_time", ""))[:10] >= since and contest.get("state") != 0
        ]
        filtered.sort(key=lambda item: item.get("begin_time", ""), reverse=True)

        exported: list[dict[str, Any]] = []
        md_lines = [
            f"# 最近一学期练习题汇总",
            "",
            f"- 班级 group: {group}",
            f"- 起始日期: {since}",
            f"- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        skipped: list[dict[str, Any]] = []
        for contest in filtered:
            try:
                detail = request_json(session, "GET", f"contests/{contest['id']}/")
            except RuntimeError as exc:
                skipped.append({"id": contest.get("id"), "title": contest.get("title"), "reason": str(exc)})
                continue
            problems = iter_problems(detail)
            md_lines.extend([
                f"## {detail.get('title', contest.get('title', ''))}",
                "",
                f"- 测验 ID: {detail.get('id', contest.get('id'))}",
                f"- 开始时间: {detail.get('begin_time', contest.get('begin_time', ''))}",
                f"- 结束时间: {detail.get('end_time', contest.get('end_time', ''))}",
                f"- 题目数: {len(problems)}",
                "",
            ])
            contest_row = {
                "id": detail.get("id", contest.get("id")),
                "title": detail.get("title", contest.get("title")),
                "begin_time": detail.get("begin_time", contest.get("begin_time")),
                "end_time": detail.get("end_time", contest.get("end_time")),
                "problems": [],
            }
            for problem in problems:
                md_lines.extend([problem_to_markdown(problem), ""])
                contest_row["problems"].append(problem)
            exported.append(contest_row)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        md_path = out_dir / f"contest_questions_group{group}_{stamp}.md"
        json_path = out_dir / f"contest_questions_group{group}_{stamp}.json"
        md_path.write_text("\n".join(md_lines).strip() + "\n", encoding="utf-8")
        json_path.write_text(json.dumps({"contests": exported, "skipped": skipped}, ensure_ascii=False, indent=2), encoding="utf-8")
        return md_path, json_path, len(filtered), sum(len(row["problems"]) for row in exported)
    finally:
        cleanup_auth_files(tmp_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="导出 OJ 测验题目汇总")
    parser.add_argument("--group", type=int, default=81)
    parser.add_argument("--since", default=current_semester_start())
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--captcha-value")
    parser.add_argument("--captcha-key")
    args = parser.parse_args()

    username = args.username or input("账号: ").strip()
    password = args.password or getpass.getpass("密码: ")
    md_path, json_path, contest_count, problem_count = export(
        group=args.group,
        since=args.since,
        username=username,
        password=password,
        captcha_value=args.captcha_value,
        captcha_key=args.captcha_key,
    )
    print(f"已导出 {contest_count} 个测验、{problem_count} 道题")
    print(f"Markdown: {md_path.resolve()}")
    print(f"JSON: {json_path.resolve()}")


if __name__ == "__main__":
    main()
