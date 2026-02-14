from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, Text, BigInteger, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()

class Task(Base):
    """任务表"""
    __tablename__ = 'tasks'
    
    id = Column(String(36), primary_key=True)
    type = Column(String(20))  # EXTRACT, FILTER, METADATA, RENAME, AUTO_PROCESS
    status = Column(String(20))  # PENDING, PROCESSING, PAUSED, COMPLETED, FAILED
    source_path = Column(Text)
    output_path = Column(Text)
    progress = Column(Integer, default=0)
    current_step = Column(String(100))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    task_metadata = Column(JSON)  # renamed from metadata to avoid SQLAlchemy reserved word
    
class WorkMetadata(Base):
    """作品元数据表"""
    __tablename__ = 'work_metadata'
    
    rjcode = Column(String(20), primary_key=True)
    work_name = Column(Text)
    maker_id = Column(String(20))
    maker_name = Column(Text)
    release_date = Column(String(20))
    series_name = Column(Text)
    series_id = Column(String(20))
    age_category = Column(String(10))
    tags = Column(JSON)  # 列表
    cvs = Column(JSON)   # 列表
    cover_url = Column(Text)
    cached_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'rjcode': self.rjcode,
            'work_name': self.work_name,
            'maker_id': self.maker_id,
            'maker_name': self.maker_name,
            'release_date': self.release_date,
            'series_name': self.series_name,
            'series_id': self.series_id,
            'age_category': self.age_category,
            'tags': self.tags,
            'cvs': self.cvs,
            'cover_url': self.cover_url,
            'cached_at': self.cached_at.isoformat() if self.cached_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }

class LibrarySnapshot(Base):
    """库存快照表"""
    __tablename__ = 'library_snapshot'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    rjcode = Column(String(20), unique=True, index=True)
    folder_path = Column(Text)
    folder_size = Column(BigInteger)
    file_count = Column(Integer)
    scanned_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_rjcode', 'rjcode'),
    )

class ExistingFolderCache(Base):
    """已有文件夹扫描缓存表"""
    __tablename__ = 'existing_folder_cache'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    folder_path = Column(Text, unique=True, index=True)  # 文件夹完整路径
    folder_name = Column(String(255))  # 文件夹名称
    rjcode = Column(String(20), index=True)  # RJ号
    
    # 查重信息（JSON格式存储）
    duplicate_info = Column(JSON, default=None)  # 查重结果
    conflict_count = Column(Integer, default=0)  # 冲突数量
    
    # 元数据
    file_count = Column(Integer, default=0)  # 文件数量
    folder_size = Column(BigInteger, default=0)  # 文件夹大小
    
    # 缓存时间
    cached_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 是否需要刷新
    needs_refresh = Column(Boolean, default=False)
    
    __table_args__ = (
        Index('idx_existing_folder_path', 'folder_path'),
        Index('idx_existing_rjcode', 'rjcode'),
        Index('idx_existing_cached_at', 'cached_at'),
    )

class ConflictWork(Base):
    """问题作品表"""
    __tablename__ = 'conflict_works'
    
    id = Column(String(36), primary_key=True)
    task_id = Column(String(36))
    rjcode = Column(String(20))
    conflict_type = Column(String(30))  # DUPLICATE, LANGUAGE_VARIANT, MULTIPLE_VERSIONS, LINKED_WORK
    existing_path = Column(Text)
    new_path = Column(Text)
    new_metadata = Column(JSON)
    status = Column(String(20), default='PENDING')  # PENDING, KEEP_NEW, KEEP_OLD, MERGE, SKIP, KEEP_BOTH
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关联作品信息（新增）
    linked_works_info = Column(JSON, default=list)  # 发现的关联作品列表
    analysis_info = Column(JSON, default=dict)  # 详细分析报告
    related_rjcodes = Column(JSON, default=list)  # 所有关联的 RJ 号

class WorkLinkage(Base):
    """作品关联表 - 存储作品关联链"""
    __tablename__ = 'work_linkages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    original_rjcode = Column(String(20), index=True)  # 原作品 RJ 号
    linked_rjcode = Column(String(20), index=True)   # 关联作品 RJ 号
    work_type = Column(String(20))  # original, parent, child
    lang = Column(String(20))       # 语言代码
    cached_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)   # 缓存过期时间
    
    __table_args__ = (
        Index('idx_original_linked', 'original_rjcode', 'linked_rjcode'),
    )

