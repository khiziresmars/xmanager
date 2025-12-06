// Use relative URLs - nginx proxies /manager/ to API service
const API_URL = '';
let currentUsers = [];
let lowTrafficUsers = [];
let unlimitedUsers = [];

// Pagination variables
let currentPage = 1;
let pageSize = 50;
let totalUsers = 0;

// Tab switching
function showTab(tabName) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.sidebar-item').forEach(item => item.classList.remove('active'));

    document.getElementById('tab-' + tabName).classList.add('active');
    if (event && event.target) {
        event.target.classList.add('active');
    }

    // Close mobile sidebar after selection
    if (window.innerWidth <= 900) {
        closeSidebar();
    }

    // Handle tab-specific actions
    if (tabName === 'api-tokens') {
        loadTokens();
        stopMonitoring();
        stopQueuePolling();
    } else if (tabName === 'monitoring') {
        startMonitoring();
        stopQueuePolling();
    } else if (tabName === 'bulk-create') {
        startQueuePolling();
        stopMonitoring();
    } else if (tabName === 'bulk-operations') {
        loadBulkUsers();
        stopMonitoring();
        stopQueuePolling();
    } else if (tabName === 'panel') {
        loadXuiStatus();
        loadPanelCredentials();
        stopMonitoring();
        stopQueuePolling();
    } else {
        stopMonitoring();
        stopQueuePolling();
    }
}

// Toggle mobile sidebar
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    sidebar.classList.toggle('mobile-open');
    overlay.classList.toggle('active');
    document.body.style.overflow = sidebar.classList.contains('mobile-open') ? 'hidden' : '';
}

// Close mobile sidebar
function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    sidebar.classList.remove('mobile-open');
    overlay.classList.remove('active');
    document.body.style.overflow = '';
}

// Toast notifications
function showToast(message, type) {
    type = type || 'success';
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(function() { toast.remove(); }, 3000);
}

// Logout function
async function logout() {
    try {
        const response = await fetch('api/auth/logout', {
            method: 'POST',
            credentials: 'include'
        });

        if (response.ok) {
            window.location.href = 'login';
        } else {
            showToast('Ошибка выхода', 'error');
        }
    } catch (error) {
        console.error('Logout error:', error);
        window.location.href = 'login';
    }
}

// Format bytes
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    var k = 1024;
    var sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    var i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

// Format date
function formatDate(timestamp) {
    if (!timestamp || timestamp === 0) return 'Бессрочно';
    var date = new Date(timestamp);
    return date.toLocaleDateString('ru-RU') + ' ' + date.toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'});
}

// Load stats
function loadStats() {
    fetch(API_URL + 'api/stats')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            document.getElementById('total-users').textContent = data.total_users || 0;
            document.getElementById('active-users').textContent = data.active_users || 0;
            document.getElementById('total-upload').textContent = formatBytes(data.total_upload || 0);
            document.getElementById('total-download').textContent = formatBytes(data.total_download || 0);
        })
        .catch(function(error) {
            console.error('Error loading stats:', error);
        });

    // Load problem users count (expired, disabled)
    fetch(API_URL + 'api/users/problems', { credentials: 'include' })
        .then(function(response) { return response.json(); })
        .then(function(data) {
            var expiredEl = document.getElementById('expired-users');
            var disabledEl = document.getElementById('disabled-users');
            if (expiredEl) expiredEl.textContent = data.expired?.count || 0;
            if (disabledEl) disabledEl.textContent = data.disabled?.count || 0;
        })
        .catch(function(error) {
            console.error('Error loading problem users:', error);
        });
}

// Store inbounds data globally
let inboundsData = [];

// Load inbounds
function loadInbounds() {
    fetch(API_URL + 'api/inbounds')
        .then(function(response) { return response.json(); })
        .then(function(data) {
            inboundsData = data.inbounds;
            var select = document.getElementById('bulk-inbound');
            select.innerHTML = data.inbounds.map(function(inbound) {
                return '<option value="' + inbound.id + '" data-protocol="' + inbound.protocol + '">' +
                       inbound.remark + ' (' + inbound.protocol + ':' + inbound.port + ')</option>';
            }).join('');

            // Trigger change event to show appropriate fields
            if (data.inbounds.length > 0) {
                handleInboundChange();
            }
        })
        .catch(function(error) {
            console.error('Error loading inbounds:', error);
        });
}

// Handle inbound selection change
function handleInboundChange() {
    var select = document.getElementById('bulk-inbound');
    var selectedId = parseInt(select.value);

    if (!selectedId) {
        document.getElementById('shadowsocks-fields').style.display = 'none';
        document.getElementById('vless-fields').style.display = 'none';
        document.getElementById('protocol-info').style.display = 'block';
        document.getElementById('protocol-name').textContent = 'Выберите inbound';
        return;
    }

    var selectedInbound = inboundsData.find(function(inbound) {
        return inbound.id === selectedId;
    });

    if (!selectedInbound) return;

    var protocol = selectedInbound.protocol.toLowerCase();

    // Hide all protocol-specific fields first
    document.getElementById('shadowsocks-fields').style.display = 'none';
    document.getElementById('vless-fields').style.display = 'none';
    document.getElementById('protocol-info').style.display = 'block';

    // Show fields based on protocol
    if (protocol === 'shadowsocks') {
        document.getElementById('shadowsocks-fields').style.display = 'block';
        document.getElementById('protocol-info').style.display = 'none';
    } else if (protocol === 'vless') {
        document.getElementById('vless-fields').style.display = 'block';
        document.getElementById('protocol-info').style.display = 'none';
    } else if (protocol === 'vmess') {
        document.getElementById('protocol-name').innerHTML = '✅ <strong>VMess</strong>: UUID генерируется автоматически';
    } else if (protocol === 'trojan') {
        document.getElementById('protocol-name').innerHTML = '✅ <strong>Trojan</strong>: Пароль генерируется автоматически';
    } else {
        document.getElementById('protocol-name').innerHTML = '✅ Протокол: <strong>' + protocol.toUpperCase() + '</strong>';
    }
}

// Load users
function loadUsers() {
    var search = document.getElementById('search-users').value;
    var offset = (currentPage - 1) * pageSize;
    var url = API_URL + 'api/users?limit=' + pageSize + '&offset=' + offset;
    if (search) url += '&search=' + search;

    fetch(url)
        .then(function(response) { return response.json(); })
        .then(function(data) {
            currentUsers = data.users;
            totalUsers = data.total;

            var tbody = document.getElementById('users-table-body');
            if (currentUsers.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="loading">Пользователей не найдено</td></tr>';
                updatePagination();
                return;
            }

            tbody.innerHTML = currentUsers.map(function(user) {
                return '<tr>' +
                    '<td><input type="checkbox" class="checkbox user-checkbox" value="' + user.id + '"></td>' +
                    '<td>' + user.email + '</td>' +
                    '<td><span class="badge ' + (user.enable ? 'badge-success' : 'badge-danger') + '">' + (user.enable ? 'Активен' : 'Заблокирован') + '</span></td>' +
                    '<td>' + formatBytes(user.up + user.down) + ' / ' + formatBytes(user.total) + '</td>' +
                    '<td>' + formatDate(user.expiry_time) + '</td>' +
                    '<td>' + (user.inbound_name || '-') + '</td>' +
                    '</tr>';
            }).join('');

            updatePagination();
        })
        .catch(function(error) {
            console.error('Error loading users:', error);
            showToast('Ошибка загрузки пользователей', 'error');
        });
}

// Pagination functions
function updatePagination() {
    var totalPages = Math.ceil(totalUsers / pageSize);
    var startItem = totalUsers === 0 ? 0 : (currentPage - 1) * pageSize + 1;
    var endItem = Math.min(currentPage * pageSize, totalUsers);

    // Update info text
    document.getElementById('users-pagination-info').textContent =
        'Показано ' + startItem + '-' + endItem + ' из ' + totalUsers;

    // Update navigation buttons
    document.getElementById('users-first-btn').disabled = currentPage === 1;
    document.getElementById('users-prev-btn').disabled = currentPage === 1;
    document.getElementById('users-next-btn').disabled = currentPage >= totalPages;
    document.getElementById('users-last-btn').disabled = currentPage >= totalPages;

    // Render page numbers
    renderPageNumbers(totalPages);
}

function renderPageNumbers(totalPages) {
    var container = document.getElementById('users-page-numbers');
    var html = '';
    var maxVisible = 5;
    var start = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    var end = Math.min(totalPages, start + maxVisible - 1);

    if (end - start < maxVisible - 1) {
        start = Math.max(1, end - maxVisible + 1);
    }

    if (start > 1) {
        html += '<button class="page-btn" onclick="goToPage(1)">1</button>';
        if (start > 2) {
            html += '<span style="color: var(--text-secondary); padding: 0 5px;">...</span>';
        }
    }

    for (var i = start; i <= end; i++) {
        html += '<button class="page-btn ' + (i === currentPage ? 'active' : '') + '" onclick="goToPage(' + i + ')">' + i + '</button>';
    }

    if (end < totalPages) {
        if (end < totalPages - 1) {
            html += '<span style="color: var(--text-secondary); padding: 0 5px;">...</span>';
        }
        html += '<button class="page-btn" onclick="goToPage(' + totalPages + ')">' + totalPages + '</button>';
    }

    container.innerHTML = html;
}

function goToPage(page) {
    currentPage = page;
    loadUsers();
}

function goToFirstPage() {
    goToPage(1);
}

function goToPrevPage() {
    if (currentPage > 1) {
        goToPage(currentPage - 1);
    }
}

function goToNextPage() {
    var totalPages = Math.ceil(totalUsers / pageSize);
    if (currentPage < totalPages) {
        goToPage(currentPage + 1);
    }
}

function goToLastPage() {
    var totalPages = Math.ceil(totalUsers / pageSize);
    goToPage(totalPages);
}

function changePageSize() {
    pageSize = parseInt(document.getElementById('page-size-select').value);
    currentPage = 1;
    loadUsers();
}

// Toggle multi-inbound selection UI
function toggleMultiInboundSelection() {
    var checkbox = document.getElementById('bulk-all-inbounds');
    var selector = document.getElementById('multi-inbound-selector');
    var warning = document.getElementById('multi-inbound-limit-warning');

    if (checkbox.checked) {
        selector.style.display = 'block';
        warning.style.display = 'block';
        loadInboundsCheckboxes();
    } else {
        selector.style.display = 'none';
        warning.style.display = 'none';
    }
}

// Load inbounds as checkboxes
function loadInboundsCheckboxes() {
    var container = document.getElementById('inbounds-checkboxes');
    container.innerHTML = '';

    inboundsData.forEach(function(inbound) {
        var label = document.createElement('label');
        label.style.cssText = 'display: flex; align-items: center; gap: 6px; cursor: pointer; font-size: 13px; padding: 6px; border-radius: 4px; background: var(--bg-secondary);';

        var checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = inbound.id;
        checkbox.className = 'inbound-checkbox';
        checkbox.checked = true;
        checkbox.onchange = updateSelectedInboundsCount;

        var protocolBadge = '';
        if (inbound.protocol === 'vless') protocolBadge = '🔵 VLESS';
        else if (inbound.protocol === 'vmess') protocolBadge = '🟢 VMess';
        else if (inbound.protocol === 'trojan') protocolBadge = '🔴 Trojan';
        else if (inbound.protocol === 'shadowsocks') protocolBadge = '🟣 SS';
        else protocolBadge = '⚪ ' + inbound.protocol;

        var span = document.createElement('span');
        span.textContent = protocolBadge + ' - ' + inbound.remark + ' (:' + inbound.port + ')';

        label.appendChild(checkbox);
        label.appendChild(span);
        container.appendChild(label);
    });

    updateSelectedInboundsCount();
}

// Toggle all inbounds checkboxes
function toggleAllInbounds() {
    var selectAll = document.getElementById('select-all-inbounds');
    var checkboxes = document.querySelectorAll('.inbound-checkbox');

    checkboxes.forEach(function(checkbox) {
        checkbox.checked = selectAll.checked;
    });

    updateSelectedInboundsCount();
}

// Update selected inbounds counter
function updateSelectedInboundsCount() {
    var checkboxes = document.querySelectorAll('.inbound-checkbox:checked');
    var count = checkboxes.length;
    var countSpan = document.getElementById('selected-inbounds-count');
    var selectAll = document.getElementById('select-all-inbounds');

    countSpan.textContent = count;

    // Update "select all" checkbox state
    var totalCheckboxes = document.querySelectorAll('.inbound-checkbox').length;
    selectAll.checked = (count === totalCheckboxes);

    // Update warning message
    var countInput = document.getElementById('bulk-count');
    var userCount = parseInt(countInput.value) || 0;
    var totalOps = userCount * count;

    var infoElem = document.getElementById('multi-inbound-info');
    if (totalOps > 5000) {
        infoElem.style.color = 'var(--danger)';
        infoElem.innerHTML = 'Выбрано: <span id="selected-inbounds-count">' + count + '</span> инбаундов - ⚠️ Слишком много операций (' + totalOps + ')';
    } else {
        infoElem.style.color = 'var(--success)';
        infoElem.innerHTML = 'Выбрано: <span id="selected-inbounds-count">' + count + '</span> инбаундов (всего операций: ' + totalOps + ')';
    }
}

// Bulk create users
function bulkCreateUsers(event) {
    event.preventDefault();

    var prefix = document.getElementById('bulk-prefix').value;
    var count = parseInt(document.getElementById('bulk-count').value);
    var traffic = parseInt(document.getElementById('bulk-traffic').value) * 1024 * 1024 * 1024;
    var expiryDays = parseInt(document.getElementById('bulk-expiry-days').value);
    var inboundId = parseInt(document.getElementById('bulk-inbound').value);
    var createInMultiInbounds = document.getElementById('bulk-all-inbounds').checked;

    // Если создаем в нескольких inbounds, inboundId не обязателен
    if (!createInMultiInbounds && (!inboundId || isNaN(inboundId))) {
        showToast('Пожалуйста, выберите Inbound или включите "Создать в нескольких inbounds"', 'error');
        return;
    }

    var protocol = null;
    var selectedInbound = null;

    // Получаем протокол только для одиночного инбаунда
    if (!createInMultiInbounds) {
        selectedInbound = inboundsData.find(function(inbound) {
            return inbound.id === inboundId;
        });

        if (!selectedInbound) {
            showToast('Ошибка: Inbound не найден', 'error');
            return;
        }

        protocol = selectedInbound.protocol.toLowerCase();
    }

    // Calculate expiry time
    var expiryTime = 0;
    if (expiryDays > 0) {
        expiryTime = Date.now() + (expiryDays * 24 * 60 * 60 * 1000);
    }

    // Base template
    var template = {
        name: "Bulk Create",
        prefix: prefix,
        total: traffic,
        expiry_time: expiryTime,
        limitIp: 0
    };

    // Add protocol-specific fields (only for single inbound)
    if (!createInMultiInbounds) {
        if (protocol === 'shadowsocks') {
            var method = document.getElementById('bulk-method').value;
            template.method = method;
        } else if (protocol === 'vless') {
            var flow = document.getElementById('bulk-flow').value;
            if (flow) {
                template.flow = flow;
            }
        }
    }
    // For VMess and Trojan, no additional fields needed (handled by backend)

    // Если выбрано "Создать в нескольких inbounds"
    if (createInMultiInbounds) {
        // Получаем выбранные инбаунды
        var selectedCheckboxes = document.querySelectorAll('.inbound-checkbox:checked');
        var selectedInboundIds = Array.from(selectedCheckboxes).map(function(cb) {
            return parseInt(cb.value);
        });

        if (selectedInboundIds.length === 0) {
            showToast('Выберите хотя бы один inbound', 'error');
            return;
        }

        // Проверяем лимиты
        var totalOperations = count * selectedInboundIds.length;
        if (count > 1000) {
            showToast('Максимум 1000 пользователей', 'error');
            return;
        }
        if (totalOperations > 5000) {
            showToast('Слишком много операций (' + totalOperations + '). Максимум 5000', 'error');
            return;
        }

        showToast('⏳ Создание ' + count + ' пользователей в ' + selectedInboundIds.length + ' inbounds... Будет создано ' + (selectedInboundIds.length > 1 ? selectedInboundIds.length + ' параллельных очередей' : '1 очередь'), 'info');

        fetch(API_URL + 'api/users/bulk-create-all-inbounds', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify({
                template: template,
                count: count,
                inbound_ids: selectedInboundIds
            })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => {
                    throw new Error(err.detail || 'Server error');
                });
            }
            return response.json();
        })
        .then(data => {
            showToast('✅ Создано ' + data.queues_count + ' параллельных очередей для ' + count + ' пользователей в ' + selectedInboundIds.length + ' inbounds', 'success');
            loadQueues(); // Обновляем список очередей
            // Очищаем форму
            document.getElementById('bulk-prefix').value = 'user';
            document.getElementById('bulk-count').value = '10';
            document.getElementById('bulk-all-inbounds').checked = false;
            toggleMultiInboundSelection(); // Скрываем селектор
        })
        .catch(error => {
            console.error('Error creating users:', error);
            showToast('Ошибка создания: ' + error.message, 'error');
        });

        return;
    }

    // Для больших объемов (>100) используем систему очередей
    if (count > 100) {
        showToast('⏳ Создание очереди для ' + count + ' пользователей...', 'info');

        fetch(API_URL + 'api/queues/bulk-create', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify({
                template: template,
                count: count,
                inbound_id: inboundId
            })
        })
        .then(response => response.json())
        .then(data => {
            showToast('✅ Очередь создана! Обработка началась...', 'success');
            // Обновляем список очередей
            loadQueues();
            // Очищаем форму
            document.getElementById('bulk-prefix').value = 'user';
            document.getElementById('bulk-count').value = '10';
        })
        .catch(error => {
            console.error('Error creating queue:', error);
            showToast('Ошибка создания очереди', 'error');
        });

        return;
    }

    // Для малых объемов (≤100) используем прямое создание
    showToast('⏳ Создание ' + count + ' пользователей...', 'info');

    fetch(API_URL + 'api/users/bulk-create', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            template: template,
            count: count,
            inbound_id: inboundId
        })
    })
    .then(function(response) {
        if (!response.ok) {
            return response.json().then(function(err) {
                throw new Error(err.detail || 'Server error');
            });
        }
        return response.json();
    })
    .then(function(data) {
        var message = 'Создано пользователей: ' + data.created + ' из ' + count;

        if (data.created === 0) {
            showToast('❌ Не удалось создать ни одного пользователя', 'error');
            if (data.errors && data.errors.length > 0) {
                console.error('Errors:', data.errors);
                alert('Ошибки:\n' + data.errors.join('\n'));
            }
        } else if (data.created < count) {
            showToast('⚠️ ' + message + ' (есть ошибки)', 'warning');
            if (data.errors && data.errors.length > 0) {
                console.error('Errors:', data.errors);
            }
        } else {
            showToast('✅ ' + message, 'success');
        }

        loadStats();
        // Очищаем форму при успешном создании
        if (data.created > 0) {
            document.getElementById('bulk-prefix').value = 'user';
            document.getElementById('bulk-count').value = '10';
        }
    })
    .catch(function(error) {
        console.error('Error creating users:', error);
        showToast('Ошибка создания пользователей: ' + error.message, 'error');
    });
}

