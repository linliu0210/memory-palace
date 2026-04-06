# DreamEngine — LLM Provider Protocol

> **启发了**：Foundation 层的 LLMProvider Protocol 抽象

## 是什么

DreamEngine 是我们团队的另一个项目——一个多角色 AI 顾问引擎。
它的 LLM Provider 层设计了一个优雅的抽象模式：

- 用 Python `Protocol` 定义接口（非 ABC 继承）
- Provider Factory 根据配置动态选择后端（OpenAI / Anthropic / DeepSeek）
- 统一的 `generate(prompt, system_prompt) -> str` 接口

这个设计让 Memory Palace 可以复用同一套 LLM 抽象，
在测试中用 MockLLM 替换，在生产中用任意后端。

## 我们借鉴了什么

| DreamEngine | Memory Palace 对应 |
|------------|-------------------|
| `LLMProvider` Protocol | `foundation/llm.py` LLMProvider Protocol |
| `ProviderFactory` | Config 驱动的 provider 选择 |
| MockLLM for tests | `conftest.py` MockLLM fixture |

## 关键参考文档

```yaml
- file: ../dream-engine/src/llm/provider_factory.py
  why: Provider 工厂模式——根据 config 动态选择 LLM 后端
  critical: 用 Protocol 而非 ABC，支持 structural subtyping

- file: ../dream-engine/src/llm/base.py
  why: LLMProvider Protocol 定义——generate() 接口签名

- file: ../dream-engine/tests/conftest.py
  why: MockLLM 设计模式——deterministic 测试替身
```
