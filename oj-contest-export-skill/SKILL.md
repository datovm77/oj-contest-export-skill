---
name: oj-contest-export
description: Export problems from a Vue/Online Judge contest or class practice page into Markdown/JSON study documents. Use when the user provides an OJ class/contest URL such as /#/contests?group=... or /#/contest/... and asks to extract, summarize, format, archive, or package recent-semester practice questions, especially on Windows/PowerShell with captcha login.
---

# OJ Contest Export

## Workflow

1. Inspect the frontend bundle when endpoints are unknown.
   - Download the app HTML and static JS chunks.
   - Search for `baseURL`, `contests/`, `contests/problems_id/`, `user/login/`, and `captcha/`.
   - For this SZTU OJ style app, API base is usually `/api`.

2. Use the bundled exporter:
   ```powershell
   python .\skills\oj-contest-export\scripts\export_contest_questions.py --group 81
   ```
   Useful options:
   ```powershell
   --group 81
   --since 2026-03-01
   --username <student-id>
   --password <password>
   --captcha-key <key>
   --captcha-value <value>
   ```

3. Captcha handling:
   - The script writes `tmp\captcha.png` only while waiting for captcha input.
   - If generating captcha manually, save `captcha_key` only temporarily.
   - Always delete `tmp\captcha.png`, `tmp\captcha.json`, and `tmp\captcha_key.txt` after login attempts.

4. Format the exported JSON:
   ```powershell
   python .\skills\oj-contest-export\scripts\format_questions.py --source .\exports\<export>.json
   ```
   The formatter creates a cleaner Markdown study document with consistent sections:
   题目描述, 输入格式, 输出格式, 样例, 实现要点与解析.

## Output Expectations

- Preserve raw JSON for repeatable post-processing.
- Produce Markdown for reading and sharing.
- Report skipped contests with reasons, especially:
  - not started / no permission
  - hidden or deleted problems
  - captcha/login failures
- Verify counts against the UI list. It is normal for a contest to contain fewer than five visible problems if the API returns fewer.

## Safety Boundaries

- Do not store passwords, cookies, session tokens, or captcha keys in persistent files.
- Do not include complete ready-to-submit solutions for active or ongoing coursework/tests. For active items, provide formatting, explanations, implementation guidance, pseudocode, or help debugging user-provided code.
- For ended practice sets, complete answer keys may be added only when the user is authorized and the context is clearly retrospective study.

## Windows Notes

- The user environment is Windows 11 with PowerShell.
- Avoid Bash heredocs. Use PowerShell-native commands or Python scripts.
- If network calls to an intranet host fail under sandboxing, rerun the exact necessary request with escalation.
