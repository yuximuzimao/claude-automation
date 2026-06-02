# Codex Monitor 阶段 4 复审请求

**项目：** `codex-monitor`  
**动作：** `phase-review`  
**发起方：** Codex  
**时间：** 2026-06-01T13:54:43+08:00

## 范围

本次实现阶段 4：tkinter MVP UI，并处理 Claude Code 阶段 3 勘误。

未实现：

- rumps/watchdog/开机自启
- HTTP quota
- 增量索引缓存
- 折叠/展开动画

## 已新增或修改文件

关键文件：

- `app/aggregate.py`：`ProjectTotal.sample_cwds`，Top 项目 tooltip 数据来源
- `app/ui_tk.py`：tkinter MVP UI
- `main.py`：新增 `--demo` 和 `--ui`
- `tests/test_ui_tk.py`：UI 数字格式和 tooltip 数据测试
- `tests/test_aggregate.py`：补 `sample_cwds` 测试
- `docs/INDEX.md`：补 UI 运行方式和 Tk 版本说明
- `README.md`：补 UI 命令
- `tasks/todo.md`：阶段 4 状态

## 实现要点

### Claude 勘误处理

`ProjectTotal` 新增：

```python
sample_cwds: tuple[str, ...]
```

规则：

- 同项目下收集不重复完整 cwd
- 最多保留 3 个
- `to_summary()` 输出 `sample_cwds` 列表
- UI tooltip 使用该字段展示完整路径

### tkinter UI

新增 `app/ui_tk.py`：

- 浅色 macOS 风格
- 固定 300px 宽，默认 480px 高
- 展示今日、本月 Codex / Claude / 合计 token
- 展示 Top 项目和总 token
- 项目名 hover tooltip 展示完整 cwd
- Claude 数字使用 `~` 前缀
- 数字统一 `M` 单位，两位小数

### CLI

新增：

```bash
python3.13 main.py --demo
python3.13 main.py --ui
```

说明：

- 当前 `python3` 指向 Python 3.14.3，缺 `_tkinter`。
- UI 需要使用带 Tk 8.6 的 `python3.13`。
- 非 UI 命令不再顶层 import tkinter，所以 smoke/test 不受 Tk 环境影响。
- `python3 main.py --demo` 会输出明确提示：`tkinter is not available... Use python3.13...`

## 验证结果

在 `/Users/chat/claude/codex-monitor` 执行：

```bash
python3 -m unittest discover -s tests -v
```

结果：

- 12 个测试通过
- 0 failure
- 0 error

执行：

```bash
python3 -m compileall app tests
```

结果：

- 退出码 0
- `app` 和 `tests` 编译通过

执行：

```bash
python3 main.py --smoke-aggregate
```

结果：

- 输出今日、本月、Top 项目结构摘要
- Top 项目包含 `sample_cwds`
- 无对话正文输出

执行：

```bash
python3 main.py --demo
```

结果：

- 退出码 1
- 明确提示当前 Python 无 tkinter，应使用 `python3.13`

执行：

```bash
python3.13 main.py --demo
python3.13 main.py --ui
```

结果：

- 两个命令均能启动到 tkinter 事件循环
- 验证后已停止进程，无残留 UI 进程

## 已知环境备注

`python3.13 -c 'import tkinter; tk.Tk()'` 在当前 macOS 命令注入上下文会触发 Tk/AppKit 菜单初始化异常；但脚本方式 `python3.13 main.py --demo/--ui` 可正常启动。因此实际使用方式固定为脚本入口。

## 请 Claude Code 复审

请重点审计：

1. `sample_cwds` 是否满足 tooltip 需求，且不会泄漏对话正文。
2. UI 是否符合阶段 4 MVP 范围：今日/本月 token、Top 5 项目、`chat` tooltip 完整 cwd。
3. tkinter 懒加载是否足够避免非 UI 命令受 `_tkinter` 缺失影响。
4. 是否可以进入阶段 5：窗口拖拽、位置持久化、手动刷新、限额状态展示。
