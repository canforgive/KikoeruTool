import os
import yaml
import logging
from typing import Optional
from pydantic import BaseModel, root_validator

class StorageConfig(BaseModel):
    """存储路径配置"""
    input_path: str = "/input"
    temp_path: str = "/temp"
    library_path: str = "/library"
    processed_archives_path: str = "/processed"
    existing_folders_path: str = "/existing"  # 已存在文件夹目录（非软件解压的文件夹）

class ClassificationRule(BaseModel):
    """分类规则"""
    type: str  # none, maker, series, rjcode
    enabled: bool = True
    path_template: str = ""  # 通用路径模板
    custom_name: Optional[str] = None  # 自定义目录名称（用于RJ号分类）
    fallback: Optional[str] = None
    max_tags: Optional[int] = None
    rjcode_range: Optional[str] = None  # RJ号范围，例如 "RJ01400000-RJ01499999"

class ProcessingConfig(BaseModel):
    """处理配置"""
    max_workers: int = 4
    retry_count: int = 3
    file_stable_checks: int = 3
    file_stable_interval: int = 2
    max_wait_time: int = 3600

class WatcherConfig(BaseModel):
    """监视器配置"""
    enabled: bool = True
    scan_interval: int = 30
    auto_start: bool = True
    auto_classify: bool = True
    delete_after_process: bool = False

class ExtractConfig(BaseModel):
    """解压配置"""
    seven_zip_path: str = "7z"
    auto_repair_extension: bool = True
    verify_after_extract: bool = True
    password_list: list = []
    extract_nested_archives: bool = True  # 是否解压嵌套压缩包
    max_nested_depth: int = 5  # 最大嵌套深度

class FilterRule(BaseModel):
    """过滤规则"""
    name: str
    pattern: str
    target: str = "file"  # file, folder, all
    action: str = "exclude"  # exclude, include
    enabled: bool = True

class FilterConfig(BaseModel):
    """过滤配置"""
    enabled: bool = True
    filter_dir: bool = True
    rules: list[FilterRule] = []

class MetadataConfig(BaseModel):
    """元数据配置"""
    locale: str = "zh_cn"
    connect_timeout: int = 10
    read_timeout: int = 10
    sleep_interval: int = 3
    http_proxy: Optional[str] = None
    cache_enabled: bool = True
    fetch_cover: bool = True
    make_folder_icon: bool = True
    remove_jpg_file: bool = True

class RenameConfig(BaseModel):
    """重命名配置"""
    template: str = "{rjcode} {work_name}"
    date_format: str = "%y%m%d"
    delimiter: str = " "
    cv_list_left: str = "(CV "
    cv_list_right: str = ")"
    exclude_square_brackets: bool = False
    illegal_char_to_full_width: bool = False
    tags_max_number: int = 5
    tags_ordered_list: list = []
    flatten_single_subfolder: bool = True  # 启用扁平化单一层级文件夹
    flatten_depth: int = 3  # 扁平化深度，最多处理多少层嵌套的单子文件夹（默认3层）
    remove_empty_folders: bool = True  # 过滤后是否移除空文件夹
    api_rename_follow_template: bool = False  # API重命名是否遵循重命名模板

class PasswordCleanupConfig(BaseModel):
    """密码库智能清理配置"""
    enabled: bool = False  # 是否启用智能清理
    max_use_count: int = 1  # 使用次数阈值，小于等于此值的密码将被清理
    cron_expression: str = "0 0 * * 0"  # Cron表达式，默认每周日午夜执行
    preserve_days: int = 30  # 保留天数，密码创建后超过此天数且使用次数<=阈值才删除
    exclude_sources: list = []  # 排除的来源类型，如 ["manual"] 表示不删除手动添加的密码

class ProcessedArchiveCleanupConfig(BaseModel):
    """已处理压缩包智能清理配置"""
    enabled: bool = False  # 是否启用智能清理
    cron_expression: str = "0 1 * * 0"  # Cron表达式，默认每周日凌晨1点执行
    # 清理策略（多选）
    strategy: str = "age"  # age: 按时间, count: 按数量, size: 按容量
    # 按时间清理
    preserve_days: int = 30  # 保留天数，处理超过此天数的压缩包
    # 按数量清理
    max_count: int = 1000  # 最大保留数量，超过此数量删除最旧的
    # 按容量清理
    max_size_gb: float = 50.0  # 最大占用空间(GB)，超过此容量删除最旧的
    # 其他选项
    exclude_reprocessing: bool = True  # 是否排除正在重新处理的压缩包

