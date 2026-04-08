"""
Round 6: E2E — Full Lifecycle Pipeline Test

IMMUTABLE SPEC: Ref: SPEC v2.0 §7.3 Round 6

This is the highest-level test. It validates the entire Memory Palace
pipeline from save → search → update → curate → verify.
All LLM calls use MockLLM.
"""

import pytest

from memory_palace.foundation.audit_log import AuditLog
from memory_palace.service.curator import CuratorService
from memory_palace.service.memory_service import MemoryService
from memory_palace.store.core_store import CoreStore
from tests.conftest import MockLLM


class TestE2EFullLifecycle:
    """End-to-end: save → search → update → curate → verify."""

    @pytest.mark.asyncio
    async def test_save_search_update_curate_verify(self, tmp_data_dir):
        """
        Complete lifecycle:
        1. save_batch(对话文本) → 提取并保存记忆
        2. search("用户偏好") → 返回相关结果
        3. save("用户改变了偏好") → 触发新记忆
        4. curate() → 搬运小人整理 → 旧偏好标记 superseded
        5. search("用户偏好") → 返回新偏好（旧偏好不出现）
        6. inspect(old_id) → 确认审计链完整
        """
        # === Step 1: save_batch with FactExtractor ===
        extract_llm = MockLLM(
            responses=['[{"content": "用户喜欢深色模式", "importance": 0.5, "tags": ["偏好"]}]']
        )
        ms = MemoryService(tmp_data_dir, llm=extract_llm)
        saved = await ms.save_batch(["用户说：我喜欢深色模式"])

        assert len(saved) >= 1
        old_item = saved[0]
        old_id = old_item.id
        assert "深色" in old_item.content

        # === Step 2: search → returns original preference ===
        results = ms.search("偏好")
        assert len(results) >= 1
        assert any("深色" in r.content for r in results)

        # === Step 3: save a new preference (conflicting) ===
        new_pref = ms.save("用户改为浅色模式", importance=0.5, tags=["偏好"])
        assert new_pref is not None
        assert "浅色" in new_pref.content

        # === Step 4: curate() → reconcile → UPDATE old preference ===
        # CuratorService.run() does:
        #   1. gather recent items from RecallStore
        #   2. extract facts (FactExtractor) → needs 1 LLM response
        #   3. reconcile each fact (ReconcileEngine) → needs 1 LLM response per fact
        curate_llm = MockLLM(
            responses=[
                # FactExtractor.extract() response
                '[{"content": "用户改为浅色模式", "importance": 0.6, "tags": ["偏好"]}]',
                # ReconcileEngine.reconcile() response — UPDATE the old item
                f'{{"action": "UPDATE", "target_id": "{old_id}",'
                f' "reason": "偏好已更新为浅色模式"}}',
            ]
        )
        curator = CuratorService(tmp_data_dir, llm=curate_llm)
        report = await curator.run()

        assert report.memories_updated >= 1

        # === Step 5: search again → new preference appears, old doesn't ===
        # RecallStore.search() filters status='active', so SUPERSEDED items are excluded
        ms2 = MemoryService(tmp_data_dir)
        results2 = ms2.search("偏好")

        # The old "深色模式" should be superseded, so it should NOT appear in active results
        old_contents = [r.content for r in results2 if "深色" in r.content]
        assert len(old_contents) == 0, (
            f"Old preference should be superseded but still found: {old_contents}"
        )

        # The new preference should appear
        new_contents = [r.content for r in results2 if "浅色" in r.content]
        assert len(new_contents) >= 1

        # === Step 6: inspect audit log → CREATE + UPDATE records ===
        audit = AuditLog(tmp_data_dir)
        entries = audit.read(memory_id=old_id)

        actions = [e.action.value for e in entries]
        assert "create" in actions, f"Expected CREATE in audit log, got: {actions}"
        assert "update" in actions, f"Expected UPDATE in audit log, got: {actions}"


class TestE2ECoreBudget:
    """End-to-end: Core Memory budget enforcement."""

    @pytest.mark.asyncio
    async def test_core_budget_enforcement(self, tmp_data_dir):
        """
        1. 连续 save 高重要性记忆直到接近 2KB 上限
        2. 验证告警触发
        3. 验证新 save 仍然成功（降级到 Recall）
        """
        ms = MemoryService(tmp_data_dir)
        core = CoreStore(tmp_data_dir)

        # Continuously save high-importance memories to Core tier (importance >= 0.7)
        # Each save goes to Core (room="general" block) and adds ~50+ bytes per item
        budget = None
        warning_triggered = False
        for i in range(30):
            ms.save(
                f"核心记忆 {i} " + "x" * 50,
                importance=0.9,
                room="general",
            )
            budget = core.budget_check("general")
            if budget["warning"]:
                warning_triggered = True
                break

        # 验证告警触发
        assert warning_triggered, (
            f"Budget warning should have triggered. "
            f"Final size: {budget['size']}, limit: {budget['limit']}"
        )
        assert budget["warning"] is True

        # 验证新 save 仍然成功（MemoryService.save() does not block on budget）
        extra = ms.save("超出预算的记忆", importance=0.9, room="general")
        assert extra is not None
        assert extra.content == "超出预算的记忆"
