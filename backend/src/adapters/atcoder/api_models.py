"""AtCoder（kenkoooo API）响应模型。

外部系统数据第一时间转化为 Pydantic 模型（见 docs/rules/backend.md），
不在 adapter 内用 dict[key] 访问。kenkoooo 响应为裸 JSON（无信封）：
提交列表为数组，题目目录为数组，难度模型为 problem_id 键的字典。

容错语义：可选字段用默认值 / None 承载（字段缺失不炸批）；类型不匹配
则校验失败，由 adapter 统一转为 PlatformError（平台格式异常，不阻断
其他账号）。

必填字段：id（去重依据）与 epoch_second（增量游标语义）——缺失即校验
失败暴露平台格式变化；epoch_second 若给默认值 0，增量拉取会把它当作
"旧于游标"提前终止，静默丢弃后续新提交。
"""

from pydantic import BaseModel, TypeAdapter


class AtSubmissionRow(BaseModel):
    """kenkoooo v3 user/submissions 单条提交（仅解析需要的字段，多余忽略）。"""

    id: int
    epoch_second: int
    problem_id: str = ""
    contest_id: str = ""
    language: str = ""
    result: str = ""


class AtProblem(BaseModel):
    """kenkoooo resources/problems.json 单题（题名来源）。"""

    id: str
    contest_id: str = ""
    problem_index: str = ""
    name: str = ""


class AtProblemModel(BaseModel):
    """kenkoooo resources/problem-models.json 单题模型（difficulty 来源）。

    实验性题目（is_experimental）无 difficulty 字段，为 None。
    """

    difficulty: int | None = None


# 列表 / 字典响应的批量校验器（模块级缓存，避免每次重建）
SUBMISSIONS = TypeAdapter(list[AtSubmissionRow])
PROBLEMS = TypeAdapter(list[AtProblem])
PROBLEM_MODELS = TypeAdapter(dict[str, AtProblemModel])
