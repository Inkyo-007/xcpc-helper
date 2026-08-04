"""日志配置。

【本文件在全局中的位置】
应用启动时，main.py 会调用一次 setup_logging()，
之后全项目任何文件里用 logging.getLogger(...) 打出的日志，
都会按这里规定的格式打印到控制台。
"""

import logging  # Python 标准库自带的日志模块，无需安装


def setup_logging(level: int = logging.INFO) -> None:
    """统一配置日志格式。

    参数 level 表示“最低显示级别”：默认 INFO，
    表示 INFO 及以上的日志（INFO/WARNING/ERROR）都会显示，
    更琐碎的 DEBUG 日志会被忽略。
    """

    # basicConfig 是 logging 模块提供的“一键初始化”函数。
    # 项目里只在启动时调用一次即可，之后的所有 logger 都生效。
    logging.basicConfig(
        level=level,
        # 日志行的排版：时间 + 级别（占 7 个字符宽度）+ 日志名 + 内容
        # 形如：14:23:01 INFO    xcpc.service.template: 模板索引构建完成，诊断 0 条
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        # 只显示时分秒，足够开发时观察
        datefmt="%H:%M:%S",
    )