// Load low traffic users
function loadLowTrafficUsers() {
    var threshold = document.getElementById('low-traffic-threshold').value;
    var sortBy = document.getElementById('low-traffic-sort').value;

    fetch(API_URL + 'api/users/low-traffic?threshold=' + threshold + '&sort_by=' + sortBy)
        .then(function(response) { return response.json(); })
        .then(function(data) {
            lowTrafficUsers = data.users;
            var tbody = document.getElementById('low-traffic-table-body');
            if (lowTrafficUsers.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="loading">Пользователей не найдено</td></tr>';
                return;
            }

            tbody.innerHTML = lowTrafficUsers.map(function(user) {
                return '<tr>' +
                    '<td><input type="checkbox" class="checkbox low-traffic-checkbox" value="' + user.id + '"></td>' +
                    '<td>' + user.email + '</td>' +
                    '<td>' + formatBytes(user.up + user.down) + '</td>' +
                    '<td style="color: var(--danger)">' + formatBytes(user.remaining || 0) + '</td>' +
                    '<td>' + formatBytes(user.total) + '</td>' +
                    '</tr>';
            }).join('');
        })
        .catch(function(error) {
            console.error('Error:', error);
            showToast('Ошибка загрузки', 'error');
        });
}

// Update filter description based on selected filter type
function updateFilterDescription() {
    var filterType = document.getElementById('unlimited-filter-type').value;
    var description = document.getElementById('filter-description');

    var descriptions = {
        'expiry': '📌 Будут найдены пользователи без ограничения по времени (expiry_time = 0)',
        'traffic': '📌 Будут найдены пользователи без ограничения трафика (total = 0 или NULL)',
        'both': '📌 Будут найдены пользователи БЕЗ обоих ограничений (бессрочные И безлимитный трафик)'
    };

    description.textContent = descriptions[filterType] || '';
}

// Load unlimited users
function loadUnlimitedUsers() {
    var filterType = document.getElementById('unlimited-filter-type').value;
    var filterSelect = document.getElementById('unlimited-filter-type');
    var filterText = filterSelect.options[filterSelect.selectedIndex].text;
    var limit = parseInt(document.getElementById('unlimited-limit').value) || 0;

    // Показываем индикатор загрузки
    var tbody = document.getElementById('unlimited-table-body');
    tbody.innerHTML = '<tr><td colspan="5" class="loading">⏳ Загрузка...</td></tr>';

    // Формируем URL с параметрами
    var url = API_URL + 'api/users/unlimited?filter_type=' + filterType;
    if (limit > 0) {
        url += '&limit=' + limit;
    }

    fetch(url)
        .then(function(response) { return response.json(); })
        .then(function(data) {
            unlimitedUsers = data.users;

            // Update status bar
            var statusBar = document.getElementById('unlimited-status-bar');
            var activeFilter = document.getElementById('unlimited-active-filter');
            var resultsCount = document.getElementById('unlimited-results-count');

            statusBar.style.display = 'block';
            activeFilter.textContent = filterText;

            // Показываем информацию о количестве результатов
            var totalCount = data.total || data.count;
            if (limit > 0 && totalCount > limit) {
                resultsCount.textContent = data.count + ' из ' + totalCount;
            } else {
                resultsCount.textContent = totalCount;
            }

            if (unlimitedUsers.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="loading">Пользователей по выбранному критерию не найдено</td></tr>';
                return;
            }

            tbody.innerHTML = unlimitedUsers.map(function(user) {
                return '<tr>' +
                    '<td><input type="checkbox" class="checkbox unlimited-checkbox" value="' + user.id + '"></td>' +
                    '<td>' + user.email + '</td>' +
                    '<td><span class="badge ' + (user.enable ? 'badge-success' : 'badge-danger') + '">' + (user.enable ? 'Активен' : 'Заблокирован') + '</span></td>' +
                    '<td>' + formatBytes(user.used_traffic || 0) + '</td>' +
                    '<td>' + formatDate(user.expiry_time) + '</td>' +
                    '</tr>';
            }).join('');

            var message = 'Загружено пользователей: ' + data.count;
            if (totalCount > data.count) {
                message += ' из ' + totalCount + ' (используйте фильтр для просмотра остальных)';
            }
            showToast(message, 'success');
        })
        .catch(function(error) {
            console.error('Error:', error);
            tbody.innerHTML = '<tr><td colspan="5" class="loading">❌ Ошибка загрузки</td></tr>';
            showToast('Ошибка загрузки', 'error');
        });
}

// Delete selected users
function deleteSelected() {
    var checkboxes = document.querySelectorAll('.user-checkbox:checked');
    var userIds = [];
    checkboxes.forEach(function(cb) { userIds.push(cb.value); });

    if (userIds.length === 0) {
        showToast('Выберите пользователей', 'error');
        return;
    }

    if (!confirm('Удалить ' + userIds.length + ' пользователей?')) return;

    fetch(API_URL + 'api/users/bulk-delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_ids: userIds})
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        showToast('Удалено: ' + data.deleted, 'success');
        loadUsers();
        loadStats();
    })
    .catch(function(error) {
        console.error('Error:', error);
        showToast('Ошибка удаления', 'error');
    });
}

// Extend expiry for unlimited users
function extendUnlimitedExpiry() {
    var checkboxes = document.querySelectorAll('.unlimited-checkbox:checked');
    var userIds = [];
    checkboxes.forEach(function(cb) { userIds.push(cb.value); });
    var days = parseInt(document.getElementById('unlimited-extend-days').value);

    if (userIds.length === 0) {
        showToast('Выберите пользователей', 'error');
        return;
    }

    fetch(API_URL + 'api/users/extend-expiry', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_ids: userIds, days: days})
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        showToast('Продлено: ' + data.updated + ' пользователей на ' + days + ' дней', 'success');
        loadUnlimitedUsers();
    })
    .catch(function(error) {
        console.error('Error:', error);
        showToast('Ошибка продления', 'error');
    });
}

// Block unlimited users
function blockUnlimitedSelected() {
    var checkboxes = document.querySelectorAll('.unlimited-checkbox:checked');
    var userIds = [];
    checkboxes.forEach(function(cb) { userIds.push(cb.value); });

    if (userIds.length === 0) {
        showToast('Выберите пользователей', 'error');
        return;
    }

    fetch(API_URL + 'api/users/toggle-status', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_ids: userIds, enable: false})
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        showToast('Заблокировано: ' + data.updated, 'success');
        loadUnlimitedUsers();
    })
    .catch(function(error) {
        console.error('Error:', error);
        showToast('Ошибка блокировки', 'error');
    });
}

// Reset traffic for unlimited users
function resetTrafficUnlimited() {
    var checkboxes = document.querySelectorAll('.unlimited-checkbox:checked');
    var userIds = [];
    checkboxes.forEach(function(cb) { userIds.push(cb.value); });

    if (userIds.length === 0) {
        showToast('Выберите пользователей', 'error');
        return;
    }

    var newLimit = prompt('Новый лимит трафика (GB):', '100');
    if (!newLimit) return;

    fetch(API_URL + 'api/users/reset-traffic', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            user_ids: userIds,
            new_limit: parseInt(newLimit) * 1024 * 1024 * 1024
        })
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        showToast('Трафик сброшен для ' + data.updated + ' пользователей. Новый лимит: ' + newLimit + ' GB', 'success');
        loadUnlimitedUsers();
    })
    .catch(function(error) {
        console.error('Error:', error);
        showToast('Ошибка сброса трафика', 'error');
    });
}

// Add traffic to unlimited users
function addTrafficUnlimited() {
    var checkboxes = document.querySelectorAll('.unlimited-checkbox:checked');
    var userIds = [];
    checkboxes.forEach(function(cb) { userIds.push(cb.value); });

    if (userIds.length === 0) {
        showToast('Выберите пользователей', 'error');
        return;
    }

    var additionalTraffic = prompt('Добавить трафик (GB):', '50');
    if (!additionalTraffic) return;

    fetch(API_URL + 'api/users/add-traffic', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            user_ids: userIds,
            additional_traffic: parseInt(additionalTraffic) * 1024 * 1024 * 1024
        })
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        showToast('Добавлено ' + additionalTraffic + ' GB для ' + data.updated + ' пользователей', 'success');
        loadUnlimitedUsers();
    })
    .catch(function(error) {
        console.error('Error:', error);
        showToast('Ошибка добавления трафика', 'error');
    });
}

// Set traffic limit for unlimited users
function setLimitUnlimited() {
    var checkboxes = document.querySelectorAll('.unlimited-checkbox:checked');
    var userIds = [];
    checkboxes.forEach(function(cb) { userIds.push(cb.value); });

    if (userIds.length === 0) {
        showToast('Выберите пользователей', 'error');
        return;
    }

    var newLimit = prompt('Установить лимит трафика (GB):', '100');
    if (!newLimit) return;

    fetch(API_URL + 'api/users/set-limit', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            user_ids: userIds,
            new_limit: parseInt(newLimit) * 1024 * 1024 * 1024
        })
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        showToast('Лимит установлен: ' + newLimit + ' GB для ' + data.updated + ' пользователей', 'success');
        loadUnlimitedUsers();
    })
    .catch(function(error) {
        console.error('Error:', error);
        showToast('Ошибка установки лимита', 'error');
    });
}

// Toggle checkboxes
function toggleAllUsers(checkbox) {
    document.querySelectorAll('.user-checkbox').forEach(function(cb) { cb.checked = checkbox.checked; });
}

function toggleAllLowTraffic(checkbox) {
    document.querySelectorAll('.low-traffic-checkbox').forEach(function(cb) { cb.checked = checkbox.checked; });
}

function toggleAllUnlimited(checkbox) {
    document.querySelectorAll('.unlimited-checkbox').forEach(function(cb) { cb.checked = checkbox.checked; });
}

// Reset traffic
function resetTrafficSelected() {
    var checkboxes = document.querySelectorAll('.low-traffic-checkbox:checked');
    var userIds = [];
    checkboxes.forEach(function(cb) { userIds.push(cb.value); });

    if (userIds.length === 0) {
        showToast('Выберите пользователей', 'error');
        return;
    }

    var newLimit = prompt('Новый лимит трафика (GB):', '100');
    if (!newLimit) return;

    fetch(API_URL + 'api/users/reset-traffic', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            user_ids: userIds,
            new_limit: parseInt(newLimit) * 1024 * 1024 * 1024
        })
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        showToast('Сброшено: ' + data.updated, 'success');
        loadLowTrafficUsers();
    })
    .catch(function(error) {
        console.error('Error:', error);
        showToast('Ошибка сброса', 'error');
    });
}

// Delete low traffic users
function deleteLowTrafficSelected() {
    var checkboxes = document.querySelectorAll('.low-traffic-checkbox:checked');
    var userIds = [];
    checkboxes.forEach(function(cb) { userIds.push(cb.value); });

    if (userIds.length === 0) {
        showToast('Выберите пользователей', 'error');
        return;
    }

    if (!confirm('Удалить ' + userIds.length + ' пользователей?')) return;

    fetch(API_URL + 'api/users/bulk-delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_ids: userIds})
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        showToast('Удалено: ' + data.deleted, 'success');
        loadLowTrafficUsers();
        loadStats();
    })
    .catch(function(error) {
        console.error('Error:', error);
        showToast('Ошибка удаления', 'error');
    });
}

// ==================== SERVER MONITORING ====================

let monitoringInterval = null;

async function loadServerMonitoring() {
    try {
        // Load online users
        const onlineResponse = await fetch(API_URL + 'api/monitoring/online-users', {
            credentials: 'include'
        });
        const onlineData = await onlineResponse.json();
        document.getElementById('online-users-count').textContent = onlineData.online_users || 0;

        // Load server health
        const healthResponse = await fetch(API_URL + 'api/monitoring/health', {
            credentials: 'include'
        });
        const health = await healthResponse.json();

        // CPU
        document.getElementById('cpu-usage').textContent = health.cpu_percent + '%';
        document.getElementById('cpu-bar').style.width = health.cpu_percent + '%';

        // Memory
        const memoryUsedGB = (health.memory_used / (1024**3)).toFixed(2);
        const memoryTotalGB = (health.memory_total / (1024**3)).toFixed(2);
        document.getElementById('memory-usage').textContent = `${memoryUsedGB} / ${memoryTotalGB} GB`;
        document.getElementById('memory-bar').style.width = health.memory_percent + '%';

        // Disk
        const diskUsedGB = (health.disk_used / (1024**3)).toFixed(2);
        const diskTotalGB = (health.disk_total / (1024**3)).toFixed(2);
        document.getElementById('disk-usage').textContent = `${diskUsedGB} / ${diskTotalGB} GB`;
        document.getElementById('disk-bar').style.width = health.disk_percent + '%';

        // Network
        document.getElementById('network-sent').textContent = formatBytes(health.network_sent);
        document.getElementById('network-recv').textContent = formatBytes(health.network_recv);

        // Uptime
        document.getElementById('server-uptime').textContent = formatUptime(health.uptime_seconds);

    } catch (error) {
        console.error('Error loading monitoring data:', error);
    }
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) {
        return `${days}д ${hours}ч`;
    } else if (hours > 0) {
        return `${hours}ч ${minutes}м`;
    } else {
        return `${minutes}м`;
    }
}

function startMonitoring() {
    loadServerMonitoring();
    // Update every 5 seconds
    if (monitoringInterval) clearInterval(monitoringInterval);
    monitoringInterval = setInterval(loadServerMonitoring, 5000);
}

function stopMonitoring() {
    if (monitoringInterval) {
        clearInterval(monitoringInterval);
        monitoringInterval = null;
    }
}

// ==================== QUEUE MANAGEMENT ====================

let queuePollingInterval = null;

