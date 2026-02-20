<template>
  <div class="settings">
    <h1 class="page-title">设置</h1>
    
    <el-form :model="config" label-position="top" v-loading="loading">
      <!-- 存储路径设置 -->
      <el-card class="setting-card">
        <template #header>
          <span>存储路径</span>
        </template>
        
        <el-alert
          title="提示：请输入完整的绝对路径，例如 D:\\MyFiles\\Input 或 /home/user/input"
          type="info"
          :closable="false"
          style="margin-bottom: 20px;"
        />
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="待处理文件夹">
              <el-input 
                v-model="config.storage.input_path" 
                placeholder="例如: D:\\prekikoeru\\test_data\\input"
              >
                <template #prefix>
                  <el-icon><Folder /></el-icon>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="临时文件夹">
              <el-input 
                v-model="config.storage.temp_path" 
                placeholder="例如: D:\\prekikoeru\\test_data\\temp"
              >
                <template #prefix>
                  <el-icon><Folder /></el-icon>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="库存文件夹">
              <el-input 
                v-model="config.storage.library_path" 
                placeholder="例如: D:\\prekikoeru\\test_data\\library"
              >
                <template #prefix>
                  <el-icon><Folder /></el-icon>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="已处理压缩包存放文件夹">
              <el-input 
                v-model="config.storage.processed_archives_path" 
                placeholder="例如: D:\\prekikoeru\\test_data\\processed"
              >
                <template #prefix>
                  <el-icon><Folder /></el-icon>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="已存在文件夹目录">
              <el-input 
                v-model="config.storage.existing_folders_path" 
                placeholder="例如: D:\\prekikoeru\\test_data\\existing"
              >
                <template #prefix>
                  <el-icon><Folder /></el-icon>
                </template>
              </el-input>
              <div class="form-tip">
                存放已解压的文件夹（非软件处理的压缩包），也以 {RJCode} {work_name} 格式命名
              </div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row>
          <el-col :span="24">
            <el-button type="primary" size="small" @click="createTestDirs">
              <el-icon><Plus /></el-icon>
              创建默认测试目录
            </el-button>
          </el-col>
        </el-row>
      </el-card>
      
      <!-- 监视器设置 -->
      <el-card class="setting-card">
        <template #header>
          <span>文件夹监视器</span>
        </template>
        
        <el-form-item label="启用监视器">
          <el-switch v-model="config.watcher.enabled" />
        </el-form-item>
        
        <el-form-item label="扫描间隔（秒）">
          <el-slider v-model="config.watcher.scan_interval" :min="10" :max="300" :step="10" show-input />
        </el-form-item>
        
        <el-form-item label="自动开始处理">
          <el-switch v-model="config.watcher.auto_start" />
        </el-form-item>
        
        <el-form-item label="自动分类">
          <el-switch v-model="config.watcher.auto_classify" />
        </el-form-item>
        
        <el-form-item label="处理后删除原文件">
          <el-switch v-model="config.watcher.delete_after_process" />
        </el-form-item>
      </el-card>
      
      <!-- 处理设置 -->
      <el-card class="setting-card">
        <template #header>
          <span>处理配置</span>
        </template>
        
        <el-form-item label="最大并发数">
          <el-slider v-model="config.processing.max_workers" :min="1" :max="10" show-input />
        </el-form-item>
        
        <el-form-item label="自动修复后缀名">
          <el-switch v-model="config.extract.auto_repair_extension" />
        </el-form-item>
        
        <el-form-item label="解压后验证">
          <el-switch v-model="config.extract.verify_after_extract" />
        </el-form-item>
        
        <el-form-item label="自动解压嵌套压缩包">
          <el-switch v-model="config.extract.extract_nested_archives" />
          <div class="form-tip">
            启用后，系统会自动检测并解压嵌套在压缩包内的其他压缩文件
          </div>
        </el-form-item>
        
        <el-form-item label="最大嵌套深度" v-if="config.extract.extract_nested_archives">
          <el-slider 
            v-model="config.extract.max_nested_depth" 
            :min="1" 
            :max="10" 
            :step="1" 
            show-input 
          />
          <div class="form-tip">
            限制嵌套压缩包的解压深度，防止无限循环。建议设置为 3-5 层
          </div>
        </el-form-item>
        
        <el-form-item label="7-Zip路径">
          <el-input 
            v-model="config.extract.seven_zip_path" 
            placeholder="例如: C:\\Program Files\\7-Zip\\7z.exe"
          >
            <template #prefix>
              <el-icon><Tools /></el-icon>
            </template>
          </el-input>
          <div class="form-tip">留空或填入"7z"将自动检测，Windows用户建议填写完整路径</div>
        </el-form-item>
        
        <el-form-item label="默认密码列表">
          <el-select
            v-model="config.extract.password_list"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入密码后按回车添加"
            style="width: 100%"
          />
        </el-form-item>
      </el-card>
      
      <!-- 过滤设置 -->
      <el-card class="setting-card">
        <template #header>
          <div class="card-header">
            <span>过滤配置</span>
            <el-switch v-model="config.filter.enabled" active-text="启用过滤" />
          </div>
        </template>
        
        <el-form-item label="过滤文件夹">
          <el-switch v-model="config.filter.filter_dir" />
        </el-form-item>
        
        <el-divider>过滤规则</el-divider>
        
        <el-alert
          title="过滤规则说明"
          type="info"
          :closable="false"
          style="margin-bottom: 15px;"
        >
          <div style="font-size: 12px; line-height: 1.6;">
            <p>• 匹配正则表达式的文件/文件夹将被<strong>删除</strong></p>
            <p>• <strong>目标</strong>：决定删除范围（文件=删单个文件，文件夹=删整个文件夹及内容！）</p>
            <p>• 处理流程：解压 → 重命名 → <strong>过滤</strong> → 扁平化 → 移动到库存</p>
          </div>
        </el-alert>
        
        <el-card shadow="never" style="margin-bottom: 15px; background-color: #f5f7fa;">
          <template #header>
            <span style="font-size: 13px; font-weight: 600;">正则示例</span>
          </template>
          <div style="font-size: 12px;">
            <p style="margin: 5px 0;"><strong>文件示例：</strong></p>
            <ul style="margin: 5px 0; padding-left: 20px;">
              <li><code>\.mp3$</code> - 删除所有MP3文件</li>
              <li><code>(?i)\.wav$</code> - 删除所有WAV文件（不区分大小写）</li>
              <li><code>^\._</code> - 删除macOS隐藏文件（以._开头）</li>
            </ul>
            <p style="margin: 10px 0 5px;"><strong>文件夹示例：</strong></p>
            <ul style="margin: 5px 0; padding-left: 20px;">
              <li><code>^__MACOSX$</code> - 删除__MACOSX文件夹</li>
              <li><code>^temp$</code> - 删除名为temp的文件夹</li>
              <li><code>sample</code> - 删除名称包含sample的文件夹</li>
            </ul>
            <p style="margin: 10px 0 5px;"><strong>全部示例：</strong></p>
            <ul style="margin: 5px 0; padding-left: 20px;">
              <li><code>thumb</code> - 删除所有包含thumb的文件和文件夹</li>
            </ul>
          </div>
        </el-card>
        
        <div v-for="(rule, index) in config.filter.rules" :key="index" class="rule-item">
          <el-card shadow="never">
            <el-row :gutter="10" align="middle">
              <el-col :span="3">
                <el-select v-model="rule.target" size="small" placeholder="目标">
                  <el-option label="文件" value="file" />
                  <el-option label="文件夹" value="folder" />
                  <el-option label="全部" value="all" />
                </el-select>
              </el-col>
              <el-col :span="5">
                <el-input v-model="rule.name" placeholder="规则名称" size="small" />
              </el-col>
              <el-col :span="10">
                <el-input v-model="rule.pattern" placeholder="正则表达式" size="small" />
              </el-col>
              <el-col :span="2">
                <el-switch v-model="rule.enabled" size="small" />
              </el-col>
              <el-col :span="2" style="text-align: right;">
                <el-button type="danger" link size="small" @click="removeFilterRule(index)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-col>
            </el-row>
            <el-row v-if="rule.pattern" style="margin-top: 5px;">
              <el-col :span="24">
                <span class="form-tip">
                  将删除{{ getTargetLabel(rule.target) }}名称匹配 "{{ rule.pattern }}" 的内容
                  <span v-if="rule.target === 'folder'" style="color: #f56c6c; margin-left: 8px;">
                    <el-icon><Warning /></el-icon> 注意：会删除整个文件夹及其所有内容！
                  </span>
                </span>
              </el-col>
            </el-row>
          </el-card>
        </div>
        
        <el-button type="primary" size="small" @click="addFilterRule" style="margin-top: 10px;">
          <el-icon><Plus /></el-icon> 添加过滤规则
        </el-button>
        
        <el-divider />
        
        <el-form-item label="自动扁平化单层文件夹">
          <el-switch v-model="config.rename.flatten_single_subfolder" />
          <div class="form-tip">
            如果文件夹内只有一个子文件夹，自动将内容移出并删除外层空文件夹。<br>
            <strong>注意：</strong>此功能在过滤完成后执行，可以处理因过滤而产生的单层文件夹结构
          </div>
        </el-form-item>

        <el-form-item label="扁平化深度" v-if="config.rename.flatten_single_subfolder">
          <el-input-number v-model="config.rename.flatten_depth" :min="1" :max="10" />
          <div class="form-tip">
            最多处理多少层嵌套的单子文件夹。例如：如果设置为3，<br>
            主文件夹 → 文件夹A → 文件夹B（B是唯一子文件夹）→ 内容，将被扁平化为主文件夹 → 内容
          </div>
        </el-form-item>

        <el-form-item label="自动移除空文件夹">
          <el-switch v-model="config.rename.remove_empty_folders" />
          <div class="form-tip">
            过滤完成后自动移除所有空文件夹（不包括根文件夹）<br>
            <strong>注意：</strong>此功能在扁平化之后执行，可以清理因过滤而产生的空文件夹
          </div>
        </el-form-item>
      </el-card>
      
      <!-- 元数据设置 -->
      <el-card class="setting-card">
        <template #header>
          <span>元数据配置</span>
        </template>
        
        <el-form-item label="语言区域">
          <el-select v-model="config.metadata.locale" style="width: 200px">
            <el-option label="简体中文" value="zh_cn" />
            <el-option label="繁体中文" value="zh_tw" />
            <el-option label="日本語" value="ja_jp" />
            <el-option label="English" value="en_us" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="启用缓存">
          <el-switch v-model="config.metadata.cache_enabled" />
        </el-form-item>
        
        <el-form-item label="下载封面">
          <el-switch v-model="config.metadata.fetch_cover" />
        </el-form-item>
        
        <el-form-item label="制作文件夹图标">
          <el-switch v-model="config.metadata.make_folder_icon" />
        </el-form-item>
        
        <el-form-item label="HTTP代理">
          <el-input v-model="config.metadata.http_proxy" placeholder="127.0.0.1:7890" />
        </el-form-item>
      </el-card>
      
      <!-- 重命名设置 -->
      <el-card class="setting-card">
        <template #header>
          <span>重命名配置</span>
        </template>
        
        <el-form-item label="重命名模板">
          <el-input v-model="config.rename.template" placeholder="{rjcode} {work_name}">
            <template #append>
              <el-tooltip content="可用变量: {rjcode}, {work_name}, {maker_name}, {cvs}, {release_date}, {tags}">
                <el-icon><QuestionFilled /></el-icon>
              </el-tooltip>
            </template>
          </el-input>
        </el-form-item>
        
        <el-form-item label="日期格式">
          <el-input v-model="config.rename.date_format" placeholder="%y%m%d" style="width: 200px" />
        </el-form-item>
        
        <el-form-item label="移除方括号内容">
          <el-switch v-model="config.rename.exclude_square_brackets" />
        </el-form-item>
        
        <el-form-item label="非法字符转全角">
          <el-switch v-model="config.rename.illegal_char_to_full_width" />
        </el-form-item>
        
        <el-form-item label="API重命名遵循模板">
          <el-switch v-model="config.rename.api_rename_follow_template" />
          <div class="form-tip">
            开启后，库存管理中的"API重命名"将使用上方的重命名模板；关闭则使用简单格式"RJ号 作品名"
          </div>
        </el-form-item>
      </el-card>
      
      <!-- 密码库智能清理 -->
      <el-card class="setting-card">
        <template #header>
          <div class="card-header">
            <span>密码库智能清理</span>
            <el-switch v-model="config.password_cleanup.enabled" active-text="启用清理" />
          </div>
        </template>

        <el-alert
          title="清理说明"
          type="info"
          :closable="false"
          style="margin-bottom: 15px;"
        >
          <div style="font-size: 12px; line-height: 1.6;">
            <p>• 系统会自动清理使用次数较少的密码，避免密码库无限膨胀</p>
            <p>• <strong>使用次数阈值</strong>：使用次数 ≤ 此值的密码将被清理</p>
            <p>• <strong>保留天数</strong>：密码创建超过此天数且使用次数 ≤ 阈值才删除</p>
            <p>• 可以使用 Cron 表达式自定义执行时间</p>
          </div>
        </el-alert>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="使用次数阈值">
              <el-slider
                v-model="config.password_cleanup.max_use_count"
                :min="0"
                :max="10"
                :step="1"
                show-input
                :disabled="!config.password_cleanup.enabled"
              />
              <div class="form-tip">
                使用次数 ≤ {{ config.password_cleanup.max_use_count }} 的密码将被清理
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保留天数">
              <el-slider
                v-model="config.password_cleanup.preserve_days"
                :min="1"
                :max="90"
                :step="1"
                show-input
                :disabled="!config.password_cleanup.enabled"
              />
              <div class="form-tip">
                密码创建后超过 {{ config.password_cleanup.preserve_days }} 天且使用次数 ≤ 阈值才删除
              </div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="Cron 表达式">
          <el-input
            v-model="config.password_cleanup.cron_expression"
            placeholder="例如: 0 0 * * 0"
            :disabled="!config.password_cleanup.enabled"
            style="width: 300px"
          >
            <template #append>
              <el-tooltip content="Cron格式：分 时 日 月 周。默认 0 0 * * 0 表示每周日午夜">
                <el-icon><QuestionFilled /></el-icon>
              </el-tooltip>
            </template>
          </el-input>
          <div class="form-tip">
            示例：0 0 * * 0（每周日午夜）、0 2 * * *（每天凌晨2点）、0 0 1 * *（每月1号）
          </div>
        </el-form-item>

        <el-form-item label="排除来源">
          <el-select
            v-model="config.password_cleanup.exclude_sources"
            multiple
            placeholder="选择要排除的密码来源"
            :disabled="!config.password_cleanup.enabled"
            style="width: 100%"
          >
            <el-option label="手动添加 (manual)" value="manual" />
            <el-option label="批量导入 (batch)" value="batch" />
            <el-option label="自动提取 (auto)" value="auto" />
          </el-select>
          <div class="form-tip">
            选中的来源类型的密码不会被清理
          </div>
        </el-form-item>

        <el-divider />

        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <el-button
            type="primary"
            size="small"
            @click="previewPasswordCleanup"
            :disabled="!config.password_cleanup.enabled"
          >
            <el-icon><View /></el-icon>
            预览清理
          </el-button>
          <el-button
            type="danger"
            size="small"
            @click="runPasswordCleanup"
            :disabled="!config.password_cleanup.enabled"
          >
            <el-icon><Delete /></el-icon>
            立即清理
          </el-button>
        </div>
      </el-card>

      <!-- 已处理压缩包智能清理 -->
      <el-card class="setting-card">
        <template #header>
          <div class="card-header">
            <span>已处理压缩包智能清理</span>
            <el-switch v-model="config.processed_archive_cleanup.enabled" active-text="启用清理" />
          </div>
        </template>

        <el-alert
          title="清理说明"
          type="info"
          :closable="false"
          style="margin-bottom: 15px;"
        >
          <div style="font-size: 12px; line-height: 1.6;">
            <p>• 系统会自动清理已处理的压缩包文件，避免磁盘空间无限占用</p>
            <p>• 支持三种清理策略：<strong>按时间</strong>、<strong>按数量</strong>、<strong>按容量</strong></p>
            <p>• 可以选择是否保留正在重新处理的压缩包</p>
          </div>
        </el-alert>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="清理策略">
              <el-select
                v-model="config.processed_archive_cleanup.strategy"
                :disabled="!config.processed_archive_cleanup.enabled"
                style="width: 100%"
              >
                <el-option label="按时间清理" value="age" />
                <el-option label="按数量清理" value="count" />
                <el-option label="按容量清理" value="size" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Cron 表达式">
              <el-input
                v-model="config.processed_archive_cleanup.cron_expression"
                placeholder="例如: 0 1 * * 0"
                :disabled="!config.processed_archive_cleanup.enabled"
              >
                <template #append>
                  <el-tooltip content="Cron格式：分 时 日 月 周。默认 0 1 * * 0 表示每周日凌晨1点">
                    <el-icon><QuestionFilled /></el-icon>
                  </el-tooltip>
                </template>
              </el-input>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 按时间清理设置 -->
        <el-form-item v-if="config.processed_archive_cleanup.strategy === 'age'" label="保留天数">
          <el-slider
            v-model="config.processed_archive_cleanup.preserve_days"
            :min="1"
            :max="365"
            :step="1"
            show-input
            :disabled="!config.processed_archive_cleanup.enabled"
          />
          <div class="form-tip">
            处理时间超过 {{ config.processed_archive_cleanup.preserve_days }} 天的压缩包将被删除
          </div>
        </el-form-item>

        <!-- 按数量清理设置 -->
        <el-form-item v-if="config.processed_archive_cleanup.strategy === 'count'" label="最大保留数量">
          <el-slider
            v-model="config.processed_archive_cleanup.max_count"
            :min="10"
            :max="10000"
            :step="10"
            show-input
            :disabled="!config.processed_archive_cleanup.enabled"
          />
          <div class="form-tip">
            最多保留 {{ config.processed_archive_cleanup.max_count }} 个压缩包，超出后删除最旧的
          </div>
        </el-form-item>

        <!-- 按容量清理设置 -->
        <el-form-item v-if="config.processed_archive_cleanup.strategy === 'size'" label="最大占用空间(GB)">
          <el-slider
            v-model="config.processed_archive_cleanup.max_size_gb"
            :min="1"
            :max="500"
            :step="1"
            show-input
            :disabled="!config.processed_archive_cleanup.enabled"
          />
          <div class="form-tip">
            压缩包总大小超过 {{ config.processed_archive_cleanup.max_size_gb }} GB 时，删除最旧的压缩包
          </div>
        </el-form-item>

        <el-form-item label="排除重新处理的压缩包">
          <el-switch
            v-model="config.processed_archive_cleanup.exclude_reprocessing"
            :disabled="!config.processed_archive_cleanup.enabled"
          />
          <div class="form-tip">
            开启后，正在重新处理的压缩包不会被清理
          </div>
        </el-form-item>

        <el-divider />

        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <el-button
            type="primary"
            size="small"
            @click="previewArchiveCleanup"
            :disabled="!config.processed_archive_cleanup.enabled"
          >
            <el-icon><View /></el-icon>
            预览清理
          </el-button>
          <el-button
            type="danger"
            size="small"
            @click="runArchiveCleanup"
            :disabled="!config.processed_archive_cleanup.enabled"
          >
            <el-icon><Delete /></el-icon>
            立即清理
          </el-button>
        </div>
      </el-card>

      <!-- 路径映射设置 -->
      <el-card class="setting-card">
        <template #header>
          <div class="card-header">
            <span>路径映射（跨设备访问）</span>
            <el-switch v-model="config.path_mapping.enabled" active-text="启用映射" />
          </div>
        </template>
        
        <el-alert
          title="路径映射说明"
          type="info"
          :closable="false"
          style="margin-bottom: 15px;"
        >
          <div style="font-size: 12px; line-height: 1.6;">
            <p>• 当您将应用部署在 Docker/远程服务器上，通过 SMB/NFS 访问文件时需要配置路径映射</p>
            <p>• 例如：Docker 内路径 <code>/viocelink/library</code> 映射到 Windows <code>W:\Viocelink\library</code></p>
            <p>• 配置后点击"打开位置"将显示映射后的本地路径，方便您复制并在资源管理器中打开</p>
          </div>
        </el-alert>
        
        <el-form-item label="打开模式">
          <el-radio-group v-model="config.path_mapping.open_mode" :disabled="!config.path_mapping.enabled">
            <el-radio label="auto">自动判断</el-radio>
            <el-radio label="direct">直接打开（同设备部署）</el-radio>
            <el-radio label="mapped">使用映射路径（跨设备部署）</el-radio>
          </el-radio-group>
          <div class="form-tip">
            <strong>自动判断</strong>：后端尝试直接打开，失败时返回映射路径
          </div>
        </el-form-item>
        
        <el-divider />
        
        <div v-for="(rule, index) in config.path_mapping.rules" :key="index" class="mapping-rule-item">
          <el-card shadow="never">
            <el-row :gutter="10" align="middle">
              <el-col :span="10">
                <el-input 
                  v-model="rule.remote_path" 
                  placeholder="远程/Docker 路径，如 /viocelink" 
                  size="small"
                  :disabled="!config.path_mapping.enabled"
                >
                  <template #prefix>
                    <el-icon><Folder /></el-icon>
                  </template>
                </el-input>
              </el-col>
              <el-col :span="1" style="text-align: center;">
                <el-icon><ArrowRight /></el-icon>
              </el-col>
              <el-col :span="10">
                <el-input 
                  v-model="rule.local_path" 
                  placeholder="本地映射路径，如 W:\\Viocelink" 
                  size="small"
                  :disabled="!config.path_mapping.enabled"
                >
                  <template #prefix>
                    <el-icon><FolderOpened /></el-icon>
                  </template>
                </el-input>
              </el-col>
              <el-col :span="1" style="text-align: center;">
                <el-switch v-model="rule.enabled" size="small" :disabled="!config.path_mapping.enabled" />
              </el-col>
              <el-col :span="2" style="text-align: right;">
                <el-button 
                  type="danger" 
                  link 
                  size="small" 
                  @click="removePathMappingRule(index)"
                  :disabled="!config.path_mapping.enabled"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-col>
            </el-row>
          </el-card>
        </div>
        
        <el-button 
          type="primary" 
          size="small" 
          @click="addPathMappingRule" 
          style="margin-top: 10px;"
          :disabled="!config.path_mapping.enabled"
        >
          <el-icon><Plus /></el-icon> 添加映射规则
        </el-button>
        
        <el-divider />
        
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <el-input
            v-model="testMappingPath"
            placeholder="输入测试路径，如 /viocelink/library/RJ12345"
            style="width: 300px;"
            :disabled="!config.path_mapping.enabled"
          >
            <template #prefix>
              <el-icon><Document /></el-icon>
            </template>
          </el-input>
          <el-button
            type="primary"
            size="small"
            @click="testPathMapping"
            :disabled="!config.path_mapping.enabled || !testMappingPath"
          >
            <el-icon><Check /></el-icon>
            测试映射
          </el-button>
        </div>
        
        <el-dialog
          v-model="testMappingDialogVisible"
          title="路径映射测试结果"
          width="500px"
        >
          <el-descriptions :column="1" border>
            <el-descriptions-item label="原始路径">
              <code>{{ testMappingResult.original_path }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="映射后路径">
              <code>{{ testMappingResult.mapped_path }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="映射状态">
              <el-tag :type="testMappingResult.is_mapped ? 'success' : 'warning'">
                {{ testMappingResult.is_mapped ? '成功映射' : '未匹配到规则' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
          <template #footer>
            <el-button @click="testMappingDialogVisible = false">关闭</el-button>
          </template>
        </el-dialog>
      </el-card>

      <!-- Kikoeru 服务器查重配置 -->
      <el-card class="setting-card">
        <template #header>
          <div class="card-header">
            <span>Kikoeru 服务器查重</span>
            <div class="header-actions">
              <el-switch 
                v-model="config.kikoeru_server.enabled" 
                active-text="启用"
                @change="saveKikoeruConfig"
              />
              <el-button 
                type="primary" 
                size="small" 
                @click="testKikoeruConnection"
                :loading="testingKikoeru"
                :disabled="!config.kikoeru_server.enabled || !config.kikoeru_server.server_url"
              >
                <el-icon><Connection /></el-icon> 测试连接
              </el-button>
            </div>
          </div>
        </template>

        <el-form 
          :model="config.kikoeru_server" 
          label-position="top"
          :disabled="!config.kikoeru_server.enabled"
        >
          <el-row :gutter="20">
            <el-col :span="16">
              <el-form-item label="服务器地址">
                <el-input 
                  v-model="config.kikoeru_server.server_url" 
                  placeholder="例如: http://192.168.1.100:8088"
                  @blur="saveKikoeruConfig"
                >
                  <template #prefix>
                    <el-icon><Link /></el-icon>
                  </template>
                </el-input>
                <div class="form-tip">Kikoeru 服务器的完整 URL 地址</div>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="API Token">
                <el-input 
                  v-model="config.kikoeru_server.api_token" 
                  placeholder="访问令牌"
                  show-password
                  @blur="saveKikoeruConfig"
                >
                  <template #prefix>
                    <el-icon><Key /></el-icon>
                  </template>
                </el-input>
                <div class="form-tip">用于认证的 API Token（如需要）</div>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="请求超时（秒）">
                <el-input-number 
                  v-model="config.kikoeru_server.timeout" 
                  :min="5" 
                  :max="60"
                  :step="5"
                  @change="saveKikoeruConfig"
                />
                <div class="form-tip">查询请求的超时时间</div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="缓存时间（秒）">
                <el-input-number 
                  v-model="config.kikoeru_server.cache_ttl" 
                  :min="60" 
                  :max="3600"
                  :step="60"
                  @change="saveKikoeruConfig"
                />
                <div class="form-tip">查重结果的缓存时间</div>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item>
            <div class="kikoeru-info">
              <el-alert
                title="关于 Kikoeru 服务器查重"
                type="info"
                :closable="false"
              >
                <template #default>
                  <p>启用后，系统在查重时会同时查询本地库和远程 Kikoeru 服务器。</p>
                  <p>适用于多个设备/服务器共享同一个 Kikoeru 库的场景。</p>
                  <p>支持的 URL 格式: <code>http://ip:port</code> 或 <code>https://domain</code></p>
                </template>
              </el-alert>
            </div>
          </el-form-item>
        </el-form>

        <!-- 测试结果对话框 -->
        <el-dialog
          v-model="kikoeruTestDialogVisible"
          title="连接测试结果"
          width="400px"
        >
          <el-result
            :icon="kikoeruTestResult.success ? 'success' : 'error'"
            :title="kikoeruTestResult.success ? '连接成功' : '连接失败'"
            :sub-title="kikoeruTestResult.message"
          >
            <template #extra v-if="kikoeruTestResult.latency > 0">
              <el-tag :type="kikoeruTestResult.success ? 'success' : 'info'">
                延迟: {{ kikoeruTestResult.latency.toFixed(0) }}ms
              </el-tag>
            </template>
          </el-result>
        </el-dialog>
      </el-card>

      <!-- 分类规则 -->
      <el-card class="setting-card">
        <template #header>
          <div class="card-header">
            <span>分类规则</span>
            <el-button type="primary" size="small" @click="addRule">
              <el-icon><Plus /></el-icon> 添加规则
            </el-button>
          </div>
        </template>
        
        <el-alert
          title="分类规则说明"
          type="info"
          :closable="false"
          style="margin-bottom: 20px;"
        >
          <div style="font-size: 12px; line-height: 1.6;">
            <p>• <strong>无</strong>：作品直接存入库存根目录</p>
            <p>• <strong>社团</strong>：按社团名称分类，可使用 {maker_name} 变量</p>
            <p>• <strong>RJ号范围</strong>：按RJ号范围分类，需设置范围和目录名称</p>
            <p>• <strong>系列</strong>：按系列名称分类，可使用 {series_name} 变量</p>
          </div>
        </el-alert>
        
        <div v-for="(rule, index) in config.classification" :key="index" class="rule-item">
          <el-card shadow="never">
            <!-- 基础路径显示 -->
            <el-row :gutter="10" align="middle" style="margin-bottom: 10px;">
              <el-col :span="24">
                <div class="base-path-display">
                  <span class="path-label">库存基础路径：</span>
                  <span class="path-value">{{ config.storage.library_path }}\</span>
                </div>
              </el-col>
            </el-row>
            
            <el-row :gutter="10" align="middle">
              <el-col :span="5">
                <el-select v-model="rule.type" placeholder="子目录类别" @change="onRuleTypeChange(rule)">
                  <el-option label="无" value="none" />
                  <el-option label="社团" value="maker" />
                  <el-option label="RJ号范围" value="rjcode" />
                  <el-option label="系列" value="series" />
                </el-select>
              </el-col>
              
              <!-- 不同分类类型的子目录输入 -->
              <el-col :span="13" v-if="rule.type === 'none'">
                <el-input disabled placeholder="无子目录" />
                <div class="form-tip">作品将直接存入库存根目录</div>
              </el-col>
              
              <el-col :span="13" v-else-if="rule.type === 'maker'">
                <el-input v-model="rule.path_template" placeholder="子目录名称，留空使用社团名">
                  <template #append>
                    <el-tooltip content="使用 {maker_name} 自动替换为社团名称">
                      <el-icon><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </template>
                </el-input>
                <div class="form-tip">使用 {maker_name} 变量或自定义名称</div>
              </el-col>
              
              <el-col :span="13" v-else-if="rule.type === 'rjcode'">
                <el-input v-model="rule.custom_name" placeholder="目录名称，如：RJ011系列">
                  <template #prepend>目录名</template>
                </el-input>
                <div class="form-tip">设置此RJ号范围的目录显示名称</div>
              </el-col>
              
              <el-col :span="13" v-else-if="rule.type === 'series'">
                <el-input v-model="rule.path_template" placeholder="子目录名称，留空使用系列名">
                  <template #append>
                    <el-tooltip content="使用 {series_name} 自动替换为系列名称">
                      <el-icon><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </template>
                </el-input>
                <div class="form-tip">使用 {series_name} 变量或自定义名称</div>
              </el-col>
              
              <el-col :span="4">
                <el-switch v-model="rule.enabled" active-text="启用" />
              </el-col>
              <el-col :span="2" style="text-align: right;">
                <el-button type="danger" link @click="removeRule(index)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-col>
            </el-row>
            
            <!-- RJ号范围详细设置 -->
            <el-row v-if="rule.type === 'rjcode'" :gutter="10" style="margin-top: 10px;">
              <el-col :span="12" :offset="5">
                <el-card shadow="never" size="small">
                  <template #header>
                    <span style="font-size: 12px;">RJ号范围配置</span>
                  </template>
                  <el-row :gutter="10">
                    <el-col :span="24">
                      <el-input 
                        v-model="rule.rjcode_range" 
                        placeholder="例如: RJ01100000-RJ01199999"
                        size="small"
                      >
                        <template #prepend>RJ号范围</template>
                      </el-input>
                      <div class="form-tip">格式: RJ01100000-RJ01199999</div>
                    </el-col>
                  </el-row>
                </el-card>
              </el-col>
            </el-row>
            
            <!-- 路径预览 -->
            <el-row :gutter="10" style="margin-top: 10px;">
              <el-col :span="24">
                <div class="path-preview">
                  <span class="preview-label">路径预览：</span>
                  <span class="preview-value">{{ getPathPreview(rule) }}</span>
                </div>
              </el-col>
            </el-row>
          </el-card>
        </div>
      </el-card>
      
      <!-- 保存按钮 -->
      <div class="actions">
        <el-button type="primary" size="large" @click="saveConfig">
          <el-icon><Check /></el-icon> 保存配置
        </el-button>
        <el-button size="large" @click="resetConfig">重置</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Folder, FolderOpened, Plus, Delete, Check, QuestionFilled, Tools, Warning, View, ArrowRight, Document, Connection, Key, Link } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { useConfigStore } from '../stores'

const configStore = useConfigStore()
const loading = ref(false)

const defaultConfig = {
  storage: {
    input_path: '/input',
    temp_path: '/temp',
    library_path: '/library'
  },
  processing: {
    max_workers: 4
  },
  watcher: {
    enabled: true,
    scan_interval: 30,
    auto_start: true,
    auto_classify: true,
    delete_after_process: false
  },
  extract: {
    auto_repair_extension: true,
    verify_after_extract: true,
    password_list: [],
    extract_nested_archives: true,
    max_nested_depth: 5
  },
  filter: {
    enabled: true,
    filter_dir: true,
    rules: [
      {
        name: '过滤无SE的文件',
        pattern: '(?:SE|音|音效)(?:[な無]し|CUT)|(?:無|なし)(?:SE|音|音效)',
        target: 'file',
        action: 'exclude',
        enabled: true
      },
      {
        name: '过滤无SE的文件夹',
        pattern: '(?:SE|音|音效)(?:[な無]し|CUT)|(?:無|なし)(?:SE|音|音效)',
        target: 'folder',
        action: 'exclude',
        enabled: true
      },
      {
        name: '过滤MP3文件',
        pattern: '\.mp3$',
        target: 'file',
        action: 'exclude',
        enabled: false
      }
    ]
  },
  metadata: {
    locale: 'zh_cn',
    cache_enabled: true,
    fetch_cover: true,
    make_folder_icon: true,
    http_proxy: ''
  },
  rename: {
    template: '{rjcode} {work_name}',
    date_format: '%y%m%d',
    exclude_square_brackets: false,
    illegal_char_to_full_width: false,
    flatten_single_subfolder: true,
    flatten_depth: 3,
    remove_empty_folders: true
  },
  classification: [
    { type: 'none', enabled: true, path_template: '', custom_name: '', fallback: null, max_tags: null, rjcode_range: null }
  ],
  password_cleanup: {
    enabled: false,
    max_use_count: 1,
    cron_expression: '0 0 * * 0',
    preserve_days: 30,
    exclude_sources: []
  },
  processed_archive_cleanup: {
    enabled: false,
    strategy: 'age',
    cron_expression: '0 1 * * 0',
    preserve_days: 30,
    max_count: 1000,
    max_size_gb: 50,
    exclude_reprocessing: true
  },
  path_mapping: {
    enabled: false,
    open_mode: 'auto',
    rules: []
  },
  kikoeru_server: {
    enabled: false,
    server_url: '',
    api_token: '',
    timeout: 10,
    cache_ttl: 300
  }
}

const config = ref(JSON.parse(JSON.stringify(defaultConfig)))

onMounted(async () => {
  await loadConfig()
})

async function loadConfig() {
  loading.value = true
  try {
    await configStore.fetchConfig()
    console.log('从后端加载的配置:', configStore.config)
    console.log('后端分类规则:', configStore.config?.classification)
    
    if (configStore.config) {
      // 合并后端配置和默认配置，确保所有字段都存在
      const mergedConfig = JSON.parse(JSON.stringify(defaultConfig))
      
      // 深拷贝配置，避免引用问题
      Object.keys(configStore.config).forEach(key => {
        if (configStore.config[key] !== null && configStore.config[key] !== undefined) {
          mergedConfig[key] = JSON.parse(JSON.stringify(configStore.config[key]))
        }
      })
      
      console.log('合并后的配置:', mergedConfig)
      console.log('合并后的分类规则:', mergedConfig.classification)
      
      // 确保 classification 数组存在且是数组
      if (!mergedConfig.classification || !Array.isArray(mergedConfig.classification)) {
        console.warn('分类规则为空或不是数组，使用默认值')
        mergedConfig.classification = JSON.parse(JSON.stringify(defaultConfig.classification))
      }
      
      // 确保每个规则都有所有必要字段
      mergedConfig.classification = mergedConfig.classification.map(rule => ({
        type: rule.type || 'none',
        enabled: rule.enabled !== false,
        path_template: rule.path_template || '',
        custom_name: rule.custom_name || '',
        fallback: rule.fallback || null,
        max_tags: rule.max_tags || null,
        rjcode_range: rule.rjcode_range || null
      }))
      
      // 确保 filter.rules 存在
      if (!mergedConfig.filter) {
        mergedConfig.filter = { enabled: true, filter_dir: true, rules: [] }
      }
      if (!mergedConfig.filter.rules || !Array.isArray(mergedConfig.filter.rules)) {
        mergedConfig.filter.rules = []
      }
      
      // 确保每个过滤规则都有 target 字段
      mergedConfig.filter.rules = mergedConfig.filter.rules.map(rule => ({
        name: rule.name || '未命名规则',
        pattern: rule.pattern || '',
        target: rule.target || 'file',
        action: rule.action || 'exclude',
        enabled: rule.enabled !== false
      }))
      
      // 确保 rename 配置完整
      if (!mergedConfig.rename) {
        mergedConfig.rename = {
          template: '{rjcode} {work_name}',
          date_format: '%y%m%d',
          exclude_square_brackets: false,
          illegal_char_to_full_width: false,
          flatten_single_subfolder: true,
          flatten_depth: 3,
          remove_empty_folders: true
        }
      }
      // 确保 flatten_single_subfolder 字段存在
      if (mergedConfig.rename.flatten_single_subfolder === undefined) {
        mergedConfig.rename.flatten_single_subfolder = true
      }
      // 确保 flatten_depth 字段存在
      if (mergedConfig.rename.flatten_depth === undefined) {
        mergedConfig.rename.flatten_depth = 3
      }
      // 确保 remove_empty_folders 字段存在
      if (mergedConfig.rename.remove_empty_folders === undefined) {
        mergedConfig.rename.remove_empty_folders = true
      }

      // 确保 extract 配置完整
      if (!mergedConfig.extract) {
        mergedConfig.extract = {
          auto_repair_extension: true,
          verify_after_extract: true,
          password_list: [],
          extract_nested_archives: true,
          max_nested_depth: 5
        }
      }
      // 确保 extract_nested_archives 字段存在
      if (mergedConfig.extract.extract_nested_archives === undefined) {
        mergedConfig.extract.extract_nested_archives = true
      }
      // 确保 max_nested_depth 字段存在
      if (mergedConfig.extract.max_nested_depth === undefined) {
        mergedConfig.extract.max_nested_depth = 5
      }

      // 确保 password_cleanup 配置完整
      if (!mergedConfig.password_cleanup) {
        mergedConfig.password_cleanup = {
          enabled: false,
          max_use_count: 1,
          cron_expression: '0 0 * * 0',
          preserve_days: 30,
          exclude_sources: []
        }
      }
      // 确保 password_cleanup 的字段都存在
      if (mergedConfig.password_cleanup.enabled === undefined) {
        mergedConfig.password_cleanup.enabled = false
      }
      if (mergedConfig.password_cleanup.max_use_count === undefined) {
        mergedConfig.password_cleanup.max_use_count = 1
      }
      if (mergedConfig.password_cleanup.cron_expression === undefined) {
        mergedConfig.password_cleanup.cron_expression = '0 0 * * 0'
      }
      if (mergedConfig.password_cleanup.preserve_days === undefined) {
        mergedConfig.password_cleanup.preserve_days = 30
      }
      if (!mergedConfig.password_cleanup.exclude_sources) {
        mergedConfig.password_cleanup.exclude_sources = []
      }

      // 确保 processed_archive_cleanup 配置完整
      if (!mergedConfig.processed_archive_cleanup) {
        mergedConfig.processed_archive_cleanup = {
          enabled: false,
          strategy: 'age',
          cron_expression: '0 1 * * 0',
          preserve_days: 30,
          max_count: 1000,
          max_size_gb: 50,
          exclude_reprocessing: true
        }
      }
      // 确保 processed_archive_cleanup 的字段都存在
      if (mergedConfig.processed_archive_cleanup.enabled === undefined) {
        mergedConfig.processed_archive_cleanup.enabled = false
      }
      if (mergedConfig.processed_archive_cleanup.strategy === undefined) {
        mergedConfig.processed_archive_cleanup.strategy = 'age'
      }
      if (mergedConfig.processed_archive_cleanup.cron_expression === undefined) {
        mergedConfig.processed_archive_cleanup.cron_expression = '0 1 * * 0'
      }
      if (mergedConfig.processed_archive_cleanup.preserve_days === undefined) {
        mergedConfig.processed_archive_cleanup.preserve_days = 30
      }
      if (mergedConfig.processed_archive_cleanup.max_count === undefined) {
        mergedConfig.processed_archive_cleanup.max_count = 1000
      }
      if (mergedConfig.processed_archive_cleanup.max_size_gb === undefined) {
        mergedConfig.processed_archive_cleanup.max_size_gb = 50
      }
      if (mergedConfig.processed_archive_cleanup.exclude_reprocessing === undefined) {
        mergedConfig.processed_archive_cleanup.exclude_reprocessing = true
      }

      // 确保 path_mapping 配置完整
      if (!mergedConfig.path_mapping) {
        mergedConfig.path_mapping = {
          enabled: false,
          open_mode: 'auto',
          rules: []
        }
      }
      // 确保 path_mapping 的字段都存在
      if (mergedConfig.path_mapping.enabled === undefined) {
        mergedConfig.path_mapping.enabled = false
      }
      if (!mergedConfig.path_mapping.open_mode) {
        mergedConfig.path_mapping.open_mode = 'auto'
      }
      if (!mergedConfig.path_mapping.rules || !Array.isArray(mergedConfig.path_mapping.rules)) {
        mergedConfig.path_mapping.rules = []
      }

      // 确保 kikoeru_server 配置完整
      if (!mergedConfig.kikoeru_server) {
        mergedConfig.kikoeru_server = {
          enabled: false,
          server_url: '',
          api_token: '',
          timeout: 10,
          cache_ttl: 300
        }
      }
      // 确保 kikoeru_server 的字段都存在
      if (mergedConfig.kikoeru_server.enabled === undefined) {
        mergedConfig.kikoeru_server.enabled = false
      }
      if (mergedConfig.kikoeru_server.server_url === undefined) {
        mergedConfig.kikoeru_server.server_url = ''
      }
      if (mergedConfig.kikoeru_server.api_token === undefined) {
        mergedConfig.kikoeru_server.api_token = ''
      }
      if (mergedConfig.kikoeru_server.timeout === undefined) {
        mergedConfig.kikoeru_server.timeout = 10
      }
      if (mergedConfig.kikoeru_server.cache_ttl === undefined) {
        mergedConfig.kikoeru_server.cache_ttl = 300
      }

      config.value = mergedConfig
      console.log('配置加载成功，分类规则:', config.value.classification)
    }
  } catch (error) {
    console.error('加载配置失败:', error)
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

function addRule() {
  if (!config.value.classification) {
    config.value.classification = []
  }
  config.value.classification.push({
    type: 'none',
    enabled: true,
    path_template: '',
    custom_name: '',
    fallback: null,
    max_tags: null,
    rjcode_range: null
  })
  console.log('添加规则成功，当前规则数:', config.value.classification.length)
}

function removeRule(index) {
  if (config.value.classification && index >= 0 && index < config.value.classification.length) {
    config.value.classification.splice(index, 1)
    console.log('删除规则成功，当前规则数:', config.value.classification.length)
  } else {
    console.error('删除规则失败，索引无效:', index)
  }
}

function onRuleTypeChange(rule) {
  // 根据类型设置默认值
  switch (rule.type) {
    case 'none':
      rule.path_template = ''
      rule.custom_name = ''
      break
    case 'maker':
      rule.path_template = rule.path_template || '{maker_name}'
      rule.custom_name = ''
      break
    case 'series':
      rule.path_template = rule.path_template || '{series_name}'
      rule.custom_name = ''
      break
    case 'rjcode':
      rule.path_template = ''
      rule.custom_name = rule.custom_name || ''
      rule.rjcode_range = rule.rjcode_range || ''
      break
  }
  console.log('规则类型变更为:', rule.type)
}

function getPathPreview(rule) {
  const basePath = config.value.storage.library_path || 'E:\\库存'
  let subPath = ''
  
  switch (rule.type) {
    case 'none':
      subPath = ''
      break
    case 'maker':
      subPath = rule.path_template || '{maker_name}'
      break
    case 'rjcode':
      subPath = rule.custom_name || 'RJ号分类'
      break
    case 'series':
      subPath = rule.path_template || '{series_name}'
      break
    default:
      subPath = ''
  }
  
  if (subPath) {
    return `${basePath}\\${subPath}\\{rjcode} {work_name}`
  } else {
    return `${basePath}\\{rjcode} {work_name}`
  }
}

function addFilterRule() {
  if (!config.value.filter.rules) {
    config.value.filter.rules = []
  }
  config.value.filter.rules.push({
    name: '新规则',
    pattern: '',
    target: 'file',
    action: 'exclude',
    enabled: true
  })
}

function getTargetLabel(target) {
  const labels = {
    'file': '文件',
    'folder': '文件夹',
    'all': '文件和文件夹'
  }
  return labels[target] || '文件'
}

function removeFilterRule(index) {
  if (config.value.filter.rules) {
    config.value.filter.rules.splice(index, 1)
  }
}

async function saveConfig() {
  try {
    loading.value = true
    
    // 调试：打印要保存的配置数据
    console.log('准备保存的配置:', JSON.parse(JSON.stringify(config.value)))
    console.log('分类规则:', config.value.classification)
    
    // 确保 classification 是数组
    if (!Array.isArray(config.value.classification)) {
      config.value.classification = []
    }
    
    // 调试：打印要保存的过滤规则
    console.log('准备保存的过滤规则:', JSON.parse(JSON.stringify(config.value.filter.rules)))
    
    // 调用后端API保存配置
    const response = await axios.post('/api/config', config.value)
    console.log('保存响应:', response.data)
    
    // 保存成功后重新加载配置，确保前端显示最新数据
    await loadConfig()
    console.log('配置已刷新，过滤规则:', config.value.filter.rules)
    
    // 显示过滤规则详情
    if (config.value.filter.rules && config.value.filter.rules.length > 0) {
      const enabledRules = config.value.filter.rules.filter(r => r.enabled)
      ElMessage.success(`配置已保存！启用的过滤规则: ${enabledRules.length} 条`)
    } else {
      ElMessage.success('配置已保存！')
    }
  } catch (error) {
    console.error('保存配置失败:', error)
    console.error('错误详情:', error.response?.data)
    ElMessage.error('保存配置失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

function resetConfig() {
  config.value = JSON.parse(JSON.stringify(defaultConfig))
  ElMessage.info('配置已重置')
}

function createTestDirs() {
  // 自动填充默认测试路径
  config.value.storage.input_path = 'test_data/input'
  config.value.storage.temp_path = 'test_data/temp'
  config.value.storage.library_path = 'test_data/library'
  config.value.storage.processed_archives_path = 'test_data/processed'
  ElMessage.success('已填充默认测试路径，请点击保存配置')
}

// 路径映射相关
const testMappingPath = ref('')
const testMappingDialogVisible = ref(false)
const testMappingResult = ref({
  original_path: '',
  mapped_path: '',
  is_mapped: false
})

// Kikoeru 服务器查重相关
const testingKikoeru = ref(false)
const kikoeruTestDialogVisible = ref(false)
const kikoeruTestResult = ref({
  success: false,
  message: '',
  latency: 0
})

async function saveKikoeruConfig() {
  try {
    // 保存到后端
    await axios.post('/api/kikoeru-server/config', config.value.kikoeru_server)
    ElMessage.success('Kikoeru 服务器配置已保存')
  } catch (error) {
    console.error('保存 Kikoeru 配置失败:', error)
    ElMessage.error('保存配置失败: ' + (error.response?.data?.detail || error.message))
  }
}

async function testKikoeruConnection() {
  if (!config.value.kikoeru_server.server_url) {
    ElMessage.warning('请先配置服务器地址')
    return
  }
  
  testingKikoeru.value = true
  try {
    const response = await axios.post('/api/kikoeru-server/test')
    kikoeruTestResult.value = response.data
    kikoeruTestDialogVisible.value = true
    
    if (response.data.success) {
      ElMessage.success('连接测试成功')
    } else {
      ElMessage.error('连接测试失败: ' + response.data.message)
    }
  } catch (error) {
    console.error('测试 Kikoeru 连接失败:', error)
    kikoeruTestResult.value = {
      success: false,
      message: error.response?.data?.detail || error.message,
      latency: 0
    }
    kikoeruTestDialogVisible.value = true
    ElMessage.error('测试连接失败')
  } finally {
    testingKikoeru.value = false
  }
}

function addPathMappingRule() {
  if (!config.value.path_mapping.rules) {
    config.value.path_mapping.rules = []
  }
  config.value.path_mapping.rules.push({
    remote_path: '',
    local_path: '',
    enabled: true
  })
}

function removePathMappingRule(index) {
  if (config.value.path_mapping.rules) {
    config.value.path_mapping.rules.splice(index, 1)
  }
}

async function testPathMapping() {
  try {
    const response = await axios.post('/api/path-mapping/test', {
      path: testMappingPath.value
    })
    testMappingResult.value = response.data
    testMappingDialogVisible.value = true
  } catch (error) {
    console.error('测试路径映射失败:', error)
    ElMessage.error('测试失败: ' + (error.response?.data?.detail || error.message))
  }
}

async function previewPasswordCleanup() {
  try {
    const response = await axios.get('/api/password-cleanup/preview')
    const data = response.data

    if (data.deleted_count === 0) {
      ElMessage.info('没有需要清理的密码')
      return
    }

    // 显示预览对话框
    const passwordList = data.deleted_passwords.map(p =>
      `• ${p.rjcode || p.filename || '通用密码'} (${p.use_count}次使用, ${p.source})`
    ).join('\n')

    await ElMessageBox.confirm(
      `将清理 ${data.deleted_count} 个密码：\n\n${passwordList}\n\n确定要立即清理吗？`,
      '清理预览',
      {
        confirmButtonText: '立即清理',
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: false
      }
    )

    // 用户确认后执行清理
    await runPasswordCleanup()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('预览清理失败:', error)
      ElMessage.error('预览清理失败: ' + (error.response?.data?.detail || error.message))
    }
  }
}

async function runPasswordCleanup() {
  try {
    loading.value = true
    const response = await axios.post('/api/password-cleanup/run')
    const data = response.data

    if (data.deleted_count === 0) {
      ElMessage.info('没有需要清理的密码')
    } else {
      ElMessage.success(`成功清理 ${data.deleted_count} 个密码`)
    }
  } catch (error) {
    console.error('执行清理失败:', error)
    ElMessage.error('执行清理失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}

async function previewArchiveCleanup() {
  try {
    const response = await axios.get('/api/processed-archive-cleanup/preview')
    const data = response.data

    if (data.deleted_count === 0) {
      ElMessage.info('没有需要清理的压缩包')
      return
    }

    // 显示预览对话框
    const archiveList = data.deleted_archives.map(a =>
      `• ${a.filename} (${a.file_size_mb.toFixed(2)} MB)`
    ).join('\n')

    await ElMessageBox.confirm(
      `将清理 ${data.deleted_count} 个压缩包，释放 ${data.freed_space_mb.toFixed(2)} MB 空间：\n\n${archiveList}\n\n确定要立即清理吗？`,
      '清理预览',
      {
        confirmButtonText: '立即清理',
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: false
      }
    )

    // 用户确认后执行清理
    await runArchiveCleanup()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('预览清理失败:', error)
      ElMessage.error('预览清理失败: ' + (error.response?.data?.detail || error.message))
    }
  }
}

async function runArchiveCleanup() {
  try {
    loading.value = true
    const response = await axios.post('/api/processed-archive-cleanup/run')
    const data = response.data

    if (data.deleted_count === 0) {
      ElMessage.info('没有需要清理的压缩包')
    } else {
      ElMessage.success(`成功清理 ${data.deleted_count} 个压缩包，释放 ${data.freed_space_mb.toFixed(2)} MB 空间`)
    }
  } catch (error) {
    console.error('执行清理失败:', error)
    ElMessage.error('执行清理失败: ' + (error.response?.data?.detail || error.message))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.settings {
  max-width: 1200px;
  margin: 0 auto;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 24px;
}

.setting-card {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.rule-item {
  margin-bottom: 12px;
}

.actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  padding: 24px 0;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.text-gray {
  color: #909399;
}

.base-path-display {
  background-color: #f5f7fa;
  padding: 8px 12px;
  border-radius: 4px;
  border-left: 4px solid #409eff;
}

.base-path-display .path-label {
  color: #606266;
  font-weight: 500;
}

.base-path-display .path-value {
  color: #409eff;
  font-family: monospace;
  font-weight: 600;
}

.path-preview {
  background-color: #f0f9ff;
  padding: 8px 12px;
  border-radius: 4px;
  border: 1px dashed #409eff;
}

.path-preview .preview-label {
  color: #606266;
  font-weight: 500;
}

.path-preview .preview-value {
  color: #67c23a;
  font-family: monospace;
  font-weight: 600;
}
</style>
