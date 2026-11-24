# 远征灰盒

在本目录用 Python 运行 `app.py --help` 查看浏览器与命令行启动方式。玩法实现使用 Python 标准库。`data.py` 加载文档目录中的事件、奖励、地图和遭遇配置，并计算运行指纹。使用仓库中的原始目录结构以便存档校验。

在本目录执行 `python -B -m unittest test_action_timing test_boards` 可检查战斗时序与棋盘规则。
