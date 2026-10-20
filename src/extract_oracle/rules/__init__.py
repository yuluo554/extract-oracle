"""判定层（`rules/*`）。

硬边界（`plan/02` §一/§二，K10）：

- **纯函数**：输入是字节层结构事实（`zip_reader.Archive`），输出 `Finding` 元组；不写盘、不联网；
- **互不 import**：各 `MOD-*` 模块之间零依赖，形状契约在包根 `findings.py`；
- **不得 import `cli`**：判定层不知道 CLI 存在（AST 守门 `tests/test_rule_boundaries.py`）。
"""
