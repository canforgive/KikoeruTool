// ==UserScript==
// @name         KikoeruTool Local Folder Opener
// @namespace    http://tampermonkey.net/
// @version      1.2
// @description  为 KikoeruTool 提供本地文件夹打开功能（简化版）
// @author       You
// @match        http://*/**
// @match        https://*/**
// @grant        GM_openInTab
// @grant        unsafeWindow
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    console.log('[KikoeruTool Helper] v1.2 脚本已加载');

    // 简单的页面检测
    function isKikoeruPage() {
        return document.querySelector('.app-container') || 
               document.title.includes('Kikoeru') ||
               document.querySelector('.el-container');
    }

    // 页面加载完成后检查
    window.addEventListener('load', () => {
        setTimeout(() => {
            if (isKikoeruPage()) {
                console.log('[KikoeruTool Helper] 检测到 Kikoeru 页面');
                
                // 设置全局标记
                window.kikoeruHelperLoaded = true;
                
                // 通知页面脚本已就绪
                window.dispatchEvent(new CustomEvent('kikoeru-helper-ready', {
                    detail: { version: '1.2' }
                }));
                
                console.log('[KikoeruTool Helper] 已就绪');
            }
        }, 1000);
    });

    // 监听前端发来的打开文件夹请求
    window.addEventListener('kikoeru-open-folder', function(event) {
        const path = event.detail?.path;
        console.log('[KikoeruTool Helper] 收到打开请求:', path);

        if (!path) {
            console.error('[KikoeruTool Helper] 路径为空');
            return;
        }

        // 转换为 file 协议格式
        let fileUrl = path.replace(/\\/g, '/');
        
        // 确保正确的格式
        if (!fileUrl.startsWith('file://')) {
            if (/^[a-zA-Z]:/.test(fileUrl)) {
                fileUrl = 'file:///' + fileUrl;
            } else {
                fileUrl = 'file://' + fileUrl;
            }
        }

        console.log('[KikoeruTool Helper] 尝试打开:', fileUrl);

        // 使用 GM_openInTab 打开（Tampermonkey 特有）
        try {
            if (typeof GM_openInTab !== 'undefined') {
                GM_openInTab(fileUrl, { active: true });
                console.log('[KikoeruTool Helper] GM_openInTab 成功');
                return;
            }
        } catch (e) {
            console.log('[KikoeruTool Helper] GM_openInTab 失败:', e);
        }

        // 备用：window.open
        try {
            const win = window.open(fileUrl, '_blank');
            if (win) {
                console.log('[KikoeruTool Helper] window.open 成功');
                // 尝试关闭新开的空白标签
                setTimeout(() => {
                    try { win.close(); } catch(e) {}
                }, 500);
                return;
            }
        } catch (e) {
            console.log('[KikoeruTool Helper] window.open 失败:', e);
        }

        // 最后一个备用：iframe
        try {
            const iframe = document.createElement('iframe');
            iframe.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;';
            iframe.src = fileUrl;
            document.body.appendChild(iframe);
            
            setTimeout(() => {
                if (iframe.parentNode) {
                    iframe.parentNode.removeChild(iframe);
                }
            }, 2000);
            
            console.log('[KikoeruTool Helper] iframe 方式已尝试');
        } catch (e) {
            console.error('[KikoeruTool Helper] 所有方法都失败:', e);
            alert('无法打开文件夹，请手动复制路径打开:\n' + path);
        }
    });
})();
