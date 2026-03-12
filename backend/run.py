import os
import sys
import logging
import uvicorn
import threading
import webbrowser
import time
import signal
import socket

IS_FROZEN = getattr(sys, 'frozen', False)

# 全局变量存储实际使用的端口
ACTUAL_PORT = 8000

def get_base_path():
    if IS_FROZEN:
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def get_exe_dir():
    if IS_FROZEN:
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def setup_paths():
    base_path = get_base_path()
    backend_path = os.path.join(base_path, 'app')
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    
    if IS_FROZEN:
        exe_dir = get_exe_dir()
        data_dir = os.path.join(exe_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        os.makedirs(os.path.join(data_dir, 'config'), exist_ok=True)
        
        os.environ['DATA_PATH'] = data_dir
        os.environ['CONFIG_PATH'] = os.path.join(data_dir, 'config', 'config.yaml')

def setup_logging():
    log_dir = os.environ.get('DATA_PATH', './data')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'app.log')
    
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = []
    root_logger.addHandler(file_handler)
    
    if sys.stdout:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)

def init_database():
    from app.models.database import init_db, engine
    from sqlalchemy import text
    
    init_db()
    
    with engine.connect() as conn:
        conn.execute(text("PRAGMA encoding='UTF-8'"))
        conn.commit()
    
    logger = logging.getLogger(__name__)
    logger.info("数据库初始化完成")

def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """检查端口是否可用（是否可以绑定）"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            # 绑定成功说明端口可用
            return True
    except OSError:
        # 绑定失败说明端口被占用
        return False

def find_available_port(start_port: int = 8000, max_attempts: int = 100) -> int:
    """从指定端口开始查找可用端口"""
    global ACTUAL_PORT
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port):
            ACTUAL_PORT = port
            return port
    raise RuntimeError(f"无法找到可用端口 (尝试了 {start_port} 到 {start_port + max_attempts - 1})")

def get_server_url() -> str:
    """获取服务器URL"""
    return f"http://localhost:{ACTUAL_PORT}"

def open_browser():
    time.sleep(1.5)
    webbrowser.open(get_server_url())

def create_tray_icon(stop_event):
    try:
        import pystray
        from PIL import Image, ImageDraw
        
        def create_icon_image():
            img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse([8, 8, 56, 56], fill=(66, 133, 244, 255))
            draw.text((18, 22), "P", fill=(255, 255, 255, 255))
            return img
        
        def on_exit(icon, item):
            stop_event.set()
            icon.stop()
        
        def on_open(icon, item):
            webbrowser.open(get_server_url())
        
        icon = pystray.Icon(
            "prekikoeru",
            create_icon_image(),
            "Prekikoeru",
            menu=pystray.Menu(
                pystray.MenuItem("打开 Web 界面", on_open, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", on_exit)
            )
        )
        
        icon.run()
    except Exception as e:
        logging.getLogger(__name__).error(f"系统托盘初始化失败: {e}")

def main():
    global ACTUAL_PORT
    setup_paths()
    setup_logging()

    base_path = get_base_path()
    frontend_path = os.path.join(base_path, 'frontend', 'dist')
    os.environ['FRONTEND_PATH'] = frontend_path

    logger = logging.getLogger(__name__)
    logger.info("="*50)
    logger.info("Prekikoeru 启动中...")
    logger.info(f"基础路径: {base_path}")
    logger.info(f"前端路径: {frontend_path}")
    logger.info(f"打包模式: {IS_FROZEN}")
    if IS_FROZEN:
        logger.info(f"EXE目录: {get_exe_dir()}")
        logger.info(f"数据目录: {os.environ.get('DATA_PATH')}")
        logger.info(f"配置文件: {os.environ.get('CONFIG_PATH')}")
    logger.info("="*50)

    # 查找可用端口
    try:
        port = find_available_port(8000)
        if port != 8000:
            logger.warning(f"端口 8000 已被占用，自动切换到端口 {port}")
            print(f"\n[提示] 端口 8000 已被占用，自动切换到端口 {port}")
        logger.info(f"使用端口: {port}")
        print(f"服务地址: {get_server_url()}")
    except RuntimeError as e:
        logger.error(str(e))
        print(f"错误: {e}")
        sys.exit(1)

    init_database()

    from app.api.routes import app

    stop_event = threading.Event()

    if IS_FROZEN:
        tray_thread = threading.Thread(
            target=create_tray_icon,
            args=(stop_event,),
            daemon=True
        )
        tray_thread.start()

        threading.Thread(target=open_browser, daemon=True).start()

    def check_stop():
        while not stop_event.is_set():
            stop_event.wait(0.5)
        os.kill(os.getpid(), signal.SIGTERM)

    if IS_FROZEN:
        threading.Thread(target=check_stop, daemon=True).start()

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=ACTUAL_PORT,
        log_level="warning",
        access_log=False,
        log_config=None
    )
    server = uvicorn.Server(config)
    server.run()

if __name__ == "__main__":
    main()