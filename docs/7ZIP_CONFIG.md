# 7-Zip 配置指南

## Windows 用户

### 方法1：自动检测（推荐，如果7-Zip在PATH中）
1. 安装 7-Zip：https://www.7-zip.org/
2. 安装时勾选 **"Add 7-Zip to PATH"**
3. 重启后端服务
4. 在设置页面保持 7-Zip 路径为默认值 `7z` 或留空

### 方法2：手动指定路径（如果自动检测失败）
1. 找到 7-Zip 安装位置，通常是：
   - `C:\Program Files\7-Zip\7z.exe`（64位）
   - `C:\Program Files (x86)\7-Zip\7z.exe`（32位）

2. 在网页设置页面填写完整路径：
   ```
   C:\Program Files\7-Zip\7z.exe
   ```

3. 保存配置
4. 无需重启服务，配置立即生效

### 方法3：便携版（无需安装）
1. 下载 7-Zip 便携版
2. 将 `7z.exe` 复制到项目任意目录，例如：`D:\tools\7z.exe`
3. 在设置页面填写路径：
   ```
   D:\tools\7z.exe
   ```

## Docker/Linux 用户

无需配置！Docker 镜像已预装 7zip，保持默认配置即可：
```yaml
extract:
  seven_zip_path: "7z"
```

## 常见问题

### Q: 提示"找不到 7z 可执行文件"
**A**: 检查以下几点：
1. 是否已安装 7-Zip
2. 路径是否正确（可以使用 `where 7z` 命令查看）
3. 配置是否已保存（点击保存配置按钮）

### Q: 保存配置后仍然报错
**A**: 
1. 刷新页面确认配置已保存
2. 检查日志页面是否有详细错误信息
3. 尝试在命令行测试 7z 是否可用：
   ```cmd
   "C:\Program Files\7-Zip\7z.exe" --help
   ```

### Q: 配置立即生效还是需要重启？
**A**: 配置**立即生效**，无需重启后端服务。每个新任务都会读取最新配置。

### Q: Docker 中需要配置吗？
**A**: **不需要**。Docker 镜像已内置 7zip，保持默认配置即可。

## 测试 7-Zip 是否可用

在 PowerShell 或 CMD 中运行：
```powershell
# 如果在 PATH 中
7z --help

# 或者使用完整路径
"C:\Program Files\7-Zip\7z.exe" --help
```

如果显示帮助信息，说明 7-Zip 可用。

## 配置示例

### Windows 默认安装
```yaml
extract:
  seven_zip_path: "C:\Program Files\7-Zip\7z.exe"
```

### Linux/Docker
```yaml
extract:
  seven_zip_path: "7z"
```

### 自动检测（推荐）
```yaml
extract:
  seven_zip_path: "7z"  # 或留空
```
