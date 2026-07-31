// js/doubao/monitor-voice.js
// 独立语音播报模块 — 监控面板自动朗读（不侵入原 strategy.js）
(function() {
    'use strict';

    // 确保全局依赖存在
    if (typeof DoubaoWorkbench === 'undefined') {
        console.warn('[monitor-voice] DoubaoWorkbench 未加载，等待...');
        return;
    }

    // 上次播报文本（去重用）
    var lastVoiceText = '';
    var voiceEnabled = true;
    var observer = null;

    // ---- 工具：清理 Markdown 标记 ----
    function cleanMarkdown(text) {
        if (!text) return '';
        var cleaned = text
            .replace(/^#+\s*/gm, '')                // 标题
            .replace(/\*\*(.*?)\*\*/g, '$1')        // 粗体
            .replace(/\*(.*?)\*/g, '$1')            // 斜体
            .replace(/__(.*?)__/g, '$1')
            .replace(/_(.*?)_/g, '$1')
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // 链接
            .replace(/!\[[^\]]*\]\([^)]*\)/g, '')    // 图片
            .replace(/^[\s]*[-*+]\s+/gm, '')         // 无序列表
            .replace(/^[\s]*\d+\.\s+/gm, '')         // 有序列表
            .replace(/\n{2,}/g, '\n')
            .trim();
        return cleaned;
    }

    // ---- 提取监控结果中的可读文本 ----
    function extractMonitorText() {
        var container = document.getElementById('monitor-results');
        if (!container) return '';

        // 直接取 innerText 会自动忽略 HTML 标签
        var raw = container.innerText || '';
        if (!raw.trim()) return '';

        // 去掉常见的无效前缀（如"暂无触发买卖点"）
        if (raw.includes('暂无触发买卖点')) {
            // 但如果有具体信号，则保留
            var hasSignal = /信号|标的|买入|卖出|预警|触发|建议/.test(raw);
            if (!hasSignal) return '';
        }

        return cleanMarkdown(raw);
    }

    // ---- 执行语音播报 ----
    function speakIfChanged(text) {
        if (!voiceEnabled) return;
        if (!text || text.length < 2) return;

        // 截断过长内容（语音播报不宜超过 200 字）
        var speakText = text;
        if (speakText.length > 200) {
            speakText = speakText.substring(0, 200) + '… 等信号';
        }

        // 去重：与上次相同则跳过
        if (speakText === lastVoiceText) return;
        lastVoiceText = speakText;

        // 调用全局 speecher
        if (typeof speecher !== 'undefined' && speecher.speak) {
            speecher.speak(speakText, false);
            console.log('[monitor-voice] 播报:', speakText);
        } else {
            console.warn('[monitor-voice] speecher 未加载，无法播报');
        }
    }

    // ---- 主动检查并播报（用于手动刷新后触发） ----
    function checkAndSpeak() {
        var text = extractMonitorText();
        if (text) {
            speakIfChanged(text);
        }
    }

    // ---- 启动 MutationObserver 监听监控面板 ----
    function startObserver() {
        if (observer) return;

        var container = document.getElementById('monitor-results');
        if (!container) {
            // 面板可能还没渲染，稍后重试
            console.warn('[monitor-voice] 监控面板未就绪，3秒后重试');
            setTimeout(startObserver, 3000);
            return;
        }

        observer = new MutationObserver(function(mutations) {
            // 防抖：延迟 300ms 等 DOM 更新稳定
            clearTimeout(window._voiceDebounceTimer);
            window._voiceDebounceTimer = setTimeout(function() {
                var text = extractMonitorText();
                if (text) {
                    speakIfChanged(text);
                }
            }, 300);
        });

        observer.observe(container, {
            childList: true,
            subtree: true,
            characterData: true
        });

        console.log('[monitor-voice] 已启动监听');
    }

    // ---- 对外 API（挂载到 DoubaoWorkbench） ----
    DoubaoWorkbench.VoiceMonitor = {
        enable: function() {
            voiceEnabled = true;
            startObserver();
        },
        disable: function() {
            voiceEnabled = false;
            if (observer) {
                observer.disconnect();
                observer = null;
            }
            console.log('[monitor-voice] 已关闭');
        },
        toggle: function() {
            if (voiceEnabled) {
                this.disable();
            } else {
                this.enable();
            }
        },
        speakNow: checkAndSpeak,   // 手动触发一次播报
        isEnabled: function() { return voiceEnabled; }
    };

    // ---- 自动启动（延迟等待页面加载） ----
    if (document.readyState === 'complete') {
        setTimeout(function() {
            DoubaoWorkbench.VoiceMonitor.enable();
        }, 1000);
    } else {
        window.addEventListener('load', function() {
            setTimeout(function() {
                DoubaoWorkbench.VoiceMonitor.enable();
            }, 1000);
        });
    }

    console.log('[monitor-voice] 模块加载完成');
})();