/* =============================================================
 * 政策信息监控 - 前端交互脚本
 * 不依赖任何第三方库，所有交互都基于原生 fetch / DOM API
 * ============================================================= */

(function () {
    'use strict';

    // ---------------- Toast ---------------- //
    function showToast(message, type) {
        type = type || 'info';
        var container = document.getElementById('toast-container');
        if (!container) return;
        var toast = document.createElement('div');
        toast.className = 'toast toast-' + type;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(function () {
            toast.classList.add('fade-out');
            setTimeout(function () {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 250);
        }, 2600);
    }
    window.showToast = showToast;

    // ---------------- HTTP helpers ---------------- //
    function request(url, options) {
        options = options || {};
        var headers = options.headers || {};
        if (options.body && !(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
            if (typeof options.body !== 'string') {
                options.body = JSON.stringify(options.body);
            }
        }
        return fetch(url, {
            method: options.method || 'GET',
            headers: headers,
            body: options.body,
        }).then(function (resp) {
            return resp.json().then(function (data) {
                return { ok: resp.ok, status: resp.status, data: data };
            }).catch(function () {
                return { ok: resp.ok, status: resp.status, data: {} };
            });
        });
    }

    // ---------------- Manual crawl ---------------- //
    function triggerCrawl(websiteName) {
        return request('/api/crawl', {
            method: 'POST',
            body: { website_name: websiteName || null },
        }).then(function (res) {
            if (res.ok) {
                showToast(res.data.message || '爬取已启动', 'success');
                showProgressPanel();
                // 爬取启动成功后立即显示控制按钮
                var controlBtns = document.getElementById('crawl-control-btns');
                if (controlBtns) controlBtns.style.display = 'flex';
                startProgressPolling();
            } else if (res.status === 409) {
                showToast(res.data.message || '已有爬取任务运行中', 'warning');
                showProgressPanel();
                var controlBtns2 = document.getElementById('crawl-control-btns');
                if (controlBtns2) controlBtns2.style.display = 'flex';
                startProgressPolling();
            } else {
                showToast(res.data.message || '启动爬取失败', 'error');
            }
            return res;
        }).catch(function () {
            showToast('网络错误，无法启动爬取', 'error');
        });
    }
    window.triggerCrawl = triggerCrawl;

    function bindManualCrawl() {
        var navBtn = document.getElementById('nav-manual-crawl');
        var pageBtn = document.getElementById('btn-trigger-crawl-all');
        function handler(ev) {
            ev.preventDefault();
            if (!confirm('确定要开始爬取吗？')) return;
            triggerCrawl(null);
        }
        if (navBtn) navBtn.addEventListener('click', handler);
        if (pageBtn) pageBtn.addEventListener('click', handler);
    }

    // ---------------- Crawl panel (selective + progress) ---------------- //
    var _progressTimer = null;

    function togglePanel(id, force) {
        var el = document.getElementById(id);
        if (!el) return;
        if (typeof force === 'boolean') {
            el.hidden = !force;
        } else {
            el.hidden = !el.hidden;
        }
    }

    function showProgressPanel() {
        togglePanel('crawl-progress-panel', true);
        var panel = document.getElementById('crawl-progress-panel');
        if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function getSelectedSites() {
        var nodes = document.querySelectorAll('.chk-site:checked');
        var arr = [];
        nodes.forEach(function (n) { arr.push(n.value); });
        return arr;
    }

    function getDateRange() {
        var df = document.getElementById('crawl-date-from');
        var dt = document.getElementById('crawl-date-to');
        return {
            date_from: df ? (df.value || '') : '',
            date_to: dt ? (dt.value || '') : '',
        };
    }

    function setSubmitButtonsDisabled(disabled) {
        ['btn-crawl-selective', 'btn-crawl-all-with-range',
         'btn-trigger-crawl-all'].forEach(function (id) {
            var b = document.getElementById(id);
            if (b) b.disabled = !!disabled;
        });
    }

    function bindCrawlPanel() {
        var toggleBtn = document.getElementById('btn-toggle-crawl-panel');
        var panel = document.getElementById('crawl-control-panel');
        if (toggleBtn && panel) {
            toggleBtn.addEventListener('click', function () {
                togglePanel('crawl-control-panel');
                var icon = toggleBtn.querySelector('.btn-icon');
                if (icon) icon.textContent = panel.hidden ? '▸' : '▾';
            });
        }

        // 分组全选
        document.querySelectorAll('.chk-group-all').forEach(function (chk) {
            chk.addEventListener('change', function () {
                var lvl = chk.getAttribute('data-level');
                document.querySelectorAll(
                    '.chk-site[data-level="' + cssEscape(lvl) + '"]'
                ).forEach(function (s) { s.checked = chk.checked; });
            });
        });
        // 子项变化 -> 同步全选状态
        document.querySelectorAll('.chk-site').forEach(function (s) {
            s.addEventListener('change', function () {
                var lvl = s.getAttribute('data-level');
                var all = document.querySelectorAll(
                    '.chk-site[data-level="' + cssEscape(lvl) + '"]');
                var checked = document.querySelectorAll(
                    '.chk-site[data-level="' + cssEscape(lvl) + '"]:checked');
                var groupChk = document.querySelector(
                    '.chk-group-all[data-level="' + cssEscape(lvl) + '"]');
                if (groupChk) {
                    groupChk.checked = (all.length > 0 && checked.length === all.length);
                    groupChk.indeterminate = (
                        checked.length > 0 && checked.length < all.length);
                }
            });
        });

        // 爬取选中
        var btnSel = document.getElementById('btn-crawl-selective');
        if (btnSel) {
            btnSel.addEventListener('click', function () {
                var sites = getSelectedSites();
                if (sites.length === 0) {
                    showToast('请勾选至少一个网站', 'warning');
                    return;
                }
                if (!confirm('确定要开始爬取选中的 ' + sites.length + ' 个网站吗？')) return;
                var range = getDateRange();
                setSubmitButtonsDisabled(true);
                request('/api/crawl/selective', {
                    method: 'POST',
                    body: {
                        websites: sites,
                        date_from: range.date_from,
                        date_to: range.date_to,
                    },
                }).then(function (res) {
                    handleCrawlStartResponse(res);
                }).catch(function () {
                    setSubmitButtonsDisabled(false);
                    showToast('网络错误，启动失败', 'error');
                });
            });
        }

        // 爬取全部（带时间范围）
        var btnAllRange = document.getElementById('btn-crawl-all-with-range');
        if (btnAllRange) {
            btnAllRange.addEventListener('click', function () {
                if (!confirm('确定要开始爬取全部网站吗？')) return;
                var range = getDateRange();
                setSubmitButtonsDisabled(true);
                request('/api/crawl/all', {
                    method: 'POST',
                    body: {
                        date_from: range.date_from,
                        date_to: range.date_to,
                    },
                }).then(function (res) {
                    handleCrawlStartResponse(res);
                }).catch(function () {
                    setSubmitButtonsDisabled(false);
                    showToast('网络错误，启动失败', 'error');
                });
            });
        }
    }

    function handleCrawlStartResponse(res) {
        var data = (res && res.data) || {};
        if (res && res.ok) {
            showToast(data.message || '爬取已启动', 'success');
            showProgressPanel();
            // 爬取启动成功后立即显示控制按钮，不等待轮询
            var controlBtns = document.getElementById('crawl-control-btns');
            if (controlBtns) controlBtns.style.display = 'flex';
            startProgressPolling();
        } else if (res && res.status === 409) {
            showToast(data.message || '已有爬取任务运行中', 'warning');
            showProgressPanel();
            var controlBtns2 = document.getElementById('crawl-control-btns');
            if (controlBtns2) controlBtns2.style.display = 'flex';
            startProgressPolling();
        } else {
            setSubmitButtonsDisabled(false);
            showToast(data.message || '启动失败', 'error');
        }
    }

    function startProgressPolling() {
        if (_progressTimer) return;
        pollProgressOnce();
        _progressTimer = setInterval(pollProgressOnce, 2000);
    }

    function stopProgressPolling() {
        if (_progressTimer) {
            clearInterval(_progressTimer);
            _progressTimer = null;
        }
    }

    function pollProgressOnce() {
        request('/api/crawl/progress').then(function (res) {
            if (!res || !res.ok || !res.data) return;
            renderProgress(res.data);
            if (!res.data.running) {
                stopProgressPolling();
                setSubmitButtonsDisabled(false);
            }
        });
    }

    // ---------------- Crawl control (cancel / pause) ---------------- //
    function cancelCrawl() {
        if (!confirm('确定要取消当前爬取任务吗？已完成的结果会保留。')) return;

        fetch('/api/crawl/cancel', { method: 'POST' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    showToast(data.message, 'warning');
                } else {
                    showToast(data.error, 'error');
                }
            })
            .catch(function () { showToast('请求失败', 'error'); });
    }

    function togglePauseCrawl() {
        fetch('/api/crawl/pause', { method: 'POST' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    var btn = document.getElementById('btn-pause-crawl');
                    if (data.paused) {
                        btn.innerHTML = '▶ 恢复爬取';
                        btn.style.background = '#52c41a';
                        showToast('已暂停', 'warning');
                    } else {
                        btn.innerHTML = '⏸ 暂停爬取';
                        btn.style.background = '#faad14';
                        showToast('已恢复', 'success');
                    }
                } else {
                    showToast(data.error, 'error');
                }
            })
            .catch(function () { showToast('请求失败', 'error'); });
    }

    function bindCrawlControl() {
        var cancelBtn = document.getElementById('btn-cancel-crawl');
        var pauseBtn = document.getElementById('btn-pause-crawl');
        if (cancelBtn) cancelBtn.addEventListener('click', cancelCrawl);
        if (pauseBtn) pauseBtn.addEventListener('click', togglePauseCrawl);
    }

    function renderProgress(p) {
        var fill = document.getElementById('progress-bar-fill');
        var label = document.getElementById('progress-bar-label');
        var current = document.getElementById('progress-current');
        var listEl = document.getElementById('progress-result-list');
        var summary = document.getElementById('progress-summary');
        var badge = document.getElementById('progress-status-badge');

        // 显示爬取配置信息
        var configInfo = document.getElementById('crawl-config-info');
        if (configInfo && p.running && p.config) {
            configInfo.style.display = 'block';

            // 模式
            var modeEl = document.getElementById('config-mode');
            if (modeEl) {
                modeEl.textContent = p.config.mode === 'all'
                    ? '全部网站'
                    : ('选中 ' + (p.config.websites || []).length + ' 个网站');
            }

            // 网站列表（仅选择性爬取时显示）
            var websitesRow = document.getElementById('config-websites-row');
            var websitesEl = document.getElementById('config-websites');
            if (p.config.mode !== 'all'
                    && (p.config.websites || []).length > 0) {
                if (websitesRow) websitesRow.style.display = 'block';
                if (websitesEl) websitesEl.textContent = p.config.websites.join('、');
            } else if (websitesRow) {
                websitesRow.style.display = 'none';
            }

            // 时间范围
            var dateRow = document.getElementById('config-date-row');
            var datesEl = document.getElementById('config-dates');
            if (!p.config.date_from && !p.config.date_to) {
                if (dateRow) dateRow.style.display = 'block';
                if (datesEl) datesEl.textContent = '全部时间';
            } else if (p.config.date_from || p.config.date_to) {
                if (dateRow) dateRow.style.display = 'block';
                var dateText = '';
                if (p.config.date_from && p.config.date_to) {
                    dateText = p.config.date_from + ' 至 ' + p.config.date_to;
                } else if (p.config.date_from) {
                    dateText = p.config.date_from + ' 起';
                } else {
                    dateText = '至 ' + p.config.date_to;
                }
                if (datesEl) datesEl.textContent = dateText;
            } else if (dateRow) {
                dateRow.style.display = 'none';
            }
        } else if (configInfo && !p.running) {
            configInfo.style.display = 'none';
        }

        var total = p.total || 0;
        var completed = p.completed || 0;
        var pct = total > 0 ? Math.floor((completed / total) * 100) : 0;

        if (fill) fill.style.width = pct + '%';
        if (label) label.textContent = completed + ' / ' + total + '  (' + pct + '%)';

        if (current) {
            if (p.running && p.current) {
                current.innerHTML = '<span class="progress-spinner"></span>'
                    + '正在爬取：<strong>' + escapeHtml(p.current) + '</strong>';
            } else if (p.running) {
                current.textContent = '正在准备任务…';
            } else if (p.end_time) {
                current.textContent = '任务完成于 ' + p.end_time;
            } else {
                current.textContent = '';
            }
        }

        // 控制按钮显隐
        var controlBtns = document.getElementById('crawl-control-btns');
        if (controlBtns) {
            controlBtns.style.display = p.running ? 'flex' : 'none';
        }

        // 如果是暂停状态，更新按钮文字
        if (p.paused) {
            var pauseBtn = document.getElementById('btn-pause-crawl');
            if (pauseBtn) {
                pauseBtn.innerHTML = '▶ 恢复爬取';
                pauseBtn.style.background = '#52c41a';
            }
        }

        if (badge) {
            if (p.running && p.paused) {
                badge.textContent = '已暂停';
                badge.className = 'progress-status-badge paused';
            } else if (p.running) {
                badge.textContent = '运行中';
                badge.className = 'progress-status-badge running';
            } else if (p.cancelled) {
                badge.textContent = '已取消';
                badge.className = 'progress-status-badge cancelled';
            } else if (total === 0) {
                badge.textContent = '空闲';
                badge.className = 'progress-status-badge idle';
            } else {
                badge.textContent = '已完成';
                badge.className = 'progress-status-badge done';
            }
        }

        if (summary) {
            if (!p.running && p.message) {
                summary.textContent = p.message;
            } else if (p.start_time) {
                summary.textContent = '开始于 ' + p.start_time;
            } else {
                summary.textContent = '';
            }
        }

        if (listEl) {
            var html = '';
            (p.results || []).forEach(function (r) {
                var iconCls = r.status === 'success' ? 'ok' : 'fail';
                var icon = r.status === 'success' ? '✓' : '✗';
                var countTxt;
                if (r.status === 'success') {
                    var inserted = r.count || 0;
                    var matched = r.total || 0;
                    var crawled = r.total_crawled || 0;
                    var parts = ['新增 ' + inserted + ' 条'];
                    if (matched) parts.push('命中 ' + matched);
                    // 仅在总爬取 > 0 且与命中不同时才额外展示
                    if (crawled && crawled !== matched) {
                        parts.push('总爬取 ' + crawled);
                    }
                    countTxt = parts.join(' / ');
                } else {
                    countTxt = '失败：' + (r.error || '未知错误');
                }
                html += '<li class="progress-result-item ' + iconCls + '">'
                    + '<span class="pri-icon">' + icon + '</span>'
                    + '<span class="pri-name">' + escapeHtml(r.name) + '</span>'
                    + '<span class="pri-count">' + escapeHtml(countTxt) + '</span>'
                    + '<span class="pri-time muted">' + escapeHtml(r.time || '') + '</span>'
                    + '</li>';
            });
            listEl.innerHTML = html;
        }
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // ---------------- Delete articles (results page) ---------------- //
    function deleteArticles(mode) {
        var message = '';
        switch(mode) {
            case 'all': message = '确定要清除所有爬取结果吗？此操作不可恢复！'; break;
            case 'filtered': message = '确定要清除当前筛选条件下的结果吗？'; break;
            case 'no_keywords': message = '确定要清除所有未匹配关键词的数据吗？'; break;
            default: return;
        }

        if (!confirm(message)) return;

        // 获取当前筛选条件
        var data = { mode: mode };
        if (mode === 'filtered') {
            var form = document.getElementById('results-filter-form');
            if (form) {
                var sourceEl = form.querySelector('[name="source"]');
                var dateFromEl = form.querySelector('[name="date_from"]');
                var dateToEl = form.querySelector('[name="date_to"]');
                var keywordEl = form.querySelector('[name="keyword"]');
                data.source = sourceEl ? sourceEl.value : '';
                data.date_from = dateFromEl ? dateFromEl.value : '';
                data.date_to = dateToEl ? dateToEl.value : '';
                data.keyword = keywordEl ? keywordEl.value : '';
            }
        }

        fetch('/api/articles/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        })
        .then(function(r) { return r.json(); })
        .then(function(result) {
            if (result.success) {
                showToast('已清除 ' + result.deleted + ' 条记录', 'success');
                setTimeout(function() { location.reload(); }, 800);
            } else {
                showToast('操作失败: ' + (result.error || '未知错误'), 'error');
            }
        })
        .catch(function(e) {
            showToast('请求失败: ' + e, 'error');
        });
    }
    window.deleteArticles = deleteArticles;

    // ---------------- Delete single article ---------------- //
    function deleteSingleArticle(id) {
        if (!confirm('确定要删除这条记录吗？')) return;

        fetch('/api/articles/' + id, { method: 'DELETE' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.success) {
                    var row = document.getElementById('article-row-' + id);
                    if (row) {
                        row.parentNode.removeChild(row);
                    } else {
                        location.reload();
                    }
                    showToast('已删除', 'success');
                } else {
                    showToast(data.error || '删除失败', 'error');
                }
            })
            .catch(function () { showToast('请求失败', 'error'); });
    }
    window.deleteSingleArticle = deleteSingleArticle;

    // ---------------- Export (results page) ---------------- //
    function bindExportButtons() {
        var form = document.getElementById('results-filter-form');
        if (!form) return;
        function buildQuery() {
            var fd = new FormData(form);
            var params = new URLSearchParams();
            ['source', 'level', 'date_from', 'date_to', 'keyword'].forEach(function (k) {
                var v = (fd.get(k) || '').toString().trim();
                if (v) params.append(k, v);
            });
            return params.toString();
        }
        var btnExcel = document.getElementById('btn-export-excel');
        var btnCsv = document.getElementById('btn-export-csv');
        if (btnExcel) {
            btnExcel.addEventListener('click', function () {
                var qs = buildQuery();
                window.location.href = '/api/export/excel' + (qs ? ('?' + qs) : '');
            });
        }
        if (btnCsv) {
            btnCsv.addEventListener('click', function () {
                var qs = buildQuery();
                window.location.href = '/api/export/csv' + (qs ? ('?' + qs) : '');
            });
        }
    }

    // ---------------- Status auto-refresh ---------------- //
    function refreshStatus() {
        var grid = document.getElementById('site-status-grid');
        if (!grid) return;
        request('/api/status').then(function (res) {
            if (!res.ok || !res.data || !res.data.sites) return;
            res.data.sites.forEach(function (site) {
                var card = grid.querySelector('[data-name="' + cssEscape(site.name) + '"]');
                if (!card) return;
                card.className = 'site-card status-' + site.status;
                var dot = card.querySelector('.status-dot');
                if (dot) dot.className = 'status-dot status-dot-' + site.status;
                var meta = card.querySelector('.site-card-meta .muted');
                if (meta) meta.textContent = site.last_crawl_time || '尚未爬取';
            });
            var label = document.getElementById('status-updated-at');
            if (label && res.data.updated_at) {
                label.textContent = '已更新 ' + res.data.updated_at.substr(11);
            }
        });
    }

    function cssEscape(s) {
        return String(s).replace(/(["\\])/g, '\\$1');
    }

    // ---------------- Keywords ---------------- //
    function bindKeywordsPage() {
        var form = document.getElementById('form-add-keyword');
        if (form) {
            form.addEventListener('submit', function (ev) {
                ev.preventDefault();
                var fd = new FormData(form);
                request('/api/keywords', {
                    method: 'POST',
                    body: {
                        keyword: fd.get('keyword'),
                        category: fd.get('category'),
                    },
                }).then(function (res) {
                    if (res.ok && res.data.status === 'ok') {
                        showToast(res.data.message || '添加成功', 'success');
                        setTimeout(function () { location.reload(); }, 600);
                    } else {
                        showToast(res.data.message || '添加失败', 'error');
                    }
                });
            });
        }

        document.querySelectorAll('.keyword-delete').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var id = btn.getAttribute('data-id');
                var name = btn.getAttribute('data-name');
                if (!confirm('确认删除关键词 "' + name + '"？')) return;
                request('/api/keywords/' + id, { method: 'DELETE' })
                    .then(function (res) {
                        if (res.ok && res.data.status === 'ok') {
                            showToast('删除成功', 'success');
                            var chip = btn.closest('.keyword-chip');
                            if (chip && chip.parentNode) chip.parentNode.removeChild(chip);
                        } else {
                            showToast(res.data.message || '删除失败', 'error');
                        }
                    });
            });
        });
    }

    // ---------------- Websites ---------------- //
    function openModal(id) {
        var el = document.getElementById(id);
        if (el) el.hidden = false;
    }
    function closeModal(id) {
        var el = document.getElementById(id);
        if (el) el.hidden = true;
    }

    function fillWebsiteForm(data) {
        var form = document.getElementById('form-website');
        if (!form) return;
        form.elements['id'].value = data.id || '';
        form.elements['name'].value = data.name || '';
        form.elements['url'].value = data.url || '';
        form.elements['level'].value = data.level || '国家';
        form.elements['buttons'].value = data.buttons || '';
        var titleEl = document.getElementById('website-modal-title');
        if (titleEl) titleEl.textContent = data.id ? '编辑网站' : '添加网站';
    }

    function bindWebsitesPage() {
        var addBtn = document.getElementById('btn-add-website');
        if (!addBtn) return;

        addBtn.addEventListener('click', function () {
            fillWebsiteForm({});
            openModal('website-modal');
        });

        // 关闭按钮
        document.querySelectorAll('[data-modal-close]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var mask = btn.closest('.modal-mask');
                if (mask) mask.hidden = true;
            });
        });
        document.querySelectorAll('.modal-mask').forEach(function (mask) {
            mask.addEventListener('click', function (ev) {
                if (ev.target === mask) mask.hidden = true;
            });
        });

        // 编辑/删除按钮
        var tbody = document.getElementById('websites-tbody');
        if (tbody) {
            tbody.addEventListener('click', function (ev) {
                var target = ev.target;
                if (target.classList.contains('btn-edit-website')) {
                    var row = target.closest('tr');
                    fillWebsiteForm({
                        id: row.dataset.id,
                        name: row.dataset.name,
                        url: row.dataset.url,
                        level: row.dataset.level,
                        buttons: row.dataset.buttons,
                    });
                    openModal('website-modal');
                } else if (target.classList.contains('btn-delete-website')) {
                    var row2 = target.closest('tr');
                    askConfirm(
                        '确认删除网站 "' + row2.dataset.name + '" 吗？此操作不可恢复。',
                        function () {
                            request('/api/websites/' + row2.dataset.id, { method: 'DELETE' })
                                .then(function (res) {
                                    if (res.ok && res.data.status === 'ok') {
                                        showToast('删除成功', 'success');
                                        row2.parentNode.removeChild(row2);
                                    } else {
                                        showToast(res.data.message || '删除失败', 'error');
                                    }
                                });
                        }
                    );
                }
            });
        }

        // 提交表单
        var form = document.getElementById('form-website');
        if (form) {
            // 快速添加常用栏目
            var suggestRow = document.getElementById('buttons-suggest');
            var inputButtons = document.getElementById('input-buttons');
            if (suggestRow && inputButtons) {
                suggestRow.addEventListener('click', function (ev) {
                    if (!ev.target.classList.contains('suggest-chip')) return;
                    var value = ev.target.getAttribute('data-value');
                    var current = (inputButtons.value || '').trim();
                    var items = current
                        ? current.split(/[,，]/).map(function (s) { return s.trim(); }).filter(Boolean)
                        : [];
                    if (items.indexOf(value) !== -1) {
                        showToast('已包含该栏目', 'warning');
                        return;
                    }
                    items.push(value);
                    inputButtons.value = items.join(',');
                });
            }

            form.addEventListener('submit', function (ev) {
                ev.preventDefault();
                var fd = new FormData(form);
                var id = fd.get('id');
                var payload = {
                    name: (fd.get('name') || '').trim(),
                    url: (fd.get('url') || '').trim(),
                    level: fd.get('level') || '国家',
                    buttons: (fd.get('buttons') || '').trim(),
                };
                if (!payload.name || !payload.url) {
                    showToast('网站名称与 URL 不能为空', 'warning');
                    return;
                }
                var url = id ? ('/api/websites/' + id) : '/api/websites';
                var method = id ? 'PUT' : 'POST';
                request(url, { method: method, body: payload })
                    .then(function (res) {
                        if (res.ok && res.data.status === 'ok') {
                            showToast(id ? '更新成功' : '添加成功', 'success');
                            closeModal('website-modal');
                            setTimeout(function () { location.reload(); }, 500);
                        } else {
                            showToast(res.data.message || '保存失败', 'error');
                        }
                    });
            });
        }
    }

    // ---------------- Confirm dialog ---------------- //
    function askConfirm(message, onOk) {
        var modal = document.getElementById('confirm-modal');
        if (!modal) {
            if (confirm(message)) onOk && onOk();
            return;
        }
        var msgEl = document.getElementById('confirm-message');
        if (msgEl) msgEl.textContent = message;
        var okBtn = document.getElementById('confirm-ok');
        var newBtn = okBtn.cloneNode(true);
        okBtn.parentNode.replaceChild(newBtn, okBtn);
        newBtn.addEventListener('click', function () {
            modal.hidden = true;
            onOk && onOk();
        });
        modal.hidden = false;
    }
    window.askConfirm = askConfirm;

    // ---------------- Boot ---------------- //
    document.addEventListener('DOMContentLoaded', function () {
        bindManualCrawl();
        bindCrawlPanel();
        bindCrawlControl();
        bindKeywordsPage();
        bindWebsitesPage();
        bindExportButtons();

        // 仪表盘自动刷新状态
        if (document.getElementById('site-status-grid')) {
            setInterval(refreshStatus, 60000);
        }
        // 页面载入时轮询一次进度：如果已有任务在跑，自动显示
        if (document.getElementById('crawl-progress-panel')) {
            request('/api/crawl/progress').then(function (res) {
                if (res && res.ok && res.data
                    && (res.data.running || (res.data.results || []).length > 0)) {
                    showProgressPanel();
                    renderProgress(res.data);
                    if (res.data.running) startProgressPolling();
                }
            });
        }
    });
})();