class PathMappingRule(BaseModel):
    """路径映射规则"""
    remote_path: str  # 远程/Docker中的路径，如 /viocelink
    local_path: str   # 本地映射路径，如 W:\Viocelink 或 \\server\share
    enabled: bool = True

class PathMappingConfig(BaseModel):
    """路径映射配置"""
    enabled: bool = False  # 是否启用路径映射
    rules: list[PathMappingRule] = []  # 映射规则列表
    # 打开方式
    open_mode: str = "auto"  # auto: 自动判断, direct: 直接打开(同设备), mapped: 使用映射路径(跨设备)

class KikoeruServerConfig(BaseModel):
    """Kikoeru 服务器查重配置"""
    enabled: bool = False  # 是否启用 Kikoeru 服务器查重
    server_url: str = ""   # Kikoeru 服务器地址，如 http://192.168.1.100:8088
    api_token: str = ""    # API 访问令牌
    timeout: int = 10      # 请求超时(秒)
    cache_ttl: int = 300   # 缓存时间(秒)

class AppConfig(BaseModel):
    """应用配置"""
    storage: StorageConfig = StorageConfig()
    processing: ProcessingConfig = ProcessingConfig()
    watcher: WatcherConfig = WatcherConfig()
    extract: ExtractConfig = ExtractConfig()
    filter: FilterConfig = FilterConfig(
        enabled=True,
        filter_dir=True,
        rules=[
            FilterRule(name="过滤无SE的WAV文件", pattern="(?:SE|音|音效)(?:[な無]し|CUT).*\.WAV$", target="file", action="exclude", enabled=True),
            FilterRule(name="过滤MP3文件", pattern="\.mp3$", target="file", action="exclude", enabled=False),
        ]
    )
    metadata: MetadataConfig = MetadataConfig()
    rename: RenameConfig = RenameConfig()
    classification: list[ClassificationRule] = [
        ClassificationRule(type="none", enabled=True, path_template="", custom_name=None, fallback=None, max_tags=None, rjcode_range=None),
    ]
    password_cleanup: PasswordCleanupConfig = PasswordCleanupConfig()
    processed_archive_cleanup: ProcessedArchiveCleanupConfig = ProcessedArchiveCleanupConfig()
    path_mapping: PathMappingConfig = PathMappingConfig()
    kikoeru_server: KikoeruServerConfig = KikoeruServerConfig()

# 全局配置实例
_config: Optional[AppConfig] = None

