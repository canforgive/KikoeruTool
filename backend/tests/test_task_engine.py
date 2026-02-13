"""
任务引擎测试
"""
import pytest
import asyncio
from unittest.mock import Mock, patch

from app.core.task_engine import TaskEngine, Task, TaskType, TaskStatus

class TestTaskEngine:
    """测试任务引擎"""
    
    @pytest.fixture
    def engine(self):
        """创建任务引擎实例"""
        return TaskEngine(max_concurrent=2)
    
    @pytest.fixture
    def sample_task(self):
        """创建示例任务"""
        return Task(
            task_type=TaskType.AUTO_PROCESS,
            source_path="/test/file.zip",
            auto_classify=True
        )
    
    @pytest.mark.asyncio
    async def test_submit_task(self, engine, sample_task):
        """测试提交任务"""
        task_id = await engine.submit(sample_task)
        
        assert task_id is not None
        assert sample_task.id == task_id
        assert len(engine.tasks) == 1
        assert engine.tasks[task_id] == sample_task
    
    @pytest.mark.asyncio
    async def test_get_task(self, engine, sample_task):
        """测试获取任务"""
        await engine.submit(sample_task)
        
        retrieved = engine.get_task(sample_task.id)
        assert retrieved == sample_task
    
    @pytest.mark.asyncio
    async def test_get_pending_tasks(self, engine):
        """测试获取待处理任务"""
        # 创建多个任务
        for i in range(3):
            task = Task(
                task_type=TaskType.AUTO_PROCESS,
                source_path=f"/test/file{i}.zip"
            )
            await engine.submit(task)
        
        pending = engine.get_pending_tasks()
        assert len(pending) == 3
    
    def test_task_start(self, sample_task):
        """测试任务开始"""
        sample_task.start()
        
        assert sample_task.status == TaskStatus.PROCESSING
        assert sample_task.started_at is not None
        assert sample_task.current_step == "处理中"
    
    def test_task_complete(self, sample_task):
        """测试任务完成"""
        sample_task.start()
        sample_task.complete()
        
        assert sample_task.status == TaskStatus.COMPLETED
        assert sample_task.completed_at is not None
        assert sample_task.progress == 100
    
    def test_task_fail(self, sample_task):
        """测试任务失败"""
        sample_task.start()
        sample_task.fail("测试错误")
        
        assert sample_task.status == TaskStatus.FAILED
        assert sample_task.error_message == "测试错误"
        assert sample_task.completed_at is not None
    
    def test_task_pause_resume(self, sample_task):
        """测试任务暂停和恢复"""
        sample_task.start()
        sample_task.pause()
        
        assert sample_task.status == TaskStatus.PAUSED
        
        sample_task.resume()
        assert sample_task.status == TaskStatus.PROCESSING
    
    @pytest.mark.asyncio
    async def test_pause_task_by_id(self, engine, sample_task):
        """测试通过ID暂停任务"""
        await engine.submit(sample_task)
        sample_task.start()
        
        engine.pause_task(sample_task.id)
        assert sample_task.status == TaskStatus.PAUSED
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, engine, sample_task):
        """测试取消任务"""
        await engine.submit(sample_task)
        
        engine.cancel_task(sample_task.id)
        assert sample_task.is_cancelled() is True
    
    def test_task_update_progress(self, sample_task):
        """测试更新进度"""
        sample_task.update_progress(50, "测试中")
        
        assert sample_task.progress == 50
        assert sample_task.current_step == "测试中"
    
    @pytest.mark.asyncio
    async def test_wait_if_paused(self, sample_task):
        """测试暂停等待"""
        sample_task.start()
        sample_task.pause()
        
        # 在后台恢复任务
        async def resume_later():
            await asyncio.sleep(0.1)
            sample_task.resume()
        
        asyncio.create_task(resume_later())
        
        # 应该在一段时间后恢复
        await asyncio.wait_for(sample_task.wait_if_paused(), timeout=1.0)
        
        assert sample_task.status == TaskStatus.PROCESSING
    
    def test_add_progress_callback(self, engine):
        """测试添加进度回调"""
        callback = Mock()
        engine.add_progress_callback(callback)
        
        assert callback in engine._progress_callbacks
