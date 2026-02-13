#!/usr/bin/env python3
"""
Prekikoeru 桌面应用入口
用于 Windows 打包
"""
import sys
import os
import subprocess
import webbrowser
import time
import signal

def main():
    """主函数"""
    # 设置环境变量
    os.environ['CONFIG_PATH'] = os.path.join(os.path.dirname(sys.executable), 'config', 'config.yaml')
    os.environ['DATA_PATH'] = os.path.join(os.path.dirname(sys.executable), 'data')
    
    # 确保目录存在
    os.makedirs(os.environ['DATA_PATH'], exist_ok=True)
    
    print("=" * 50)
    print("Prekikoeru - DLsite 作品整理工具")
    print("=" * 50)
    print()
    print("正在启动服务...")
    
    # 启动后端服务
    try:
        import uvicorn
        from app.api.routes import app
        
        # 在浏览器中打开
        time.sleep(2)
        webbrowser.open('http://localhost:8000')
        
        print("服务已启动，正在浏览器中打开...")
        print("按 Ctrl+C 停止服务")
        print()
        
        # 运行服务
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        
    except KeyboardInterrupt:
        print("\n正在停止服务...")
    except Exception as e:
        print(f"启动失败: {e}")
        input("按 Enter 键退出...")

if __name__ == "__main__":
    main()