async function loadQueues() {
    try {
        const response = await fetch(API_URL + 'api/queues', {
            credentials: 'include'
        });
        const data = await response.json();

        const tbody = document.getElementById('queues-table-body');
        tbody.innerHTML = '';

        if (data.queues && data.queues.length > 0) {
            data.queues.forEach(queue => {
                const progress = queue.progress;
                const percent = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;

                const statusBadge = getQueueStatusBadge(queue.status);
                const actions = getQueueActions(queue);

                // Extract metadata
                const metadata = queue.metadata || {};
                const inbound = metadata.inbound_remark || '-';
                const protocol = metadata.protocol || '-';
                const prefix = metadata.prefix || '-';

                // Add batch info if multi-inbound
                const batchInfo = metadata.multi_inbound ?
                    ` <span style="color: #999; font-size: 11px;">(${metadata.batch_number}/${metadata.total_batches_for_inbound})</span>` : '';

                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><code>${queue.id.substring(0, 8)}...</code></td>
                    <td>${inbound}${batchInfo}</td>
                    <td><span class="badge" style="background: rgba(59, 130, 246, 0.2); color: #3b82f6;">${protocol}</span></td>
                    <td><code>${prefix}</code></td>
                    <td>${progress.total}</td>
                    <td>
                        <div style="width: 100%;">
                            ${progress.completed} / ${progress.total} (${percent}%)
                            <div style="background: var(--bg-primary); height: 6px; border-radius: 3px; margin-top: 4px; overflow: hidden;">
                                <div style="background: var(--accent); height: 100%; width: ${percent}%; transition: width 0.3s;"></div>
                            </div>
                        </div>
                    </td>
                    <td>${statusBadge}</td>
                    <td>${formatDate(queue.created_at)}</td>
                    <td>${actions}</td>
                `;
                tbody.appendChild(row);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="9">Нет очередей</td></tr>';
        }
    } catch (error) {
        console.error('Error loading queues:', error);
    }
}

function getQueueStatusBadge(status) {
    const badges = {
        'pending': '<span class="badge" style="background: rgba(251, 191, 36, 0.2); color: #f59e0b;">Ожидание</span>',
        'processing': '<span class="badge" style="background: rgba(59, 130, 246, 0.2); color: #3b82f6;">Обработка...</span>',
        'completed': '<span class="badge badge-success">Завершено</span>',
        'failed': '<span class="badge badge-danger">Ошибка</span>',
        'cancelled': '<span class="badge" style="background: rgba(156, 163, 175, 0.2); color: #9ca3af;">Отменено</span>'
    };
    return badges[status] || status;
}

function getQueueActions(queue) {
    if (queue.status === 'processing' || queue.status === 'pending') {
        return `<button class="btn btn-sm btn-danger" onclick="cancelQueue('${queue.id}')">Отменить</button>`;
    } else {
        return `<button class="btn btn-sm btn-secondary" onclick="deleteQueue('${queue.id}')">Удалить</button>`;
    }
}

async function cancelQueue(queueId) {
    if (!confirm('Отменить эту очередь?')) {
        return;
    }

    try {
        const response = await fetch(API_URL + `api/queues/${queueId}/cancel`, {
            method: 'POST',
            credentials: 'include'
        });

        if (response.ok) {
            showToast('Очередь отменена', 'success');
            loadQueues();
        } else {
            showToast('Ошибка отмены очереди', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка отмены очереди', 'error');
    }
}

async function deleteQueue(queueId) {
    if (!confirm('Удалить эту очередь?')) {
        return;
    }

    try {
        const response = await fetch(API_URL + `api/queues/${queueId}`, {
            method: 'DELETE',
            credentials: 'include'
        });

        if (response.ok) {
            showToast('Очередь удалена', 'success');
            loadQueues();
        } else {
            showToast('Ошибка удаления очереди', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка удаления очереди', 'error');
    }
}

function startQueuePolling() {
    loadQueues();
    // Обновляем каждые 3 секунды
    if (queuePollingInterval) clearInterval(queuePollingInterval);
    queuePollingInterval = setInterval(loadQueues, 3000);
}

function stopQueuePolling() {
    if (queuePollingInterval) {
        clearInterval(queuePollingInterval);
        queuePollingInterval = null;
    }
}

// ==================== API TOKEN MANAGEMENT ====================

async function generateToken() {
    const tokenName = document.getElementById('token-name').value.trim();

    if (!tokenName) {
        showToast('Введите название токена', 'error');
        return;
    }

    try {
        const response = await fetch(API_URL + 'api/tokens/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ name: tokenName })
        });

        const data = await response.json();

        if (response.ok) {
            // Display the new token
            document.getElementById('new-token-value').textContent = data.token;
            document.getElementById('token-display').style.display = 'block';
            document.getElementById('token-name').value = '';

            // Store token in hidden field for copying
            window.currentToken = data.token;
        } else {
            showToast(data.detail || 'Ошибка создания токена', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка создания токена', 'error');
    }
}

function copyToken() {
    const tokenValue = window.currentToken;
    navigator.clipboard.writeText(tokenValue).then(() => {
        showToast('Токен скопирован в буфер обмена', 'success');
    }).catch(() => {
        showToast('Не удалось скопировать токен', 'error');
    });
}

function closeTokenDisplay() {
    document.getElementById('token-display').style.display = 'none';
    window.currentToken = null;
    loadTokens();
}

async function loadTokens() {
    try {
        const response = await fetch(API_URL + 'api/tokens', {
            credentials: 'include'
        });
        const data = await response.json();

        const tbody = document.getElementById('tokens-table-body');
        tbody.innerHTML = '';

        if (data.tokens && data.tokens.length > 0) {
            data.tokens.forEach(token => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${escapeHtml(token.name)}</td>
                    <td><code>${escapeHtml(token.token_preview)}</code></td>
                    <td>${formatDate(token.created_at)}</td>
                    <td>${token.last_used ? formatDate(token.last_used) : 'Не использовался'}</td>
                    <td>
                        <span class="badge ${token.active ? 'badge-success' : 'badge-danger'}">
                            ${token.active ? 'Активен' : 'Отозван'}
                        </span>
                    </td>
                    <td>
                        ${token.active ?
                            `<button class="btn btn-sm btn-warning" onclick="revokeToken('${token.full_token}')">Отозвать</button>` :
                            ''}
                        <button class="btn btn-sm btn-danger" onclick="deleteToken('${token.full_token}')">Удалить</button>
                        <button class="btn btn-sm btn-secondary" onclick="copyFullToken('${token.full_token}')">Копировать</button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="6">Нет токенов</td></tr>';
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка загрузки токенов', 'error');
    }
}

async function revokeToken(token) {
    if (!confirm('Отозвать этот токен? Он больше не будет работать.')) {
        return;
    }

    try {
        const response = await fetch(API_URL + `api/tokens/${encodeURIComponent(token)}/revoke`, {
            method: 'POST',
            credentials: 'include'
        });

        if (response.ok) {
            showToast('Токен отозван', 'success');
            loadTokens();
        } else {
            showToast('Ошибка отзыва токена', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка отзыва токена', 'error');
    }
}

async function deleteToken(token) {
    if (!confirm('Удалить этот токен? Это действие нельзя отменить.')) {
        return;
    }

    try {
        const response = await fetch(API_URL + `api/tokens/${encodeURIComponent(token)}`, {
            method: 'DELETE',
            credentials: 'include'
        });

        if (response.ok) {
            showToast('Токен удален', 'success');
            loadTokens();
        } else {
            showToast('Ошибка удаления токена', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка удаления токена', 'error');
    }
}

function copyFullToken(token) {
    navigator.clipboard.writeText(token).then(() => {
        showToast('Токен скопирован', 'success');
    }).catch(() => {
        showToast('Не удалось скопировать', 'error');
    });
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== VERSION & UPDATE MANAGEMENT ====================

async function loadVersion() {
    try {
        const response = await fetch(API_URL + 'api/system/version', {
            credentials: 'include'
        });
        const data = await response.json();

        document.getElementById('version-info').textContent =
            `⚙️ ${data.version_name} v${data.current_version}`;

        // Auto-check for updates on load
        checkForUpdates(false);
    } catch (error) {
        console.error('Error loading version:', error);
        document.getElementById('version-info').textContent = '⚙️ Версия недоступна';
    }
}

async function checkForUpdates(showLoading = true) {
    const updateButtons = document.getElementById('update-buttons');
    const updateStatus = document.getElementById('update-status');

    try {
        const response = await fetch(API_URL + 'api/system/update/check?force=' + showLoading, {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.update_available) {
            // Show update button only when update available
            updateButtons.style.display = 'flex';
            document.getElementById('new-version').textContent = data.latest_version;
            updateStatus.textContent = `✨ v${data.latest_version} доступна`;

            if (showLoading) {
                showToast(`Доступна новая версия: ${data.latest_version}`, 'info');
            }
        } else {
            // Hide update section when no update
            updateButtons.style.display = 'none';
        }
    } catch (error) {
        console.error('Error checking updates:', error);
        updateButtons.style.display = 'none';
    }
}

let updateProgressInterval = null;

function showUpdateModal() {
    document.getElementById('update-progress-modal').style.display = 'flex';
    // Reset UI
    document.getElementById('update-progress-bar').style.width = '0%';
    document.getElementById('update-progress-bar').textContent = '0%';
    document.getElementById('update-progress-stage').textContent = 'Подготовка...';
    document.getElementById('update-progress-message').textContent = 'Начало обновления...';
    document.getElementById('update-success-message').style.display = 'none';
    document.getElementById('update-error-message').style.display = 'none';
    document.getElementById('close-update-modal-btn').style.display = 'none';
}

function closeUpdateModal() {
    document.getElementById('update-progress-modal').style.display = 'none';
    if (updateProgressInterval) {
        clearInterval(updateProgressInterval);
        updateProgressInterval = null;
    }
}

function updateProgressUI(progress) {
    const progressBar = document.getElementById('update-progress-bar');
    const stageElem = document.getElementById('update-progress-stage');
    const messageElem = document.getElementById('update-progress-message');

    // Update progress bar
    progressBar.style.width = progress.progress + '%';
    progressBar.textContent = progress.progress + '%';

    // Update stage message
    const stageNames = {
        'checking': '🔍 Проверка обновлений',
        'backup': '💾 Создание резервной копии',
        'downloading': '⬇️ Скачивание обновления',
        'extracting': '📦 Распаковка файлов',
        'installing': '⚙️ Установка файлов',
        'dependencies': '📚 Установка зависимостей',
        'restarting': '🔄 Перезапуск сервиса',
        'completed': '✅ Обновление завершено',
        'failed': '❌ Ошибка обновления',
        'idle': '⏸️ Ожидание'
    };

    stageElem.textContent = stageNames[progress.status] || progress.status;
    messageElem.textContent = progress.message || '';
}

async function pollUpdateStatus() {
    try {
        const response = await fetch(API_URL + 'api/system/update/status', {
            credentials: 'include'
        });

        // Ignore 502/401 errors during service restart
        if (response.status === 502 || response.status === 401) {
            // Service is restarting, continue polling
            console.log('Service restarting (502/401), will retry...');
            return;
        }

        if (!response.ok) return;

        const data = await response.json();
        const progress = data.progress;

        updateProgressUI(progress);

        // Check if completed or failed
        if (progress.status === 'completed') {
            clearInterval(updateProgressInterval);
            document.getElementById('update-success-message').style.display = 'block';

            // Countdown and reload
            let countdown = 5;
            const countdownElem = document.getElementById('reload-countdown');
            const countdownInterval = setInterval(() => {
                countdown--;
                countdownElem.textContent = countdown;
                if (countdown <= 0) {
                    clearInterval(countdownInterval);
                    window.location.reload();
                }
            }, 1000);

        } else if (progress.status === 'failed') {
            clearInterval(updateProgressInterval);
            document.getElementById('update-error-message').textContent = '❌ Ошибка: ' + progress.message;
            document.getElementById('update-error-message').style.display = 'block';
            document.getElementById('close-update-modal-btn').style.display = 'inline-block';
        }

    } catch (error) {
        // Network errors during restart are expected
        console.log('Polling error (service restarting):', error.message);
        // Continue polling, don't show error
    }
}

async function performUpdate() {
    if (!confirm('⚠️ ВНИМАНИЕ!\n\nОбновление перезапустит сервис.\nВы потеряете текущую сессию и должны будете войти заново.\n\nПродолжить?')) {
        return;
    }

    const updateBtn = document.getElementById('perform-update-btn');
    updateBtn.disabled = true;
    updateBtn.innerHTML = '⏳ Обновление...';

    // Show progress modal
    showUpdateModal();

    try {
        // Start update
        const response = await fetch(API_URL + 'api/system/update', {
            method: 'POST',
            credentials: 'include'
        });

        const data = await response.json();

        if (response.ok) {
            // Start polling for progress
            updateProgressInterval = setInterval(pollUpdateStatus, 2000);  // Poll every 2 seconds
            pollUpdateStatus();  // Poll immediately

        } else {
            // Show error
            document.getElementById('update-error-message').textContent = '❌ Ошибка запуска обновления: ' + (data.error || data.detail || 'Unknown error');
            document.getElementById('update-error-message').style.display = 'block';
            document.getElementById('close-update-modal-btn').style.display = 'inline-block';

            updateBtn.disabled = false;
            updateBtn.innerHTML = '⬆️ Обновить до <span id="new-version"></span>';
        }
    } catch (error) {
        console.error('Error starting update:', error);
        document.getElementById('update-error-message').textContent = '❌ Ошибка сети: ' + error.message;
        document.getElementById('update-error-message').style.display = 'block';
        document.getElementById('close-update-modal-btn').style.display = 'inline-block';

        updateBtn.disabled = false;
        updateBtn.innerHTML = '⬆️ Обновить до <span id="new-version"></span>';
    }
}

// ==================== EXPIRED USERS MANAGEMENT ====================

async function loadExpiredUsers() {
    try {
        const response = await fetch(API_URL + 'api/users/expired', {
            credentials: 'include'
        });
        const data = await response.json();

        const tbody = document.getElementById('expired-table-body');
        tbody.innerHTML = '';

        if (data.users && data.users.length > 0) {
            data.users.forEach(user => {
                const expiredDate = user.expiry_time > 0 ? new Date(user.expiry_time).toLocaleString() : 'Н/Д';
                const used = formatBytes(user.up + user.down);
                const status = user.enable ? 'Активен' : 'Отключен';

                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><input type="checkbox" class="checkbox user-checkbox-expired" value="${user.id}"></td>
                    <td>${user.email}</td>
                    <td>${user.inbound_id}</td>
                    <td>${expiredDate}</td>
                    <td>${used}</td>
                    <td><span class="badge ${user.enable ? 'badge-success' : 'badge-danger'}">${status}</span></td>
                `;
                tbody.appendChild(row);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="6">Нет истекших пользователей</td></tr>';
        }
    } catch (error) {
        console.error('Error loading expired users:', error);
        showToast('Ошибка загрузки истекших пользователей', 'error');
    }
}

async function loadDisabledUsers() {
    try {
        const response = await fetch(API_URL + 'api/users/disabled', {
            credentials: 'include'
        });
        const data = await response.json();

        const tbody = document.getElementById('disabled-table-body');
        tbody.innerHTML = '';

        if (data.users && data.users.length > 0) {
            data.users.forEach(user => {
                const expiryDate = user.expiry_time > 0 ? new Date(user.expiry_time).toLocaleString() : 'Бессрочно';
                const used = formatBytes(user.up + user.down);

                const row = document.createElement('tr');
                row.innerHTML = `
                    <td><input type="checkbox" class="checkbox user-checkbox-disabled" value="${user.id}"></td>
                    <td>${user.email}</td>
                    <td>${user.inbound_id}</td>
                    <td>${expiryDate}</td>
                    <td>${used}</td>
                `;
                tbody.appendChild(row);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="5">Нет отключенных пользователей</td></tr>';
        }
    } catch (error) {
        console.error('Error loading disabled users:', error);
        showToast('Ошибка загрузки отключенных пользователей', 'error');
    }
}

function toggleAllExpired(checkbox) {
    const checkboxes = document.querySelectorAll('.user-checkbox-expired');
    checkboxes.forEach(cb => cb.checked = checkbox.checked);
}

function toggleAllDisabled(checkbox) {
    const checkboxes = document.querySelectorAll('.user-checkbox-disabled');
    checkboxes.forEach(cb => cb.checked = checkbox.checked);
}

async function deleteExpiredSelected() {
    const checkboxes = document.querySelectorAll('.user-checkbox-expired:checked');
    const userIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

    if (userIds.length === 0) {
        showToast('Выберите пользователей для удаления', 'error');
        return;
    }

    if (!confirm(`Удалить ${userIds.length} пользователей?`)) {
        return;
    }

    try {
        const response = await fetch(API_URL + 'api/users/bulk-delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify({ user_ids: userIds })
        });

        const data = await response.json();

        if (response.ok) {
            showToast(`✅ Удалено: ${data.deleted} пользователей`, 'success');
            loadExpiredUsers();
        } else {
            showToast('Ошибка удаления: ' + data.detail, 'error');
        }
    } catch (error) {
        console.error('Error deleting users:', error);
        showToast('Ошибка удаления пользователей', 'error');
    }
}

async function deleteAllExpired() {
    try {
        const response = await fetch(API_URL + 'api/users/expired', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.users.length === 0) {
            showToast('Нет истекших пользователей для удаления', 'info');
            return;
        }

        if (!confirm(`Удалить ВСЕ ${data.users.length} истекших пользователей?`)) {
            return;
        }

        const userIds = data.users.map(u => u.id);

        const deleteResponse = await fetch(API_URL + 'api/users/bulk-delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify({ user_ids: userIds })
        });

        const deleteData = await deleteResponse.json();

        if (deleteResponse.ok) {
            showToast(`✅ Удалено: ${deleteData.deleted} пользователей`, 'success');
            loadExpiredUsers();
        } else {
            showToast('Ошибка удаления: ' + deleteData.detail, 'error');
        }
    } catch (error) {
        console.error('Error deleting all expired:', error);
        showToast('Ошибка удаления пользователей', 'error');
    }
}

async function deleteDisabledSelected() {
    const checkboxes = document.querySelectorAll('.user-checkbox-disabled:checked');
    const userIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

    if (userIds.length === 0) {
        showToast('Выберите пользователей для удаления', 'error');
        return;
    }

    if (!confirm(`Удалить ${userIds.length} пользователей?`)) {
        return;
    }

    try {
        const response = await fetch(API_URL + 'api/users/bulk-delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify({ user_ids: userIds })
        });

        const data = await response.json();

        if (response.ok) {
            showToast(`✅ Удалено: ${data.deleted} пользователей`, 'success');
            loadDisabledUsers();
        } else {
            showToast('Ошибка удаления: ' + data.detail, 'error');
        }
    } catch (error) {
        console.error('Error deleting users:', error);
        showToast('Ошибка удаления пользователей', 'error');
    }
}

async function deleteAllDisabled() {
    try {
        const response = await fetch(API_URL + 'api/users/disabled', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.users.length === 0) {
            showToast('Нет отключенных пользователей для удаления', 'info');
            return;
        }

        if (!confirm(`Удалить ВСЕ ${data.users.length} отключенных пользователей?`)) {
            return;
        }

        const userIds = data.users.map(u => u.id);

        const deleteResponse = await fetch(API_URL + 'api/users/bulk-delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            credentials: 'include',
            body: JSON.stringify({ user_ids: userIds })
        });

        const deleteData = await deleteResponse.json();

        if (deleteResponse.ok) {
            showToast(`✅ Удалено: ${deleteData.deleted} пользователей`, 'success');
            loadDisabledUsers();
        } else {
            showToast('Ошибка удаления: ' + deleteData.detail, 'error');
        }
    } catch (error) {
        console.error('Error deleting all disabled:', error);
        showToast('Ошибка удаления пользователей', 'error');
    }
}

function showEnableModal() {
    const checkboxes = document.querySelectorAll('.user-checkbox-disabled:checked');
    if (checkboxes.length === 0) {
        showToast('Выберите пользователей для включения', 'error');
        return;
    }
    document.getElementById('enable-modal').style.display = 'flex';
}

function closeEnableModal() {
    document.getElementById('enable-modal').style.display = 'none';
}

async function confirmEnableUsers() {
    const checkboxes = document.querySelectorAll('.user-checkbox-disabled:checked');
    const userIds = Array.from(checkboxes).map(cb => parseInt(cb.value));

    const expiryDays = parseInt(document.getElementById('enable-expiry-days').value) || 0;
    const trafficGB = parseInt(document.getElementById('enable-traffic-gb').value) || 0;

    closeEnableModal();
    showToast('⏳ Включение пользователей...', 'info');

    const expiryTime = expiryDays > 0 ? Date.now() + (expiryDays * 24 * 60 * 60 * 1000) : 0;
    const trafficBytes = trafficGB * 1024 * 1024 * 1024;

    let enabled = 0;
    let updated = 0;

    for (const userId of userIds) {
        try {
            // 1. Enable user
            const enableResponse = await fetch(API_URL + `api/users/${userId}/toggle`, {
                method: 'PUT',
                credentials: 'include'
            });

            if (enableResponse.ok) {
                enabled++;

                // 2. Set expiry time if specified
                if (expiryDays >= 0) {
                    await fetch(API_URL + `api/users/${userId}/expiry`, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        credentials: 'include',
                        body: JSON.stringify({ expiry_days: expiryDays })
                    });
                }

                // 3. Set traffic limit if specified
                if (trafficGB > 0) {
                    await fetch(API_URL + `api/users/${userId}/traffic`, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        credentials: 'include',
                        body: JSON.stringify({ traffic_limit: trafficBytes })
                    });
                }

                updated++;
            }
        } catch (error) {
            console.error('Error enabling user:', error);
        }
    }

    showToast(`✅ Включено: ${enabled}, обновлено: ${updated} из ${userIds.length} пользователей`, 'success');
    loadDisabledUsers();
}

// ==================== SSL CERTIFICATE MANAGEMENT ====================

function showSSLModal() {
    document.getElementById('ssl-progress-modal').style.display = 'flex';
    document.getElementById('ssl-progress-message').style.display = 'block';
    document.getElementById('ssl-success-message').style.display = 'none';
    document.getElementById('ssl-error-message').style.display = 'none';
    document.getElementById('close-ssl-modal-btn').style.display = 'none';
}

function closeSSLModal() {
    document.getElementById('ssl-progress-modal').style.display = 'none';
}

