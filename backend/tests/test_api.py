"""
API 路由测试
"""
import pytest
from fastapi.testclient import TestClient

def test_health_check(client: TestClient):
    """测试健康检查端点"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_tasks_empty(client: TestClient):
    """测试获取空任务列表"""
    response = client.get("/api/tasks")
    assert response.status_code == 200
    assert response.json() == []

def test_create_task(client: TestClient):
    """测试创建任务"""
    task_data = {
        "source_path": "/test/path/file.zip",
        "task_type": "auto_process",
        "auto_classify": True
    }
    response = client.post("/api/tasks", json=task_data)
    assert response.status_code == 200
    data = response.json()
    assert data["source_path"] == task_data["source_path"]
    assert data["type"] == task_data["task_type"]
    assert "id" in data

def test_get_task_by_id(client: TestClient):
    """测试根据ID获取任务"""
    # 先创建任务
    task_data = {
        "source_path": "/test/path/file.zip",
        "task_type": "auto_process"
    }
    create_response = client.post("/api/tasks", json=task_data)
    task_id = create_response.json()["id"]
    
    # 获取任务
    response = client.get(f"/api/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["id"] == task_id

def test_get_task_not_found(client: TestClient):
    """测试获取不存在的任务"""
    response = client.get("/api/tasks/non-existent-id")
    assert response.status_code == 404

def test_pause_task(client: TestClient):
    """测试暂停任务"""
    # 创建任务
    task_data = {"source_path": "/test/file.zip"}
    create_response = client.post("/api/tasks", json=task_data)
    task_id = create_response.json()["id"]
    
    # 暂停任务
    response = client.post(f"/api/tasks/{task_id}/pause")
    assert response.status_code == 200
    assert response.json()["message"] == "任务已暂停"

def test_get_config(client: TestClient):
    """测试获取配置"""
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "storage" in data
    assert "watcher" in data
    assert "processing" in data

def test_watcher_start_stop(client: TestClient):
    """测试监视器启动和停止"""
    # 启动监视器
    start_response = client.post("/api/watcher/start")
    assert start_response.status_code == 200
    
    # 获取状态
    status_response = client.get("/api/watcher/status")
    assert status_response.status_code == 200
    
    # 停止监视器
    stop_response = client.post("/api/watcher/stop")
    assert stop_response.status_code == 200