class KikoeruSearchConfig(Base):
    """Kikoeru 搜索配置表"""
    __tablename__ = 'kikoeru_search_configs'
    
    id = Column(String(36), primary_key=True)
    name = Column(String(100), default='Kikoeru')  # 配置名称
    search_url_template = Column(Text)  # 搜索 URL 模板，如 http://xxx/api/search?keyword=%s
    show_url_template = Column(Text)   # 显示 URL 模板，如 http://xxx/works?keyword=%s
    enabled = Column(Boolean, default=False)
    custom_headers = Column(JSON, default=dict)  # 自定义请求头
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'search_url_template': self.search_url_template,
            'show_url_template': self.show_url_template,
            'enabled': self.enabled,
            'custom_headers': self.custom_headers or {},
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ProcessedArchive(Base):
    """已处理压缩包表"""
    __tablename__ = 'processed_archives'
    
    id = Column(String(36), primary_key=True)
    original_path = Column(Text)  # 原始路径
    current_path = Column(Text)   # 当前路径（在processed目录中）
    filename = Column(Text)       # 文件名
    rjcode = Column(String(20), index=True)  # RJ号
    file_size = Column(BigInteger)  # 文件大小
    processed_at = Column(DateTime, default=datetime.utcnow)  # 最后处理时间
    process_count = Column(Integer, default=1)  # 处理次数
    task_id = Column(String(36))  # 关联的任务ID
    status = Column(String(20), default='completed')  # completed, reprocessing
    
    __table_args__ = (
        Index('idx_filename', 'filename'),  # 文件名索引用于去重查询
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'original_path': self.original_path,
            'current_path': self.current_path,
            'filename': self.filename,
            'rjcode': self.rjcode,
            'file_size': self.file_size,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'process_count': self.process_count,
            'task_id': self.task_id,
            'status': self.status
        }

class PasswordEntry(Base):
    """密码库表 - 存储解压密码"""
    __tablename__ = 'password_entries'
    
    id = Column(String(36), primary_key=True)
    rjcode = Column(String(20), index=True)  # RJ号（可选，用于关联作品）
    filename = Column(String(255), index=True)  # 文件名（可选，用于关联特定文件）
    password = Column(String(255), nullable=False)  # 密码
    description = Column(Text)  # 描述/备注
    source = Column(String(50), default='manual')  # 来源：manual手动, batch批量导入, auto自动提取
    use_count = Column(Integer, default=0)  # 使用次数
    last_used_at = Column(DateTime)  # 最后使用时间
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_password_rjcode', 'rjcode'),
        Index('idx_password_filename', 'filename'),
    )
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'rjcode': self.rjcode,
            'filename': self.filename,
            'password': self.password,
            'description': self.description,
            'source': self.source,
            'use_count': self.use_count,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class WatcherConfig(Base):
    """监视器配置表"""
    __tablename__ = 'watcher_config'

    id = Column(Integer, primary_key=True)
    watch_path = Column(Text)
    scan_interval = Column(Integer, default=30)
    auto_start = Column(Boolean, default=True)
    auto_classify = Column(Boolean, default=True)
    delete_after_process = Column(Boolean, default=False)
    is_running = Column(Boolean, default=False)

class PasswordCleanupLog(Base):
    """密码清理日志表"""
    __tablename__ = 'password_cleanup_logs'

    id = Column(String(36), primary_key=True)
    deleted_count = Column(Integer, default=0)  # 删除的密码数量
    config_snapshot = Column(JSON)  # 执行时的配置快照
    deleted_passwords_summary = Column(JSON)  # 删除的密码摘要（不包含完整密码）
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'deleted_count': self.deleted_count,
            'config_snapshot': self.config_snapshot,
            'deleted_passwords_summary': self.deleted_passwords_summary,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ProcessedArchiveCleanupLog(Base):
    """已处理压缩包清理日志表"""
    __tablename__ = 'processed_archive_cleanup_logs'

    id = Column(String(36), primary_key=True)
    deleted_count = Column(Integer, default=0)  # 删除的压缩包数量
    freed_space_bytes = Column(BigInteger, default=0)  # 释放的空间（字节）
    config_snapshot = Column(JSON)  # 执行时的配置快照
    deleted_archives_summary = Column(JSON)  # 删除的压缩包摘要
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'deleted_count': self.deleted_count,
            'freed_space_bytes': self.freed_space_bytes,
            'freed_space_mb': self.freed_space_bytes / (1024 * 1024) if self.freed_space_bytes else 0,
            'config_snapshot': self.config_snapshot,
            'deleted_archives_summary': self.deleted_archives_summary,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# 数据库连接
def get_db_path():
    data_dir = os.environ.get('DATA_PATH', './data')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'cache.db')

# 数据库连接，确保支持UTF-8
engine = create_engine(
    f'sqlite:///{get_db_path()}',
    connect_args={
        'check_same_thread': False,
    },
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
