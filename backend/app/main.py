import os
import logging
import uvicorn
from .api.routes import app

def setup_logging():
    """设置日志"""
    # 创建日志目录
    log_dir = os.environ.get('DATA_PATH', './data')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'app.log')
    
    # 配置日志格式 - 单行格式，便于解析
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = []  # 清除现有处理器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger('uvicorn').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy').setLevel(logging.WARNING)

def init_database():
    """初始化数据库"""
    from .models.database import init_db, engine
    from sqlalchemy import text
    
    # 初始化数据库表
    init_db()
    
    # 确保SQLite使用UTF-8编码
    with engine.connect() as conn:
        conn.execute(text("PRAGMA encoding='UTF-8'"))
        conn.commit()
    
    logger = logging.getLogger(__name__)
    logger.info("数据库初始化完成，使用UTF-8编码")

def main():
    """主入口"""
    setup_logging()
    
    logger = logging.getLogger(__name__)
    logger.info("="*50)
    logger.info("Prekikoeru 启动中...")
    logger.info("="*50)
    
    # 初始化数据库
    init_database()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

if __name__ == "__main__":
    main()
