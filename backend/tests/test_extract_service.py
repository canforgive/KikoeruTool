"""
解压服务测试
"""
import pytest
import os
import tempfile
import zipfile
from unittest.mock import Mock, patch

from app.core.extract_service import ExtractService
from app.core.task_engine import Task

class TestExtractService:
    """测试解压服务"""
    
    @pytest.fixture
    def extract_service(self):
        """创建解压服务实例"""
        return ExtractService()
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def create_test_zip(self, path, password=None):
        """创建测试ZIP文件"""
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('test.txt', 'test content')
            zf.writestr('test_dir/nested.txt', 'nested content')
    
    @pytest.mark.asyncio
    async def test_detect_real_type_zip(self, extract_service, temp_dir):
        """测试检测ZIP文件类型"""
        zip_path = os.path.join(temp_dir, 'test.zip')
        self.create_test_zip(zip_path)
        
        file_type = await extract_service._detect_real_type(zip_path)
        assert file_type == 'zip'
    
    @pytest.mark.asyncio
    async def test_repair_extension(self, extract_service, temp_dir):
        """测试修复文件后缀名"""
        # 创建错误后缀名的文件
        wrong_path = os.path.join(temp_dir, 'test.zi')
        correct_path = os.path.join(temp_dir, 'test.zip')
        self.create_test_zip(wrong_path)
        
        # 修复后缀名
        result = await extract_service._repair_extension(wrong_path)
        
        # 验证
        assert result == correct_path
        assert os.path.exists(correct_path)
        assert not os.path.exists(wrong_path)
    
    @pytest.mark.asyncio
    async def test_detect_volume_set(self, extract_service, temp_dir):
        """测试检测分卷压缩包"""
        # 创建分卷文件
        base_path = os.path.join(temp_dir, 'test')
        for i in range(1, 4):
            with open(f"{base_path}.part{i}.rar", 'w') as f:
                f.write(f"part {i}")
        
        first_volume = f"{base_path}.part1.rar"
        volume_set = extract_service._detect_volume_set(first_volume)
        
        assert volume_set is not None
        assert len(volume_set.volumes) == 3
    
    @pytest.mark.asyncio
    async def test_get_archive_info(self, extract_service, temp_dir):
        """测试获取压缩包信息"""
        zip_path = os.path.join(temp_dir, 'test.zip')
        self.create_test_zip(zip_path)
        
        archive_info = await extract_service._get_archive_info(zip_path)
        
        assert archive_info is not None
        assert len(archive_info.file_list) == 2
        assert any(f['name'] == 'test.txt' for f in archive_info.file_list)
    
    @pytest.mark.asyncio
    async def test_verify_extraction(self, extract_service, temp_dir):
        """测试解压验证"""
        # 创建压缩包
        zip_path = os.path.join(temp_dir, 'test.zip')
        self.create_test_zip(zip_path)
        
        # 获取文件信息
        archive_info = await extract_service._get_archive_info(zip_path)
        
        # 解压
        import subprocess
        output_path = os.path.join(temp_dir, 'output')
        os.makedirs(output_path, exist_ok=True)
        subprocess.run(['unzip', zip_path, '-d', output_path], check=True)
        
        # 验证
        result = await extract_service._verify_extraction(archive_info, output_path)
        assert result is True

    @pytest.mark.asyncio
    async def test_extract_task(self, extract_service, temp_dir):
        """测试完整的解压任务"""
        # 创建测试压缩包
        zip_path = os.path.join(temp_dir, 'RJ123456.zip')
        self.create_test_zip(zip_path)
        
        # 创建任务
        task = Mock(spec=Task)
        task.source_path = zip_path
        task.update_progress = Mock()
        
        # 执行解压
        output_path = await extract_service.extract(task)
        
        # 验证
        assert output_path is not None
        assert os.path.exists(output_path)
        assert task.update_progress.called
