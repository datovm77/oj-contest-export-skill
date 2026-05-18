import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from export_contest_questions import html_to_text


GUIDANCE: dict[int, str] = {
    68: "按题意建立 CPoint -> CCircle -> CCylinder 的继承链。圆面积和圆柱体体积都按 pi=3.14 计算，输出格式中的标点、括号和换行必须与样例一致。",
    69: "二维点类负责 x、y 和到原点距离；三维点类继承二维点并增加 z。比较距离时可比较平方和，避免不必要的浮点误差；输出通常按题面要求打印距离或最大点。",
    175: "用基类保存姓名、年龄等公共信息，派生类分别处理研究生/本科生或不同学生类型的成绩。读取类型字符后分支构造对象，再调用统一接口计算并输出。",
    73: "设计基础时间类保存时分秒，派生秒表/闹钟类处理增加秒数。核心是把时分秒转为总秒数，加上偏移后对 24*3600 取模，再还原为时分秒。",
    74: "旧身份证与新身份证可抽象公共姓名和出生日期，新身份证在旧证基础上补全年份与校验位。注意闰年日期合法性、字符串截取和固定格式输出。",
    112: "向量类用动态数组或 vector 保存元素，构造时读取长度和元素。需要实现输出、求和、平均值或题面指定操作；重点是封装数据和按格式打印。",
    113: "两个向量长度可能不同，友元函数适合访问私有数组并完成加减、点积等操作。拷贝构造要深拷贝动态数组，避免多个对象共享同一块内存。",
    114: "用静态成员统计已创建向量对象数量或统一编号。每组输入创建对象并执行题面要求的统计，注意静态变量属于类而不是对象。",
    115: "类复合通常是学生类包含成绩向量类。先读取姓名和成绩个数，再把成绩封装进向量对象，由学生对象负责计算总分/平均分并输出。",
    116: "友元类可以访问向量类私有成员。按题面让工具类完成矩阵/向量运算，输入多组数据时逐组创建对象并输出计算结果。",
    119: "机器人类保存编号、类型、能量等属性。根据变身命令修改类型或属性，最后按题面输出每个机器人状态；注意字符命令与类型字符的映射。",
    120: "虚拟电话对象的构造函数读取号码、等级、状态、姓名等信息，析构或成员函数负责统计费用/状态。多条记录读到结束，按样例顺序输出。",
    121: "账户类保存账号、类型和余额；拷贝构造用于从已有账户复制生成新账户。根据输入的源/目标类型执行复制或转换，注意余额与类型字符输出。",
    122: "电视类保存频道、音量、模式等静态限制，遥控器作为友元修改电视私有状态。每条命令先校验范围，越界时按题面要求保持或修正。",
    59: "旅馆类用静态成员统计顾客人数和总收入。房价作为公共参数，循环读取顾客姓名直到结束标记，最后输出人数、收入或题面指定统计。",
    57: "账户类的静态成员保存利率，友元函数可以直接计算利息或处理转账。输入每个账户的本金、存取款后更新余额并按格式输出。",
    56: "定义点类和距离友元函数。每组输入两个点，计算 sqrt((x1-x2)^2+(y1-y2)^2)，输出精度按题面或样例控制。",
    58: "复数类保存实部虚部，用友元函数实现加减。读取初始复数和若干操作，每次更新当前复数，输出时注意正负虚部的符号格式。",
    62: "日期类和时间类分别封装年月日、时分秒；友元函数或组合输出完整日期时间。重点是按样例补零或不补零的格式。",
    45: "Equation 类保存 a、b、c 并在构造后求二次方程根。判别式大于、等于、小于零分别处理；复根输出要按题面格式控制小数。",
    50: "题目考察构造与拷贝构造的调用顺序。按输入类型创建对象或复制对象，并在构造/析构函数中打印题面指定文本。",
    51: "电话号码升位可用拷贝构造从旧号码生成新号码。核心是字符串规则替换或前缀补位，保持号码长度和输出顺序。",
    52: "软件备份类保存软件名、备份状态、日期等。拷贝构造表示复制一个备份对象；根据命令更新备份状态并输出。",
    53: "手机服务通常涉及 SIM/服务类和深拷贝。用构造函数初始化号码、套餐、日期等，用拷贝构造复制服务信息，注意堆内存释放。",
    31: "Point 类保存坐标，构造后计算两点距离或输出点信息。每组四个数可视为两个点，按欧氏距离公式处理。",
    32: "Date 类构造时保存年月日，并判断该日期是当年第几天或下一天。关键是闰年判断和每月天数表。",
    33: "分数类构造时解析 a/b，约分需要 gcd。按题面执行分数加减乘除或比较，输出最简分数。",
    34: "对象数组保存一组点。每组先读点数，再读坐标，通常要求计算折线长度、面积或最远点；用 vector<Point> 组织。",
    35: "Stack 类封装数组、栈顶和容量。输入一组数后按题面执行入栈/出栈/逆序输出，注意空栈和满栈边界。",
    27: "结构化学生信息适合定义 Student 类数组。逐条读取姓名、学号、性别、学院、电话，按题面排序、查找或格式化输出。",
    156: "存折类保存账号、姓名、余额。读入开户信息和两次金额操作，按存款/取款规则更新余额，注意余额不足时的提示。",
    162: "身体评估类根据身高体重计算 BMI 或标准体重差。每人读取姓名、身高、体重等，输出评估结果时注意浮点精度。",
    30: "点和圆类分别保存点坐标和圆心半径。判断点到圆心距离与半径关系，输出点在圆内、圆上或圆外。",
    160: "对象数组保存多只猫的名字和体重。遍历找最大体重对象，若有并列按题面处理；输出名字和体重。",
    19: "用引用参数实现三个数排序或求最大最小。函数内部交换引用变量，主函数逐组读入并输出排序后的结果。",
    134: "通过引用参数一次性返回最大值和最小值。每组先读 n，再读 n 个整数，遍历更新 max/min。",
    133: "定义小票/银行卡结构体，按字段读取商户、终端、银行、日期、卡号、金额等，再按题面格式输出。",
    20: "生日结构体保存年月日。比较日期大小时先比年，再比月，再比日；排序后取第二个年龄或第二大/小日期。",
    21: "把学生学号和代码字符串存入结构体数组。抄袭查找通常是比较字符串相似、包含或指定规则匹配，使用指针和函数封装比较逻辑。",
    13: "用指针数组保存 12 个月英文名或中文名。输入月份号，合法则输出对应字符串，非法按题面输出错误提示。",
    14: "用字符指针或 strcmp 比较两字符串。每组读两个字符串，输出较大/较小或比较结果，注意大小写 ASCII 顺序。",
    18: "密钥加密按密钥数字逐位移动字符。读取原文和数字串，循环使用密钥位，对字母做偏移并保持大小写范围。",
    11: "矩阵左转就是把原矩阵第 j 列变成新矩阵倒数第 j 行。3x3 或题面固定规模时直接下标转换即可。",
    16: "动态矩阵用 new 或 vector<vector<int>> 根据行列分配。逐组读取矩阵，按题面进行转置、求和、最大值或输出，结束后释放内存。",
}


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).rstrip("\n") for item in value]
    return [str(value).rstrip("\n")]