def load_config(config_path: str = None) -> AppConfig:
    """加载配置"""
    global _config
    logger = logging.getLogger(__name__)
    
    if config_path is None:
        # 优先从环境变量读取配置路径
        env_config_path = os.environ.get('CONFIG_PATH')
        if env_config_path:
            config_path = env_config_path
            logger.info(f"从环境变量 CONFIG_PATH 读取配置路径: {config_path}")
        else:
            # 根据当前文件位置确定配置路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 从 backend/app/config/settings.py 到项目根目录
            project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
            config_path = os.path.join(project_root, 'config', 'config.yaml')
    
    logger.info(f"加载配置文件: {config_path}")
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            logger.info(f"YAML 加载的原始数据: {config_data}")
            logger.info(f"YAML 中的 classification: {config_data.get('classification')}")
            logger.info(f"YAML 中的 classification 数量: {len(config_data.get('classification', []))}")
            if 'classification' in config_data and config_data['classification']:
                validated_rules = []
                for rule_data in config_data['classification']:
                    try:
                        # 确保所有必需字段都有值
                        rule_data_cleaned = dict(rule_data)  # 复制原始数据
                        
                        # path_template 可以是空字符串，不要转为 None
                        if 'path_template' not in rule_data_cleaned or rule_data_cleaned['path_template'] is None:
                            rule_data_cleaned['path_template'] = ''
                        
                        # 其他 None 值处理
                        for k, v in rule_data_cleaned.items():
                            if v is None and k not in ['path_template', 'custom_name', 'fallback', 'rjcode_range']:
                                # 这些字段允许为 None
                                pass
                        
                        rule = ClassificationRule(**rule_data_cleaned)
                        validated_rules.append(rule)
                    except Exception as e:
                        logger.warning(f"分类规则加载失败: {rule_data}, 错误: {e}, 使用默认规则")
                if validated_rules:
                    config_data['classification'] = [r.model_dump() for r in validated_rules]
                else:
                    config_data['classification'] = [
                        ClassificationRule(type="none", enabled=True, path_template="", custom_name=None, fallback=None, max_tags=None, rjcode_range=None).model_dump()
                    ]
            
            # 确保 filter.rules 字段格式正确
            if 'filter' in config_data and config_data['filter'] and 'rules' in config_data['filter'] and config_data['filter']['rules']:
                validated_filter_rules = []
                for rule_data in config_data['filter']['rules']:
                    try:
                        # 确保 target 字段存在
                        if 'target' not in rule_data or not rule_data['target']:
                            rule_data['target'] = 'file'
                        rule = FilterRule(**rule_data)
                        validated_filter_rules.append(rule)
                    except Exception as e:
                        logger.warning(f"过滤规则加载失败: {rule_data}, 错误: {e}, 跳过此规则")
                if validated_filter_rules:
                    config_data['filter']['rules'] = [r.model_dump() for r in validated_filter_rules]
            
            # 确保 rename 配置完整（兼容旧配置）
            if 'rename' in config_data:
                # 如果 flatten_single_subfolder 未设置，默认为 True
                if 'flatten_single_subfolder' not in config_data['rename']:
                    config_data['rename']['flatten_single_subfolder'] = True
                    logger.info("添加缺失的 flatten_single_subfolder 配置，默认为 True")
                # 如果 flatten_depth 未设置，默认为 3
                if 'flatten_depth' not in config_data['rename']:
                    config_data['rename']['flatten_depth'] = 3
                    logger.info("添加缺失的 flatten_depth 配置，默认为 3")
                # 如果 remove_empty_folders 未设置，默认为 True
                if 'remove_empty_folders' not in config_data['rename']:
                    config_data['rename']['remove_empty_folders'] = True
                    logger.info("添加缺失的 remove_empty_folders 配置，默认为 True")
                # 如果 api_rename_follow_template 未设置，默认为 False
                if 'api_rename_follow_template' not in config_data['rename']:
                    config_data['rename']['api_rename_follow_template'] = False
                    logger.info("添加缺失的 api_rename_follow_template 配置，默认为 False")
                # 记录模板值用于调试
                logger.info(f"[CONFIG] rename.template = '{config_data['rename'].get('template', 'NOT SET')}'")

            # 确保 password_cleanup 配置完整（兼容旧配置）
            if 'password_cleanup' not in config_data or not config_data['password_cleanup']:
                config_data['password_cleanup'] = {
                    'enabled': False,
                    'max_use_count': 1,
                    'cron_expression': '0 0 * * 0',
                    'preserve_days': 30,
                    'exclude_sources': []
                }
                logger.info("添加缺失的 password_cleanup 配置，使用默认值")
            else:
                # 确保所有字段都存在
                if 'enabled' not in config_data['password_cleanup']:
                    config_data['password_cleanup']['enabled'] = False
                if 'max_use_count' not in config_data['password_cleanup']:
                    config_data['password_cleanup']['max_use_count'] = 1
                if 'cron_expression' not in config_data['password_cleanup']:
                    config_data['password_cleanup']['cron_expression'] = '0 0 * * 0'
                if 'preserve_days' not in config_data['password_cleanup']:
                    config_data['password_cleanup']['preserve_days'] = 30
                if 'exclude_sources' not in config_data['password_cleanup']:
                    config_data['password_cleanup']['exclude_sources'] = []

            # 确保 processed_archive_cleanup 配置完整（兼容旧配置）
            if 'processed_archive_cleanup' not in config_data or not config_data['processed_archive_cleanup']:
                config_data['processed_archive_cleanup'] = {
                    'enabled': False,
                    'strategy': 'age',
                    'cron_expression': '0 1 * * 0',
                    'preserve_days': 30,
                    'max_count': 1000,
                    'max_size_gb': 50,
                    'exclude_reprocessing': True
                }
                logger.info("添加缺失的 processed_archive_cleanup 配置，使用默认值")
            else:
                # 确保所有字段都存在
                if 'enabled' not in config_data['processed_archive_cleanup']:
                    config_data['processed_archive_cleanup']['enabled'] = False
                if 'strategy' not in config_data['processed_archive_cleanup']:
                    config_data['processed_archive_cleanup']['strategy'] = 'age'
                if 'cron_expression' not in config_data['processed_archive_cleanup']:
                    config_data['processed_archive_cleanup']['cron_expression'] = '0 1 * * 0'
                if 'preserve_days' not in config_data['processed_archive_cleanup']:
                    config_data['processed_archive_cleanup']['preserve_days'] = 30
                if 'max_count' not in config_data['processed_archive_cleanup']:
                    config_data['processed_archive_cleanup']['max_count'] = 1000
                if 'max_size_gb' not in config_data['processed_archive_cleanup']:
                    config_data['processed_archive_cleanup']['max_size_gb'] = 50
                if 'exclude_reprocessing' not in config_data['processed_archive_cleanup']:
                    config_data['processed_archive_cleanup']['exclude_reprocessing'] = True

            _config = AppConfig(**config_data)
            logger.info(f"[CONFIG] 加载后 template = '{_config.rename.template}'")
            logger.info(f"AppConfig 创建成功")
            logger.info(f"AppConfig 中的 classification: {_config.classification}")
            logger.info(f"AppConfig 中的 classification 数量: {len(_config.classification)}")
            for i, rule in enumerate(_config.classification):
                logger.info(f"规则 {i}: type={rule.type}, enabled={rule.enabled}, custom_name={rule.custom_name}")
        except Exception as e:
            logger.error(f"配置文件加载失败，使用默认配置: {e}")
            _config = AppConfig()
    else:
        logger.info("配置文件不存在，使用默认配置")
        _config = AppConfig()
        # 保存默认配置
        config_dir = os.path.dirname(config_path)
        os.makedirs(config_dir, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(_config.model_dump(), f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        logger.info(f"默认配置已保存到: {config_path}")
    
    return _config

def get_config() -> AppConfig:
    """获取配置"""
    if _config is None:
        return load_config()
    return _config

def deep_merge(base: dict, update: dict) -> dict:
    """深度合并两个字典"""
    result = base.copy()
    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result

def save_config(config_data: dict, config_path: str = None) -> AppConfig:
    """保存配置到文件（支持部分更新）"""
    global _config
    
    logger = logging.getLogger(__name__)
    
    if config_path is None:
        env_config_path = os.environ.get('CONFIG_PATH')
        if env_config_path:
            config_path = env_config_path
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
            config_path = os.path.join(project_root, 'config', 'config.yaml')
    
    config_path = os.path.abspath(config_path)
    logger.info(f"保存配置到: {config_path}")
    
    # 确保目录存在
    config_dir = os.path.dirname(config_path)
    os.makedirs(config_dir, exist_ok=True)
    
    try:
        # 读取现有配置（如果存在）
        existing_config = {}
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                existing_config = yaml.safe_load(f) or {}
                logger.info(f"读取现有配置: {len(existing_config)} 个顶层键")
        
        # 深度合并配置
        merged_config = deep_merge(existing_config, config_data)
        logger.info(f"合并后配置: {len(merged_config)} 个顶层键")
        
        # 验证配置有效性（尝试创建 AppConfig）
        try:
            test_config = AppConfig(**merged_config)
            logger.info("配置验证通过")
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            # 如果验证失败，尝试使用当前内存中的配置作为基础
            if _config:
                current_dict = _config.model_dump()
                merged_config = deep_merge(current_dict, config_data)
                test_config = AppConfig(**merged_config)
                logger.info("使用内存配置作为基础后验证通过")
        
        # 写入文件
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(merged_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        # 更新内存中的配置
        _config = AppConfig(**merged_config)
        logger.info("配置已成功保存并更新")
        
        return _config
        
    except Exception as e:
        logger.error(f"保存配置失败: {e}")
        raise

def reload_config() -> AppConfig:
    """重新加载配置（用于配置变更后）"""
    global _config
    config_path = os.environ.get('CONFIG_PATH', './config/config.yaml')
    
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            _config = AppConfig(**config_data)
    
    return _config
