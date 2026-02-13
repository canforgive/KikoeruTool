// ==UserScript==
// @name         KikoeruTool Local Folder Opener
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  为 KikoeruTool 提供本地文件夹打开功能
// @author       You
// @match        http://*/**
// @match        https://*/**
// @grant        GM_openInTab
// @grant        unsafeWindow
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';

    console.log('[KikoeruTool Helper] 脚本已加载');

    // 监听前端发来的打开文件夹请求
    window.addEventListener('kikoeru-open-folder', function(event) {
        const path = event.detail.path;
        console.log('[KikoeruTool Helper] 收到打开请求:', path);

        if (!path) {
            console.error('[KikoeruTool Helper] 路径为空');
            return;
        }

        // 将 Windows 路径转换为 file 协议
        let fileUrl = path.replace(/\\/g, '/');
        if (/^[a-zA-Z]:/.test(fileUrl)) {
            fileUrl = 'file:///' + fileUrl;
        } else {
            fileUrl = 'file://' + fileUrl;
        }

        console.log('[KikoeruTool Helper] 尝试打开:', fileUrl);

        // 方法1: GM_openInTab (Tampermonkey 特有 API)
        try {
            if (typeof GM_openInTab !== 'undefined') {
                GM_openInTab(fileUrl, { active: true });
                console.log('[KikoeruTool Helper] 使用 GM_openInTab 打开成功');
                return;
            }
        } catch (e) {
            console.log('[KikoeruTool Helper] GM_openInTab 失败:', e);
        }

        // 方法2: 使用 window.open (在 Tampermonkey 环境中权限更高)
        try {
            const win = window.open(fileUrl, '_blank');
            if (win) {
                console.log('[KikoeruTool Helper] window.open 成功');
                return;
            }
        } catch (e) {
            console.log('[KikoeruTool Helper] window.open 失败:', e);
        }

        // 方法3: 修改 location (最后手段)
        try {
            // 创建一个隐藏的 iframe 来尝试加载
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
            alert('Tampermonkey 也无法打开本地文件夹，请手动复制路径打开\n路径: ' + path);
        }
    });

    // 在页面上显示一个提示，告知用户脚本已加载
    const checkKikoeru = setInterval(() => {
        if (document.querySelector('.app-container') || document.title.includes('Kikoeru')) {
            clearInterval(checkKikoeru);
            console.log('[KikoeruTool Helper] 检测到 Kikoeru 页面');

            // 可以在这里添加一个全局标记
            window.kikoeruHelperLoaded = true;

            // 通知页面脚本已就绪
            window.dispatchEvent(new CustomEvent('kikoeru-helper-ready', {
                detail: { version: '1.0' }
            }));
        }
    }, 1000);
})();