def clean_text(value: Any) -> str:
    text = html_to_text(value)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def code_block(label: str, value: Any) -> list[str]:
    values = as_list(value)
    if not values:
        return []
    lines = [f"**{label}**"]
    for item in values:
        lines.extend(["```text", item, "```"])
    return lines


def render_problem(problem: dict[str, Any], index: int) -> list[str]:
    lines: list[str] = []
    title = clean_text(problem.get("title"))
    score = problem.get("_score")
    header = f"### {index}. {title or '未命名题目'}"
    if score is not None:
        header += f"（{score} 分）"
    lines.extend([header, "", f"- 题目 ID: `{problem.get('id')}`"])
    if problem.get("time_limit") is not None and problem.get("memory_limit") is not None:
        lines.append(f"- 限制: {problem.get('time_limit')}s / {problem.get('memory_limit')}MB")
    lines.append("")

    for label, key in [
        ("题目描述", "description"),
        ("输入格式", "input_description"),
        ("输出格式", "output_description"),
        ("提示", "hint"),
    ]:
        text = clean_text(problem.get(key))
        if text:
            lines.extend([f"**{label}**", "", text, ""])

    lines.extend(code_block("样例输入", problem.get("sample_input")))
    if problem.get("sample_input"):
        lines.append("")
    lines.extend(code_block("样例输出", problem.get("sample_output")))
    if problem.get("sample_output"):
        lines.append("")

    guidance = GUIDANCE.get(int(problem.get("id", 0)), "先抽象题目中的实体为类，再把输入处理、核心计算和格式化输出分离实现。")
    lines.extend([
        "**实现要点与解析**",
        "",
        guidance,
        "",
        "**参考代码位置**",
        "",
        "请在这里整理你自己的 C++ 实现；我可以继续帮你检查编译错误、边界条件和样例输出。",
        "",
    ])
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Format exported OJ contest JSON as a clean study Markdown document.")
    parser.add_argument("--source", required=True, help="JSON file produced by export_contest_questions.py")
    parser.add_argument("--output", help="Output Markdown path. Defaults to exports/<source-stem>_formatted_<timestamp>.md")
    args = parser.parse_args()

    source = Path(args.source)
    data = json.loads(source.read_text(encoding="utf-8"))
    contests = data["contests"] if isinstance(data, dict) and "contests" in data else data
    out = Path(args.output) if args.output else Path("exports") / f"{source.stem}_formatted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 25级大数据1班 C++ 练习题汇总",
        "",
        f"- 来源文件: `{source.name}`",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 测验数: {len(contests)}",
        f"- 题目数: {sum(len(contest['problems']) for contest in contests)}",
        "",
    ]
    for contest in contests:
        lines.extend([
            f"## {contest['title']}",
            "",
            f"- 测验 ID: `{contest['id']}`",
            f"- 时间: {contest.get('begin_time', '')} 至 {contest.get('end_time', '')}",
            f"- 本节题目数: {len(contest['problems'])}",
            "",
        ])
        for idx, problem in enumerate(contest["problems"], start=1):
            lines.extend(render_problem(problem, idx))
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(out.resolve())


if __name__ == "__main__":
    main()
