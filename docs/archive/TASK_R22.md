# Round 22 — Multi-persona

> **Round**: 22 / Phase C  
> **分支**: `feat/v1.0-phase-c`  
> **前置**: R21 完成  
> **交付**: Multi-persona 切换支持 + CLI 命令 + MCP 支持

---

## 目标

支持多 persona 隔离：不同 Agent 或场景使用独立的记忆空间。

---

## 必读文档

1. `PROJECT_CONTEXT_V10.md` + `CONVENTIONS_V10.md`
2. `src/memory_palace/config.py` — 数据目录配置
3. `src/memory_palace/service/memory_service.py` — data_dir 如何使用

---

## 交付件

### 1. [MODIFY] `src/memory_palace/config.py`

```python
class PersonaConfig(BaseModel):
    """A named persona with its own data directory."""
    name: str
    data_dir: str  # 相对或绝对路径
    description: str = ""

class Config(BaseSettings):
    ...
    personas: list[PersonaConfig] = [
        PersonaConfig(name="default", data_dir="~/.memory_palace", description="默认 persona")
    ]
    active_persona: str = "default"
```

### 2. [NEW] `src/memory_palace/service/persona_manager.py`

```python
class PersonaManager:
    """Manages multiple persona profiles.
    
    Each persona has:
    - Independent data_dir (core, recall, archival, audit all separate)
    - Shared config (LLM, embedding settings)
    """
    
    def __init__(self, config: Config): ...
    
    def list_personas(self) -> list[PersonaConfig]: ...
    def get_active(self) -> PersonaConfig: ...
    def switch(self, name: str) -> PersonaConfig: ...
    def create(self, name: str, data_dir: str, description: str = "") -> PersonaConfig: ...
    def delete(self, name: str) -> bool: ...
    
    def build_service(self, persona_name: str | None = None) -> MemoryService:
        """Build a MemoryService for the given (or active) persona."""
```

### 3. [MODIFY] `src/memory_palace/integration/cli.py`

新增 `persona` 命令组:
```python
@persona_app.command("list")
@persona_app.command("create")
@persona_app.command("switch")
@persona_app.command("delete")
```

所有现有命令增加 `--persona` 选项 (默认 "default")。

### 4. [MODIFY] `src/memory_palace/integration/mcp_server.py`

- 新增 `switch_persona(name: str)` tool
- 新增 `list_personas()` tool
- `palace://personas` resource

### 5. [NEW] `tests/test_service/test_persona_manager.py`

```
test_list_personas_default — 默认有 "default"
test_create_persona — 创建新 persona
test_switch_persona — 切换后 active 变更
test_delete_persona — 删除非 active persona
test_delete_active_persona_fails — 不能删除当前 active
test_build_service_default — 构建默认 persona 的 service
test_build_service_custom — 构建自定义 persona 的 service
test_persona_data_isolation — 两个 persona save 不互相干扰
test_persona_config_persistence — 创建后重新加载能找到
test_duplicate_name_fails — 重名报错
```

预计 ~10 tests。

---

## 约束

1. 每个 persona 完全独立的 data_dir (不共享 SQLite/ChromaDB)
2. 不能删除当前 active persona
3. Config 变更需要持久化到 YAML (写回 memory_palace.yaml)
4. "default" persona 永远存在，不能删除

---

## 验证

```bash
pytest tests/ -q
pytest tests/test_service/test_persona_manager.py -v
ruff check
git commit -m "feat(R22): Multi-persona profile switching"
```