async function loadSSLStatus() {
    try {
        const response = await fetch(API_URL + 'api/ssl/status', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            const cert = data.certificate;

            // Update domain
            document.getElementById('ssl-domain').textContent = data.domain || 'Не настроен';

            if (cert.has_certificate) {
                // Status with color
                const statusElem = document.getElementById('ssl-status');
                if (cert.is_expired) {
                    statusElem.textContent = '❌ Истёк';
                    statusElem.style.color = 'var(--danger)';
                } else if (cert.needs_renewal) {
                    statusElem.textContent = '⚠️ Требует обновления';
                    statusElem.style.color = 'var(--warning)';
                } else {
                    statusElem.textContent = '✅ Действителен';
                    statusElem.style.color = 'var(--success)';
                }

                // Days until expiry
                const daysElem = document.getElementById('ssl-days-left');
                daysElem.textContent = cert.days_until_expiry !== null ? cert.days_until_expiry : '-';
                if (cert.days_until_expiry < 0) {
                    daysElem.style.color = 'var(--danger)';
                } else if (cert.days_until_expiry < 30) {
                    daysElem.style.color = 'var(--warning)';
                } else {
                    daysElem.style.color = 'var(--success)';
                }

                // Expiry date
                if (cert.not_after) {
                    const expiryDate = new Date(cert.not_after);
                    document.getElementById('ssl-expiry-date').textContent = expiryDate.toLocaleDateString('ru-RU', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                } else {
                    document.getElementById('ssl-expiry-date').textContent = '-';
                }

                // Certificate details
                const details = `
Домен: ${data.domain || 'N/A'}
Статус: ${cert.status}
Путь к сертификату: ${cert.cert_path || 'N/A'}
Путь к ключу: ${cert.key_path || 'N/A'}
Действителен с: ${cert.not_before ? new Date(cert.not_before).toLocaleString('ru-RU') : 'N/A'}
Действителен до: ${cert.not_after ? new Date(cert.not_after).toLocaleString('ru-RU') : 'N/A'}
Дней до истечения: ${cert.days_until_expiry !== null ? cert.days_until_expiry : 'N/A'}
Требует обновления: ${cert.needs_renewal ? 'Да' : 'Нет'}
Subject: ${cert.subject || 'N/A'}
                `.trim();
                document.getElementById('ssl-cert-details').textContent = details;

            } else {
                document.getElementById('ssl-status').textContent = '⚠️ Не найден';
                document.getElementById('ssl-status').style.color = 'var(--warning)';
                document.getElementById('ssl-days-left').textContent = '-';
                document.getElementById('ssl-expiry-date').textContent = '-';
                document.getElementById('ssl-cert-details').textContent = cert.message || 'Сертификат не найден';
            }
        } else {
            showToast('Ошибка загрузки статуса SSL: ' + (data.detail || 'Unknown error'), 'error');
        }
    } catch (error) {
        console.error('Error loading SSL status:', error);
        showToast('Ошибка загрузки статуса SSL', 'error');
    }
}

async function renewSSLCertificate(force = false) {
    const confirmMsg = force
        ? '⚠️ Принудительное обновление SSL сертификата?\n\nЭто обновит сертификат даже если он ещё действителен, перезапустит Nginx и 3x-ui.\n\nПродолжить?'
        : '🔐 Обновить SSL сертификат?\n\nЭто обновит сертификат через Let\'s Encrypt (если требуется) и перезапустит сервисы.\n\nПродолжить?';

    if (!confirm(confirmMsg)) {
        return;
    }

    showSSLModal();
    document.getElementById('ssl-progress-message').textContent = 'Обновление сертификата через Let\'s Encrypt...';

    try {
        const response = await fetch(API_URL + 'api/ssl/renew?force=' + force, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        document.getElementById('ssl-progress-message').style.display = 'none';

        if (data.success) {
            const successElem = document.getElementById('ssl-success-message');
            if (data.renewed) {
                successElem.innerHTML = '✅ Сертификат успешно обновлён!<br><small>' + (data.message || '') + '</small>';
            } else {
                successElem.innerHTML = 'ℹ️ ' + (data.message || 'Обновление не требуется');
            }
            successElem.style.display = 'block';
            showToast('SSL сертификат обновлён', 'success');
            loadSSLStatus();
        } else {
            const errorElem = document.getElementById('ssl-error-message');
            errorElem.textContent = '❌ Ошибка: ' + (data.message || 'Unknown error');
            errorElem.style.display = 'block';
            showToast('Ошибка обновления SSL: ' + (data.message || 'Unknown'), 'error');
        }

        document.getElementById('close-ssl-modal-btn').style.display = 'inline-block';

    } catch (error) {
        console.error('Error renewing SSL:', error);
        document.getElementById('ssl-progress-message').style.display = 'none';
        const errorElem = document.getElementById('ssl-error-message');
        errorElem.textContent = '❌ Ошибка: ' + error.message;
        errorElem.style.display = 'block';
        document.getElementById('close-ssl-modal-btn').style.display = 'inline-block';
        showToast('Ошибка обновления SSL', 'error');
    }
}

async function update3xuiCertificate() {
    if (!confirm('Обновить пути сертификата в панели 3x-ui?\n\nЭто обновит настройки 3x-ui для использования текущего Let\'s Encrypt сертификата и перезапустит сервисы.')) {
        return;
    }

    try {
        const response = await fetch(API_URL + 'api/ssl/update-3xui', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Сертификат в 3x-ui обновлён, сервисы перезапущены', 'success');
            loadSSLStatus();
        } else {
            showToast('Ошибка: ' + (data.message || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error updating 3x-ui certificate:', error);
        showToast('Ошибка обновления 3x-ui', 'error');
    }
}

async function restartSSLServices() {
    if (!confirm('Перезапустить Nginx и 3x-ui?\n\nЭто применит изменения сертификата.')) {
        return;
    }

    try {
        const response = await fetch(API_URL + 'api/ssl/restart-services', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            const services = data.services;
            let msg = 'Результаты перезапуска:\n';
            msg += `• Nginx: ${services.nginx.success ? '✅' : '❌'} ${services.nginx.message}\n`;
            msg += `• 3x-ui: ${services['x-ui'].success ? '✅' : '❌'} ${services['x-ui'].message}`;
            showToast(msg, services.nginx.success && services['x-ui'].success ? 'success' : 'warning');
        } else {
            showToast('Ошибка: ' + (data.message || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error restarting services:', error);
        showToast('Ошибка перезапуска сервисов', 'error');
    }
}

// ==================== EXPIRED USERS EXTENSION ====================

function showExtendExpiredModal() {
    document.getElementById('extend-expired-modal').style.display = 'flex';
}

function closeExtendExpiredModal() {
    document.getElementById('extend-expired-modal').style.display = 'none';
}

async function extendExpiredUsers() {
    const checkboxes = document.querySelectorAll('#expired-table-body input[type="checkbox"]:checked');
    if (checkboxes.length === 0) {
        showToast('Выберите пользователей для продления', 'warning');
        return;
    }

    const days = parseInt(document.getElementById('extend-expiry-days').value) || 30;
    const resetTraffic = document.getElementById('extend-reset-traffic').value === 'yes';

    const userIds = Array.from(checkboxes).map(cb => cb.value);
    await processExtendUsers(userIds, days, resetTraffic);
    closeExtendExpiredModal();
}

async function extendAllExpiredUsers() {
    if (!confirm('Продлить ВСЕХ истекших пользователей?')) return;

    const days = parseInt(document.getElementById('extend-expiry-days').value) || 30;
    const resetTraffic = document.getElementById('extend-reset-traffic').value === 'yes';

    // Get all expired user IDs
    const rows = document.querySelectorAll('#expired-table-body tr');
    const userIds = [];
    rows.forEach(row => {
        const checkbox = row.querySelector('input[type="checkbox"]');
        if (checkbox) userIds.push(checkbox.value);
    });

    if (userIds.length === 0) {
        showToast('Нет истекших пользователей', 'warning');
        return;
    }

    await processExtendUsers(userIds, days, resetTraffic);
    closeExtendExpiredModal();
}

async function processExtendUsers(userIds, days, resetTraffic) {
    let extended = 0;
    let errors = 0;
    const total = userIds.length;

    // Show progress
    const tbody = document.getElementById('expired-table-body');
    const progressHtml = `<tr><td colspan="6" style="text-align: center; padding: 20px;">
        <div style="display: inline-block; width: 30px; height: 30px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite;"></div>
        <br><br>
        <span id="extend-progress" style="color: var(--accent);">Продление: 0/${total}</span>
    </td></tr>`;
    tbody.innerHTML = progressHtml;

    for (const id of userIds) {
        try {
            // Update progress
            document.getElementById('extend-progress').textContent = `Продление: ${extended + 1}/${total}`;

            // Extend expiry
            const expiryResponse = await fetch(API_URL + 'api/users/extend-expiry', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({user_ids: [id], days: days})
            });

            // Enable user
            await fetch(API_URL + `api/users/${id}/toggle`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({enable: true})
            });

            // Reset traffic if needed
            if (resetTraffic) {
                await fetch(API_URL + 'api/users/reset-traffic', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    credentials: 'include',
                    body: JSON.stringify({user_ids: [id]})
                });
            }

            extended++;
        } catch (error) {
            console.error('Error extending user:', error);
            errors++;
        }
    }

    showToast(`✅ Продлено: ${extended}, ошибок: ${errors}`, extended > 0 ? 'success' : 'error');
    loadExpiredUsers();
}

// ==================== X-UI CONTROL ====================

let panelUrl = ':54321/panel/';

async function loadXuiStatus() {
    try {
        const response = await fetch(API_URL + 'api/server/info', {credentials: 'include'});
        const info = await response.json();

        const statusElem = document.getElementById('xui-service-status');
        if (info.xui_installed) {
            statusElem.textContent = '✅ Активен';
            statusElem.style.color = 'var(--success)';
        } else {
            statusElem.textContent = '❌ Не установлен';
            statusElem.style.color = 'var(--danger)';
        }

        document.getElementById('xui-version').textContent = info.xui_version || '-';
        document.getElementById('xray-version').textContent = info.xray_version || '-';
        document.getElementById('tcp-connections').textContent = info.tcp_connections || '0';

        if (info.panel_url) {
            panelUrl = info.panel_url;
        }

    } catch (error) {
        console.error('Error loading X-UI status:', error);
    }
}

function openPanel() {
    const host = window.location.hostname;
    window.open(`https://${host}/esmars/panel/`, '_blank');
}

async function runSpeedtest() {
    const resultDiv = document.getElementById('speedtest-result');
    resultDiv.innerHTML = '<span style="color: var(--accent);">🚀 Запуск speedtest (до 2 минут)...</span>';

    try {
        const response = await fetch(API_URL + 'api/server/speedtest', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            resultDiv.innerHTML = `
                <div style="padding: 10px; background: var(--bg-primary); border-radius: 6px;">
                    ⬇️ Download: <strong>${data.download} Mbps</strong> |
                    ⬆️ Upload: <strong>${data.upload} Mbps</strong> |
                    🏓 Ping: <strong>${data.ping} ms</strong>
                    <br><small style="color: var(--text-secondary);">Server: ${data.server}</small>
                </div>
            `;
        } else {
            resultDiv.innerHTML = `<span style="color: var(--danger);">❌ ${data.message}</span>`;
        }
    } catch (error) {
        resultDiv.innerHTML = '<span style="color: var(--danger);">❌ Ошибка speedtest</span>';
    }
}

async function regenerateKeys() {
    if (!confirm('⚠️ Это сгенерирует НОВЫЕ UUID/пароли для ВСЕХ пользователей!\n\nВсе текущие ключи перестанут работать.\n\nПродолжить?')) return;

    try {
        const response = await fetch(API_URL + 'api/users/regenerate-keys', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast(`✅ ${data.message}`, 'success');
        } else {
            showToast('Ошибка: ' + data.message, 'error');
        }
    } catch (error) {
        showToast('Ошибка регенерации ключей', 'error');
    }
}

async function applySNI() {
    const sni = prompt('Введите SNI домен для применения ко всем Reality inbounds:', 'www.google.com');
    if (!sni) return;

    try {
        const response = await fetch(API_URL + `api/inbounds/apply-sni?sni=${encodeURIComponent(sni)}`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast(`✅ ${data.message}`, 'success');
        } else {
            showToast('Ошибка: ' + data.message, 'error');
        }
    } catch (error) {
        showToast('Ошибка применения SNI', 'error');
    }
}

async function xuiAction(action) {
    if (!confirm(`${action === 'restart' ? 'Перезапустить' : action === 'stop' ? 'Остановить' : 'Запустить'} x-ui?`)) return;

    try {
        const response = await fetch(API_URL + `api/system/xui/${action}`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (response.ok) {
            showToast(`✅ X-UI: ${action}`, 'success');
            setTimeout(loadXuiStatus, 2000);
        } else {
            showToast(`Ошибка: ${data.detail || 'Unknown'}`, 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка выполнения команды', 'error');
    }
}

async function loadXuiLogs(type) {
    try {
        const response = await fetch(API_URL + `api/system/logs?type=${type}&lines=100`, {
            credentials: 'include'
        });
        const data = await response.json();
        document.getElementById('xui-logs').textContent = data.logs || 'Логи пусты';
    } catch (error) {
        console.error('Error loading logs:', error);
        document.getElementById('xui-logs').textContent = 'Ошибка загрузки логов';
    }
}

function clearXuiLogs() {
    document.getElementById('xui-logs').textContent = 'Логи очищены';
}

async function updateDatFiles() {
    if (!confirm('Обновить GeoIP и GeoSite файлы?\n\nЭто загрузит последние версии баз данных маршрутизации.')) return;

    showToast('⏳ Обновление dat файлов...', 'info');

    try {
        const response = await fetch(API_URL + 'api/system/update-dat', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Dat файлы обновлены', 'success');
        } else {
            showToast('Ошибка: ' + (data.message || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка обновления dat файлов', 'error');
    }
}

async function updateXray() {
    if (!confirm('Обновить Xray до последней версии?')) return;

    try {
        const response = await fetch(API_URL + 'api/system/xray/update', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (response.ok) {
            showToast('✅ Xray обновлен', 'success');
            loadXuiStatus();
        } else {
            showToast('Ошибка: ' + (data.detail || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка обновления Xray', 'error');
    }
}

// ==================== INBOUND MANAGEMENT ====================

async function loadInboundsTable() {
    const container = document.getElementById('inbounds-list-container');
    container.innerHTML = '<div style="text-align: center; padding: 20px; color: #666;">⏳ Загрузка...</div>';

    try {
        const response = await fetch(API_URL + 'api/inbounds', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.inbounds && data.inbounds.length > 0) {
            container.innerHTML = data.inbounds.map(ib => {
                const stream = ib.stream_settings || {};
                const security = stream.security || 'none';
                const network = stream.network || 'tcp';

                // Extract security-specific details
                let securityBadge = '';
                let destInfo = '';
                let sniInfo = '';

                if (security === 'reality') {
                    securityBadge = '<span class="protocol-badge security-reality">Reality</span>';
                    const reality = stream.realitySettings || {};
                    destInfo = reality.dest || '-';
                    sniInfo = (reality.serverNames || [])[0] || '-';
                } else if (security === 'tls') {
                    securityBadge = '<span class="protocol-badge security-tls">TLS</span>';
                    const tls = stream.tlsSettings || {};
                    sniInfo = (tls.serverNames || [])[0] || '-';
                }

                // Format traffic
                const formatBytes = (bytes) => {
                    if (!bytes) return '0 B';
                    const k = 1024;
                    const sizes = ['B', 'KB', 'MB', 'GB'];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
                };

                return `
                    <div class="inbound-card" id="inbound-${ib.id}">
                        <div class="inbound-header" onclick="toggleInboundDetails(${ib.id})">
                            <span class="inbound-status-dot ${ib.enable ? 'active' : 'inactive'}"></span>

                            <div class="inbound-info">
                                <div class="inbound-name">${ib.remark || 'Без названия'}</div>
                                <div class="inbound-meta">
                                    <span>Port: ${ib.port}</span>
                                    <span>↓ ${formatBytes(ib.down)}</span>
                                    <span>↑ ${formatBytes(ib.up)}</span>
                                    <span>${ib.users_count || 0} clients</span>
                                </div>
                            </div>

                            <div class="inbound-badges">
                                <span class="protocol-badge protocol-${ib.protocol}">${ib.protocol.toUpperCase()}</span>
                                ${securityBadge}
                            </div>

                            <div class="inbound-actions" onclick="event.stopPropagation()">
                                <button class="btn-icon" onclick="editInbound(${ib.id})" title="Edit">✏️</button>
                                <button class="btn-icon" onclick="toggleInbound(${ib.id})" title="Toggle">${ib.enable ? '⏸️' : '▶️'}</button>
                                <button class="btn-icon" onclick="deleteInbound(${ib.id}, '${ib.remark || 'Inbound'}')" title="Delete" style="color: var(--danger);">🗑️</button>
                            </div>
                        </div>

                        <div class="inbound-details">
                            <div class="detail-grid">
                                <div class="detail-item">
                                    <div class="detail-label">ID</div>
                                    <div class="detail-value">${ib.id}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Network</div>
                                    <div class="detail-value">${network}</div>
                                </div>
                                <div class="detail-item">
                                    <div class="detail-label">Security</div>
                                    <div class="detail-value">${security}</div>
                                </div>
                                ${destInfo ? `
                                <div class="detail-item">
                                    <div class="detail-label">Dest</div>
                                    <div class="detail-value">${destInfo}</div>
                                </div>` : ''}
                                ${sniInfo ? `
                                <div class="detail-item">
                                    <div class="detail-label">SNI</div>
                                    <div class="detail-value">${sniInfo}</div>
                                </div>` : ''}
                                <div class="detail-item">
                                    <div class="detail-label">Listen</div>
                                    <div class="detail-value">${ib.listen || '0.0.0.0'}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            container.innerHTML = '<div style="text-align: center; padding: 40px; color: #666;">Нет inbounds</div>';
        }
    } catch (error) {
        console.error('Error:', error);
        container.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--danger);">Ошибка загрузки</div>';
    }
}

// Toggle accordion details
function toggleInboundDetails(id) {
    const card = document.getElementById(`inbound-${id}`);
    if (card) {
        card.classList.toggle('expanded');
    }
}

// ==================== INBOUND VISUAL EDITOR ====================

let currentInboundData = null; // Store original data for reset

// Generate random string
function generateRandomString(length = 8) {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

// Generate random port (30000-60000)
function generateRandomPort() {
    const port = Math.floor(Math.random() * 30000) + 30000;
    document.getElementById('edit-inbound-port').value = port;
}

// Generate random path
function generateRandomPath() {
    const path = '/' + generateRandomString(8);
    document.getElementById('edit-ws-path').value = path;
}

// Generate random service name
function generateRandomServiceName() {
    document.getElementById('edit-grpc-service').value = generateRandomString(10);
}

// Generate Short ID (hex string)
function generateShortId() {
    const hex = '0123456789abcdef';
    let shortId = '';
    for (let i = 0; i < 8; i++) {
        shortId += hex.charAt(Math.floor(Math.random() * 16));
    }
    document.getElementById('edit-reality-short-ids').value = shortId;
}

// Generate X25519 keys via API
async function generateX25519Keys() {
    try {
        const response = await fetch(API_URL + 'api/generator/x25519', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.private_key && data.public_key) {
            document.getElementById('edit-reality-private-key').value = data.private_key;
            document.getElementById('edit-reality-public-key').value = data.public_key;
            showToast('✅ X25519 ключи сгенерированы', 'success');
        } else {
            showToast('Ошибка генерации ключей', 'error');
        }
    } catch (error) {
        console.error('Error generating X25519:', error);
        showToast('Ошибка генерации ключей', 'error');
    }
}

// Switch inbound modal tabs
function switchInboundTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.modal-tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update tab content
    document.querySelectorAll('.modal-tab-content').forEach(content => {
        content.style.display = 'none';
    });
    document.getElementById(`inbound-tab-${tabName}`).style.display = 'block';

    // If switching to advanced, sync visual fields to JSON
    if (tabName === 'advanced') {
        syncVisualToJson();
    }
}

// Update transport settings visibility based on network type
function updateTransportFields() {
    const network = document.getElementById('edit-network-type').value;

    // Hide all transport settings
    ['tcp', 'ws', 'grpc', 'httpupgrade', 'splithttp'].forEach(type => {
        const elem = document.getElementById(`transport-${type}-settings`);
        if (elem) elem.style.display = 'none';
    });

    // Show selected transport settings
    const selectedElem = document.getElementById(`transport-${network}-settings`);
    if (selectedElem) selectedElem.style.display = 'block';
}

// Update security settings visibility
function updateSecurityFields() {
    const security = document.getElementById('edit-security-type').value;

    document.getElementById('security-reality-settings').style.display =
        security === 'reality' ? 'block' : 'none';
    document.getElementById('security-tls-settings').style.display =
        security === 'tls' ? 'block' : 'none';
}

// Parse inbound data into visual fields
function parseInboundToVisual(ib) {
    const stream = ib.stream_settings || {};
    const sniff = ib.sniffing || {};

    // Basic fields
    document.getElementById('edit-inbound-listen').value = ib.listen || '';

    // Sniffing
    document.getElementById('edit-sniffing-enabled').checked = sniff.enabled !== false;
    const destOverride = sniff.destOverride || ['http', 'tls', 'quic'];
    document.getElementById('sniff-http').checked = destOverride.includes('http');
    document.getElementById('sniff-tls').checked = destOverride.includes('tls');
    document.getElementById('sniff-quic').checked = destOverride.includes('quic');
    document.getElementById('sniff-fakedns').checked = destOverride.includes('fakedns');

    // Network type
    const network = stream.network || 'tcp';
    document.getElementById('edit-network-type').value = network;

    // Transport-specific settings
    if (network === 'ws') {
        const wsSettings = stream.wsSettings || {};
        document.getElementById('edit-ws-path').value = wsSettings.path || '/';
        document.getElementById('edit-ws-host').value = (wsSettings.headers || {}).Host || '';
    } else if (network === 'grpc') {
        const grpcSettings = stream.grpcSettings || {};
        document.getElementById('edit-grpc-service').value = grpcSettings.serviceName || '';
        document.getElementById('edit-grpc-mode').value = grpcSettings.multiMode ? 'multi' : 'gun';
    } else if (network === 'httpupgrade') {
        const httpSettings = stream.httpupgradeSettings || {};
        document.getElementById('edit-httpupgrade-path').value = httpSettings.path || '/';
        document.getElementById('edit-httpupgrade-host').value = httpSettings.host || '';
    } else if (network === 'splithttp') {
        const splitSettings = stream.splithttpSettings || {};
        document.getElementById('edit-splithttp-path').value = splitSettings.path || '/';
        document.getElementById('edit-splithttp-host').value = splitSettings.host || '';
    } else if (network === 'tcp') {
        const tcpSettings = stream.tcpSettings || {};
        document.getElementById('edit-tcp-header-type').value =
            (tcpSettings.header || {}).type || 'none';
    }

    // Security type
    const security = stream.security || 'none';
    document.getElementById('edit-security-type').value = security;

    // Reality settings
    if (security === 'reality') {
        const reality = stream.realitySettings || {};
        document.getElementById('edit-reality-dest').value = reality.dest || '';
        document.getElementById('edit-reality-sni').value =
            (reality.serverNames || [])[0] || '';
        document.getElementById('edit-reality-private-key').value = reality.privateKey || '';
        document.getElementById('edit-reality-public-key').value = reality.publicKey || '';
        document.getElementById('edit-reality-short-ids').value =
            (reality.shortIds || []).join(', ');
        document.getElementById('edit-reality-fingerprint').value =
            reality.fingerprint || 'chrome';
        document.getElementById('edit-reality-spider-x').value = reality.spiderX || '/';
    }

    // TLS settings
    if (security === 'tls') {
        const tls = stream.tlsSettings || {};
        document.getElementById('edit-tls-server-name').value = tls.serverName || '';
        document.getElementById('edit-tls-cert-file').value =
            (tls.certificates || [{}])[0].certificateFile || '';
        document.getElementById('edit-tls-key-file').value =
            (tls.certificates || [{}])[0].keyFile || '';

        // uTLS fingerprint
        const fingerprintEl = document.getElementById('edit-tls-fingerprint');
        if (fingerprintEl) {
            fingerprintEl.value = tls.fingerprint || 'chrome';
        }

        // ALPN
        const alpnSelect = document.getElementById('edit-tls-alpn');
        if (alpnSelect && tls.alpn) {
            Array.from(alpnSelect.options).forEach(opt => {
                opt.selected = tls.alpn.includes(opt.value);
            });
        }

        // TLS versions
        const minVersionEl = document.getElementById('edit-tls-min-version');
        const maxVersionEl = document.getElementById('edit-tls-max-version');
        if (minVersionEl) minVersionEl.value = tls.minVersion || '';
        if (maxVersionEl) maxVersionEl.value = tls.maxVersion || '';
    }

    // Update visibility
    updateTransportFields();
    updateSecurityFields();
}

// Sync visual fields to JSON textareas
function syncVisualToJson() {
    const stream = buildStreamSettingsFromVisual();
    const sniffing = buildSniffingFromVisual();

    document.getElementById('edit-inbound-stream').value =
        JSON.stringify(stream, null, 2);
    document.getElementById('edit-inbound-sniffing').value =
        JSON.stringify(sniffing, null, 2);
}

// Build stream settings from visual fields
function buildStreamSettingsFromVisual() {
    const network = document.getElementById('edit-network-type').value;
    const security = document.getElementById('edit-security-type').value;

    const stream = {
        network: network,
        security: security
    };

    // Transport settings
    if (network === 'ws') {
        stream.wsSettings = {
            path: document.getElementById('edit-ws-path').value || '/',
            headers: {}
        };
        const host = document.getElementById('edit-ws-host').value;
        if (host) stream.wsSettings.headers.Host = host;
    } else if (network === 'grpc') {
        stream.grpcSettings = {
            serviceName: document.getElementById('edit-grpc-service').value || '',
            multiMode: document.getElementById('edit-grpc-mode').value === 'multi'
        };
    } else if (network === 'httpupgrade') {
        stream.httpupgradeSettings = {
            path: document.getElementById('edit-httpupgrade-path').value || '/',
            host: document.getElementById('edit-httpupgrade-host').value || ''
        };
    } else if (network === 'splithttp') {
        stream.splithttpSettings = {
            path: document.getElementById('edit-splithttp-path').value || '/',
            host: document.getElementById('edit-splithttp-host').value || ''
        };
    } else if (network === 'tcp') {
        const headerType = document.getElementById('edit-tcp-header-type').value;
        if (headerType !== 'none') {
            stream.tcpSettings = { header: { type: headerType } };
        }
    }

    // Security settings
    if (security === 'reality') {
        const shortIds = document.getElementById('edit-reality-short-ids').value
            .split(',').map(s => s.trim()).filter(s => s);
        const sni = document.getElementById('edit-reality-sni').value;

        stream.realitySettings = {
            show: false,
            dest: document.getElementById('edit-reality-dest').value || 'www.microsoft.com:443',
            xver: 0,
            serverNames: sni ? [sni] : ['www.microsoft.com'],
            privateKey: document.getElementById('edit-reality-private-key').value,
            shortIds: shortIds.length ? shortIds : [''],
            fingerprint: document.getElementById('edit-reality-fingerprint').value || 'chrome',
            spiderX: document.getElementById('edit-reality-spider-x').value || '/'
        };
    } else if (security === 'tls') {
        const tlsSettings = {
            serverName: document.getElementById('edit-tls-server-name').value,
            certificates: [{
                certificateFile: document.getElementById('edit-tls-cert-file').value,
                keyFile: document.getElementById('edit-tls-key-file').value
            }]
        };

        // Add fingerprint (uTLS)
        const fingerprint = document.getElementById('edit-tls-fingerprint')?.value;
        if (fingerprint) {
            tlsSettings.fingerprint = fingerprint;
        }

        // Add ALPN
        const alpnSelect = document.getElementById('edit-tls-alpn');
        if (alpnSelect) {
            const alpn = Array.from(alpnSelect.selectedOptions).map(o => o.value);
            if (alpn.length > 0) tlsSettings.alpn = alpn;
        }

        // Add TLS versions
        const minVersion = document.getElementById('edit-tls-min-version')?.value;
        const maxVersion = document.getElementById('edit-tls-max-version')?.value;
        if (minVersion) tlsSettings.minVersion = minVersion;
        if (maxVersion) tlsSettings.maxVersion = maxVersion;

        stream.tlsSettings = tlsSettings;
    }

    return stream;
}

// Build sniffing from visual fields
function buildSniffingFromVisual() {
    const destOverride = [];
    if (document.getElementById('sniff-http').checked) destOverride.push('http');
    if (document.getElementById('sniff-tls').checked) destOverride.push('tls');
    if (document.getElementById('sniff-quic').checked) destOverride.push('quic');
    if (document.getElementById('sniff-fakedns').checked) destOverride.push('fakedns');

    return {
        enabled: document.getElementById('edit-sniffing-enabled').checked,
        destOverride: destOverride
    };
}

// Reset inbound form to original values
function resetInboundForm() {
    if (currentInboundData) {
        parseInboundToVisual(currentInboundData);
        document.getElementById('edit-inbound-stream').value =
            currentInboundData.stream_settings ?
            JSON.stringify(currentInboundData.stream_settings, null, 2) : '';
        document.getElementById('edit-inbound-settings').value =
            currentInboundData.settings ?
            JSON.stringify(currentInboundData.settings, null, 2) : '';
        document.getElementById('edit-inbound-sniffing').value =
            currentInboundData.sniffing ?
            JSON.stringify(currentInboundData.sniffing, null, 2) : '';
        showToast('Форма сброшена', 'info');
    }
}

// Preset templates for inbound configuration
const INBOUND_PRESETS = {
    vless_reality: {
        network: 'tcp',
        security: 'reality',
        realitySettings: {
            dest: 'www.microsoft.com:443',
            serverNames: ['www.microsoft.com'],
            fingerprint: 'chrome',
            spiderX: '/'
        }
    },
    vless_ws_tls: {
        network: 'ws',
        security: 'tls',
        wsSettings: { path: '/vless', headers: {} },
        tlsSettings: { fingerprint: 'chrome', alpn: ['h2', 'http/1.1'] }
    },
    vmess_ws_tls: {
        network: 'ws',
        security: 'tls',
        wsSettings: { path: '/vmess', headers: {} },
        tlsSettings: { fingerprint: 'chrome', alpn: ['h2', 'http/1.1'] }
    },
    trojan_tls: {
        network: 'tcp',
        security: 'tls',
        tlsSettings: { fingerprint: 'chrome', alpn: ['h2', 'http/1.1'] }
    },
    vless_grpc: {
        network: 'grpc',
        security: 'tls',
        grpcSettings: { serviceName: 'grpc', multiMode: true },
        tlsSettings: { fingerprint: 'chrome', alpn: ['h2'] }
    },
    shadowsocks: {
        network: 'tcp',
        security: 'none'
    }
};

// Apply preset to inbound form
async function applyPresetToInbound(presetName) {
    const preset = INBOUND_PRESETS[presetName];
    if (!preset) {
        showToast('Шаблон не найден', 'error');
        return;
    }

    // Set network type
    document.getElementById('edit-network-type').value = preset.network;

    // Set security type
    document.getElementById('edit-security-type').value = preset.security;

    // Apply transport settings
    if (preset.network === 'ws' && preset.wsSettings) {
        document.getElementById('edit-ws-path').value = preset.wsSettings.path || '/';
        document.getElementById('edit-ws-host').value = '';
    } else if (preset.network === 'grpc' && preset.grpcSettings) {
        document.getElementById('edit-grpc-service').value = preset.grpcSettings.serviceName || 'grpc';
        document.getElementById('edit-grpc-mode').value = preset.grpcSettings.multiMode ? 'multi' : 'gun';
    }

    // Apply security settings
    if (preset.security === 'reality' && preset.realitySettings) {
        document.getElementById('edit-reality-dest').value = preset.realitySettings.dest || 'www.microsoft.com:443';
        document.getElementById('edit-reality-sni').value = (preset.realitySettings.serverNames || [])[0] || 'www.microsoft.com';
        document.getElementById('edit-reality-fingerprint').value = preset.realitySettings.fingerprint || 'chrome';
        document.getElementById('edit-reality-spider-x').value = preset.realitySettings.spiderX || '/';
        // Generate keys if empty
        if (!document.getElementById('edit-reality-private-key').value) {
            await generateX25519Keys();
        }
        if (!document.getElementById('edit-reality-short-ids').value) {
            generateShortId();
        }
    } else if (preset.security === 'tls' && preset.tlsSettings) {
        const fingerprintEl = document.getElementById('edit-tls-fingerprint');
        if (fingerprintEl) {
            fingerprintEl.value = preset.tlsSettings.fingerprint || 'chrome';
        }
        // Set ALPN
        const alpnSelect = document.getElementById('edit-tls-alpn');
        if (alpnSelect && preset.tlsSettings.alpn) {
            Array.from(alpnSelect.options).forEach(opt => {
                opt.selected = preset.tlsSettings.alpn.includes(opt.value);
            });
        }
    }

    // Update field visibility
    updateTransportFields();
    updateSecurityFields();

    // Switch to security tab to show result
    switchInboundTab('security');

    showToast(`✅ Шаблон "${presetName}" применён`, 'success');
}

// Create new inbound from preset template
async function createInboundFromPreset(presetName) {
    try {
        showToast('⏳ Создание inbound...', 'info');

        const response = await fetch(API_URL + 'api/presets/create-inbound', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                preset_name: presetName,
                auto_generate: true  // Auto-generate keys, ports, etc.
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(`✅ Inbound "${data.remark}" создан на порту ${data.port}`, 'success');
            loadInboundsTable();  // Refresh list
        } else {
            showToast('❌ Ошибка: ' + (data.detail || data.error || 'Неизвестная ошибка'), 'error');
        }
    } catch (error) {
        console.error('Error creating inbound from preset:', error);
        showToast('❌ Ошибка создания inbound', 'error');
    }
}

// Update fingerprint on all TLS/Reality inbounds
async function updateAllFingerprints() {
    const fingerprint = prompt('Введите fingerprint для всех inbounds:\n(chrome, firefox, safari, ios, android, edge, randomized, random)', 'chrome');

    if (!fingerprint) return;

    try {
        showToast('⏳ Обновление fingerprint...', 'info');

        const response = await fetch(API_URL + 'api/inbounds/bulk-update-fingerprint', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ fingerprint: fingerprint })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(`✅ Обновлено ${data.updated_count} inbounds`, 'success');
            loadInboundsTable();
        } else {
            showToast('❌ Ошибка: ' + (data.detail || data.error), 'error');
        }
    } catch (error) {
        console.error('Error updating fingerprints:', error);
        showToast('❌ Ошибка обновления', 'error');
    }
}

// Show bulk optimize modal
function showBulkOptimizeModal() {
    // Create modal if not exists
    let modal = document.getElementById('bulk-optimize-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'bulk-optimize-modal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 500px;">
                <div class="modal-header">
                    <h3>⚙️ Массовая оптимизация</h3>
                    <button class="modal-close" onclick="document.getElementById('bulk-optimize-modal').style.display='none'">&times;</button>
                </div>
                <div class="modal-body" style="padding: 20px;">
                    <div class="form-group">
                        <label class="form-label">Fingerprint (uTLS)</label>
                        <select class="form-input" id="bulk-fingerprint">
                            <option value="">-- Не менять --</option>
                            <option value="chrome" selected>chrome</option>
                            <option value="firefox">firefox</option>
                            <option value="safari">safari</option>
                            <option value="ios">ios</option>
                            <option value="android">android</option>
                            <option value="randomized">randomized</option>
                            <option value="random">random</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Применить к</label>
                        <div style="display: flex; flex-direction: column; gap: 8px;">
                            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                                <input type="checkbox" id="bulk-apply-tls" checked> TLS inbounds
                            </label>
                            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                                <input type="checkbox" id="bulk-apply-reality" checked> Reality inbounds
                            </label>
                        </div>
                    </div>

                    <div class="form-group">
                        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                            <input type="checkbox" id="bulk-enable-sniffing" checked>
                            <span>Включить Sniffing на всех</span>
                        </label>
                    </div>

                    <button class="btn btn-primary" onclick="applyBulkOptimization()" style="width: 100%; margin-top: 15px;">
                        ⚡ Применить оптимизацию
                    </button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    modal.style.display = 'flex';
}

// Apply bulk optimization
async function applyBulkOptimization() {
    const fingerprint = document.getElementById('bulk-fingerprint').value;
    const applyTls = document.getElementById('bulk-apply-tls').checked;
    const applyReality = document.getElementById('bulk-apply-reality').checked;
    const enableSniffing = document.getElementById('bulk-enable-sniffing').checked;

    try {
        showToast('⏳ Применение оптимизации...', 'info');

        const response = await fetch(API_URL + 'api/inbounds/bulk-optimize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                fingerprint: fingerprint || null,
                apply_to_tls: applyTls,
                apply_to_reality: applyReality,
                enable_sniffing: enableSniffing
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(`✅ Оптимизировано ${data.updated_count} inbounds`, 'success');
            document.getElementById('bulk-optimize-modal').style.display = 'none';
            loadInboundsTable();
        } else {
            showToast('❌ Ошибка: ' + (data.detail || data.error), 'error');
        }
    } catch (error) {
        console.error('Error applying optimization:', error);
        showToast('❌ Ошибка оптимизации', 'error');
    }
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('📋 Скопировано', 'success');
    }).catch(err => {
        console.error('Copy failed:', err);
    });
}

async function editInbound(id) {
    try {
        const response = await fetch(API_URL + `api/inbounds/${id}/full`, {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success && data.inbound) {
            const ib = data.inbound;
            currentInboundData = ib; // Store for reset

            // Basic fields
            document.getElementById('edit-inbound-id').value = id;
            document.getElementById('edit-inbound-remark').value = ib.remark || '';
            document.getElementById('edit-inbound-port').value = ib.port || '';
            document.getElementById('edit-inbound-protocol').value = ib.protocol || '';
            document.getElementById('edit-inbound-enable').value = ib.enable ? '1' : '0';

            // Format JSON fields (Advanced tab)
            document.getElementById('edit-inbound-stream').value =
                ib.stream_settings ? JSON.stringify(ib.stream_settings, null, 2) : '';
            document.getElementById('edit-inbound-settings').value =
                ib.settings ? JSON.stringify(ib.settings, null, 2) : '';
            document.getElementById('edit-inbound-sniffing').value =
                ib.sniffing ? JSON.stringify(ib.sniffing, null, 2) : '';

            // Parse to visual fields
            parseInboundToVisual(ib);

            // Reset to first tab
            switchInboundTab('basic');

            document.getElementById('inbound-modal-title').textContent = `Редактировать: ${ib.remark}`;
            document.getElementById('inbound-edit-modal').style.display = 'flex';
        } else {
            showToast('Ошибка загрузки inbound', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка загрузки inbound', 'error');
    }
}

function closeInboundModal() {
    document.getElementById('inbound-edit-modal').style.display = 'none';
    currentInboundData = null;
}

async function saveInbound() {
    // Check authentication before saving
    if (!await ensureAuthenticated()) {
        return;
    }

    const id = document.getElementById('edit-inbound-id').value;
    const activeTab = document.querySelector('.modal-tab.active');
    const isAdvancedTab = activeTab && activeTab.dataset.tab === 'advanced';

    // Parse JSON fields - use visual or advanced based on active tab
    let streamSettings, settings, sniffing;

    if (isAdvancedTab) {
        // Use raw JSON from advanced tab
        try {
            const streamText = document.getElementById('edit-inbound-stream').value.trim();
            streamSettings = streamText ? JSON.parse(streamText) : null;
        } catch (e) {
            showToast('Ошибка в Stream Settings JSON', 'error');
            return;
        }

        try {
            const sniffingText = document.getElementById('edit-inbound-sniffing').value.trim();
            sniffing = sniffingText ? JSON.parse(sniffingText) : null;
        } catch (e) {
            showToast('Ошибка в Sniffing JSON', 'error');
            return;
        }
    } else {
        // Build from visual fields
        streamSettings = buildStreamSettingsFromVisual();
        sniffing = buildSniffingFromVisual();
    }

    // Settings always from JSON (contains clients)
    try {
        const settingsText = document.getElementById('edit-inbound-settings').value.trim();
        settings = settingsText ? JSON.parse(settingsText) : null;
    } catch (e) {
        showToast('Ошибка в Settings JSON', 'error');
        return;
    }

    const data = {
        remark: document.getElementById('edit-inbound-remark').value,
        port: parseInt(document.getElementById('edit-inbound-port').value),
        enable: parseInt(document.getElementById('edit-inbound-enable').value),
        listen: document.getElementById('edit-inbound-listen').value || '',
        stream_settings: streamSettings,
        settings: settings,
        sniffing: sniffing
    };

    try {
        const response = await fetch(API_URL + `api/inbounds/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(data)
        });
        const result = await response.json();

        if (result.success) {
            showToast('✅ Inbound сохранен', 'success');
            closeInboundModal();
            loadInboundsTable();
        } else {
            showToast('Ошибка: ' + (result.message || result.detail), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка сохранения', 'error');
    }
}

async function toggleInbound(id) {
    try {
        const response = await fetch(API_URL + `api/inbounds/${id}/toggle`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            loadInboundsTable();
        } else {
            showToast('Ошибка: ' + (data.message || data.detail), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка переключения', 'error');
    }
}

async function deleteInbound(id, name) {
    if (!confirm(`Удалить inbound "${name}"?\n\n⚠️ Все пользователи этого inbound будут удалены!`)) return;

    try {
        const response = await fetch(API_URL + `api/inbounds/${id}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast(`✅ ${data.message}`, 'success');
            loadInboundsTable();
        } else {
            showToast('Ошибка: ' + (data.message || data.detail), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка удаления', 'error');
    }
}

// ==================== SNI SCANNER ====================

async function discoverSNI() {
    const provider = document.getElementById('sni-provider').value;
    const count = parseInt(document.getElementById('sni-discover-count').value) || 20;
    const btn = event.target;
    btn.disabled = true;
    btn.innerHTML = '⏳ Поиск...';

    const tbody = document.getElementById('sni-results-body');
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 30px;">
        <div style="display: inline-block; width: 30px; height: 30px; border: 3px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite;"></div>
        <br><br>
        <span style="color: var(--accent);">Сканирование ${provider.toUpperCase()} IP диапазонов...</span><br>
        <small style="color: var(--text-secondary);">Проверяется ${count} IP адресов. Это может занять до 30 секунд.</small>
    </td></tr>`;

    // Add spin animation if not exists
    if (!document.getElementById('spin-style')) {
        const style = document.createElement('style');
        style.id = 'spin-style';
        style.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
        document.head.appendChild(style);
    }

    try {
        const response = await fetch(API_URL + `api/sni/discover?provider=${provider}&count=${count}`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        btn.disabled = false;
        btn.innerHTML = '🚀 Найти';

        if (data.results && data.results.length > 0) {
            tbody.innerHTML = data.results.map(r => `
                <tr>
                    <td><strong>${r.domain}</strong><br><small style="color: var(--text-secondary);">${r.ip}</small></td>
                    <td>✅</td>
                    <td>✅</td>
                    <td>${r.latency}ms</td>
                    <td style="color: var(--success);">✅ OK</td>
                    <td>
                        <button class="btn btn-success" style="padding: 3px 6px; font-size: 10px;" onclick="saveSNI('${r.domain}', ${r.latency})">💾</button>
                    </td>
                </tr>
            `).join('');
            showToast(`✅ Найдено ${data.found} доменов из ${data.scanned} IP`, 'success');
        } else {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--warning);">Домены не найдены. Попробуйте другой провайдер.</td></tr>';
        }
    } catch (error) {
        btn.disabled = false;
        btn.innerHTML = '🚀 Найти';
        console.error('Error:', error);
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--danger);">Ошибка сканирования: ' + error.message + '</td></tr>';
    }
}

async function testSingleSNI() {
    const domain = document.getElementById('sni-single-domain').value.trim();
    if (!domain) {
        showToast('Введите домен', 'error');
        return;
    }

    const resultDiv = document.getElementById('sni-single-result');
    resultDiv.innerHTML = '<span style="color: var(--accent);">⏳ Тестирование...</span>';

    try {
        const response = await fetch(API_URL + `api/sni/test?domain=${encodeURIComponent(domain)}`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.error) {
            resultDiv.innerHTML = `<span style="color: var(--danger);">❌ ${data.error}</span>`;
        } else {
            const tls = data.tls_version === 'TLSv1.3' ? '✅' : '⚠️';
            const h2 = data.h2_support ? '✅' : '❌';
            resultDiv.innerHTML = `
                <div style="padding: 10px; background: var(--bg-primary); border-radius: 6px;">
                    <div><strong>${domain}</strong></div>
                    <div style="margin-top: 8px;">
                        ${tls} TLS: ${data.tls_version || '-'} |
                        ${h2} H2: ${data.h2_support ? 'Да' : 'Нет'} |
                        ⏱️ ${data.latency_ms}ms
                    </div>
                    ${data.tls_version === 'TLSv1.3' && data.h2_support ?
                        `<button class="btn btn-success" style="margin-top: 8px; padding: 4px 8px; font-size: 11px;" onclick="saveSNI('${domain}', ${data.latency_ms})">💾 Сохранить</button>` : ''}
                </div>
            `;
        }
    } catch (error) {
        console.error('Error:', error);
        resultDiv.innerHTML = '<span style="color: var(--danger);">❌ Ошибка</span>';
    }
}

async function loadSNISuggestions() {
    try {
        const response = await fetch(API_URL + 'api/sni/suggestions', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.suggestions) {
            document.getElementById('sni-domains-list').value = data.suggestions.join('\n');
            showToast('Загружены популярные домены', 'success');
        }
    } catch (error) {
        showToast('Ошибка загрузки', 'error');
    }
}

async function scanSNIDomains() {
    const domainsText = document.getElementById('sni-domains-list').value.trim();
    if (!domainsText) {
        showToast('Введите домены для сканирования', 'error');
        return;
    }

    const domains = domainsText.split('\n').map(d => d.trim()).filter(d => d);
    if (domains.length === 0) return;

    const tbody = document.getElementById('sni-results-body');
    tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px;"><span style="color: var(--accent);">⏳ Сканирование ' + domains.length + ' доменов...</span></td></tr>';

    try {
        const response = await fetch(API_URL + 'api/sni/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ domains: domains })
        });
        const data = await response.json();

        if (data.results && data.results.length > 0) {
            tbody.innerHTML = data.results.map(r => {
                const statusColor = r.status === 'ok' ? 'var(--success)' : r.status === 'partial' ? 'var(--warning)' : 'var(--danger)';
                const statusText = r.status === 'ok' ? '✅ OK' : r.status === 'partial' ? '⚠️ Частично' : '❌ Ошибка';
                return `
                    <tr>
                        <td><strong>${r.domain}</strong></td>
                        <td>${r.tls13 ? '✅' : '❌'}</td>
                        <td>${r.h2 ? '✅' : '❌'}</td>
                        <td>${r.latency ? r.latency + 'ms' : '-'}</td>
                        <td style="color: ${statusColor};">${statusText}</td>
                        <td>
                            ${r.status === 'ok' ? `<button class="btn btn-success" style="padding: 3px 6px; font-size: 10px;" onclick="saveSNI('${r.domain}', ${r.latency})">💾</button>` : ''}
                        </td>
                    </tr>
                `;
            }).join('');
            showToast(`Сканирование завершено: ${data.results.filter(r => r.status === 'ok').length} подходящих`, 'success');
        } else {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px;">Нет результатов</td></tr>';
        }
    } catch (error) {
        console.error('Error:', error);
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--danger);">Ошибка сканирования</td></tr>';
    }
}

async function saveSNI(domain, latency) {
    try {
        const response = await fetch(API_URL + `api/sni/save?domain=${encodeURIComponent(domain)}&latency=${latency || 0}`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast(`✅ ${domain} сохранен`, 'success');
            loadSavedSNI();
        } else {
            showToast('Ошибка: ' + data.message, 'error');
        }
    } catch (error) {
        showToast('Ошибка сохранения', 'error');
    }
}

async function loadSavedSNI() {
    try {
        const response = await fetch(API_URL + 'api/sni/saved', {
            credentials: 'include'
        });
        const data = await response.json();

        const list = document.getElementById('sni-saved-list');
        if (data.domains && data.domains.length > 0) {
            list.innerHTML = data.domains.map(d => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0; border-bottom: 1px solid var(--border);">
                    <span><strong>${d.domain}</strong> <span style="color: var(--text-secondary);">${d.latency ? d.latency + 'ms' : ''}</span></span>
                    <button class="btn btn-danger" style="padding: 2px 6px; font-size: 10px;" onclick="deleteSavedSNI('${d.domain}')">🗑️</button>
                </div>
            `).join('');
        } else {
            list.innerHTML = '<span style="color: var(--text-secondary);">Нет сохраненных доменов</span>';
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function deleteSavedSNI(domain) {
    try {
        const response = await fetch(API_URL + `api/sni/saved/${encodeURIComponent(domain)}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast(`${domain} удален`, 'success');
            loadSavedSNI();
        }
    } catch (error) {
        showToast('Ошибка удаления', 'error');
    }
}

// ==================== FINGERPRINT MANAGEMENT ====================

async function loadFingerprints() {
    const info = document.getElementById('fingerprint-info');
    info.innerHTML = '<span style="color: var(--accent);">⏳ Загрузка...</span>';

    try {
        const response = await fetch(API_URL + 'api/inbounds/fingerprints', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success && data.inbounds.length > 0) {
            let html = '<div style="margin-top: 10px;"><strong>Текущие fingerprints:</strong></div>';
            html += '<div style="margin-top: 8px; max-height: 150px; overflow-y: auto;">';
            data.inbounds.forEach(ib => {
                html += `<div style="padding: 4px 0; border-bottom: 1px solid var(--border);">
                    <span style="color: var(--text-primary);">${ib.remark}</span>
                    <span style="color: var(--text-secondary);"> (${ib.protocol}/${ib.security})</span>:
                    <span style="color: var(--accent); font-weight: 500;">${ib.fingerprint}</span>
                </div>`;
            });
            html += '</div>';
            info.innerHTML = html;
        } else if (data.inbounds && data.inbounds.length === 0) {
            info.innerHTML = '<span style="color: var(--warning);">⚠️ Нет inbounds с поддержкой fingerprint (TLS/Reality)</span>';
        } else {
            info.innerHTML = `<span style="color: var(--danger);">❌ ${data.message || 'Ошибка'}</span>`;
        }
    } catch (error) {
        console.error('Error:', error);
        info.innerHTML = '<span style="color: var(--danger);">❌ Ошибка загрузки</span>';
    }
}

async function updateFingerprints() {
    const fingerprint = document.getElementById('fingerprint-select').value;
    if (!confirm(`Обновить fingerprint на всех inbounds?\n\nНовое значение: ${fingerprint}\n\nX-UI будет перезапущен.`)) return;

    const info = document.getElementById('fingerprint-info');
    info.innerHTML = '<span style="color: var(--accent);">⏳ Обновление...</span>';

    try {
        const response = await fetch(API_URL + `api/inbounds/fingerprints/update?fingerprint=${fingerprint}`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast(`✅ Обновлено ${data.updated_count} inbounds`, 'success');
            info.innerHTML = `<span style="color: var(--success);">✅ Fingerprint обновлен на ${data.updated_count} inbounds</span>`;
            loadXuiStatus();
        } else {
            showToast('Ошибка: ' + (data.message || 'Unknown'), 'error');
            info.innerHTML = `<span style="color: var(--danger);">❌ ${data.message || 'Ошибка'}</span>`;
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка обновления fingerprint', 'error');
        info.innerHTML = '<span style="color: var(--danger);">❌ Ошибка обновления</span>';
    }
}

// ==================== SYSTEM OPTIMIZATION ====================

async function checkSystemOptimization() {
    try {
        const response = await fetch(API_URL + 'api/system/optimization/check', {
            credentials: 'include'
        });
        const data = await response.json();

        // Update status cards
        const bbrStatus = document.getElementById('bbr-status');
        if (data.bbr_enabled) {
            bbrStatus.textContent = '✅ ' + (data.bbr_version || 'Enabled');
            bbrStatus.style.color = 'var(--success)';
        } else {
            bbrStatus.textContent = '❌ Не установлен';
            bbrStatus.style.color = 'var(--danger)';
        }

        const tcpStatus = document.getElementById('tcp-status');
        if (data.tcp_optimized) {
            tcpStatus.textContent = '✅ Оптимизирован';
            tcpStatus.style.color = 'var(--success)';
        } else {
            tcpStatus.textContent = '⚠️ Стандартный';
            tcpStatus.style.color = 'var(--warning)';
        }

        document.getElementById('kernel-version').textContent = data.kernel || '-';

        // Show detailed results
        let results = `Версия ядра: ${data.kernel || 'N/A'}\n`;
        results += `BBR: ${data.bbr_enabled ? '✅ Включен' : '❌ Выключен'}\n`;
        results += `Версия BBR: ${data.bbr_version || 'N/A'}\n`;
        results += `TCP оптимизация: ${data.tcp_optimized ? '✅' : '❌'}\n\n`;
        results += `Текущие настройки:\n${data.sysctl_values || 'N/A'}`;

        document.getElementById('system-check-results').textContent = results;

    } catch (error) {
        console.error('Error:', error);
        document.getElementById('system-check-results').textContent = 'Ошибка проверки системы';
    }
}

async function installBBR() {
    if (!confirm('⚠️ Установить BBR3?\n\nЭто может потребовать перезагрузки сервера.')) return;

    showToast('⏳ Установка BBR3...', 'info');

    try {
        const response = await fetch(API_URL + 'api/system/optimization/install-bbr', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ BBR установлен. ' + (data.message || ''), 'success');
            checkSystemOptimization();
        } else {
            showToast('Ошибка: ' + (data.message || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка установки BBR', 'error');
    }
}

async function optimizeTCP() {
    if (!confirm('Применить TCP оптимизации?')) return;

    try {
        const response = await fetch(API_URL + 'api/system/optimization/tcp', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ TCP оптимизирован', 'success');
            checkSystemOptimization();
        } else {
            showToast('Ошибка: ' + (data.message || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка оптимизации TCP', 'error');
    }
}

async function installAllOptimizations() {
    if (!confirm('⚠️ Установить все оптимизации?\n\nBBR3 + TCP оптимизации. Может потребоваться перезагрузка.')) return;

    showToast('⏳ Установка оптимизаций...', 'info');

    try {
        const response = await fetch(API_URL + 'api/system/optimization/install-all', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Все оптимизации установлены', 'success');
            checkSystemOptimization();
        } else {
            showToast('Ошибка: ' + (data.message || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка установки', 'error');
    }
}

// ==================== UPDATE SERVER MANAGEMENT ====================

async function checkUpdateServer() {
    try {
        const response = await fetch(API_URL + 'api/system/update-server/status', {
            credentials: 'include'
        });
        const data = await response.json();

        // Update status display
        const statusEl = document.getElementById('update-server-status');
        const installedEl = document.getElementById('update-server-installed');

        if (data.installed) {
            installedEl.textContent = '✅ Да';
            installedEl.style.color = 'var(--success)';

            if (data.running) {
                statusEl.textContent = '🟢 Работает';
                statusEl.style.color = 'var(--success)';
            } else {
                statusEl.textContent = '🔴 Остановлен';
                statusEl.style.color = 'var(--danger)';
            }

            // Update buttons
            document.getElementById('btn-install-update-server').style.display = 'none';
            document.getElementById('btn-start-update-server').style.display = data.running ? 'none' : 'inline-flex';
            document.getElementById('btn-stop-update-server').style.display = data.running ? 'inline-flex' : 'none';
            document.getElementById('btn-restart-update-server').style.display = data.running ? 'inline-flex' : 'none';
        } else {
            installedEl.textContent = '❌ Нет';
            installedEl.style.color = 'var(--danger)';
            statusEl.textContent = '⚪ Не установлен';
            statusEl.style.color = 'var(--text-secondary)';

            // Show only install button
            document.getElementById('btn-install-update-server').style.display = 'inline-flex';
            document.getElementById('btn-start-update-server').style.display = 'none';
            document.getElementById('btn-stop-update-server').style.display = 'none';
            document.getElementById('btn-restart-update-server').style.display = 'none';
        }

    } catch (error) {
        console.error('Error checking update server:', error);
        showToast('Ошибка проверки сервера обновлений', 'error');
    }
}

async function installUpdateServer() {
    if (!confirm('Установить Центр обновлений?\n\nБудет создан отдельный сервис на порту 8889.')) return;

    showToast('⏳ Установка сервера обновлений...', 'info');

    try {
        const response = await fetch(API_URL + 'api/system/update-server/install', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Сервер обновлений установлен', 'success');
            checkUpdateServer();
        } else {
            showToast('Ошибка: ' + (data.message || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast('Ошибка установки', 'error');
    }
}

async function controlUpdateServer(action) {
    const actionNames = {
        'start': 'Запуск',
        'stop': 'Остановка',
        'restart': 'Перезапуск'
    };

    showToast(`⏳ ${actionNames[action]} сервера обновлений...`, 'info');

    try {
        const response = await fetch(API_URL + `api/system/update-server/${action}`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast(`✅ ${actionNames[action]} выполнен`, 'success');
            checkUpdateServer();
        } else {
            showToast('Ошибка: ' + (data.message || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showToast(`Ошибка: ${actionNames[action]}`, 'error');
    }
}

// ==================== PANEL MANAGEMENT ====================

// Load panel credentials
async function loadPanelCredentials() {
    try {
        const response = await fetch('/api/panel/credentials');
        const data = await response.json();

        if (data.success && data.credentials) {
            document.getElementById('panel-credentials-box').style.display = 'block';
            document.getElementById('panel-username').textContent = data.credentials.username || '-';
            document.getElementById('panel-password').textContent = data.credentials.password || '-';
            document.getElementById('panel-port').textContent = data.credentials.web_port || '-';
        }
    } catch (error) {
        console.error('Error loading credentials:', error);
    }
}

// Toggle credentials visibility
let credsVisible = false;
function toggleCredentialsVisibility() {
    credsVisible = !credsVisible;
    const content = document.getElementById('panel-creds-content');
    const btn = document.getElementById('toggle-creds-btn');

    if (credsVisible) {
        content.style.display = 'block';
        btn.textContent = '🙈 Скрыть';
    } else {
        content.style.display = 'none';
        btn.textContent = '👁️ Показать';
    }
}

// Show reset credentials modal
function showResetCredentialsModal() {
    showTab('panel-manage');
}

// Load panel status
async function loadPanelStatus() {
    try {
        const response = await fetch('/api/panel/status');
        const data = await response.json();

        if (data.success && data.status) {
            const s = data.status;
            document.getElementById('pm-status').textContent = s.running ? '🟢 Работает' : '🔴 Остановлен';
            document.getElementById('pm-status').style.color = s.running ? 'var(--success)' : 'var(--danger)';
            document.getElementById('pm-version').textContent = s.version || '-';
            document.getElementById('pm-xray').textContent = s.xray_version || '-';
            document.getElementById('pm-users').textContent = s.users_count || '0';
            document.getElementById('pm-inbounds').textContent = s.inbounds_count || '0';
            document.getElementById('pm-dbsize').textContent = s.database_size || '-';
        }
    } catch (error) {
        console.error('Error loading panel status:', error);
        showToast('Ошибка загрузки статуса панели', 'error');
    }
}

// Generate random password
function generateRandomPassword() {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%&*';
    let password = '';
    for (let i = 0; i < 16; i++) {
        password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    document.getElementById('new-panel-password').value = password;
}

// Reset panel credentials
async function resetPanelCredentials() {
    const username = document.getElementById('new-panel-username').value || 'admin';
    const password = document.getElementById('new-panel-password').value;

    if (!password) {
        showToast('Введите новый пароль', 'error');
        return;
    }

    if (!confirm(`Сбросить учётные данные панели?\n\nНовый логин: ${username}\nНовый пароль: ${password}`)) {
        return;
    }

    try {
        const response = await fetch('/api/panel/reset-credentials', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Учётные данные сброшены. Перезапустите панель.', 'success');
            loadPanelCredentials();
        } else {
            showToast('Ошибка: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error resetting credentials:', error);
        showToast('Ошибка сброса учётных данных', 'error');
    }
}

// Create panel backup
async function createPanelBackup() {
    try {
        const response = await fetch('/api/panel/backup', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Бэкап создан: ' + data.backup_path, 'success');
            loadPanelBackups();
        } else {
            showToast('Ошибка: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error creating backup:', error);
        showToast('Ошибка создания бэкапа', 'error');
    }
}

// Load panel backups
async function loadPanelBackups() {
    try {
        const response = await fetch('/api/panel/backups');
        const data = await response.json();

        document.getElementById('panel-backups-list').style.display = 'block';
        const tbody = document.getElementById('backups-tbody');

        if (data.success && data.backups && data.backups.length > 0) {
            tbody.innerHTML = data.backups.map(b => `
                <tr>
                    <td>${b.filename}</td>
                    <td>${b.size || '-'}</td>
                    <td>${b.created || '-'}</td>
                    <td>
                        <button class="btn btn-warning" onclick="restoreBackup('${b.path}')" style="font-size: 11px; padding: 4px 8px;">🔄 Восстановить</button>
                    </td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="4">Нет резервных копий</td></tr>';
        }
    } catch (error) {
        console.error('Error loading backups:', error);
    }
}

// Restore backup
async function restoreBackup(backupPath) {
    if (!confirm('Восстановить базу данных из этого бэкапа?\n\nТекущие данные будут перезаписаны!')) {
        return;
    }

    try {
        const response = await fetch('/api/panel/restore?backup_path=' + encodeURIComponent(backupPath), {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ База данных восстановлена. Перезапустите панель.', 'success');
        } else {
            showToast('Ошибка: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error restoring backup:', error);
        showToast('Ошибка восстановления', 'error');
    }
}

// Reinstall panel
async function reinstallPanel() {
    const fork = document.getElementById('panel-fork-select').value;
    const preserveDb = document.getElementById('preserve-db').checked;
    const preserveConfig = document.getElementById('preserve-config').checked;

    const forkNames = {
        'mhsanaei': 'MHSanaei',
        'alireza': 'Alireza0',
        'franzkafka': 'FranzKafkaYu'
    };

    if (!confirm(`⚠️ ВНИМАНИЕ: Переустановка панели!\n\nФорк: ${forkNames[fork] || fork}\nСохранить БД: ${preserveDb ? 'Да' : 'Нет'}\nСохранить настройки: ${preserveConfig ? 'Да' : 'Нет'}\n\nЭто может занять несколько минут. Продолжить?`)) {
        return;
    }

    showToast('Переустановка начата...', 'info');

    try {
        const response = await fetch('/api/panel/reinstall', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                fork: fork,
                preserve_database: preserveDb,
                preserve_config: preserveConfig
            })
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Панель переустановлена!', 'success');
            loadPanelStatus();
        } else {
            showToast('Ошибка: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error reinstalling panel:', error);
        showToast('Ошибка переустановки', 'error');
    }
}

// ==================== NGINX MANAGEMENT ====================

// Load nginx status
async function loadNginxStatus() {
    try {
        const response = await fetch('/api/nginx/status');
        const data = await response.json();

        if (data.success) {
            document.getElementById('nginx-running').textContent = data.running ? '🟢 Работает' : '🔴 Остановлен';
            document.getElementById('nginx-running').style.color = data.running ? 'var(--success)' : 'var(--danger)';

            document.getElementById('nginx-valid').textContent = data.config_valid ? '✅ OK' : '❌ Ошибка';
            document.getElementById('nginx-valid').style.color = data.config_valid ? 'var(--success)' : 'var(--danger)';

            document.getElementById('nginx-ssl').textContent = data.ssl_enabled ? '🔒 Включён' : '🔓 Выключен';
            document.getElementById('nginx-xui-manager').textContent = data.has_xui_manager ? '✅' : '❌';

            if (data.domains && data.domains.length > 0) {
                document.getElementById('nginx-domains').innerHTML = '<strong>Домены:</strong> ' + data.domains.join(', ');
            }

            // Show issues if any
            const issuesDiv = document.getElementById('nginx-issues');
            if ((data.errors && data.errors.length > 0) || (data.warnings && data.warnings.length > 0)) {
                issuesDiv.style.display = 'block';
                document.getElementById('nginx-errors').innerHTML = data.errors ? data.errors.map(e => '❌ ' + e).join('<br>') : '';
                document.getElementById('nginx-warnings').innerHTML = data.warnings ? data.warnings.map(w => '⚠️ ' + w).join('<br>') : '';
            } else {
                issuesDiv.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error loading nginx status:', error);
        showToast('Ошибка загрузки статуса nginx', 'error');
    }
}

// Test nginx config
async function testNginxConfig() {
    try {
        const response = await fetch('/api/nginx/test', { method: 'POST' });
        const data = await response.json();

        if (data.valid) {
            showToast('✅ Конфигурация nginx валидна', 'success');
        } else {
            showToast('❌ Ошибка конфигурации: ' + data.output, 'error');
        }
    } catch (error) {
        console.error('Error testing nginx config:', error);
        showToast('Ошибка тестирования', 'error');
    }
}

// Reload nginx
async function reloadNginx() {
    if (!confirm('Перезагрузить nginx?')) return;

    try {
        const response = await fetch('/api/nginx/reload', { method: 'POST' });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Nginx перезагружен', 'success');
        } else {
            showToast('Ошибка: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error reloading nginx:', error);
        showToast('Ошибка перезагрузки nginx', 'error');
    }
}

// Load nginx config
async function loadNginxConfig() {
    try {
        const response = await fetch('/api/nginx/config');
        const data = await response.json();

        const pre = document.getElementById('nginx-config-content');
        pre.style.display = 'block';

        if (data.success && data.configs) {
            let content = '';
            for (const [file, config] of Object.entries(data.configs)) {
                content += `# === ${file} ===\n${config}\n\n`;
            }
            pre.textContent = content;
        } else {
            pre.textContent = 'Ошибка загрузки конфигурации';
        }
    } catch (error) {
        console.error('Error loading nginx config:', error);
    }
}

// Analyze inbound requirements
async function analyzeInboundRequirements() {
    try {
        const response = await fetch('/api/nginx/inbound-requirements');
        const data = await response.json();

        const reqDiv = document.getElementById('inbound-requirements');
        const tbody = document.getElementById('inbound-req-tbody');
        const suggestedDiv = document.getElementById('suggested-nginx-config');

        if (data.success && data.requirements) {
            reqDiv.style.display = 'block';

            tbody.innerHTML = data.requirements.map(r => `
                <tr>
                    <td>${r.remark || 'Inbound ' + r.inbound_id}</td>
                    <td>${r.network}</td>
                    <td>${r.port}</td>
                    <td style="color: ${r.needs_nginx ? 'var(--warning)' : 'var(--success)'}">
                        ${r.needs_nginx ? '⚠️ Да' : '✅ Нет'}
                    </td>
                    <td style="font-size: 11px;">${r.reason || '-'}</td>
                </tr>
            `).join('');

            if (data.suggested_config && data.needs_nginx_count > 0) {
                suggestedDiv.style.display = 'block';
                document.getElementById('suggested-config-content').textContent = data.suggested_config;
            } else {
                suggestedDiv.style.display = 'none';
            }

            showToast(`Найдено ${data.needs_nginx_count} inbound(s), требующих nginx`, 'info');
        }
    } catch (error) {
        console.error('Error analyzing requirements:', error);
        showToast('Ошибка анализа', 'error');
    }
}

// Copy suggested nginx config
function copySuggestedConfig() {
    const config = document.getElementById('suggested-config-content').textContent;
    copyToClipboard(config);
}

// ==================== CAMOUFLAGE MANAGEMENT ====================

let allTemplates = [];

// Load camouflage status
async function loadCamouflageStatus() {
    try {
        const response = await fetch('/api/camouflage/current');
        const data = await response.json();

        if (data.success) {
            document.getElementById('camo-installed').textContent = data.installed ? '✅ Да' : '❌ Нет';
            document.getElementById('camo-installed').style.color = data.installed ? 'var(--success)' : 'var(--text-secondary)';
            document.getElementById('camo-template-name').textContent = data.template_name || '-';
        }
    } catch (error) {
        console.error('Error loading camouflage status:', error);
    }
}

// Load camouflage templates
async function loadCamouflageTemplates() {
    try {
        const response = await fetch('/api/camouflage/templates');
        const data = await response.json();

        if (data.success && data.templates) {
            allTemplates = data.templates;
            renderTemplates(data.templates);

            // Load categories
            const catResponse = await fetch('/api/camouflage/categories');
            const catData = await catResponse.json();

            if (catData.success) {
                const select = document.getElementById('template-category-filter');
                catData.categories.forEach(cat => {
                    const option = document.createElement('option');
                    option.value = cat.id;
                    option.textContent = cat.name;
                    select.appendChild(option);
                });
                document.getElementById('templates-filter').style.display = 'block';
            }
        }
    } catch (error) {
        console.error('Error loading templates:', error);
        showToast('Ошибка загрузки шаблонов', 'error');
    }
}

// Render templates
function renderTemplates(templates) {
    const gallery = document.getElementById('templates-gallery');
    gallery.innerHTML = templates.map(t => `
        <div style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; border: 1px solid var(--border);">
            <h4 style="margin-top: 0; margin-bottom: 10px;">${t.name}</h4>
            <p style="color: var(--text-secondary); font-size: 12px; margin-bottom: 10px;">${t.description || '-'}</p>
            <div style="font-size: 11px; color: var(--text-secondary); margin-bottom: 10px;">
                <span style="background: var(--accent); color: white; padding: 2px 6px; border-radius: 4px;">${t.category}</span>
            </div>
            <div class="btn-group">
                <button class="btn btn-primary" onclick="installTemplate('${t.id}')" style="font-size: 12px; padding: 6px 12px;">📥 Установить</button>
                <button class="btn btn-secondary" onclick="previewTemplate('${t.id}')" style="font-size: 12px; padding: 6px 12px;">👁️ Предпросмотр</button>
            </div>
        </div>
    `).join('');
}

// Filter templates
function filterTemplates() {
    const category = document.getElementById('template-category-filter').value;
    if (!category) {
        renderTemplates(allTemplates);
    } else {
        renderTemplates(allTemplates.filter(t => t.category === category));
    }
}

// Install template
async function installTemplate(templateId) {
    if (!confirm('Установить этот шаблон?\n\nТекущий index.html будет заменён.')) return;

    try {
        const response = await fetch('/api/camouflage/install', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ template_id: templateId, backup: true })
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Шаблон установлен!', 'success');
            loadCamouflageStatus();
        } else {
            showToast('Ошибка: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error installing template:', error);
        showToast('Ошибка установки', 'error');
    }
}

// Preview template
async function previewTemplate(templateId) {
    try {
        const response = await fetch('/api/camouflage/preview/' + templateId);
        const data = await response.json();

        if (data.success && data.html) {
            const win = window.open('', '_blank');
            win.document.write(data.html);
            win.document.close();
        } else {
            showToast('Ошибка предпросмотра', 'error');
        }
    } catch (error) {
        console.error('Error previewing:', error);
    }
}

// Install random template
async function installRandomTemplate() {
    if (!confirm('Установить случайный шаблон?')) return;

    try {
        const response = await fetch('/api/camouflage/install-random', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({})
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Случайный шаблон установлен: ' + (data.template_name || ''), 'success');
            loadCamouflageStatus();
        } else {
            showToast('Ошибка: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error installing random template:', error);
        showToast('Ошибка установки', 'error');
    }
}

// Install custom HTML
async function installCustomHtml() {
    const html = document.getElementById('custom-html-input').value;

    if (!html || html.trim().length < 50) {
        showToast('Введите HTML код (минимум 50 символов)', 'error');
        return;
    }

    if (!confirm('Установить этот HTML как fake сайт?')) return;

    try {
        const response = await fetch('/api/camouflage/install-custom', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ html_content: html, backup: true })
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Кастомный HTML установлен!', 'success');
            loadCamouflageStatus();
        } else {
            showToast('Ошибка: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error installing custom HTML:', error);
        showToast('Ошибка установки', 'error');
    }
}

// Remove camouflage
async function removeCamouflage() {
    if (!confirm('Удалить fake сайт и восстановить оригинал?')) return;

    try {
        const response = await fetch('/api/camouflage/remove', { method: 'DELETE' });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Fake сайт удалён', 'success');
            loadCamouflageStatus();
        } else {
            showToast('Ошибка: ' + (data.error || 'Unknown'), 'error');
        }
    } catch (error) {
        console.error('Error removing camouflage:', error);
        showToast('Ошибка удаления', 'error');
    }
}

// ==================== AUTOMATION ====================

// Load automation settings
async function loadAutomationSettings() {
    try {
        const response = await fetch(API_URL + 'api/automation/settings', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success && data.settings) {
            const s = data.settings;
            document.getElementById('backup-enabled').checked = s.backup_enabled;
            document.getElementById('backup-interval').value = s.backup_interval_hours;
            document.getElementById('backup-retention').value = s.backup_retention_days;
            document.getElementById('ssl-auto-check').checked = s.ssl_check_enabled;
            document.getElementById('ssl-auto-renew').checked = s.ssl_auto_renew;
            document.getElementById('warp-health-check').checked = s.warp_health_check_enabled;
            document.getElementById('warp-auto-restart').checked = s.warp_auto_restart;
        }
    } catch (error) {
        console.error('Error loading automation settings:', error);
    }
}

// Save automation settings
async function saveAutomationSettings() {
    const settings = {
        backup_enabled: document.getElementById('backup-enabled').checked,
        backup_interval_hours: parseInt(document.getElementById('backup-interval').value),
        backup_retention_days: parseInt(document.getElementById('backup-retention').value),
        ssl_check_enabled: document.getElementById('ssl-auto-check').checked,
        ssl_auto_renew: document.getElementById('ssl-auto-renew').checked,
        warp_health_check_enabled: document.getElementById('warp-health-check').checked,
        warp_auto_restart: document.getElementById('warp-auto-restart').checked
    };

    try {
        const response = await fetch(API_URL + 'api/automation/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify(settings)
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Настройки сохранены', 'success');
        } else {
            showToast('Ошибка сохранения', 'error');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        showToast('Ошибка сохранения', 'error');
    }
}

// Load services status
async function loadServicesStatus() {
    try {
        const response = await fetch(API_URL + 'api/automation/services', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success && data.services) {
            data.services.forEach(svc => {
                let elemId = '';
                if (svc.service === 'x-ui') elemId = 'service-xui-status';
                else if (svc.service === 'xui-manager') elemId = 'service-manager-status';
                else if (svc.service === 'nginx') elemId = 'service-nginx-status';

                if (elemId) {
                    const elem = document.getElementById(elemId);
                    if (elem) {
                        elem.textContent = svc.active ? '✅ Активен' : '❌ Остановлен';
                        elem.style.color = svc.active ? 'var(--success)' : 'var(--danger)';
                    }
                }
            });
        }

        // Also check WARP
        checkWarpStatus();
    } catch (error) {
        console.error('Error loading services status:', error);
    }
}

// Restart service
async function restartService(service) {
    if (!confirm(`Перезапустить ${service}?`)) return;

    try {
        const response = await fetch(API_URL + `api/automation/service/${service}/restart`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast(`✅ ${service} перезапущен`, 'success');
            setTimeout(loadServicesStatus, 2000);
        } else {
            showToast('Ошибка: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error restarting service:', error);
        showToast('Ошибка перезапуска', 'error');
    }
}

// Check SSL certificates
async function checkSSLCertificates() {
    const container = document.getElementById('ssl-certificates-list');
    container.innerHTML = '<p style="color: var(--accent);">Проверка...</p>';

    try {
        const response = await fetch(API_URL + 'api/automation/ssl/check', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success && data.certificates.length > 0) {
            let html = '<div style="display: flex; flex-direction: column; gap: 10px;">';
            data.certificates.forEach(cert => {
                const statusColor = cert.status === 'ok' ? 'var(--success)' :
                                  cert.status === 'warning' ? 'var(--warning)' : 'var(--danger)';
                html += `
                    <div style="background: var(--bg-tertiary); padding: 10px; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong>${cert.domain}</strong>
                            <div style="font-size: 12px; color: var(--text-secondary);">
                                Истекает: ${new Date(cert.expiry).toLocaleDateString()}
                            </div>
                        </div>
                        <div style="color: ${statusColor}; font-weight: 600;">
                            ${cert.days_left} дней
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            container.innerHTML = html;
        } else {
            container.innerHTML = '<p style="color: var(--text-secondary);">SSL сертификаты не найдены</p>';
        }
    } catch (error) {
        console.error('Error checking SSL:', error);
        container.innerHTML = '<p style="color: var(--danger);">Ошибка проверки</p>';
    }
}

// Renew SSL certificates
async function renewSSLCertificates() {
    if (!confirm('Запустить продление SSL сертификатов?')) return;

    showToast('Запуск продления SSL...', 'info');

    try {
        const response = await fetch(API_URL + 'api/automation/ssl/renew', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Сертификаты продлены', 'success');
            checkSSLCertificates();
        } else {
            showToast('Ошибка: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error renewing SSL:', error);
        showToast('Ошибка продления', 'error');
    }
}

// Check WARP status
async function checkWarpStatus() {
    try {
        const response = await fetch(API_URL + 'api/automation/warp/status', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            const statusElem = document.getElementById('warp-connection-status');
            const ipElem = document.getElementById('warp-ip');
            const countryElem = document.getElementById('warp-country');
            const serviceElem = document.getElementById('service-warp-status');

            if (!data.installed) {
                statusElem.textContent = 'Не установлен';
                statusElem.style.color = 'var(--text-secondary)';
                if (serviceElem) {
                    serviceElem.textContent = 'Не установлен';
                    serviceElem.style.color = 'var(--text-secondary)';
                }
            } else if (data.connected) {
                statusElem.textContent = '✅ Подключен';
                statusElem.style.color = 'var(--success)';
                ipElem.textContent = data.ip || '-';
                countryElem.textContent = data.country || '-';
                if (serviceElem) {
                    serviceElem.textContent = '✅ Активен';
                    serviceElem.style.color = 'var(--success)';
                }
            } else {
                statusElem.textContent = '❌ Отключен';
                statusElem.style.color = 'var(--danger)';
                if (serviceElem) {
                    serviceElem.textContent = '❌ Отключен';
                    serviceElem.style.color = 'var(--danger)';
                }
            }
        }
    } catch (error) {
        console.error('Error checking WARP:', error);
    }
}

// Restart WARP
async function restartWarp() {
    try {
        const response = await fetch(API_URL + 'api/automation/warp/restart', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ WARP перезапущен', 'success');
            setTimeout(checkWarpStatus, 3000);
        } else {
            showToast('Ошибка перезапуска WARP', 'error');
        }
    } catch (error) {
        console.error('Error restarting WARP:', error);
        showToast('Ошибка перезапуска', 'error');
    }
}

// ==================== BACKUPS ====================

// Load backups
async function loadBackups() {
    const tbody = document.getElementById('backups-table-body');
    tbody.innerHTML = '<tr><td colspan="4" class="loading">Загрузка...</td></tr>';

    try {
        const response = await fetch(API_URL + 'api/automation/backups', {
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success && data.backups.length > 0) {
            tbody.innerHTML = data.backups.map(backup => `
                <tr>
                    <td>${new Date(backup.timestamp).toLocaleString()}</td>
                    <td>${backup.files_count}</td>
                    <td>${backup.size_human}</td>
                    <td>
                        <button class="btn btn-primary" style="padding: 4px 8px; font-size: 11px;"
                            onclick="restoreBackup('${backup.name}')">🔄 Восстановить</button>
                        <button class="btn btn-danger" style="padding: 4px 8px; font-size: 11px;"
                            onclick="deleteBackup('${backup.name}')">🗑️</button>
                    </td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-secondary);">Нет бэкапов</td></tr>';
        }
    } catch (error) {
        console.error('Error loading backups:', error);
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--danger);">Ошибка загрузки</td></tr>';
    }
}

// Create backup
async function createBackup() {
    showToast('Создание бэкапа...', 'info');

    try {
        const response = await fetch(API_URL + 'api/automation/backup/create', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast(`✅ Бэкап создан: ${data.files.length} файлов`, 'success');
            loadBackups();
        } else {
            showToast('Ошибка: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error creating backup:', error);
        showToast('Ошибка создания бэкапа', 'error');
    }
}

// Restore backup
async function restoreBackup(name) {
    if (!confirm(`Восстановить из бэкапа ${name}?\n\nЭто перезапишет текущие данные!`)) return;

    showToast('Восстановление...', 'info');

    try {
        const response = await fetch(API_URL + `api/automation/backup/restore/${name}`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast(`✅ Восстановлено: ${data.restored_files.length} файлов`, 'success');
            // Reload page after restore
            setTimeout(() => window.location.reload(), 2000);
        } else {
            showToast('Ошибка: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error restoring backup:', error);
        showToast('Ошибка восстановления', 'error');
    }
}

// Delete backup
async function deleteBackup(name) {
    if (!confirm(`Удалить бэкап ${name}?`)) return;

    try {
        const response = await fetch(API_URL + `api/automation/backup/${name}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        const data = await response.json();

        if (data.success) {
            showToast('✅ Бэкап удалён', 'success');
            loadBackups();
        } else {
            showToast('Ошибка удаления', 'error');
        }
    } catch (error) {
        console.error('Error deleting backup:', error);
        showToast('Ошибка удаления', 'error');
    }
}

// ==================== BULK OPERATIONS ====================

let bulkUsersData = [];
let bulkSelectedIds = new Set();

// Load users for bulk operations (all users)
async function loadBulkUsers() {
    try {
        // Load ALL users for bulk operations
        const response = await fetch(API_URL + 'api/users?per_page=10000', { credentials: 'include' });
        if (!response.ok) throw new Error('Failed to load users');
        const data = await response.json();
        bulkUsersData = data.users || data;
        renderBulkUsersTable();
    } catch (error) {
        console.error('Error loading bulk users:', error);
        showToast('Ошибка загрузки пользователей', 'error');
    }
}

// Render bulk users table
function renderBulkUsersTable() {
    const tbody = document.getElementById('bulk-users-table');
    if (!tbody) return;

    const searchTerm = (document.getElementById('bulk-search')?.value || '').toLowerCase();
    const filteredUsers = bulkUsersData.filter(user =>
        user.email.toLowerCase().includes(searchTerm)
    );

    if (filteredUsers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px;">Пользователи не найдены</td></tr>';
        return;
    }

    tbody.innerHTML = filteredUsers.map(user => {
        const isSelected = bulkSelectedIds.has(user.id.toString());
        const status = !user.enable ? 'Отключен' :
                      (user.expiryTime && user.expiryTime < Date.now()) ? 'Истёк' : 'Активен';
        const statusColor = status === 'Активен' ? 'var(--success)' :
                           status === 'Истёк' ? 'var(--warning)' : 'var(--danger)';
        const expiry = user.expiryTime ? new Date(user.expiryTime).toLocaleDateString('ru-RU') : 'Бессрочно';
        const traffic = user.totalGB ? (user.totalGB + ' GB') : 'Безлимит';

        return `
            <tr class="bulk-user-row ${isSelected ? 'selected' : ''}">
                <td><input type="checkbox" class="bulk-checkbox" data-id="${user.id}" ${isSelected ? 'checked' : ''} onchange="bulkToggleUser('${user.id}', this.checked)"></td>
                <td>${user.email}</td>
                <td style="color: ${statusColor}">${status}</td>
                <td>${expiry}</td>
                <td>${traffic}</td>
            </tr>
        `;
    }).join('');

    updateBulkSelectedCount();
}

// Toggle single user selection
function bulkToggleUser(userId, checked) {
    if (checked) {
        bulkSelectedIds.add(userId.toString());
    } else {
        bulkSelectedIds.delete(userId.toString());
    }
    updateBulkSelectedCount();
    const row = document.querySelector(`[data-id="${userId}"]`)?.closest('tr');
    if (row) row.classList.toggle('selected', checked);
}

// Toggle all users
function bulkToggleAll(checked) {
    const searchTerm = (document.getElementById('bulk-search')?.value || '').toLowerCase();
    bulkUsersData.filter(u => u.email.toLowerCase().includes(searchTerm)).forEach(user => {
        if (checked) bulkSelectedIds.add(user.id.toString());
        else bulkSelectedIds.delete(user.id.toString());
    });
    renderBulkUsersTable();
}

function bulkSelectAll() {
    bulkUsersData.forEach(u => bulkSelectedIds.add(u.id.toString()));
    if (document.getElementById('bulk-select-all-checkbox')) document.getElementById('bulk-select-all-checkbox').checked = true;
    renderBulkUsersTable();
}

function bulkSelectNone() {
    bulkSelectedIds.clear();
    if (document.getElementById('bulk-select-all-checkbox')) document.getElementById('bulk-select-all-checkbox').checked = false;
    renderBulkUsersTable();
}

function bulkSelectExpired() {
    bulkSelectNone();
    const now = Date.now();
    bulkUsersData.forEach(u => { if (u.expiryTime && u.expiryTime < now && u.expiryTime !== 0) bulkSelectedIds.add(u.id.toString()); });
    renderBulkUsersTable();
}

function bulkSelectDisabled() {
    bulkSelectNone();
    bulkUsersData.forEach(u => { if (!u.enable) bulkSelectedIds.add(u.id.toString()); });
    renderBulkUsersTable();
}

function bulkSelectActive() {
    bulkSelectNone();
    const now = Date.now();
    bulkUsersData.forEach(u => { if (u.enable && (!u.expiryTime || u.expiryTime === 0 || u.expiryTime > now)) bulkSelectedIds.add(u.id.toString()); });
    renderBulkUsersTable();
}

function bulkFilterUsers() { renderBulkUsersTable(); }

function updateBulkSelectedCount() {
    const el = document.getElementById('bulk-selected-count');
    if (el) el.textContent = bulkSelectedIds.size;
}

function showBulkProgress(show, text = 'Подготовка...') {
    const progress = document.getElementById('bulk-progress');
    if (progress) {
        progress.style.display = show ? 'block' : 'none';
        const progressText = document.getElementById('bulk-progress-text');
        const progressBar = document.getElementById('bulk-progress-bar');
        if (progressText) progressText.textContent = text;
        if (progressBar) { progressBar.style.width = '0%'; progressBar.classList.toggle('progress-active', show); }
    }
}

function updateBulkProgress(percent, text) {
    const bar = document.getElementById('bulk-progress-bar');
    const txt = document.getElementById('bulk-progress-text');
    if (bar) bar.style.width = percent + '%';
    if (txt && text) txt.textContent = text;
}

async function bulkExtendExpiry() {
    if (bulkSelectedIds.size === 0) { showToast('Выберите пользователей', 'warning'); return; }
    const days = parseInt(document.getElementById('bulk-extend-days')?.value || 30);
    if (days < 1 || days > 365) { showToast('Введите дни от 1 до 365', 'warning'); return; }
    if (!confirm(`Продлить срок для ${bulkSelectedIds.size} пользователей на ${days} дней?`)) return;
    showBulkProgress(true, 'Продление сроков...');
    try {
        const response = await fetch(API_URL + 'api/users/batch/extend-expiry', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ user_ids: Array.from(bulkSelectedIds), days: days })
        });
        const result = await response.json();
        if (result.success) {
            updateBulkProgress(100, `Готово! Обработано: ${result.processed}, Скорость: ${result.speed_per_second?.toFixed(1) || '-'}/сек`);
            showToast(`Продлено ${result.processed} пользователей`, 'success');
            setTimeout(() => { showBulkProgress(false); loadBulkUsers(); loadUsers(); }, 2000);
        } else throw new Error(result.detail || 'Error');
    } catch (e) { showToast('Ошибка: ' + e.message, 'error'); showBulkProgress(false); }
}

async function bulkSetExpiry() {
    if (bulkSelectedIds.size === 0) { showToast('Выберите пользователей', 'warning'); return; }
    const expiryInput = document.getElementById('bulk-set-expiry')?.value;
    if (!expiryInput) { showToast('Выберите дату', 'warning'); return; }
    if (!confirm(`Установить дату для ${bulkSelectedIds.size} пользователей?`)) return;
    showBulkProgress(true, 'Установка даты...');
    try {
        const response = await fetch(API_URL + 'api/users/batch/set-expiry', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ user_ids: Array.from(bulkSelectedIds), expiry_time: new Date(expiryInput).getTime() })
        });
        const result = await response.json();
        if (result.success) {
            updateBulkProgress(100, `Готово! Обработано: ${result.processed}`);
            showToast(`Обновлено ${result.processed} пользователей`, 'success');
            setTimeout(() => { showBulkProgress(false); loadBulkUsers(); loadUsers(); }, 2000);
        } else throw new Error(result.detail || 'Error');
    } catch (e) { showToast('Ошибка: ' + e.message, 'error'); showBulkProgress(false); }
}

async function bulkAddTraffic() {
    if (bulkSelectedIds.size === 0) { showToast('Выберите пользователей', 'warning'); return; }
    const gb = parseInt(document.getElementById('bulk-add-traffic')?.value || 10);
    if (gb < 1 || gb > 1000) { showToast('Введите GB от 1 до 1000', 'warning'); return; }
    if (!confirm(`Добавить ${gb} GB для ${bulkSelectedIds.size} пользователей?`)) return;
    showBulkProgress(true, 'Добавление трафика...');
    try {
        const response = await fetch(API_URL + 'api/users/batch/add-traffic', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ user_ids: Array.from(bulkSelectedIds), traffic_gb: gb })
        });
        const result = await response.json();
        if (result.success) {
            updateBulkProgress(100, `Готово! Обработано: ${result.processed}`);
            showToast(`Добавлен трафик для ${result.processed} пользователей`, 'success');
            setTimeout(() => { showBulkProgress(false); loadBulkUsers(); loadUsers(); }, 2000);
        } else throw new Error(result.detail || 'Error');
    } catch (e) { showToast('Ошибка: ' + e.message, 'error'); showBulkProgress(false); }
}

async function bulkResetTraffic() {
    if (bulkSelectedIds.size === 0) { showToast('Выберите пользователей', 'warning'); return; }
    const newLimitGB = parseInt(document.getElementById('bulk-reset-traffic')?.value || 0);
    if (!confirm(`Сбросить трафик для ${bulkSelectedIds.size} пользователей?`)) return;
    showBulkProgress(true, 'Сброс трафика...');
    try {
        const response = await fetch(API_URL + 'api/users/batch/reset-traffic', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ user_ids: Array.from(bulkSelectedIds), new_limit_gb: newLimitGB })
        });
        const result = await response.json();
        if (result.success) {
            updateBulkProgress(100, `Готово! Обработано: ${result.processed}`);
            showToast(`Сброшен трафик для ${result.processed} пользователей`, 'success');
            setTimeout(() => { showBulkProgress(false); loadBulkUsers(); loadUsers(); }, 2000);
        } else throw new Error(result.detail || 'Error');
    } catch (e) { showToast('Ошибка: ' + e.message, 'error'); showBulkProgress(false); }
}

async function bulkToggleUsers(enable) {
    if (bulkSelectedIds.size === 0) { showToast('Выберите пользователей', 'warning'); return; }
    if (!confirm(`${enable ? 'Включить' : 'Отключить'} ${bulkSelectedIds.size} пользователей?`)) return;
    showBulkProgress(true, enable ? 'Включение...' : 'Отключение...');
    try {
        const response = await fetch(API_URL + 'api/users/batch/toggle', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ user_ids: Array.from(bulkSelectedIds), enable: enable })
        });
        const result = await response.json();
        if (result.success) {
            updateBulkProgress(100, `Готово! Обработано: ${result.processed}`);
            showToast(`${enable ? 'Включено' : 'Отключено'} ${result.processed} пользователей`, 'success');
            setTimeout(() => { showBulkProgress(false); loadBulkUsers(); loadUsers(); }, 2000);
        } else throw new Error(result.detail || 'Error');
    } catch (e) { showToast('Ошибка: ' + e.message, 'error'); showBulkProgress(false); }
}

async function bulkDeleteUsers() {
    if (bulkSelectedIds.size === 0) { showToast('Выберите пользователей', 'warning'); return; }
    if (!confirm(`УДАЛИТЬ ${bulkSelectedIds.size} пользователей? Это необратимо!`)) return;
    if (!confirm('Вы уверены? Данные будут удалены безвозвратно!')) return;
    showBulkProgress(true, 'Удаление...');
    let deleted = 0, failed = 0;
    const total = bulkSelectedIds.size;
    for (const userId of bulkSelectedIds) {
        try {
            const r = await fetch(API_URL + 'api/users/' + userId, { method: 'DELETE', credentials: 'include' });
            if (r.ok) deleted++; else failed++;
            updateBulkProgress(Math.round(((deleted + failed) / total) * 100), `Удалено: ${deleted}/${total}`);
        } catch { failed++; }
    }
    updateBulkProgress(100, `Готово! Удалено: ${deleted}, Ошибок: ${failed}`);
    showToast(`Удалено ${deleted} пользователей`, deleted > 0 ? 'success' : 'error');
    setTimeout(() => { showBulkProgress(false); bulkSelectedIds.clear(); loadBulkUsers(); loadUsers(); }, 2000);
}

// ==================== QUICK OPERATIONS (NO SELECTION NEEDED) ====================

// Ensure bulk users data is loaded (all users, not paginated)
async function ensureBulkUsersLoaded() {
    if (bulkUsersData.length === 0) {
        showToast('Загрузка пользователей...', 'info');
        try {
            // Load ALL users by setting high per_page limit
            const response = await fetch(API_URL + 'api/users?per_page=10000', { credentials: 'include' });
            if (!response.ok) throw new Error('Failed to load');
            const data = await response.json();
            bulkUsersData = data.users || data;
            showToast(`Загружено ${bulkUsersData.length} пользователей`, 'success');
        } catch (e) {
            showToast('Ошибка загрузки', 'error');
            return false;
        }
    }
    return true;
}

// Quick extend all expired users
async function quickExtendAllExpired() {
    if (!await ensureBulkUsersLoaded()) return;

    const days = parseInt(document.getElementById('quick-extend-days')?.value || 30);
    if (days < 1 || days > 365) { showToast('Введите дни от 1 до 365', 'warning'); return; }

    // Get expired user IDs
    const expiredIds = bulkUsersData
        .filter(u => u.expiryTime && u.expiryTime < Date.now() && u.expiryTime !== 0)
        .map(u => u.id.toString());

    if (expiredIds.length === 0) { showToast('Нет истекших пользователей', 'info'); return; }
    if (!confirm(`Продлить ${expiredIds.length} истекших пользователей на ${days} дней?`)) return;

    showBulkProgress(true, 'Продление истекших...');
    try {
        const response = await fetch(API_URL + 'api/users/batch/extend-expiry', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ user_ids: expiredIds, days: days })
        });
        const result = await response.json();
        if (result.success) {
            updateBulkProgress(100, `Готово! Продлено: ${result.processed}`);
            showToast(`Продлено ${result.processed} пользователей`, 'success');
            setTimeout(() => { showBulkProgress(false); loadBulkUsers(); loadUsers(); loadExpiredUsers(); }, 2000);
        } else throw new Error(result.detail || 'Error');
    } catch (e) { showToast('Ошибка: ' + e.message, 'error'); showBulkProgress(false); }
}

// Quick enable all disabled users
async function quickEnableAllDisabled() {
    if (!await ensureBulkUsersLoaded()) return;
    const disabledIds = bulkUsersData.filter(u => !u.enable).map(u => u.id.toString());

    if (disabledIds.length === 0) { showToast('Нет отключенных пользователей', 'info'); return; }
    if (!confirm(`Включить ${disabledIds.length} отключенных пользователей?`)) return;

    showBulkProgress(true, 'Включение отключенных...');
    try {
        const response = await fetch(API_URL + 'api/users/batch/toggle', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ user_ids: disabledIds, enable: true })
        });
        const result = await response.json();
        if (result.success) {
            updateBulkProgress(100, `Готово! Включено: ${result.processed}`);
            showToast(`Включено ${result.processed} пользователей`, 'success');
            setTimeout(() => { showBulkProgress(false); loadBulkUsers(); loadUsers(); loadDisabledUsers(); }, 2000);
        } else throw new Error(result.detail || 'Error');
    } catch (e) { showToast('Ошибка: ' + e.message, 'error'); showBulkProgress(false); }
}

// Quick delete all disabled users
async function quickDeleteAllDisabled() {
    if (!await ensureBulkUsersLoaded()) return;
    const disabledIds = bulkUsersData.filter(u => !u.enable).map(u => u.id.toString());

    if (disabledIds.length === 0) { showToast('Нет отключенных пользователей', 'info'); return; }
    if (!confirm(`УДАЛИТЬ ${disabledIds.length} отключенных пользователей? Это необратимо!`)) return;
    if (!confirm('Вы уверены? Данные будут удалены безвозвратно!')) return;

    showBulkProgress(true, 'Удаление отключенных...');
    let deleted = 0, failed = 0;
    const total = disabledIds.length;
    for (const userId of disabledIds) {
        try {
            const r = await fetch(API_URL + 'api/users/' + userId, { method: 'DELETE', credentials: 'include' });
            if (r.ok) deleted++; else failed++;
            updateBulkProgress(Math.round(((deleted + failed) / total) * 100), `Удалено: ${deleted}/${total}`);
        } catch { failed++; }
    }
    updateBulkProgress(100, `Готово! Удалено: ${deleted}, Ошибок: ${failed}`);
    showToast(`Удалено ${deleted} пользователей`, deleted > 0 ? 'success' : 'error');
    setTimeout(() => { showBulkProgress(false); loadBulkUsers(); loadUsers(); loadDisabledUsers(); }, 2000);
}

// Quick reset traffic for expired users
async function quickResetTrafficExpired() {
    if (!await ensureBulkUsersLoaded()) return;
    const expiredIds = bulkUsersData
        .filter(u => u.expiryTime && u.expiryTime < Date.now() && u.expiryTime !== 0)
        .map(u => u.id.toString());

    if (expiredIds.length === 0) { showToast('Нет истекших пользователей', 'info'); return; }
    if (!confirm(`Сбросить трафик у ${expiredIds.length} истекших пользователей?`)) return;

    showBulkProgress(true, 'Сброс трафика...');
    try {
        const response = await fetch(API_URL + 'api/users/batch/reset-traffic', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ user_ids: expiredIds, new_limit_gb: 0 })
        });
        const result = await response.json();
        if (result.success) {
            updateBulkProgress(100, `Готово! Сброшено: ${result.processed}`);
            showToast(`Сброшен трафик у ${result.processed} пользователей`, 'success');
            setTimeout(() => { showBulkProgress(false); loadBulkUsers(); loadUsers(); }, 2000);
        } else throw new Error(result.detail || 'Error');
    } catch (e) { showToast('Ошибка: ' + e.message, 'error'); showBulkProgress(false); }
}

// Quick reset traffic for all users
async function quickResetTrafficAll() {
    if (!await ensureBulkUsersLoaded()) return;
    if (bulkUsersData.length === 0) { showToast('Нет пользователей', 'info'); return; }
    if (!confirm(`Сбросить трафик у ВСЕХ ${bulkUsersData.length} пользователей?`)) return;
    if (!confirm('Вы уверены? Это затронет ВСЕХ пользователей!')) return;

    const allIds = bulkUsersData.map(u => u.id.toString());
    showBulkProgress(true, 'Сброс трафика у всех...');
    try {
        const response = await fetch(API_URL + 'api/users/batch/reset-traffic', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include',
            body: JSON.stringify({ user_ids: allIds, new_limit_gb: 0 })
        });
        const result = await response.json();
        if (result.success) {
            updateBulkProgress(100, `Готово! Сброшено: ${result.processed}`);
            showToast(`Сброшен трафик у ${result.processed} пользователей`, 'success');
            setTimeout(() => { showBulkProgress(false); loadBulkUsers(); loadUsers(); }, 2000);
        } else throw new Error(result.detail || 'Error');
    } catch (e) { showToast('Ошибка: ' + e.message, 'error'); showBulkProgress(false); }
}

// ==================== SESSION MANAGEMENT ====================

// Auto-refresh session every 20 minutes to prevent expiration
setInterval(async () => {
    try {
        await fetch(API_URL + 'api/health', { credentials: 'include' });
        console.log('Session refreshed');
    } catch (e) {
        console.warn('Session refresh failed:', e);
    }
}, 20 * 60 * 1000);

// Check authentication before critical operations
async function ensureAuthenticated() {
    try {
        const response = await fetch(API_URL + 'api/health', { credentials: 'include' });
        if (response.status === 401) {
            showToast('Сессия истекла. Перезайдите в систему.', 'error');
            setTimeout(() => window.location.href = '/login', 2000);
            return false;
        }
        return true;
    } catch (e) {
        console.error('Auth check failed:', e);
        return false;
    }
}

// ==================== INITIALIZATION ====================

// Initialize
window.onload = function() {
    // Load panel credentials on X-UI control tab
    loadPanelCredentials();
    loadStats();
    loadInbounds();
    loadUsers();
    loadVersion();  // Load version info
    loadInboundsTable();  // Load inbounds table
    loadXuiStatus();  // Load X-UI status
    loadExpiredUsers();  // Load expired users
    loadDisabledUsers();  // Load disabled users

    // Refresh stats every 30 seconds
    setInterval(loadStats, 30000);

    // Check for updates every 6 hours
    setInterval(() => checkForUpdates(false), 6 * 60 * 60 * 1000);
};
