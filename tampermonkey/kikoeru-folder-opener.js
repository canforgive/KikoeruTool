// ==UserScript==
// @name         KikoeruTool Local Folder Opener
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  为 KikoeruTool 提供本地文件夹打开功能（直接调用资源管理器）
// @author       You
// @match        http://*/**
// @match        https://*/**
// @grant        GM_openInTab
// @grant        GM_notification
// @grant        unsafeWindow
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    console.log('[KikoeruTool Helper] 脚本已加载 v1.1');

    // 检测是否在 Kikoeru 页面
    let isKikoeruPage = false;
    const checkInterval = setInterval(() => {
        if (document.querySelector('.app-container') || 
            document.title.includes('Kikoeru') ||
            document.querySelector('.el-container')) {
            if (!isKikoeruPage) {
                isKikoeruPage = true;
                clearInterval(checkInterval);
                console.log('[KikoeruTool Helper] 检测到 Kikoeru 页面');
                
                // 通知页面脚本已就绪
                window.dispatchEvent(new CustomEvent('kikoeru-helper-ready', {
                    detail: { version: '1.1', features: ['open-folder'] }
                }));

                // 显示提示
                showNotification('KikoeruTool Helper 已加载', '可以直接点击"尝试打开"按钮打开文件夹');
            }
        }
    }, 500);

    // 监听前端发来的打开文件夹请求
    window.addEventListener('kikoeru-open-folder', function(event) {
        const path = event.detail?.path;
        console.log('[KikoeruTool Helper] 收到打开请求:', path);

        if (!path) {
            console.error('[KikoeruTool Helper] 路径为空');
            showNotification('错误', '路径为空', 'error');
            return;
        }

        // 转换为资源管理器可用的路径格式
        const explorerPath = convertToExplorerPath(path);
        console.log('[KikoeruTool Helper] 转换后路径:', explorerPath);

        // 方法1: 使用 file:// 协议（最通用）
        openWithFileProtocol(explorerPath);
    });

    // 将各种路径格式转换为资源管理器格式
    function convertToExplorerPath(inputPath) {
        let path = inputPath;
        
        // 统一使用正斜杠
        path = path.replace(/\\/g, '/');
        
        // 如果是 Windows 驱动器路径（如 V:/...）
        if (/^[a-zA-Z]:/.test(path)) {
            // 确保格式为 file:///V:/路径
            if (!path.startsWith('/')) {
                path = '/' + path;
            }
            return 'file://' + path;
        }
        
        // 如果已经是 file:// 格式，直接返回
        if (path.startsWith('file://')) {
            return path;
        }
        
        // 其他情况，添加 file:// 前缀
        return 'file://' + path;
    }

    // 使用 file:// 协议打开
    function openWithFileProtocol(fileUrl) {
        console.log('[KikoeruTool Helper] 方法1 - file:// 协议:', fileUrl);
        
        try {
            // 方法1a: GM_openInTab
            if (typeof GM_openInTab !== 'undefined') {
                GM_openInTab(fileUrl, { 
                    active: true,
                    insert: true 
                });
                console.log('[KikoeruTool Helper] GM_openInTab 调用成功');
                showNotification('正在打开', '文件夹正在打开，请查看资源管理器');
                return;
            }
        } catch (e) {
            console.log('[KikoeruTool Helper] GM_openInTab 失败:', e);
        }
        
        // 方法1b: window.open（在 Tampermonkey 环境中权限更高）
        try {
            const win = window.open(fileUrl, '_blank');
            if (win) {
                console.log('[KikoeruTool Helper] window.open 成功');
                showNotification('正在打开', '文件夹正在打开');
                
                // 3秒后关闭新开的空白标签页
                setTimeout(() => {
                    try {
                        win.close();
                    } catch(e) {}
                }, 3000);
                return;
            } else {
                console.log('[KikoeruTool Helper] window.open 返回 null，可能被阻止');
            }
        } catch (e) {
            console.log('[KikoeruTool Helper] window.open 失败:', e);
        }
        
        // 方法1c: 使用 iframe 尝试加载
        try {
            const iframe = document.createElement('iframe');
            iframe.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;pointer-events:none;';
            iframe.src = fileUrl;
            document.body.appendChild(iframe);
            
            showNotification('正在尝试', '正在尝试打开文件夹...');
            
            setTimeout(() => {
                if (iframe.parentNode) {
                    iframe.parentNode.removeChild(iframe);
                }
            }, 2000);
            return;
        } catch (e) {
            console.error('[KikoeruTool Helper] iframe 方式失败:', e);
        }
        
        // 所有方法都失败
        console.error('[KikoeruTool Helper] 所有方法都失败');
        showNotification('打开失败', '请手动复制路径到资源管理器打开', 'error');
        
        // 触发失败事件，让前端处理
        window.dispatchEvent(new CustomEvent('kikoeru-open-failed', {
            detail: { path: fileUrl, reason: 'all_methods_failed' }
        }));
    }

    // 显示通知
    function showNotification(title, text, type = 'info') {
        if (typeof GM_notification !== 'undefined') {
            GM_notification({
                title: title,
                text: text,
                timeout: 3000
            });
        } else {
            console.log(`[KikoeruTool Helper] ${title}: ${text}`);
        }
    }

    // 在页面上添加一个提示条（可选）
    function addHelperIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'kikoeru-helper-indicator';
        indicator.style.cssText = `
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: #67c23a;
            color: white;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 9999;
            opacity: 0.8;
            pointer-events: none;
        `;
        indicator.textContent = 'Tampermonkey 助手已激活';
        document.body.appendChild(indicator);
        
        // 5秒后淡出
        setTimeout(() => {
            indicator.style.transition = 'opacity 1s';
            indicator.style.opacity = '0';
            setTimeout(() => {
                if (indicator.parentNode) {
                    indicator.parentNode.removeChild(indicator);
                }
            }, 1000);
        }, 5000);
    }

    // 页面加载完成后添加指示器
    window.addEventListener('load', () => {
        setTimeout(addHelperIndicator, 1000);
    });
})();
