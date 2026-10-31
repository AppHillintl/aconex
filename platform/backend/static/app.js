
function onLettersPeriodPresetChange(preset) {
    const fIn = document.getElementById('sub-letters-from-date');
    const tIn = document.getElementById('sub-letters-to-date');
    if (!fIn || !tIn) return;

    if (preset === 'all') {
        fIn.value = '';
        tIn.value = '';
        loadProjectLetters(1);
        return;
    }

    const today = new Date();
    const formatDate = (d) => d.toISOString().split('T')[0];
    tIn.value = formatDate(today);

    let days = 0;
    if (preset === 'today_yesterday') days = 1;
    else if (preset === '7d') days = 7;
    else if (preset === '14d') days = 14;
    else if (preset === '30d') days = 30;
    else if (preset === '60d') days = 60;

    const fromDate = new Date();
    fromDate.setDate(today.getDate() - days);
    fIn.value = formatDate(fromDate);

    loadProjectLetters(1);
}
window.onLettersPeriodPresetChange = onLettersPeriodPresetChange;


function updateContractorRfiCompanyDropdown(companies) {
    const compSelect = document.getElementById('crfi-filter-company');
    if (!compSelect || !companies) return;
    const curVal = compSelect.value;
    let html = '<option value="all">All Responsible Companies</option>';
    companies.forEach(c => {
        html += `<option value="${escapeHtml(c)}" ${c === curVal ? 'selected' : ''}>${escapeHtml(c)}</option>`;
    });
    compSelect.innerHTML = html;
}
window.updateContractorRfiCompanyDropdown = updateContractorRfiCompanyDropdown;


// =========================================================================
// ANTIGRAVITY ENTERPRISE TABLE ENGINE: MULTI-SORT & COLUMN VISIBILITY
// =========================================================================
const AntigravityTableEngine = (function() {
    const sortStates = {};
    const hiddenColumns = {};

    function getTable(tableOrId) {
        if (typeof tableOrId === 'string') return document.getElementById(tableOrId);
        return tableOrId;
    }

    function initTable(tableId) {
        const table = getTable(tableId);
        if (!table) return;

        // Restore hidden columns from localStorage
        try {
            const saved = localStorage.getItem('table_cols_' + tableId);
            if (saved) {
                hiddenColumns[tableId] = new Set(JSON.parse(saved));
                applyColumnVisibility(tableId);
            }
        } catch(e) {}

        // Bind headers for sorting
        const ths = table.querySelectorAll('thead th');
        ths.forEach((th, idx) => {
            const text = th.innerText.trim().toLowerCase();
            if (text === 'action' || text === '' || th.classList.contains('no-sort')) return;

            th.classList.add('cursor-pointer', 'select-none', 'hover:bg-slate-800/80', 'transition');
            th.title = 'Click to sort \u2022 Hold Ctrl (or Cmd) for multi-sort';

            let badge = th.querySelector('.sort-badge');
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'sort-badge ml-1.5 inline-block text-[10px] text-amber-400 font-bold';
                th.appendChild(badge);
            }

            th.onclick = function(e) {
                handleHeaderClick(tableId, idx, e);
            };
        });
    }

    function handleHeaderClick(tableId, colIndex, e) {
        const table = getTable(tableId);
        if (!table) return;

        const isMulti = e.ctrlKey || e.metaKey;
        if (!sortStates[tableId]) sortStates[tableId] = [];
        let state = sortStates[tableId];

        const existingIdx = state.findIndex(s => s.colIndex === colIndex);

        if (isMulti) {
            if (existingIdx !== -1) {
                if (state[existingIdx].dir === 'asc') {
                    state[existingIdx].dir = 'desc';
                } else {
                    state.splice(existingIdx, 1);
                }
            } else {
                state.push({ colIndex, dir: 'asc' });
            }
        } else {
            if (existingIdx !== -1 && state.length === 1) {
                if (state[0].dir === 'asc') {
                    state[0].dir = 'desc';
                } else {
                    state = [];
                }
            } else {
                state = [{ colIndex, dir: 'asc' }];
            }
        }
        sortStates[tableId] = state;

        updateHeaderBadges(tableId);
        sortTableRows(tableId);
    }

    function updateHeaderBadges(tableId) {
        const table = getTable(tableId);
        if (!table) return;
        const state = sortStates[tableId] || [];
        const ths = table.querySelectorAll('thead th');

        ths.forEach((th, idx) => {
            const badge = th.querySelector('.sort-badge');
            if (!badge) return;
            const sortEntry = state.find(s => s.colIndex === idx);
            if (!sortEntry) {
                badge.innerHTML = '';
            } else {
                const arrow = sortEntry.dir === 'asc' ? '▲' : '▼';
                if (state.length > 1) {
                    const level = state.indexOf(sortEntry) + 1;
                    badge.innerHTML = `<span class="px-1 py-0.2 rounded bg-amber-500/20 text-amber-300 font-mono text-[9px]">${arrow} ${level}</span>`;
                } else {
                    badge.innerHTML = `<span class="text-amber-400 font-mono text-[10px]">${arrow}</span>`;
                }
            }
        });
    }

    function sortTableRows(tableId) {
        const table = getTable(tableId);
        if (!table) return;
        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const state = sortStates[tableId] || [];
        if (state.length === 0) return;

        const rows = Array.from(tbody.querySelectorAll('tr'));
        if (rows.length <= 1) return;

        rows.sort((rowA, rowB) => {
            for (const { colIndex, dir } of state) {
                const cellA = rowA.children[colIndex]?.innerText?.trim() || '';
                const cellB = rowB.children[colIndex]?.innerText?.trim() || '';

                const comp = compareValues(cellA, cellB);
                if (comp !== 0) {
                    return dir === 'asc' ? comp : -comp;
                }
            }
            return 0;
        });

        rows.forEach(r => tbody.appendChild(r));
    }

    function compareValues(a, b) {
        if (!a && !b) return 0;
        if (!a) return 1;
        if (!b) return -1;

        const cleanA = a.replace(/[^\d.-]/g, '');
        const cleanB = b.replace(/[^\d.-]/g, '');
        const numA = parseFloat(cleanA);
        const numB = parseFloat(cleanB);
        if (!isNaN(numA) && !isNaN(numB) && cleanA.length > 0 && cleanB.length > 0 && (!a.includes('-') || a.match(/\d{4}-\d{2}-\d{2}/))) {
            if (a.match(/\d{4}-\d{2}-\d{2}/) && b.match(/\d{4}-\d{2}-\d{2}/)) {
                return a.localeCompare(b);
            }
            if (!isNaN(numA) && !isNaN(numB) && a.match(/^[\d,.]+(\s*d)?$/i)) {
                return numA - numB;
            }
        }

        return a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' });
    }

    function toggleColumnPicker(tableId, e) {
        if (e) e.stopPropagation();
        let picker = document.getElementById('col-picker-' + tableId);
        if (picker) {
            picker.remove();
            return;
        }

        document.querySelectorAll('.col-picker-dropdown').forEach(p => p.remove());

        const table = getTable(tableId);
        if (!table) return;

        const ths = Array.from(table.querySelectorAll('thead th'));
        if (ths.length === 0) return;

        picker = document.createElement('div');
        picker.id = 'col-picker-' + tableId;
        picker.className = 'col-picker-dropdown absolute z-50 mt-1 right-0 w-64 bg-slate-900 border border-slate-700/80 rounded-xl shadow-2xl p-3 text-xs text-slate-200 animate-in fade-in duration-150';
        picker.onclick = (ev) => ev.stopPropagation();

        let html = `
            <div class="flex items-center justify-between pb-2 mb-2 border-b border-slate-800">
                <span class="font-bold text-white flex items-center gap-1.5"><i data-lucide="sliders" class="w-3.5 h-3.5 text-amber-400"></i> Configure Columns</span>
                <button type="button" onclick="AntigravityTableEngine.resetColumns('${tableId}')" class="text-[10px] text-amber-400 hover:text-amber-300 font-semibold cursor-pointer">Reset All</button>
            </div>
            <div class="space-y-1.5 max-h-60 overflow-y-auto pr-1">
        `;

        if (!hiddenColumns[tableId]) hiddenColumns[tableId] = new Set();
        const hidden = hiddenColumns[tableId];

        ths.forEach((th, idx) => {
            const label = th.innerText.replace(/[\n▲▼0-9]/g, '').trim();
            if (!label || label.toLowerCase() === 'action') return;
            const isChecked = !hidden.has(idx);

            html += `
                <label class="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-800/60 cursor-pointer transition">
                    <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="AntigravityTableEngine.setColumnVisible('${tableId}', ${idx}, this.checked)" class="rounded border-slate-700 text-amber-500 focus:ring-0 cursor-pointer">
                    <span class="truncate">${escapeHtml(label)}</span>
                </label>
            `;
        });

        html += `</div>`;
        picker.innerHTML = html;

        const btn = e.currentTarget || e.target;
        const parent = btn.parentElement;
        if (parent) {
            parent.style.position = 'relative';
            parent.appendChild(picker);
        }

        const closeHandler = function() {
            picker.remove();
            document.removeEventListener('click', closeHandler);
        };
        setTimeout(() => document.addEventListener('click', closeHandler), 50);
        if (window.lucide) lucide.createIcons();
    }

    function setColumnVisible(tableId, colIndex, isVisible) {
        if (!hiddenColumns[tableId]) hiddenColumns[tableId] = new Set();
        if (isVisible) {
            hiddenColumns[tableId].delete(colIndex);
        } else {
            hiddenColumns[tableId].add(colIndex);
        }
        applyColumnVisibility(tableId);
        try {
            localStorage.setItem('table_cols_' + tableId, JSON.stringify(Array.from(hiddenColumns[tableId])));
        } catch(e) {}
    }

    function resetColumns(tableId) {
        hiddenColumns[tableId] = new Set();
        applyColumnVisibility(tableId);
        try {
            localStorage.removeItem('table_cols_' + tableId);
        } catch(e) {}
        const picker = document.getElementById('col-picker-' + tableId);
        if (picker) {
            picker.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
        }
    }

    function applyColumnVisibility(tableId) {
        const table = getTable(tableId);
        if (!table) return;
        const hidden = hiddenColumns[tableId] || new Set();

        const allRows = table.querySelectorAll('tr');
        allRows.forEach(row => {
            Array.from(row.children).forEach((cell, idx) => {
                if (hidden.has(idx)) {
                    cell.style.display = 'none';
                } else {
                    cell.style.display = '';
                }
            });
        });
    }

    return {
        initTable,
        handleHeaderClick,
        toggleColumnPicker,
        setColumnVisible,
        resetColumns,
        applyColumnVisibility
    };
})();
window.AntigravityTableEngine = AntigravityTableEngine;

// Ras El Hekma Projects Hub & Controls Platform Engine
// Global State
let allProjects = [];
let selectedCategory = 'all';
let activeProjectData = null;
let currentSubTab = 'letters';
let currentColorMode = 'none';

// Sorting & Multi-Sort State
const sortStates = {
    letters: [],
    hill_ssc: [],
    rfis: [],
    shop_drawings: [],
    material_submittals: [],
    workflows: [],
    transmittals: [],
    other_mail: [],
    other_docs: []
};
const textWrapModes = {
    letters: true,
    hill_ssc: true,
    rfis: true,
    shop_drawings: true,
    material_submittals: true,
    workflows: true,
    transmittals: true,
    other_mail: true,
    other_docs: true
};
const pageStates = {
    letters: 1,
    hill_ssc: 1,
    rfis: 1,
    shop_drawings: 1,
    material_submittals: 1,
    workflows: 1,
    transmittals: 1,
    other_mail: 1,
    other_docs: 1
};
const totalCounts = {
    letters: 0,
    hill_ssc: 0,
    rfis: 0,
    shop_drawings: 0,
    material_submittals: 0,
    workflows: 0,
    transmittals: 0,
    other_mail: 0,
    other_docs: 0
};

// Controls Tab State
let ctrlProjectsList = [];
let ctrlCategoryFilter = 'all';
let ctrlSelectedCategory = 'all';
let ctrlProjectSearchTerm = '';
let ctrlSelectedProjectId = null;
let ctrlActiveReport = null;
let ctrlViewMode = 'report'; // 'report' or 'email'
let ctrlTableCategory = 'all'; // 'all', 'workflows', 'mail', 'rfis'
let ctrlTableTypeFilter = '';
let ctrlTableSearchQuery = '';
let ctrlTablePage = 1;
let ctrlTablePageSize = 25;
let ctrlSectionScope = { workflows: true, mail: false, rfis: true, scrs: true };
let ctrlSelectedKeys = new Set();
let selectedUploadFile = null;

// Date & Time Display Formatting Toggle
let showDateTimeMode = false;
function toggleDateTimeDisplay() {
    showDateTimeMode = !showDateTimeMode;
    document.querySelectorAll('.toggle-datetime-checkbox').forEach(cb => {
        cb.checked = showDateTimeMode;
    });
    reloadCurrentSubTab();
    if (ctrlActiveReport) renderCtrlTable();
}

function formatAppDate(dateStr) {
    if (!dateStr || dateStr === '-' || dateStr === 'null' || dateStr === 'None') return '-';
    const str = String(dateStr).trim();
    if (!str) return '-';

    const parts = str.replace('T', ' ').split(' ');
    const datePart = parts[0];
    const timePart = parts[1] || '';

    if (!showDateTimeMode) {
        return datePart;
    }

    if (timePart && timePart !== '00:00:00' && timePart !== '00:00') {
        const timeShort = timePart.substring(0, 5);
        return `${datePart} ${timeShort}`;
    }
    return datePart;
}

// ==========================================
// ORACLE ACONEX OFFICIAL LINK RESOLVERS
// Hyperlinks ALWAYS use direct IDs:
//   - Mails / RFIs: /MiniURL?type=MAILSEARCH&...&cid={id}
//   - Documents: /ViewDoc?trackingid={id}&...
// ==========================================
function getAconexMailUrl(item) {
    const direct = String(item?.aconex_url || '');
    if (direct.includes('/MiniURL?') || direct.includes('/ViewDoc?')) return direct;
    const cid = item?.correspondence_id || item?.mail_id;
    if (cid && !isNaN(Number(cid))) {
        return `https://mea.aconex.com/MiniURL?type=MAILSEARCH&mailbox=5&pid=1744833878&cid=${cid}`;
    }
    const mailNo = String(item?.mail_no || item?.rfi_no || item?.item_no || '').replace(/^["']+|["']+$/g, '').trim();
    if (mailNo) {
        return `/api/aconex/mail?mail_no=${encodeURIComponent(mailNo)}`;
    }
    if (direct.startsWith('http') && !direct.includes('docno:')) return direct;
    return `https://mea.aconex.com`;
}

function getAconexDocUrl(item) {
    const direct = String(item?.aconex_url || item?.aconex_doc_url || '');
    if (direct.includes('/MiniURL?')) return direct;
    const rawDocNo = String(item?.document_no || item?.doc_no || item?.item_no || '').replace(/^["']+|["']+$/g, '').trim();
    if (rawDocNo) return `/api/aconex/doc?doc_no=${encodeURIComponent(rawDocNo)}`;
    if (direct.startsWith('http') && !direct.includes('docno:') && !direct.includes('trackingid=')) return direct;
    return `https://mea.aconex.com`;
}

function getAconexWorkflowUrl(item) {
    const direct = String(item?.aconex_url || '');
    if (direct.includes('/ViewDoc?') || direct.includes('/MiniURL?')) return direct;
    const rawDocNo = String(item?.document_no || '').replace(/^["']+|["']+$/g, '').trim();
    if (rawDocNo) return `/api/aconex/doc?doc_no=${encodeURIComponent(rawDocNo)}`;
    const wfNo = String(item?.workflow_no || '').trim();
    if (wfNo) {
        return `https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=WORKFLOW-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=workflowNumber%3A${encodeURIComponent(wfNo)}`;
    }
    return `https://mea.aconex.com`;
}

// Global safety net: any legacy search link containing searchQuery or docno rendered anywhere in the app
// (discipline portals, daily feed, transmittals, timelines) is rewritten on click
// to the direct ViewDoc / MiniURL hyperlink with ID via the backend resolver.
document.addEventListener('click', function (ev) {
    const a = ev.target && ev.target.closest ? ev.target.closest('a[href]') : null;
    if (!a) return;
    const href = a.getAttribute('href') || '';
    if (!/mea\.aconex\.com/i.test(href)) return;

    // Direct ViewDoc or MiniURL links with IDs are already 100% authoritative!
    if (href.includes('/ViewDoc?') || href.includes('/MiniURL?')) return;

    const m = href.match(/searchQuery=([^&]+)/i);
    if (!m) return;
    let q = '';
    try { q = decodeURIComponent(m[1].replace(/\+/g, ' ')); } catch (e) { q = m[1]; }

    // Check if it's a doc query
    const dm = q.match(/(?:docno|documentNo|documentNumber)\s*:\s*"?([^"&]+)"?/i);
    if (dm && dm[1]) {
        ev.preventDefault();
        ev.stopPropagation();
        window.open(`/api/aconex/doc?doc_no=${encodeURIComponent(dm[1].trim())}`, '_blank', 'noopener');
        return;
    }

    // Check if it's a mail/rfi query
    const mm = q.match(/(?:mailNumber|mail_no|mailNo|id)\s*:\s*"?([^"&]+)"?/i);
    if (mm && mm[1]) {
        ev.preventDefault();
        ev.stopPropagation();
        window.open(`/api/aconex/mail?mail_no=${encodeURIComponent(mm[1].trim())}`, '_blank', 'noopener');
        return;
    }
}, true);

// Hill & SSC Direct Letters State
let hsdCurrentDirection = 'all';
let hsdCurrentPage = 1;
let hsdPageSize = 25;
let hsdSearchQuery = '';
let hsdSortCol = 'sent_date';
let hsdSortDir = 'desc';

// Sidebar Collapse State & Toggle
let isSidebarCollapsed = false;
function toggleSidebar() {
    isSidebarCollapsed = !isSidebarCollapsed;
    const sidebar = document.getElementById('main-sidebar');
    const content = document.getElementById('main-content-wrapper');
    const toggleIcon = document.getElementById('sidebar-toggle-icon');
    const toggleBtn = document.getElementById('sidebar-toggle-btn');

    if (isSidebarCollapsed) {
        if (sidebar) sidebar.classList.add('-translate-x-full');
        if (content) {
            content.classList.remove('ml-72');
            content.classList.add('ml-0');
        }
        if (toggleBtn) {
            toggleBtn.style.left = '0px';
            toggleBtn.style.transform = 'translate(0, -50%)';
            toggleBtn.setAttribute('title', 'Expand Sidebar');
        }
        if (toggleIcon) toggleIcon.setAttribute('data-lucide', 'chevron-right');
    } else {
        if (sidebar) sidebar.classList.remove('-translate-x-full');
        if (content) {
            content.classList.remove('ml-0');
            content.classList.add('ml-72');
        }
        if (toggleBtn) {
            toggleBtn.style.left = '18rem'; // 288px (w-72)
            toggleBtn.style.transform = 'translate(-50%, -50%)';
            toggleBtn.setAttribute('title', 'Collapse Sidebar');
        }
        if (toggleIcon) toggleIcon.setAttribute('data-lucide', 'chevron-left');
    }
    if (window.lucide) lucide.createIcons();
}
window.toggleSidebar = toggleSidebar;
window.switchPrimaryTab = switchPrimaryTab;

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) lucide.createIcons();
    loadAllProjects();
    fetch('/api/database/cutoff')
        .then(r => r.json())
        .then(data => {
            if (data && data.formatted) {
                const el = document.getElementById('header-data-cutoff');
                if (el) el.innerText = data.formatted;
            }
            if (data && data.last_sync_formatted) {
                const elSync = document.getElementById('header-last-sync');
                if (elSync) elSync.innerText = data.last_sync_formatted;
            }
        })
        .catch(() => {});
    updateLegendStrip();
    // Pre-populate Hill Internal Actions badge in background
    fetch('/api/controls/hill_team')
        .then(r => r.json())
        .then(json => {
            const list = json.data || [];
            let total = 0;
            list.forEach(e => total += (e.overdue_steps || 0) + (e.overdue_mails || 0));
            const sideBadge = document.getElementById('badge-hill-internal-count');
            // Pre-populate Daily Deliverables Feed badge in background
            fetch('/api/feed/summary?timeframe=today_yesterday')
                .then(r => r.json())
                .then(res => {
                    const badge = document.getElementById('badge-daily-feed-count');
                    if (badge && res.total_items !== undefined) {
                        badge.innerText = `${res.total_items.toLocaleString()} New`;
                    }
                })
                .catch(() => {});
            if (sideBadge) sideBadge.innerText = `${total.toLocaleString()} Overdue`;
        })
        .catch(() => {});

    // Pre-populate Hill & SSC Direct Letters badge in background
    fetch('/api/hill_ssc/direct?page_size=1')
        .then(r => r.json())
        .then(json => {
            const total = json.total || 106;
            const badge = document.getElementById('badge-hill-ssc-direct-count');
            if (badge) badge.innerText = `${total} Letters`;
            const kpiTotal = document.getElementById('stat-hsd-total');
            if (kpiTotal) kpiTotal.innerText = total;
            const kpiIn = document.getElementById('stat-hsd-inbound');
            if (kpiIn) kpiIn.innerText = json.inbound_count || 69;
            const kpiOut = document.getElementById('stat-hsd-outbound');
            if (kpiOut) kpiOut.innerText = json.outbound_count || 37;
        })
        .catch(() => {});
});

// ==========================================
// 1. PROJECTS HUB DIRECTORY
// ==========================================
async function loadAllProjects() {
    try {
        const res = await fetch('/api/projects');
        const json = await res.json();
        allProjects = json.data || [];
        window.allProjects = allProjects;

        updateHeaderAndPillCounters();
        filterAndRenderProjects();
        initMasterPlanMap();
    } catch (err) {
        console.error('Error loading projects:', err);
        const grid = document.getElementById('projects-grid');
        if (grid) {
            grid.innerHTML = `
                <div class="col-span-full py-12 text-center text-rose-400 bg-rose-500/10 rounded-2xl border border-rose-500/20 p-6">
                    <p class="font-bold">Error loading projects directory: ${err.message}</p>
                    <button onclick="loadAllProjects()" class="mt-4 px-4 py-2 bg-rose-600 text-white rounded-lg text-xs font-bold">Retry</button>
                </div>
            `;
        }
    }
}

// ==========================================
// 1.1 INTERACTIVE MASTER PLAN SYNOPTIC MAP
// ==========================================
let masterPlanLoaded = false;
let masterPlanScale = 1.0;
let masterPlanPanX = 0;
let masterPlanPanY = 0;
let isPanningMap = false;
let startPanX = 0;
let startPanY = 0;
let hasDragged = false;
let isFullscreenMap = false;

async function initMasterPlanMap() {
    const container = document.getElementById('master-plan-svg-container');
    const viewport = document.getElementById('master-plan-viewport');
    const tooltip = document.getElementById('master-plan-tooltip');
    if (!container || !viewport || !tooltip) return;

    if (!masterPlanLoaded) {
        try {
            const res = await fetch(`/static/images/master_plan_interactive.svg?v=${Date.now()}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const svgContent = await res.text();
            container.innerHTML = svgContent;
            masterPlanLoaded = true;
            if (window.lucide) lucide.createIcons();
            attachMasterPlanInteractivity(container, viewport, tooltip);
        } catch (err) {
            console.error('Failed to load Master Plan SVG:', err);
            container.innerHTML = `
                <div class="flex flex-col items-center justify-center p-6 text-rose-400 text-xs">
                    <p class="font-bold mb-2">Failed to load interactive Master Plan map</p>
                    <button onclick="masterPlanLoaded=false; initMasterPlanMap()" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700">Retry</button>
                </div>
            `;
            return;
        }
    } else {
        attachMasterPlanInteractivity(container, viewport, tooltip);
    }
}

function attachMasterPlanInteractivity(container, viewport, tooltip) {
    const interactiveElements = container.querySelectorAll('.synoptic-area, .callout-group');
    if (interactiveElements.length === 0) return;

    interactiveElements.forEach(el => {
        // Avoid duplicate listeners
        if (el._hasMasterPlanListener) return;
        el._hasMasterPlanListener = true;

        // Hover Enter & Move
        el.addEventListener('mouseenter', (e) => handleMasterPlanHover(e, el, viewport, tooltip));
        el.addEventListener('mousemove', (e) => positionMasterPlanTooltip(e, viewport, tooltip));
        el.addEventListener('mouseleave', () => handleMasterPlanLeave(tooltip));

        // Click to Open Workspace immediately
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            const pid = resolveMapProjectId(el);
            if (pid) {
                openProjectWorkspace(pid);
            }
        });
    });
}

function resolveMapProjectId(el) {
    let pid = el.getAttribute('data-project-id') || '';
    const aid = el.getAttribute('data-area-id') || el.id || '';
    
    const areaMap = {
        'Dp01': 'DP01',
        'DP01': 'DP01',
        'Dp02': 'DP02',
        'DP02': 'DP02',
        'Dp03-East': 'DP03-East',
        'Dp03_x20_East': 'DP03-East',
        'Dp03-E': 'DP03-East',
        'Dp03_x20_West': 'DP03-West',
        'Dp03-West': 'DP03-West',
        'Dp03-W': 'DP03-West',
        'Dp04': 'DP04',
        'DP04': 'DP04',
        'Dp05': 'DP05',
        'DP05': 'DP05',
        'Dpo6': 'DP06',
        'DP06': 'DP06',
        'Dp07': 'DP07',
        'DP07': 'DP07',
        'Dp08': 'DP08 - South Golf',
        'DP08': 'DP08 - South Golf',
        'Grand_x20_Canal': 'Grand Canal',
        'Grand Canal': 'Grand Canal',
        'West_x20_canal': 'West Canal',
        'West Canal': 'West Canal',
        'Ring_x20_Road': 'Infra',
        'Ring Road': 'Infra',
        'Infra': 'Infra',
        'MSS': 'MMS / Substation',
        'MMS': 'MMS / Substation',
        'MMS / Substation': 'MMS / Substation',
        'RO': 'RO Plant',
        'RO Plant': 'RO Plant',
        'STP': 'STP',
        'Airport': 'Airport'
    };

    if (areaMap[pid]) return areaMap[pid];
    if (areaMap[aid]) return areaMap[aid];
    return pid || aid;
}
window.resolveMapProjectId = resolveMapProjectId;

function handleMasterPlanHover(e, el, viewport, tooltip) {
    const aid = el.getAttribute('data-area-id') || el.id || '';
    const pid = resolveMapProjectId(el);
    const code = el.getAttribute('data-code') || pid || aid;
    const cat = el.getAttribute('data-category') || (pid.startsWith('DP') ? 'Wadi Yemm' : 'Infrastructure & Strategic Projects');

    // Synchronize hover state between polygon path and callout badge
    document.querySelectorAll(`[data-area-id="${aid}"]`).forEach(node => {
        node.classList.add('is-hovered');
    });

    // Lookup real-time metrics from allProjects
    const pData = allProjects.find(p => p.project_id === pid || p.project_name === pid) || {};
    const title = pData.project_title || el.getAttribute('data-title') || pid;
    const cno = pData.contract_no || el.getAttribute('data-contract') || '';
    const ctor = pData.contractor_name || el.getAttribute('data-contractor') || 'PMC / Consultant';
    const docsCount = pData.total_documents != null ? pData.total_documents.toLocaleString() : '-';
    const lettersCount = pData.total_letters != null ? pData.total_letters.toLocaleString() : (pData.total_mails != null ? pData.total_mails.toLocaleString() : '-');
    const rfisCount = pData.total_rfis != null ? pData.total_rfis.toLocaleString() : '-';
    const isWY = cat === 'Wadi Yemm';

    tooltip.innerHTML = `
        <div class="flex items-center justify-between gap-2 mb-2 pb-2 border-b border-slate-800">
            <span class="text-sm font-black text-sky-400 tracking-wide">${code}</span>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${isWY ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'}">
                ${cat}
            </span>
        </div>
        <div class="text-xs font-bold text-white mb-1.5 leading-snug">${title}</div>
        <div class="text-[11px] text-slate-400 mb-0.5">Contractor: <span class="text-slate-200 font-semibold">${ctor}</span></div>
        ${cno ? `<div class="text-[11px] text-slate-400 mb-2">Contract: <span class="text-sky-300 font-mono">${cno}</span></div>` : ''}

        <div class="grid grid-cols-3 gap-1.5 pt-2 border-t border-slate-800 text-center">
            <div class="bg-slate-950/70 rounded p-1.5 border border-slate-800">
                <div class="text-[9.5px] text-slate-400 font-medium">Letters</div>
                <div class="text-xs font-black text-indigo-400 font-mono">${lettersCount}</div>
            </div>
            <div class="bg-slate-950/70 rounded p-1.5 border border-slate-800">
                <div class="text-[9.5px] text-slate-400 font-medium">RFIs</div>
                <div class="text-xs font-black text-amber-400 font-mono">${rfisCount}</div>
            </div>
            <div class="bg-slate-950/70 rounded p-1.5 border border-slate-800">
                <div class="text-[9.5px] text-slate-400 font-medium">Docs</div>
                <div class="text-xs font-black text-emerald-400 font-mono">${docsCount}</div>
            </div>
        </div>

        <div class="mt-2.5 py-1 px-2 rounded-lg bg-sky-500/15 border border-sky-500/30 text-sky-300 text-[10.5px] font-bold text-center flex items-center justify-center gap-1.5 shadow-sm">
            <span>👉 Click to open workspace</span>
            <i data-lucide="arrow-right" class="w-3 h-3"></i>
        </div>
    `;

    if (window.lucide) lucide.createIcons();
    positionMasterPlanTooltip(e, viewport, tooltip);
    tooltip.classList.remove('hidden');
}

function positionMasterPlanTooltip(e, viewport, tooltip) {
    const vpRect = viewport.getBoundingClientRect();
    let left = e.clientX - vpRect.left + 16;
    let top = e.clientY - vpRect.top + 16;

    // Boundary constraints
    const tooltipWidth = 288;
    const tooltipHeight = 210;
    if (left + tooltipWidth > vpRect.width) {
        left = left - tooltipWidth - 24;
    }
    if (top + tooltipHeight > vpRect.height) {
        top = top - tooltipHeight - 20;
    }
    if (left < 10) left = 10;
    if (top < 10) top = 10;

    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
}

function handleMasterPlanLeave(tooltip) {
    document.querySelectorAll('.synoptic-area.is-hovered, .callout-group.is-hovered').forEach(node => {
        node.classList.remove('is-hovered');
    });
    if (tooltip) tooltip.classList.add('hidden');
}

function zoomMasterPlan(factor) {
    masterPlanScale = Math.min(3.5, Math.max(0.75, masterPlanScale * factor));
    updateMasterPlanTransform();
}

function resetMasterPlanZoom() {
    masterPlanScale = 1.0;
    masterPlanPanX = 0;
    masterPlanPanY = 0;
    updateMasterPlanTransform();
}

function updateMasterPlanTransform() {
    const svgEl = document.querySelector('#master-plan-svg-container svg');
    if (svgEl) {
        svgEl.style.transform = `translate(${masterPlanPanX}px, ${masterPlanPanY}px) scale(${masterPlanScale})`;
        svgEl.style.transformOrigin = 'center center';
        svgEl.style.transition = isPanningMap ? 'none' : 'transform 0.15s ease-out';
    }
}

function toggleMasterPlanFullscreen() {
    const card = document.getElementById('master-plan-card');
    const viewport = document.getElementById('master-plan-viewport');
    if (!card || !viewport) return;

    isFullscreenMap = !isFullscreenMap;
    if (isFullscreenMap) {
        card.classList.add('fixed', 'inset-0', 'z-50', 'm-0', 'rounded-none', 'h-screen', 'flex', 'flex-col', 'p-4');
        viewport.style.aspectRatio = 'auto';
        viewport.classList.remove('max-h-[480px]');
        viewport.classList.add('flex-1', 'h-full');
    } else {
        card.classList.remove('fixed', 'inset-0', 'z-50', 'm-0', 'rounded-none', 'h-screen', 'flex', 'flex-col', 'p-4');
        viewport.style.aspectRatio = '1568 / 672';
        viewport.classList.remove('flex-1', 'h-full');
        viewport.classList.add('max-h-[480px]');
    }
}

// Support Esc key to exit fullscreen for either map
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (isFullscreenMap) toggleMasterPlanFullscreen();
        if (isCtrlFullscreenMap) toggleCtrlMasterPlanFullscreen();
    }
});

function updateHeaderAndPillCounters() {
    let totalDocs = 0;
    let totalMails = 0;
    let totalRFIs = 0;
    let countWY = 0;
    let countISP = 0;
    let countDes = 0;
    let totalOverdueAll = 0;

    allProjects.forEach(p => {
        totalDocs += (p.total_documents || 0);
        totalMails += (p.total_mails || 0);
        totalRFIs += (p.total_rfis || 0);
        totalOverdueAll += (p.overdue_workflows || 0) + (p.overdue_mails || 0) + (p.overdue_rfis || 0);

        if (p.category === 'Wadi Yemm') countWY++;
        else if (p.category === 'Infrastructure & Strategic Projects') countISP++;
        else if (p.category === 'Design Consultancy') countDes++;
    });

    const setTxt = (id, txt) => { const el = document.getElementById(id); if (el) el.innerText = txt; };
    setTxt('stat-total-projects', allProjects.length);
    setTxt('badge-projects-count', `${allProjects.length} Pkgs`);
    setTxt('badge-overdue-total-count', `${Number(totalOverdueAll).toLocaleString()} Overdue`);
    setTxt('stat-total-docs', Number(totalDocs).toLocaleString());
    setTxt('top-total-docs', Number(totalDocs).toLocaleString());
    setTxt('stat-total-mails', Number(totalMails).toLocaleString());
    setTxt('top-total-mails', Number(totalMails).toLocaleString());
    setTxt('stat-total-rfis', Number(totalRFIs).toLocaleString());

    setTxt('count-pill-all', allProjects.length);
    setTxt('count-pill-wy', countWY);
    setTxt('count-pill-isp', countISP);
    setTxt('count-pill-des', countDes);
}

function setCategoryFilter(cat) {
    selectedCategory = cat;
    document.querySelectorAll('.cat-pill').forEach(btn => {
        const btnCat = btn.getAttribute('data-cat');
        if (btnCat === cat) {
            btn.className = 'cat-pill px-4 py-2 rounded-xl text-xs font-bold bg-sky-600 text-white shadow-md shadow-sky-600/20 transition';
        } else {
            btn.className = 'cat-pill px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition';
        }
    });
    filterAndRenderProjects();
}

let projectsViewMode = 'grid';

function setProjectsViewMode(mode) {
    projectsViewMode = mode;
    const btnGrid = document.getElementById('btn-projects-view-grid');
    const btnTable = document.getElementById('btn-projects-view-table');
    const gridCont = document.getElementById('projects-grid');
    const tableCont = document.getElementById('projects-table-container');

    if (mode === 'grid') {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5';
        if (gridCont) gridCont.classList.remove('hidden');
        if (tableCont) tableCont.classList.add('hidden');
    } else {
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm';
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5';
        if (tableCont) tableCont.classList.remove('hidden');
        if (gridCont) gridCont.classList.add('hidden');
    }
    filterAndRenderProjects();
}
window.setProjectsViewMode = setProjectsViewMode;

function onProjectsSearchInput(val) {
    const clearBtn = document.getElementById('projects-search-clear');
    if (clearBtn) {
        if (val && val.trim().length > 0) {
            clearBtn.classList.remove('hidden');
        } else {
            clearBtn.classList.add('hidden');
        }
    }
    filterAndRenderProjects();
}
window.onProjectsSearchInput = onProjectsSearchInput;

function clearProjectsSearch() {
    const input = document.getElementById('projects-search-input');
    if (input) input.value = '';
    const clearBtn = document.getElementById('projects-search-clear');
    if (clearBtn) clearBtn.classList.add('hidden');
    filterAndRenderProjects();
}
window.clearProjectsSearch = clearProjectsSearch;

function filterAndRenderProjects() {
    const container = document.getElementById('projects-grid');
    const tableBody = document.getElementById('projects-table-tbody');
    if (!container) return;

    const searchInput = document.getElementById('projects-search-input');
    const q = (searchInput?.value || '').trim().toLowerCase();
    const clearBtn = document.getElementById('projects-search-clear');
    if (clearBtn) {
        if (q.length > 0) clearBtn.classList.remove('hidden');
        else clearBtn.classList.add('hidden');
    }

    const filtered = allProjects.filter(p => {
        if (selectedCategory !== 'all' && p.category !== selectedCategory) return false;
        if (q) {
            const str = `${p.project_name || ''} ${p.project_title || ''} ${p.contractor_name || ''} ${p.contract_no || ''} ${p.k_package_no || ''}`.toLowerCase();
            if (!str.includes(q)) return false;
        }
        return true;
    });

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="col-span-full py-16 text-center text-slate-500 bg-slate-900/40 rounded-2xl border border-slate-800 p-8 flex flex-col items-center justify-center">
                <i data-lucide="layers" class="w-12 h-12 text-slate-600 mb-3"></i>
                <p class="text-sm font-bold text-slate-300 mb-1">No packages match the selected criteria</p>
                ${q ? `<p class="text-xs text-slate-500 mb-4 max-w-md font-mono bg-slate-950 px-3 py-1 rounded border border-slate-800">Search: "${escapeHtml(q)}"</p>` : ''}
                <button type="button" onclick="clearProjectsSearch(); setCategory('all');" class="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-2 cursor-pointer shadow-lg shadow-sky-600/20">
                    <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i>
                    <span>Clear Search & Show All Packages</span>
                </button>
            </div>
        `;
        if (tableBody) {
            tableBody.innerHTML = `<tr><td colspan="9" class="p-8 text-center text-slate-500">
                <div>No packages match criteria. <button onclick="clearProjectsSearch(); setCategory('all');" class="text-sky-400 underline font-bold ml-2">Reset</button></div>
            </td></tr>`;
        }
        if (window.lucide) lucide.createIcons();
        return;
    }

    let gridHtml = '';
    let tableHtml = '';

    filtered.forEach(p => {
        const isWY = p.category === 'Wadi Yemm';
        const isISP = p.category === 'Infrastructure & Strategic Projects';
        const catBadgeClass = isWY ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' :
                              isISP ? 'bg-amber-500/15 text-amber-400 border-amber-500/30' :
                              'bg-purple-500/15 text-purple-400 border-purple-500/30';
        const catLabel = isWY ? 'Wadi Yemm' : isISP ? 'Infra & Strategic' : 'Design Consultancy';

        const pid = p.project_id || '';
        const kcode = (p.k_package_no || '').split('/')[0].trim();
        const displayCode = (kcode && kcode !== pid) ? `${pid} • ${kcode}` : (pid || kcode);

        // Tile / Card View HTML
        gridHtml += `
            <div class="bg-slate-900 rounded-2xl border border-slate-800 hover:border-sky-500/50 p-5 flex flex-col justify-between transition-all duration-200 hover:shadow-xl hover:shadow-sky-500/5 group">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-3">
                        <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${catBadgeClass}">
                            ${catLabel}
                        </span>
                        <span class="text-[11px] font-mono font-bold text-sky-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                            ${displayCode}
                        </span>
                    </div>

                    <h3 class="text-base font-extrabold text-white group-hover:text-sky-400 transition mb-1 leading-snug">
                        ${escapeHtml(p.project_title || p.project_name)}
                    </h3>

                    <div class="flex items-center gap-1.5 text-xs text-slate-400 mb-4">
                        <i data-lucide="hard-hat" class="w-3.5 h-3.5 text-slate-500"></i>
                        <span class="truncate text-slate-300 font-medium">${escapeHtml(p.contractor_name || 'PMC / Consultant')}</span>
                    </div>

                    <div class="grid grid-cols-3 gap-2 p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 mb-4 text-center">
                        <div>
                            <span class="text-[10px] text-slate-400 block">Letters</span>
                            <span class="text-sm font-mono font-bold text-sky-400">${(p.total_letters || p.total_mails || 0).toLocaleString()}</span>
                        </div>
                        <div>
                            <span class="text-[10px] text-slate-400 block">RFIs</span>
                            <span class="text-sm font-mono font-bold text-amber-400">${(p.total_rfis || 0).toLocaleString()}</span>
                        </div>
                        <div>
                            <span class="text-[10px] text-slate-400 block">Workflows</span>
                            <span class="text-sm font-mono font-bold text-purple-400">${(p.total_workflows || 0).toLocaleString()}</span>
                        </div>
                    </div>
                </div>

                <button onclick="openProjectWorkspace('${p.project_id}')" class="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-sky-600 text-slate-200 hover:text-white text-xs font-bold flex items-center justify-center gap-2 border border-slate-700/60 hover:border-transparent transition-all shadow-sm cursor-pointer">
                    <span>Open Package Workspace</span>
                    <i data-lucide="arrow-right" class="w-3.5 h-3.5"></i>
                </button>
            </div>
        `;

        // Compact Table View HTML
        tableHtml += `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="p-3.5 whitespace-nowrap">
                    <span class="text-xs font-mono font-bold text-sky-400 bg-slate-950 px-2.5 py-1 rounded-lg border border-slate-800">
                        ${displayCode}
                    </span>
                </td>
                <td class="p-3.5">
                    <button onclick="openProjectWorkspace('${p.project_id}')" class="text-left font-bold text-white hover:text-sky-400 transition leading-snug cursor-pointer">
                        ${escapeHtml(p.project_title || p.project_name)}
                    </button>
                    ${p.contract_no ? `<div class="text-[10px] font-mono text-slate-500 mt-0.5">Contract: ${escapeHtml(p.contract_no)}</div>` : ''}
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${catBadgeClass}">
                        ${catLabel}
                    </span>
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <div class="flex items-center gap-1.5 text-xs text-slate-300">
                        <i data-lucide="hard-hat" class="w-3.5 h-3.5 text-slate-500"></i>
                        <span>${escapeHtml(p.contractor_name || 'PMC / Consultant')}</span>
                    </div>
                </td>
                <td class="p-3.5 text-center font-mono font-bold text-sky-400 whitespace-nowrap">
                    ${(p.total_letters || p.total_mails || 0).toLocaleString()}
                </td>
                <td class="p-3.5 text-center font-mono font-bold text-amber-400 whitespace-nowrap">
                    ${(p.total_rfis || 0).toLocaleString()}
                </td>
                <td class="p-3.5 text-center font-mono font-bold text-purple-400 whitespace-nowrap">
                    ${(p.total_workflows || 0).toLocaleString()}
                </td>
                <td class="p-3.5 text-center font-mono font-bold text-emerald-400 whitespace-nowrap">
                    ${(p.total_documents || 0).toLocaleString()}
                </td>
                <td class="p-3.5 text-center whitespace-nowrap">
                    <button onclick="openProjectWorkspace('${p.project_id}')" class="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-sky-600 text-slate-200 hover:text-white text-xs font-bold inline-flex items-center gap-1.5 border border-slate-700/60 hover:border-transparent transition shadow-sm cursor-pointer">
                        <span>Workspace</span>
                        <i data-lucide="arrow-right" class="w-3 h-3"></i>
                    </button>
                </td>
            </tr>
        `;
    });

    container.innerHTML = gridHtml;
    if (tableBody) {
        tableBody.innerHTML = tableHtml;
    }
    if (window.lucide) lucide.createIcons();
}

// ==========================================
// 2. PROJECT 360 WORKSPACE
// ==========================================
async function openProjectWorkspace(projectId) {
    if (!projectId) return;
    if (projectId === 'Ring Road' || projectId === 'Ring_x20_Road') {
        projectId = 'Infra';
    }
    if (projectId === 'MMS' || projectId === 'MSS' || projectId === 'MMS-Substation') {
        projectId = 'MMS / Substation';
    }
    if (projectId === 'RO') projectId = 'RO Plant';
    if (projectId === 'DP08') projectId = 'DP08 - South Golf';
    document.getElementById('view-projects-hub').classList.add('hidden');
    document.getElementById('view-project-workspace').classList.remove('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });

    try {
        const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}`);
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`HTTP ${res.status}: ${errText || res.statusText}`);
        }
        const data = await res.json();
        if (data.info && (data.info.project_id === 'MMS / Substation' || data.info.project_id === 'MMS')) {
            data.info.project_id = 'MMS';
        }
        activeProjectData = data;

        const info = data.info || {};
        const kpis = data.kpis || {};

        const pid = info.project_id || projectId;
        const kcode = (info.k_package_no || '').split('/')[0].trim();

        // Update Top Header
        document.getElementById('proj-header-title').innerText = info.project_title || info.project_name || pid;
        document.getElementById('proj-header-contractor').innerText = info.contractor_name || 'N/A';
        document.getElementById('proj-header-contract').innerText = info.contract_no || '-';
        document.getElementById('proj-header-kcode').innerText = kcode || pid;

        const catEl = document.getElementById('proj-badge-category');
        if (catEl) catEl.innerText = info.category || 'Package';

        // Update Sidebar Active Widget
        const sideWidget = document.getElementById('sidebar-active-project-widget');
        if (sideWidget) {
            sideWidget.classList.remove('hidden');
            document.getElementById('sidebar-active-pkg-title').innerText = info.project_title || pid;
            document.getElementById('sidebar-active-pkg-code').innerText = (kcode && kcode !== pid) ? `${pid} • ${kcode}` : pid;
            document.getElementById('sidebar-active-pkg-contractor').innerText = info.contractor_name || 'PMC / Consultant';
        }

        // Update KPI Counters
        const setTxt = (id, v) => { const el = document.getElementById(id); if (el) el.innerText = Number(v || 0).toLocaleString(); };
        setTxt('proj-kpi-letters', kpis.total_letters);
        setTxt('subtab-count-letters', kpis.total_letters);

        setTxt('proj-kpi-rfis', kpis.total_rfis);
        setTxt('subtab-count-rfis', kpis.total_rfis);
        const isDp01 = (info.project_id === 'DP01');
        const rfiTitle = document.getElementById('subtab-title-rfis');
        if (rfiTitle) {
            rfiTitle.textContent = isDp01 ? 'Site Clarifications (SCR)' : 'RFIs';
        }
        const kpiTitle = document.getElementById('proj-kpi-rfi-title');
        if (kpiTitle) {
            kpiTitle.textContent = isDp01 ? 'Site Clarifications (SCR)' : 'RFIs';
        }
        const kpiDesc = document.getElementById('proj-kpi-rfi-desc');
        if (kpiDesc) {
            kpiDesc.textContent = isDp01 ? 'Site Clarifications (0 RFIs)' : 'Technical Queries';
        }
        const rfiSearchInput = document.getElementById('sub-rfis-search');
        if (rfiSearchInput) {
            rfiSearchInput.placeholder = isDp01 ? 'Search SCR subject, reference, or number...' : 'Search RFI subject or number...';
        }
        const rfiColNum = document.getElementById('sub-rfis-col-num');
        if (rfiColNum) {
            rfiColNum.innerText = isDp01 ? 'SCR No' : 'RFI No';
        }

        setTxt('proj-kpi-shopdrw', kpis.total_shop_drawings);
        setTxt('subtab-count-shop_drawings', kpis.total_shop_drawings);

        setTxt('proj-kpi-mat', kpis.total_material_submittals);
        setTxt('subtab-count-material_submittals', kpis.total_material_submittals);

        setTxt('proj-kpi-workflows', kpis.total_workflows);
        setTxt('subtab-count-workflows', kpis.total_workflows);
        setTxt('subtab-count-transmittals', kpis.total_transmittals);

        const otherTotal = (kpis.total_other_docs || 0) + (kpis.total_other_mails || 0);
        setTxt('proj-kpi-other', otherTotal);
        setTxt('subtab-count-other_mail', kpis.total_other_mails);
        setTxt('subtab-count-other_docs', kpis.total_other_docs);

        // Populate Letters Sender Dropdown
        const lettersFromSelect = document.getElementById('sub-letters-from-org');
        if (lettersFromSelect) {
            lettersFromSelect.innerHTML = '<option value="">All Senders (From Org)</option>';
            (data.letter_from_orgs || []).forEach(org => {
                lettersFromSelect.innerHTML += `<option value="${org}">${org}</option>`;
            });
        }

        // Populate RFIs From and To Orgs Dropdowns
        const rfiFromSelect = document.getElementById('sub-rfis-from-org');
        if (rfiFromSelect) {
            rfiFromSelect.innerHTML = '<option value="">From: All Orgs</option>';
            (data.rfi_from_orgs || []).forEach(org => {
                if (org && typeof org === 'string' && org.trim()) {
                    const cleanOrg = org.trim();
                    rfiFromSelect.innerHTML += `<option value="${escapeHtml(cleanOrg)}" title="${escapeHtml(cleanOrg)}">${escapeHtml(cleanOrg)}</option>`;
                }
            });
        }

        const rfiToSelect = document.getElementById('sub-rfis-to-org');
        if (rfiToSelect) {
            rfiToSelect.innerHTML = '<option value="">To: All Orgs</option>';
            (data.rfi_to_orgs || []).forEach(org => {
                if (org && typeof org === 'string' && org.trim()) {
                    const cleanOrg = org.trim();
                    rfiToSelect.innerHTML += `<option value="${escapeHtml(cleanOrg)}" title="${escapeHtml(cleanOrg)}">${escapeHtml(cleanOrg)}</option>`;
                }
            });
        }

        // Populate Discipline Dropdowns (Clean names without misleading project-wide static counts)
        ['shopdrw', 'mat', 'otherdocs'].forEach(prefix => {
            const el = document.getElementById(`sub-${prefix}-discipline`);
            if (el) {
                el.innerHTML = '<option value="">All Disciplines</option>';
                (data.disciplines || []).forEach(d => {
                    el.innerHTML += `<option value="${d.name}">${d.name}</option>`;
                });
            }
        });

        // Populate Status Dropdowns (Clean names without misleading project-wide static counts)
        ['shopdrw', 'mat', 'otherdocs'].forEach(prefix => {
            const el = document.getElementById(`sub-${prefix}-status`);
            if (el) {
                el.innerHTML = '<option value="">All Status</option>';
                (data.doc_statuses || []).forEach(s => {
                    el.innerHTML += `<option value="${s.name}">${s.name}</option>`;
                });
            }
        });

        // Populate Other Mail Types (Clean names without static counts)
        const otherMailSelect = document.getElementById('sub-othermail-type');
        if (otherMailSelect) {
            otherMailSelect.innerHTML = '<option value="">All Other Mail Types</option>';
            (data.other_mail_types || []).forEach(m => {
                otherMailSelect.innerHTML += `<option value="${m.name}">${m.name}</option>`;
            });
        }

        // Populate Other Doc Types (Clean names without static counts)
        const otherDocsSelect = document.getElementById('sub-otherdocs-type');
        if (otherDocsSelect) {
            otherDocsSelect.innerHTML = '<option value="">All Other Doc Types</option>';
            (data.other_doc_types || []).forEach(t => {
                otherDocsSelect.innerHTML += `<option value="${t.name}">${t.name}</option>`;
            });
        }

        // Reset Sorts & Default to Letters
        Object.keys(sortStates).forEach(k => clearTableSort(k, false));
        setProjectSubTab('letters');
    } catch (err) {
        console.error('Error opening workspace:', err);
        alert('Error loading workspace: ' + err.message);
    }
}

function closeProjectWorkspace() {
    activeProjectData = null;
    document.getElementById('view-project-workspace').classList.add('hidden');
    document.getElementById('view-projects-hub').classList.remove('hidden');
    const sideWidget = document.getElementById('sidebar-active-project-widget');
    if (sideWidget) sideWidget.classList.add('hidden');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function setProjectSubTab(tab) {
    currentSubTab = tab;
    const tabs = ['letters', 'rfis', 'workflows', 'transmittals', 'other_mail', 'shop_drawings', 'material_submittals', 'other_docs'];
    tabs.forEach(t => {
        const btn = document.getElementById(`subtab-btn-${t}`);
        const panel = document.getElementById(`subpanel-${t}`);
        if (t === tab) {
            if (btn) btn.className = 'subtab-btn w-full px-3.5 py-2.5 rounded-xl text-xs font-bold bg-sky-600 text-white flex items-center justify-between gap-2 shadow-sm transition';
            if (panel) panel.classList.remove('hidden');
        } else {
            if (btn) btn.className = 'subtab-btn w-full px-3.5 py-2.5 rounded-xl text-xs font-semibold bg-slate-900 text-slate-300 hover:bg-slate-800 border border-slate-800 flex items-center justify-between gap-2 transition';
            if (panel) panel.classList.add('hidden');
        }
    });

    updateLegendStrip();

    if (tab === 'letters') loadProjectLetters(1);
    else if (tab === 'hill_ssc') loadProjectHillSsc(1);
    else if (tab === 'rfis') loadProjectRFIs(1);
    else if (tab === 'shop_drawings') loadProjectShopDrawings(1);
    else if (tab === 'material_submittals') loadProjectMaterials(1);
    else if (tab === 'workflows') loadProjectWorkflows(1);
    else if (tab === 'transmittals') loadProjectTransmittals(1);
    else if (tab === 'other_mail') loadProjectOtherMail(1);
    else if (tab === 'other_docs') loadProjectOtherDocs(1);
}

// ==========================================
// 3. DELIVERABLES DATA LOADERS
// ==========================================

// 1. Letters Fetch
async function loadProjectLetters(page = 1) {
    if (!activeProjectData) return;
    pageStates.letters = page;
    let pid = activeProjectData.info?.project_id || '';
    if (pid === 'MMS / Substation') pid = 'MMS';
    const search = document.getElementById('sub-letters-search')?.value || '';
    const direction = document.getElementById('sub-letters-direction')?.value || '';
    const fromOrg = document.getElementById('sub-letters-from-org')?.value || '';
    const overdue = document.getElementById('sub-letters-overdue')?.checked;
    const limit = parseInt(document.getElementById('sub-letters-limit')?.value || '50');

    const tbody = document.getElementById('sub-letters-tbody');
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-slate-400">Loading letters...</td></tr>';

    try {
        const offset = (page - 1) * limit;
        const fromDateVal = document.getElementById('sub-letters-from-date')?.value || '';
        const toDateVal = document.getElementById('sub-letters-to-date')?.value || '';

        let url = `/api/projects/${encodeURIComponent(pid)}/correspondence?category=letters&limit=${limit}&offset=${offset}${buildSortQueryString('letters')}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (direction) url += `&direction=${encodeURIComponent(direction)}`;
        if (fromOrg) url += `&from_org=${encodeURIComponent(fromOrg)}`;
        if (overdue) url += `&is_overdue=true`;
        if (fromDateVal) url += `&from_date=${encodeURIComponent(fromDateVal)}`;
        if (toDateVal) url += `&to_date=${encodeURIComponent(toDateVal)}`;

        const res = await fetch(url);
        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || `Server returned HTTP ${res.status}`);
        }
        const data = await res.json();
        const records = Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []);
        const total = typeof data.total === 'number' ? data.total : records.length;
        totalCounts.letters = total;

        updatePaginationUI('letters', page, limit, total, records.length);

        if (records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-slate-500">No letters match filters</td></tr>';
            return;
        }

        const wrap = textWrapModes.letters;
        const textCls = wrap ? 'whitespace-normal break-words leading-relaxed' : 'truncate';

        let html = '';
        records.forEach(m => {
            const aconexUrl = getAconexMailUrl(m);
            const overdueBadge = m.is_overdue ? `<span class="text-rose-400 font-bold font-mono text-[10px] whitespace-nowrap">${m.days_late}d late</span>` : `<span class="text-slate-500 font-mono text-[10px]">0d</span>`;
            const tintClass = getRowTintClass('letters', m);

            html += `
                <tr class="hover:bg-slate-800/40 transition ${tintClass}">
                    <td class="p-2.5 overflow-hidden">
                        <div class="flex items-center justify-between gap-1.5">
                            <a href="${aconexUrl}" target="_blank" class="font-mono font-bold text-sky-400 hover:underline truncate">
                                ${m.mail_no}
                            </a>
                            <button onclick="openLetterThreadModal('${m.mail_no}', '${m.ref_no || ''}')" title="Explore Letter Thread" class="px-1.5 py-0.5 rounded bg-indigo-500/10 hover:bg-indigo-500 text-indigo-400 hover:text-white border border-indigo-500/20 text-[10px] font-bold flex-shrink-0">
                                Thread
                            </button>
                        </div>
                    </td>
                    <td class="p-2.5 text-slate-300 truncate">${m.type || 'Letter'}</td>
                    <td class="p-2.5 font-medium text-slate-200 overflow-hidden ${textCls}">${m.subject || '-'}</td>
                    <td class="p-2.5 font-mono text-slate-400 text-[11px] truncate">${m.ref_no || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${m.from_org || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${m.to_org || '-'}</td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(m.sent_date)}</td>
                    <td class="p-2.5 overflow-hidden">${overdueBadge}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-rose-400">Error: ${err.message}</td></tr>`;
    }
}

// 1.1 Hill & SSC Letters Fetch
async function loadProjectHillSsc(page = 1) {
    if (!activeProjectData) return;
    pageStates.hill_ssc = page;
    let pid = activeProjectData.info?.project_id || '';
    if (pid === 'MMS / Substation') pid = 'MMS';
    const search = document.getElementById('sub-hill_ssc-search')?.value || '';
    const direction = document.getElementById('sub-hill_ssc-direction')?.value || '';
    const overdue = document.getElementById('sub-hill_ssc-overdue')?.checked;
    const limit = parseInt(document.getElementById('sub-hill_ssc-limit')?.value || '50');

    const tbody = document.getElementById('sub-hill_ssc-tbody');
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-slate-400">Loading Hill &amp; SSC letters...</td></tr>';

    try {
        const offset = (page - 1) * limit;
        let url = `/api/projects/${encodeURIComponent(pid)}/hill_ssc?limit=${limit}&offset=${offset}${buildSortQueryString('hill_ssc')}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (direction) url += `&direction=${encodeURIComponent(direction)}`;
        if (overdue) url += `&is_overdue=true`;

        const res = await fetch(url);
        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || `Server returned HTTP ${res.status}`);
        }
        const data = await res.json();
        const records = Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []);
        const total = typeof data.total === 'number' ? data.total : records.length;
        totalCounts.hill_ssc = total;

        updatePaginationUI('hill_ssc', page, limit, total, records.length);

        if (records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-slate-500">No Hill &amp; SSC letters match filters</td></tr>';
            return;
        }

        const wrap = textWrapModes.hill_ssc;
        const textCls = wrap ? 'whitespace-normal break-words leading-relaxed' : 'truncate';

        let html = '';
        records.forEach(m => {
            const aconexUrl = getAconexMailUrl(m);
            const isOut = (m.direction || '').includes('Outbound');
            const dirBadge = isOut 
                ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">Outbound (To Shaker/ECG)</span>`
                : `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/10 text-purple-300 border border-purple-500/20">Inbound (From Shaker/ECG)</span>`;
            const tintClass = getRowTintClass('letters', m);

            html += `
                <tr class="hover:bg-slate-800/40 transition ${tintClass}">
                    <td class="p-2.5 overflow-hidden">
                        <div class="flex items-center justify-between gap-1.5">
                            <a href="${aconexUrl}" target="_blank" class="font-mono font-bold text-sky-400 hover:underline truncate">
                                ${m.mail_no}
                            </a>
                            <button onclick="openLetterThreadModal('${m.mail_no}', '${m.ref_no || ''}')" title="Explore Letter Thread" class="px-1.5 py-0.5 rounded bg-indigo-500/10 hover:bg-indigo-500 text-indigo-400 hover:text-white border border-indigo-500/20 text-[10px] font-bold flex-shrink-0">
                                Thread
                            </button>
                        </div>
                    </td>
                    <td class="p-2.5 overflow-hidden">${dirBadge}</td>
                    <td class="p-2.5 font-medium text-slate-200 overflow-hidden ${textCls}">${m.subject || '-'}</td>
                    <td class="p-2.5 font-mono text-slate-400 text-[11px] truncate">${m.ref_no || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${m.from_name ? `${m.from_name} (${m.from_org})` : (m.from_org || '-')}</td>
                    <td class="p-2.5 text-slate-300 truncate">${m.to_org || '-'}</td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(m.sent_date)}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-rose-400">Error: ${err.message}</td></tr>`;
    }
}

// 2. RFIs & Site Clarifications Fetch
function getRfiStatusBadge(status, isOverdue) {
    const st = (status || '').trim();
    if (isOverdue || st === 'Overdue') {
        return `<span class="px-2 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-400 border border-rose-500/30 font-bold animate-pulse">Overdue</span>`;
    }
    switch (st) {
        case 'Responded':
            return `<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-semibold">Responded</span>`;
        case 'Closed-Out':
            return `<span class="px-2 py-0.5 rounded text-[10px] bg-teal-500/20 text-teal-400 border border-teal-500/30 font-semibold">Closed-Out</span>`;
        case 'Outstanding':
        case 'Open':
            return `<span class="px-2 py-0.5 rounded text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 font-semibold">Outstanding</span>`;
        case 'No Action Required':
        case 'N/A':
            return `<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700">N/A</span>`;
        default:
            return `<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 border border-slate-700">${st || 'Closed'}</span>`;
    }
}

async function loadProjectRFIs(page = 1) {
    if (!activeProjectData) return;
    pageStates.rfis = page;
    let pid = activeProjectData.info?.project_id || '';
    if (pid === 'MMS / Substation') pid = 'MMS';
    const search = document.getElementById('sub-rfis-search')?.value || '';
    const status = document.getElementById('sub-rfis-status')?.value || '';
    const type = document.getElementById('sub-rfis-type')?.value || '';
    const fromOrg = document.getElementById('sub-rfis-from-org')?.value || '';
    const toOrg = document.getElementById('sub-rfis-to-org')?.value || '';
    const overdue = document.getElementById('sub-rfis-overdue')?.checked;
    const limit = parseInt(document.getElementById('sub-rfis-limit')?.value || '50');

    const tbody = document.getElementById('sub-rfis-tbody');
    tbody.innerHTML = '<tr><td colspan="9" class="text-center py-8 text-slate-400">Loading RFIs...</td></tr>';

    try {
        const offset = (page - 1) * limit;
        let url = `/api/projects/${encodeURIComponent(pid)}/rfis?limit=${limit}&offset=${offset}${buildSortQueryString('rfis')}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        if (type) url += `&mail_type=${encodeURIComponent(type)}`;
        if (fromOrg) url += `&from_org=${encodeURIComponent(fromOrg)}`;
        if (toOrg) url += `&to_org=${encodeURIComponent(toOrg)}`;
        if (overdue) url += `&is_overdue=true`;

        const res = await fetch(url);
        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || `Server returned HTTP ${res.status}`);
        }
        const data = await res.json();
        const records = Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []);
        const total = typeof data.total === 'number' ? data.total : records.length;
        totalCounts.rfis = total;

        // DP01 Tab header and label customization
        const rfiTitle = document.getElementById('subtab-title-rfis');
        if (rfiTitle) {
            rfiTitle.textContent = data.is_dp01_clarifications ? 'Site Clarifications (SCR)' : 'RFIs';
        }

        updatePaginationUI('rfis', page, limit, total, records.length);

        if (records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center py-8 text-slate-500">No items match filters</td></tr>';
            return;
        }

        const wrap = textWrapModes.rfis;
        const textCls = wrap ? 'whitespace-normal break-words leading-relaxed' : 'truncate';

        let html = '';
        records.forEach(r => {
            const aconexUrl = getAconexMailUrl(r);
            const statusBadge = getRfiStatusBadge(r.status, r.is_overdue);
            const overdueBadge = r.is_overdue ? `<span class="text-rose-400 font-bold font-mono text-[10px]">${r.days_late}d late</span>` : `<span class="text-slate-500 font-mono text-[10px]">0d</span>`;
            const tintClass = getRowTintClass('rfis', r);

            html += `
                <tr class="hover:bg-slate-800/40 transition ${tintClass}">
                    <td class="p-2.5 overflow-hidden">
                        <div class="flex items-center justify-between gap-1.5">
                            <a href="${aconexUrl}" target="_blank" class="font-mono font-bold text-sky-400 hover:underline truncate">
                                ${r.mail_no}
                            </a>
                            <button onclick="openRfiThreadModal('${r.mail_no}')" title="Explore Response Thread" class="px-1.5 py-0.5 rounded bg-amber-500/10 hover:bg-amber-500 text-amber-400 hover:text-slate-950 border border-amber-500/20 text-[10px] font-bold flex-shrink-0">
                                Thread
                            </button>
                        </div>
                    </td>
                    <td class="p-2.5 text-slate-400 truncate">${r.type || 'RFI'}</td>
                    <td class="p-2.5 font-medium text-slate-200 overflow-hidden ${textCls}">${r.subject || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${r.from_org || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${r.to_org || '-'}</td>
                    <td class="p-2.5 overflow-hidden">${statusBadge}</td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(r.sent_date)}</td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(r.due_date)}</td>
                    <td class="p-2.5 overflow-hidden">${overdueBadge}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-rose-400">Error: ${err.message}</td></tr>`;
    }
}

// 3. Shop Drawings Fetch
async function loadProjectShopDrawings(page = 1) {
    if (!activeProjectData) return;
    pageStates.shop_drawings = page;
    let pid = activeProjectData.info?.project_id || '';
    if (pid === 'MMS / Substation') pid = 'MMS';
    const search = document.getElementById('sub-shopdrw-search')?.value || '';
    const disc = document.getElementById('sub-shopdrw-discipline')?.value || '';
    const status = document.getElementById('sub-shopdrw-status')?.value || '';
    const limit = parseInt(document.getElementById('sub-shopdrw-limit')?.value || '50');

    const tbody = document.getElementById('sub-shopdrw-tbody');
    tbody.innerHTML = '<tr><td colspan="6" class="text-center py-8 text-slate-400">Loading shop drawings...</td></tr>';

    try {
        const offset = (page - 1) * limit;
        let url = `/api/projects/${encodeURIComponent(pid)}/documents?category=shop_drawings&limit=${limit}&offset=${offset}${buildSortQueryString('shop_drawings')}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (disc) url += `&discipline=${encodeURIComponent(disc)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;

        const res = await fetch(url);
        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || `Server returned HTTP ${res.status}`);
        }
        const data = await res.json();
        const records = Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []);
        const total = typeof data.total === 'number' ? data.total : records.length;
        totalCounts.shop_drawings = total;

        updatePaginationUI('shop_drawings', page, limit, total, records.length);

        if (records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center py-8 text-slate-500">No shop drawings found</td></tr>';
            return;
        }

        const wrap = textWrapModes.shop_drawings;
        const textCls = wrap ? 'whitespace-normal break-words leading-relaxed' : 'truncate';

        let html = '';
        records.forEach(d => {
            const aconexUrl = getAconexDocUrl(d);
            const tintClass = getRowTintClass('shop_drawings', d);

            html += `
                <tr class="hover:bg-slate-800/40 transition ${tintClass}">
                    <td class="p-2.5 overflow-hidden">
                        <a href="${aconexUrl}" target="_blank" class="font-mono font-bold text-cyan-400 hover:underline truncate block">
                            ${d.document_no}
                        </a>
                    </td>
                    <td class="p-2.5 font-medium text-slate-200 overflow-hidden ${textCls}">${d.title || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${d.discipline || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${d.status || d.review_status || '-'}</td>
                    <td class="p-2.5 font-mono text-center text-slate-400">${d.revision || '-'}</td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(d.date_modified)}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-8 text-rose-400">Error: ${err.message}</td></tr>`;
    }
}

// 4. Material Submittals Fetch
async function loadProjectMaterials(page = 1) {
    if (!activeProjectData) return;
    pageStates.material_submittals = page;
    let pid = activeProjectData.info?.project_id || '';
    if (pid === 'MMS / Substation') pid = 'MMS';
    const search = document.getElementById('sub-mat-search')?.value || '';
    const disc = document.getElementById('sub-mat-discipline')?.value || '';
    const status = document.getElementById('sub-mat-status')?.value || '';
    const limit = parseInt(document.getElementById('sub-mat-limit')?.value || '50');

    const tbody = document.getElementById('sub-mat-tbody');
    tbody.innerHTML = '<tr><td colspan="6" class="text-center py-8 text-slate-400">Loading material submittals...</td></tr>';

    try {
        const offset = (page - 1) * limit;
        let url = `/api/projects/${encodeURIComponent(pid)}/documents?category=material_submittals&limit=${limit}&offset=${offset}${buildSortQueryString('material_submittals')}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (disc) url += `&discipline=${encodeURIComponent(disc)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;

        const res = await fetch(url);
        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || `Server returned HTTP ${res.status}`);
        }
        const data = await res.json();
        const records = Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []);
        const total = typeof data.total === 'number' ? data.total : records.length;
        totalCounts.material_submittals = total;

        updatePaginationUI('material_submittals', page, limit, total, records.length);

        if (records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center py-8 text-slate-500">No material submittals found</td></tr>';
            return;
        }

        const wrap = textWrapModes.material_submittals;
        const textCls = wrap ? 'whitespace-normal break-words leading-relaxed' : 'truncate';

        let html = '';
        records.forEach(d => {
            const aconexUrl = getAconexDocUrl(d);
            const tintClass = getRowTintClass('material_submittals', d);

            html += `
                <tr class="hover:bg-slate-800/40 transition ${tintClass}">
                    <td class="p-2.5 overflow-hidden">
                        <a href="${aconexUrl}" target="_blank" class="font-mono font-bold text-orange-400 hover:underline truncate block">
                            ${d.document_no}
                        </a>
                    </td>
                    <td class="p-2.5 font-medium text-slate-200 overflow-hidden ${textCls}">${d.title || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${d.discipline || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${d.status || d.review_status || '-'}</td>
                    <td class="p-2.5 font-mono text-center text-slate-400">${d.revision || '-'}</td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(d.date_modified)}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-8 text-rose-400">Error: ${err.message}</td></tr>`;
    }
}

// 5. Workflows Fetch (with Progress Bar & Step Tracker)
async function loadProjectWorkflows(page = 1) {
    if (!activeProjectData) return;
    pageStates.workflows = page;
    let pid = activeProjectData.info?.project_id || '';
    if (pid === 'MMS / Substation') pid = 'MMS';
    const search = document.getElementById('sub-wf-search')?.value || '';
    const status = document.getElementById('sub-wf-status')?.value || '';
    const overdue = document.getElementById('sub-wf-overdue')?.checked;
    const limit = parseInt(document.getElementById('sub-wf-limit')?.value || '50');

    const tbody = document.getElementById('sub-wf-tbody');
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-slate-400">Loading workflows...</td></tr>';

    try {
        const offset = (page - 1) * limit;
        let url = `/api/projects/${encodeURIComponent(pid)}/workflows?limit=${limit}&offset=${offset}${buildSortQueryString('workflows')}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        if (overdue) url += `&has_overdue=true`;

        const res = await fetch(url);
        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || `Server returned HTTP ${res.status}`);
        }
        const data = await res.json();
        const records = Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []);
        const total = typeof data.total === 'number' ? data.total : records.length;
        totalCounts.workflows = total;

        updatePaginationUI('workflows', page, limit, total, records.length);

        if (records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-slate-500">No workflows match filters</td></tr>';
            return;
        }

        const wrap = textWrapModes.workflows;
        const textCls = wrap ? 'whitespace-normal break-words leading-relaxed' : 'truncate';

        let html = '';
        records.forEach(w => {
            const aconexUrl = getAconexWorkflowUrl(w);
            const statusBadge = w.status === 'Active' ? `<span class="px-1.5 py-0.5 rounded text-[10px] bg-sky-500/20 text-sky-400 border border-sky-500/30 font-semibold">Review</span>` :
                                `<span class="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400">${w.status}</span>`;
            const overdueBadge = w.overdue_steps > 0 ? `<span class="px-1.5 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-400 font-bold whitespace-nowrap">${w.overdue_steps} Late</span>` : `<span class="text-emerald-400 text-[10px]">On Track</span>`;

            // Progress Calculations
            const totSteps = w.total_steps || 1;
            const compSteps = w.completed_steps || 0;
            const pct = w.pct_completed || Math.round((compSteps / totSteps) * 100);
            const remain = w.remaining_steps || Math.max(0, totSteps - compSteps);
            const curStepNo = Math.min(totSteps, compSteps + 1);

            // Build Aconex-style Sequential Chevron Step Pipeline
            let pipelineHtml = '';
            if (w.steps_pipeline && w.steps_pipeline.length > 0) {
                pipelineHtml = `<div class="flex items-center gap-1.5 flex-wrap">`;
                w.steps_pipeline.forEach((st, idx) => {
                    const isLast = idx === w.steps_pipeline.length - 1;
                    let badgeBg = '';
                    let iconHtml = '';
                    let statusLabel = '';
                    const durLabel = st.duration_days > 0 ? ` &bull; ${st.duration_days}d` : '';

                    if (st.step_status === 'Completed') {
                        badgeBg = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40';
                        iconHtml = '<span class="text-emerald-400 font-bold">✓</span>';
                        statusLabel = `Done${durLabel}`;
                    } else if (st.is_overdue || st.step_status === 'Overdue') {
                        badgeBg = 'bg-rose-500/25 text-rose-200 border-rose-500/50 font-bold ring-1 ring-rose-500/40';
                        iconHtml = '<span class="text-rose-300">⚠️</span>';
                        statusLabel = `Overdue (+${st.days_late}d late${durLabel})`;
                    } else if (st.step_status === 'Current') {
                        badgeBg = 'bg-sky-500/20 text-sky-200 border-sky-500/40 font-bold ring-1 ring-sky-500/30';
                        iconHtml = '<span class="text-sky-300">⏳</span>';
                        statusLabel = `Current${durLabel}`;
                    } else {
                        badgeBg = 'bg-slate-800/40 text-slate-400 border-slate-700/50';
                        iconHtml = '<span class="text-slate-500">○</span>';
                        statusLabel = 'Pending';
                    }

                    pipelineHtml += `
                        <div class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] border ${badgeBg}" title="${st.step_name} (${st.assigned_to_name || '-'})">
                            ${iconHtml}
                            <span class="font-semibold">${st.step_name}</span>
                            <span class="font-mono text-[9px] opacity-80">(${statusLabel})</span>
                        </div>
                    `;
                    if (!isLast) {
                        pipelineHtml += `<i data-lucide="arrow-right" class="w-3 h-3 text-slate-500 flex-shrink-0"></i>`;
                    }
                });
                pipelineHtml += `</div>`;
            } else {
                pipelineHtml = `<div class="text-[10px] text-slate-400">Step ${curStepNo} of ${totSteps} (${pct}%)</div>`;
            }

            const tintClass = getRowTintClass('workflows', w);

            html += `
                <tr class="hover:bg-slate-800/40 transition ${tintClass}">
                    <td class="p-2.5 overflow-hidden">
                        <a href="${aconexUrl}" target="_blank" class="font-mono font-bold text-sky-400 hover:underline truncate block">
                            ${w.workflow_no}
                        </a>
                    </td>
                    <td class="p-2.5 font-medium text-slate-200 overflow-hidden ${textCls}">${w.workflow_name || '-'}</td>
                    <td class="p-2.5 overflow-hidden">${statusBadge}</td>
                    <!-- Aconex-style Chevron Step Pipeline -->
                    <td class="p-2.5 overflow-hidden">
                        <div class="space-y-1.5">
                            <div class="flex items-center justify-between text-[10px] font-mono">
                                <span class="font-bold text-slate-300">Step ${curStepNo} of ${totSteps}</span>
                                <span class="font-black ${w.overdue_steps > 0 ? 'text-rose-400' : 'text-emerald-400'}">${pct}%</span>
                            </div>
                            ${pipelineHtml}
                        </div>
                    </td>
                    <!-- Current Step & Assignee -->
                    <td class="p-2.5 text-slate-300 overflow-hidden">
                        <div class="font-semibold text-white ${textCls}">${w.current_step || 'Review Step'}</div>
                        <div class="text-[10px] text-slate-400 truncate mt-0.5">
                            ${w.current_org || '-'} ${w.current_user ? '(' + w.current_user + ')' : ''}
                        </div>
                    </td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(w.start_date)}</td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(w.due_date)}</td>
                    <td class="p-2.5 overflow-hidden">${overdueBadge}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-rose-400">Error: ${err.message}</td></tr>`;
    }
}

// 6. Other Mail Fetch
async function loadProjectOtherMail(page = 1) {
    if (!activeProjectData) return;
    pageStates.other_mail = page;
    let pid = activeProjectData.info?.project_id || '';
    if (pid === 'MMS / Substation') pid = 'MMS';
    const search = document.getElementById('sub-othermail-search')?.value || '';
    const mailType = document.getElementById('sub-othermail-type')?.value || '';
    const overdue = document.getElementById('sub-othermail-overdue')?.checked;
    const limit = parseInt(document.getElementById('sub-othermail-limit')?.value || '50');

    const tbody = document.getElementById('sub-othermail-tbody');
    tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-slate-400">Loading other correspondence...</td></tr>';

    try {
        const offset = (page - 1) * limit;
        let url = `/api/projects/${encodeURIComponent(pid)}/correspondence?category=other_mail&limit=${limit}&offset=${offset}${buildSortQueryString('other_mail')}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (mailType) url += `&mail_type=${encodeURIComponent(mailType)}`;
        if (overdue) url += `&is_overdue=true`;

        const res = await fetch(url);
        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || `Server returned HTTP ${res.status}`);
        }
        const data = await res.json();
        const records = Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []);
        const total = typeof data.total === 'number' ? data.total : records.length;
        totalCounts.other_mail = total;

        updatePaginationUI('other_mail', page, limit, total, records.length);

        if (records.length === 0) {
            if (overdue) {
                tbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-slate-400">
                    <p class="font-semibold text-slate-300 mb-1">No overdue items found for this selection.</p>
                    <p class="text-xs text-slate-500 mb-3">All items of this type are currently on schedule.</p>
                    <button onclick="document.getElementById('sub-othermail-overdue').checked=false;loadProjectOtherMail(1);" class="px-3.5 py-1.5 bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded-lg text-xs font-bold border border-indigo-500/40 transition">
                        Show All Records (Include On-Schedule)
                    </button>
                </td></tr>`;
            } else {
                tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-slate-500">No records found</td></tr>';
            }
            return;
        }

        const wrap = textWrapModes.other_mail;
        const textCls = wrap ? 'whitespace-normal break-words leading-relaxed' : 'truncate';

        let html = '';
        records.forEach(m => {
            const aconexUrl = getAconexMailUrl(m);
            const tintClass = getRowTintClass('other_mail', m);

            html += `
                <tr class="hover:bg-slate-800/40 transition ${tintClass}">
                    <td class="p-2.5 overflow-hidden">
                        <a href="${aconexUrl}" target="_blank" class="font-mono font-bold text-indigo-400 hover:underline truncate block">
                            ${m.mail_no}
                        </a>
                    </td>
                    <td class="p-2.5 text-slate-300 truncate">${m.type || '-'}</td>
                    <td class="p-2.5 font-medium text-slate-200 overflow-hidden ${textCls}">${m.subject || '-'}</td>
                    <td class="p-2.5 font-mono text-slate-400 text-[11px] truncate">${m.ref_no || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${m.from_org || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${m.to_org || '-'}</td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(m.sent_date)}</td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(m.due_date)}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-rose-400">Error: ${err.message}</td></tr>`;
    }
}

// 7. Other Documents Fetch
async function loadProjectOtherDocs(page = 1) {
    if (!activeProjectData) return;
    pageStates.other_docs = page;
    let pid = activeProjectData.info?.project_id || '';
    if (pid === 'MMS / Substation') pid = 'MMS';
    const search = document.getElementById('sub-otherdocs-search')?.value || '';
    const docType = document.getElementById('sub-otherdocs-type')?.value || '';
    const disc = document.getElementById('sub-otherdocs-discipline')?.value || '';
    const status = document.getElementById('sub-otherdocs-status')?.value || '';
    const limit = parseInt(document.getElementById('sub-otherdocs-limit')?.value || '50');

    const tbody = document.getElementById('sub-otherdocs-tbody');
    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-slate-400">Loading other documents...</td></tr>';

    try {
        const offset = (page - 1) * limit;
        let url = `/api/projects/${encodeURIComponent(pid)}/documents?category=other_docs&limit=${limit}&offset=${offset}${buildSortQueryString('other_docs')}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (docType) url += `&doc_type=${encodeURIComponent(docType)}`;
        if (disc) url += `&discipline=${encodeURIComponent(disc)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;

        const res = await fetch(url);
        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || `Server returned HTTP ${res.status}`);
        }
        const data = await res.json();
        const records = Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []);
        const total = typeof data.total === 'number' ? data.total : records.length;
        totalCounts.other_docs = total;

        updatePaginationUI('other_docs', page, limit, total, records.length);

        if (records.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center py-8 text-slate-500">No other documents found</td></tr>';
            return;
        }

        const wrap = textWrapModes.other_docs;
        const textCls = wrap ? 'whitespace-normal break-words leading-relaxed' : 'truncate';

        let html = '';
        records.forEach(d => {
            const aconexUrl = getAconexDocUrl(d);
            const tintClass = getRowTintClass('other_docs', d);

            html += `
                <tr class="hover:bg-slate-800/40 transition ${tintClass}">
                    <td class="p-2.5 overflow-hidden">
                        <a href="${aconexUrl}" target="_blank" class="font-mono font-bold text-emerald-400 hover:underline truncate block">
                            ${d.document_no}
                        </a>
                    </td>
                    <td class="p-2.5 font-medium text-slate-200 overflow-hidden ${textCls}">${d.title || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${d.doc_type || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${d.discipline || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${d.status || d.review_status || '-'}</td>
                    <td class="p-2.5 font-mono text-center text-slate-400">${d.revision || '-'}</td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(d.date_modified)}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-8 text-rose-400">Error: ${err.message}</td></tr>`;
    }
}

// 8. Document Transmittals Fetch (Ingested from transmittal history by document.csv)
let transmittalsFilterOptionsLoaded = false;
async function loadProjectTransmittals(page = 1) {
    if (!activeProjectData) return;
    pageStates.transmittals = page;
    const pid = activeProjectData.info.project_id;
    const search = document.getElementById('sub-transmittals-search')?.value || '';
    const docType = document.getElementById('sub-transmittals-type')?.value || '';
    const disc = document.getElementById('sub-transmittals-discipline')?.value || '';
    const status = document.getElementById('sub-transmittals-status')?.value || '';
    const limit = parseInt(document.getElementById('sub-transmittals-limit')?.value || '50');

    const tbody = document.getElementById('sub-transmittals-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="9" class="text-center py-8 text-slate-400">Loading document transmittals...</td></tr>';

    try {
        const params = new URLSearchParams({
            page: page,
            limit: limit
        });
        if (search && search.trim()) params.append('search', search.trim());
        if (docType && docType !== 'all') params.append('doc_type', docType);
        if (disc && disc !== 'all') params.append('discipline', disc);
        if (status && status !== 'all') params.append('status', status);

        if (pid === 'MMS / Substation') pid = 'MMS';
        const res = await fetch(`/api/projects/${encodeURIComponent(pid)}/transmittals?${params.toString()}`);
        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || `Server returned HTTP ${res.status}`);
        }
        const data = await res.json();
        const records = Array.isArray(data.data) ? data.data : (Array.isArray(data) ? data : []);
        const total = typeof data.total === 'number' ? data.total : records.length;
        totalCounts.transmittals = total;

        updatePaginationUI('transmittals', page, limit, total, records.length);

        // Populate Filter Dropdowns dynamically
        if (data.filter_options) {
            const typeSel = document.getElementById('sub-transmittals-type');
            if (typeSel && typeSel.options.length <= 1 && data.filter_options.types) {
                const cur = typeSel.value;
                let html = '<option value="">All Document Types</option>';
                data.filter_options.types.forEach(t => { html += `<option value="${t}">${t}</option>`; });
                typeSel.innerHTML = html;
                if (cur) typeSel.value = cur;
            }
            const discSel = document.getElementById('sub-transmittals-discipline');
            if (discSel && discSel.options.length <= 1 && data.filter_options.disciplines) {
                const cur = discSel.value;
                let html = '<option value="">All Disciplines</option>';
                data.filter_options.disciplines.forEach(d => { html += `<option value="${d}">${d}</option>`; });
                discSel.innerHTML = html;
                if (cur) discSel.value = cur;
            }
            const statSel = document.getElementById('sub-transmittals-status');
            if (statSel && statSel.options.length <= 1 && data.filter_options.statuses) {
                const cur = statSel.value;
                let html = '<option value="">All Status</option>';
                data.filter_options.statuses.forEach(s => { html += `<option value="${s}">${s}</option>`; });
                statSel.innerHTML = html;
                if (cur) statSel.value = cur;
            }
        }

        if (data.data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center py-8 text-slate-500">No document transmittals found matching criteria.</td></tr>';
            return;
        }

        const wrap = textWrapModes.transmittals;
        const textCls = wrap ? 'whitespace-normal break-words leading-relaxed' : 'truncate';

        let html = '';
        data.data.forEach(d => {
            const aconexDocUrl = d.aconex_doc_url || getAconexDocUrl(d);
            const aconexTransUrl = d.aconex_transmittal_url;
            const statusUpper = (d.status || '').toUpperCase();
            let statusBadge = 'bg-slate-800 text-slate-300';
            if (statusUpper.includes('APPR') || statusUpper.includes('ISSUED')) statusBadge = 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
            else if (statusUpper.includes('REV') || statusUpper.includes('COMM')) statusBadge = 'bg-amber-500/20 text-amber-300 border border-amber-500/30';
            else if (statusUpper.includes('REJ')) statusBadge = 'bg-rose-500/20 text-rose-300 border border-rose-500/30';

            html += `
                <tr class="hover:bg-slate-800/40 transition">
                    <td class="p-2.5 overflow-hidden">
                        <a href="${aconexDocUrl}" target="_blank" class="font-mono font-bold text-emerald-400 hover:underline truncate block">
                            ${d.document_no || '-'}
                        </a>
                    </td>
                    <td class="p-2.5 font-medium text-slate-200 overflow-hidden ${textCls}">${d.title || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${d.type || '-'}</td>
                    <td class="p-2.5 text-slate-300 truncate">${d.discipline || '-'}</td>
                    <td class="p-2.5 text-center whitespace-nowrap">
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${statusBadge}">${d.status || '-'}</span>
                    </td>
                    <td class="p-2.5 font-mono text-center text-slate-400">${d.revision || '-'}</td>
                    <td class="p-2.5 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(d.date_modified)}</td>
                    <td class="p-2.5 overflow-hidden">
                        ${aconexTransUrl && d.transmittal_no !== 'N/A'
                            ? `<a href="${aconexTransUrl}" target="_blank" class="font-mono font-bold text-sky-400 hover:underline truncate block flex items-center gap-1 group">
                                 <span>${d.transmittal_no}</span>
                                 <i data-lucide="external-link" class="w-3 h-3 opacity-0 group-hover:opacity-100 transition text-sky-400"></i>
                               </a>`
                            : `<span class="font-mono text-slate-400 truncate block">${d.transmittal_no || '-'}</span>`}
                    </td>
                    <td class="p-2.5 text-slate-300 ${textCls}">
                        <div class="font-semibold text-slate-200 text-xs">${d.transmitted_to_org || d.transmittal_in_from_org || '-'}</div>
                        <div class="text-[10px] text-slate-400 truncate">${d.transmitted_recipients || '-'}</div>
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-8 text-rose-400">Error: ${err.message}</td></tr>`;
    }
}

function exportProjectTransmittalsExcel() {
    if (!activeProjectData) return;
    const pid = activeProjectData.info.project_id;
    const search = document.getElementById('sub-transmittals-search')?.value || '';
    const docType = document.getElementById('sub-transmittals-type')?.value || '';
    const disc = document.getElementById('sub-transmittals-discipline')?.value || '';
    const status = document.getElementById('sub-transmittals-status')?.value || '';

    const params = new URLSearchParams();
    if (search && search.trim()) params.append('search', search.trim());
    if (docType && docType !== 'all') params.append('doc_type', docType);
    if (disc && disc !== 'all') params.append('discipline', disc);
    if (status && status !== 'all') params.append('status', status);

    window.open(`/api/projects/${encodeURIComponent(pid)}/transmittals/export?${params.toString()}`, '_blank');
}

// ==========================================
// 4. VISUAL LEGEND & ROW COLOR TINTING
// ==========================================
function onColorModeChanged(mode) {
    currentColorMode = mode;
    updateLegendStrip();
    reloadCurrentSubTab();
}

function filterByTypePill(category, typeName) {
    if (category === 'other_mail') {
        const sel = document.getElementById('sub-othermail-type');
        if (sel) {
            sel.value = typeName;
            const overdueChk = document.getElementById('sub-othermail-overdue');
            if (overdueChk) overdueChk.checked = false;
            loadProjectOtherMail(1);
            updateLegendStrip();
        }
    } else if (category === 'other_docs') {
        const sel = document.getElementById('sub-otherdocs-type');
        if (sel) {
            sel.value = typeName;
            loadProjectOtherDocs(1);
            updateLegendStrip();
        }
    }
}

function updateLegendStrip() {
    const strip = document.getElementById('visual-legend-strip');
    if (!strip) return;

    // Interactive type pill legend for Other Mail
    if (currentSubTab === 'other_mail' && activeProjectData && activeProjectData.other_mail_types && activeProjectData.other_mail_types.length > 0) {
        const curSelected = document.getElementById('sub-othermail-type')?.value || '';
        let pills = `<span class="text-slate-400 font-semibold mr-1">Filter Type:</span>`;
        pills += `<button onclick="filterByTypePill('other_mail', '')" class="px-2 py-0.5 rounded text-[10px] font-bold ${curSelected === '' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'} border border-slate-700 transition">All Types</button>`;
        activeProjectData.other_mail_types.slice(0, 10).forEach(t => {
            const isSel = curSelected === t.name;
            const safeName = t.name.replace(/'/g, "\\'");
            pills += `<button onclick="filterByTypePill('other_mail', '${safeName}')" class="px-2 py-0.5 rounded text-[10px] font-bold ${isSel ? 'bg-indigo-600 text-white border-indigo-400' : 'bg-indigo-500/10 text-indigo-300 hover:bg-indigo-500/20 border-indigo-500/30'} border transition" title="${t.name}">
                ${t.name} <span class="opacity-70 font-mono text-[9px]">(${t.count})</span>
            </button>`;
        });
        strip.innerHTML = pills;
        return;
    }

    // Interactive type pill legend for Other Documents
    if (currentSubTab === 'other_docs' && activeProjectData && activeProjectData.other_doc_types && activeProjectData.other_doc_types.length > 0) {
        const curSelected = document.getElementById('sub-otherdocs-type')?.value || '';
        let pills = `<span class="text-slate-400 font-semibold mr-1">Filter Type:</span>`;
        pills += `<button onclick="filterByTypePill('other_docs', '')" class="px-2 py-0.5 rounded text-[10px] font-bold ${curSelected === '' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'} border border-slate-700 transition">All Types</button>`;
        activeProjectData.other_doc_types.slice(0, 10).forEach(t => {
            const isSel = curSelected === t.name;
            const safeName = t.name.replace(/'/g, "\\'");
            pills += `<button onclick="filterByTypePill('other_docs', '${safeName}')" class="px-2 py-0.5 rounded text-[10px] font-bold ${isSel ? 'bg-emerald-600 text-white border-emerald-400' : 'bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 border-emerald-500/30'} border transition" title="${t.name}">
                ${t.name} <span class="opacity-70 font-mono text-[9px]">(${t.count})</span>
            </button>`;
        });
        strip.innerHTML = pills;
        return;
    }

    if (currentColorMode === 'none') {
        strip.innerHTML = '<span class="text-slate-500 italic">Default clean styling. Select color mode to highlight rows.</span>';
        return;
    }

    if (currentColorMode === 'discipline') {
        strip.innerHTML = `
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">Architecture</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-400 border border-sky-500/30">Structure</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">Mechanical</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">Electrical</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-teal-500/20 text-teal-400 border border-teal-500/30">Plumbing</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Civil / Infra</span>
        `;
    } else if (currentColorMode === 'type') {
        strip.innerHTML = `
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/30">Shop Drawing</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30">Material Submittal</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">Letter</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30">RFI</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Transmittal</span>
        `;
    } else if (currentColorMode === 'status') {
        strip.innerHTML = `
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Approved / Closed</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-400 border border-sky-500/30">In Review / Open</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/30">Revise / Rejected</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-red-600/30 text-red-400 border border-red-500/40">Overdue</span>
        `;
    }
}

function getRowTintClass(tab, item) {
    if (currentColorMode === 'none') return '';

    if (currentColorMode === 'discipline') {
        const disc = (item.discipline || item.discipline_name || '').toLowerCase();
        if (disc.includes('arch')) return 'tint-arch';
        if (disc.includes('struct')) return 'tint-struct';
        if (disc.includes('mech') || disc.includes('hvac')) return 'tint-mech';
        if (disc.includes('elec')) return 'tint-elec';
        if (disc.includes('plumb') || disc.includes('pip')) return 'tint-plumb';
        if (disc.includes('civil') || disc.includes('infra') || disc.includes('road')) return 'tint-civil';
        return 'tint-pmc';
    }

    if (currentColorMode === 'type') {
        const typeStr = (item.doc_type || item.type || item.mail_type || tab).toLowerCase();
        if (typeStr.includes('shop') || typeStr.includes('draw')) return 'tint-shopdrw';
        if (typeStr.includes('mat')) return 'tint-mat';
        if (typeStr.includes('letter')) return 'tint-letter';
        if (typeStr.includes('rfi') || typeStr.includes('clarif')) return 'tint-rfi';
        if (typeStr.includes('transmittal')) return 'tint-transmittal';
        if (typeStr.includes('inspect') || typeStr.includes('wir')) return 'tint-civil';
        if (typeStr.includes('model') || typeStr.includes('bim')) return 'tint-struct';
        if (typeStr.includes('report') || typeStr.includes('calc')) return 'tint-mech';
        if (typeStr.includes('ncr') || typeStr.includes('notice')) return 'tint-rejected';
        return '';
    }

    if (currentColorMode === 'status') {
        if (item.is_overdue || (item.overdue_steps && item.overdue_steps > 0)) return 'tint-overdue';
        const st = (item.status || item.review_status || item.current_step_status || '').toLowerCase();
        if (st.includes('approved') || st.includes('closed') || st.includes('completed') || st.includes('code a')) return 'tint-approved';
        if (st.includes('review') || st.includes('open') || st.includes('active') || st.includes('current') || st.includes('code b')) return 'tint-review';
        if (st.includes('revise') || st.includes('rejected') || st.includes('code c') || st.includes('code d')) return 'tint-rejected';
        return '';
    }

    return '';
}

function reloadCurrentSubTab() {
    if (currentSubTab === 'letters') loadProjectLetters(pageStates.letters);
    else if (currentSubTab === 'hill_ssc') loadProjectHillSsc(pageStates.hill_ssc);
    else if (currentSubTab === 'rfis') loadProjectRFIs(pageStates.rfis);
    else if (currentSubTab === 'shop_drawings') loadProjectShopDrawings(pageStates.shop_drawings);
    else if (currentSubTab === 'material_submittals') loadProjectMaterials(pageStates.material_submittals);
    else if (currentSubTab === 'workflows') loadProjectWorkflows(pageStates.workflows);
    else if (currentSubTab === 'transmittals') loadProjectTransmittals(pageStates.transmittals);
    else if (currentSubTab === 'other_mail') loadProjectOtherMail(pageStates.other_mail);
    else if (currentSubTab === 'other_docs') loadProjectOtherDocs(pageStates.other_docs);
}

// ==========================================
// 5. SORTING & PAGINATION HELPERS
// ==========================================
function handleColumnSort(tableKey, colKey, event) {
    const isMulti = Boolean(event && (event.ctrlKey || event.metaKey));
    const currentList = sortStates[tableKey];
    const existingIdx = currentList.findIndex(s => s.col === colKey);

    if (isMulti) {
        if (existingIdx !== -1) {
            if (currentList[existingIdx].dir === 'ASC') {
                currentList[existingIdx].dir = 'DESC';
            } else {
                currentList.splice(existingIdx, 1);
            }
        } else {
            currentList.push({ col: colKey, dir: 'ASC' });
        }
    } else {
        if (existingIdx !== -1 && currentList.length === 1) {
            if (currentList[0].dir === 'ASC') {
                sortStates[tableKey] = [{ col: colKey, dir: 'DESC' }];
            } else {
                sortStates[tableKey] = [];
            }
        } else {
            sortStates[tableKey] = [{ col: colKey, dir: 'ASC' }];
        }
    }

    renderSortBadges(tableKey);
    reloadCurrentSubTab();
}

function clearTableSort(tableKey, reload = true) {
    sortStates[tableKey] = [];
    renderSortBadges(tableKey);
    if (reload) reloadCurrentSubTab();
}

function renderSortBadges(tableKey) {
    const container = document.getElementById(`sort-indicators-${tableKey}`);
    const clearBtn = document.getElementById(`clear-sort-${tableKey}-btn`);
    const currentList = sortStates[tableKey] || [];

    // Keep the toolbar clean! Only show a sleek Reset Sort button when sorting is active
    if (container) {
        container.innerHTML = '';
    }
    if (clearBtn) {
        if (currentList.length > 0) clearBtn.classList.remove('hidden');
        else clearBtn.classList.add('hidden');
    }

    // Render sort indicator badges DIRECTLY on the <th> headers of the table
    const table = document.getElementById(`table-${tableKey}`);
    if (table) {
        const ths = table.querySelectorAll('thead th');
        ths.forEach(th => {
            const badge = th.querySelector('.sort-badge');
            const colKey = th.getAttribute('onclick')?.match(/'([^']+)',\s*event/)?.[1] || '';
            const sortEntry = currentList.find(s => s.col === colKey);
            if (!badge) return;
            if (!sortEntry) {
                badge.innerHTML = '';
                th.classList.remove('text-amber-400', 'bg-slate-800/60');
            } else {
                const arrow = sortEntry.dir === 'ASC' ? '▲' : '▼';
                if (currentList.length > 1) {
                    const level = currentList.indexOf(sortEntry) + 1;
                    badge.innerHTML = `<span class="px-1 py-0.2 rounded bg-amber-500/20 text-amber-300 font-mono text-[9px]">${arrow} ${level}</span>`;
                } else {
                    badge.innerHTML = `<span class="text-amber-400 font-mono text-[10px]">${arrow}</span>`;
                }
                th.classList.add('text-amber-400');
            }
        });
    }
}

function buildSortQueryString(tableKey) {
    const list = sortStates[tableKey];
    if (!list || list.length === 0) return '';
    const clause = list.map(s => `${s.col} ${s.dir}`).join(',');
    return `&sort=${encodeURIComponent(clause)}`;
}

function toggleTextWrap(tableKey) {
    const toggle = document.getElementById(`wrap-${tableKey}-toggle`);
    if (toggle) textWrapModes[tableKey] = toggle.checked;
    reloadCurrentSubTab();
}

function updatePaginationUI(tableKey, page, limit, total, currentCount) {
    const prefix = (tableKey === 'shop_drawings' ? 'shopdrw' : (tableKey === 'material_submittals' ? 'mat' : (tableKey === 'other_mail' ? 'othermail' : (tableKey === 'other_docs' ? 'otherdocs' : (tableKey === 'workflows' ? 'wf' : tableKey)))));
    const infoEl = document.getElementById(`sub-${prefix}-pagination-info`);
    const prevBtn = document.getElementById(`sub-${prefix}-prev-btn`);
    const nextBtn = document.getElementById(`sub-${prefix}-next-btn`);
    const pageIndicator = document.getElementById(`sub-${prefix}-page-indicator`);

    const prevBtnTop = document.getElementById(`sub-${prefix}-prev-btn-top`);
    const nextBtnTop = document.getElementById(`sub-${prefix}-next-btn-top`);
    const pageIndicatorTop = document.getElementById(`sub-${prefix}-page-indicator-top`);

    const safeTotal = Number(total || 0);
    const safeCount = Number(currentCount || 0);
    const totalPages = Math.ceil(safeTotal / limit) || 1;
    const start = safeTotal === 0 ? 0 : (page - 1) * limit + 1;
    const end = (page - 1) * limit + safeCount;

    const infoText = safeTotal === 0 ? 'Showing 0 of 0' : `Showing ${start.toLocaleString()} - ${end.toLocaleString()} of ${safeTotal.toLocaleString()}`;
    const pageText = `Page ${page} of ${totalPages}`;

    const infoElBottom = document.getElementById(`sub-${prefix}-pagination-info-bottom`);
    if (infoEl) infoEl.innerText = infoText;
    if (infoElBottom) infoElBottom.innerText = infoText;
    if (pageIndicator) pageIndicator.innerText = pageText;
    if (pageIndicatorTop) pageIndicatorTop.innerText = pageText;

    const isPrevDisabled = page <= 1;
    const isNextDisabled = page >= totalPages;

    if (prevBtn) prevBtn.disabled = isPrevDisabled;
    if (prevBtnTop) prevBtnTop.disabled = isPrevDisabled;
    if (nextBtn) nextBtn.disabled = isNextDisabled;
    if (nextBtnTop) nextBtnTop.disabled = isNextDisabled;
}

function nextPage(tableKey) {
    const cur = pageStates[tableKey] || 1;
    const prefix = (tableKey === 'shop_drawings' ? 'shopdrw' : (tableKey === 'material_submittals' ? 'mat' : (tableKey === 'other_mail' ? 'othermail' : (tableKey === 'other_docs' ? 'otherdocs' : (tableKey === 'workflows' ? 'wf' : tableKey)))));
    const limit = parseInt(document.getElementById(`sub-${prefix}-limit`)?.value || '50');
    const total = totalCounts[tableKey] || 0;
    const totalPages = Math.ceil(total / limit) || 1;

    if (cur < totalPages) {
        if (tableKey === 'letters') loadProjectLetters(cur + 1);
        else if (tableKey === 'hill_ssc') loadProjectHillSsc(cur + 1);
        else if (tableKey === 'rfis') loadProjectRFIs(cur + 1);
        else if (tableKey === 'shop_drawings') loadProjectShopDrawings(cur + 1);
        else if (tableKey === 'material_submittals') loadProjectMaterials(cur + 1);
        else if (tableKey === 'workflows') loadProjectWorkflows(cur + 1);
        else if (tableKey === 'transmittals') loadProjectTransmittals(cur + 1);
        else if (tableKey === 'other_mail') loadProjectOtherMail(cur + 1);
        else if (tableKey === 'other_docs') loadProjectOtherDocs(cur + 1);
    }
}

function prevPage(tableKey) {
    const cur = pageStates[tableKey] || 1;
    if (cur > 1) {
        if (tableKey === 'letters') loadProjectLetters(cur - 1);
        else if (tableKey === 'hill_ssc') loadProjectHillSsc(cur - 1);
        else if (tableKey === 'rfis') loadProjectRFIs(cur - 1);
        else if (tableKey === 'shop_drawings') loadProjectShopDrawings(cur - 1);
        else if (tableKey === 'material_submittals') loadProjectMaterials(cur - 1);
        else if (tableKey === 'workflows') loadProjectWorkflows(cur - 1);
        else if (tableKey === 'transmittals') loadProjectTransmittals(cur - 1);
        else if (tableKey === 'other_mail') loadProjectOtherMail(cur - 1);
        else if (tableKey === 'other_docs') loadProjectOtherDocs(cur - 1);
    }
}

function changeLimit(tableKey) {
    if (tableKey === 'letters') loadProjectLetters(1);
    else if (tableKey === 'hill_ssc') loadProjectHillSsc(1);
    else if (tableKey === 'rfis') loadProjectRFIs(1);
    else if (tableKey === 'shop_drawings') loadProjectShopDrawings(1);
    else if (tableKey === 'material_submittals') loadProjectMaterials(1);
    else if (tableKey === 'workflows') loadProjectWorkflows(1);
    else if (tableKey === 'transmittals') loadProjectTransmittals(1);
    else if (tableKey === 'other_mail') loadProjectOtherMail(1);
    else if (tableKey === 'other_docs') loadProjectOtherDocs(1);
}

// ==========================================
// 6. EXCEL EXPORTS
// ==========================================
function exportCurrentProjectExcel() {
    if (!activeProjectData) return;
    let pid = activeProjectData.info?.project_id || '';
    if (pid === 'MMS / Substation') pid = 'MMS';
    window.location.href = `/api/projects/${encodeURIComponent(pid)}/export`;
}

function exportCurrentProjectRfiLog() {
    if (!activeProjectData || !activeProjectData.info) return;
    let pid = activeProjectData.info?.project_id || '';
    if (pid === 'MMS / Substation') pid = 'MMS';
    window.location.href = `/api/rfi_explore/export_excel?project_id=${encodeURIComponent(pid)}`;
}

function exportFilteredData(category) {
    if (!activeProjectData || !activeProjectData.info) return;
    let pid = activeProjectData.info?.project_id || '';
    if (pid === 'MMS / Substation') pid = 'MMS';
    let url = `/api/projects/${encodeURIComponent(pid)}/export_filtered?category=${encodeURIComponent(category)}`;

    if (category === 'letters') {
        const search = document.getElementById('sub-letters-search')?.value || '';
        const direction = document.getElementById('sub-letters-direction')?.value || '';
        const fromOrg = document.getElementById('sub-letters-from-org')?.value || '';
        const overdue = document.getElementById('sub-letters-overdue')?.checked;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (direction) url += `&direction=${encodeURIComponent(direction)}`;
        if (fromOrg) url += `&from_org=${encodeURIComponent(fromOrg)}`;
        if (overdue) url += `&is_overdue=true`;
        url += buildSortQueryString('letters');
    } else if (category === 'hill_ssc') {
        const search = document.getElementById('sub-hill_ssc-search')?.value || '';
        const direction = document.getElementById('sub-hill_ssc-direction')?.value || '';
        const overdue = document.getElementById('sub-hill_ssc-overdue')?.checked;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (direction) url += `&direction=${encodeURIComponent(direction)}`;
        if (overdue) url += `&is_overdue=true`;
        url += buildSortQueryString('hill_ssc');
    } else if (category === 'rfis') {
        const search = document.getElementById('sub-rfis-search')?.value || '';
        const mailType = document.getElementById('sub-rfis-type')?.value || '';
        const status = document.getElementById('sub-rfis-status')?.value || '';
        const fromOrg = document.getElementById('sub-rfis-from-org')?.value || '';
        const toOrg = document.getElementById('sub-rfis-to-org')?.value || '';
        const overdue = document.getElementById('sub-rfis-overdue')?.checked;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (mailType) url += `&mail_type=${encodeURIComponent(mailType)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        if (fromOrg) url += `&from_org=${encodeURIComponent(fromOrg)}`;
        if (toOrg) url += `&to_org=${encodeURIComponent(toOrg)}`;
        if (overdue) url += `&is_overdue=true`;
        url += buildSortQueryString('rfis');
    } else if (category === 'shop_drawings') {
        const search = document.getElementById('sub-shopdrw-search')?.value || '';
        const disc = document.getElementById('sub-shopdrw-discipline')?.value || '';
        const status = document.getElementById('sub-shopdrw-status')?.value || '';
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (disc) url += `&discipline=${encodeURIComponent(disc)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        url += buildSortQueryString('shop_drawings');
    } else if (category === 'material_submittals') {
        const search = document.getElementById('sub-mat-search')?.value || '';
        const disc = document.getElementById('sub-mat-discipline')?.value || '';
        const status = document.getElementById('sub-mat-status')?.value || '';
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (disc) url += `&discipline=${encodeURIComponent(disc)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        url += buildSortQueryString('material_submittals');
    } else if (category === 'workflows') {
        const search = document.getElementById('sub-wf-search')?.value || '';
        const status = document.getElementById('sub-wf-status')?.value || '';
        const overdue = document.getElementById('sub-wf-overdue')?.checked;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        if (overdue) url += `&is_overdue=true`;
        url += buildSortQueryString('workflows');
    } else if (category === 'other_mail') {
        const search = document.getElementById('sub-othermail-search')?.value || '';
        const type = document.getElementById('sub-othermail-type')?.value || '';
        const overdue = document.getElementById('sub-othermail-overdue')?.checked;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (type) url += `&mail_type=${encodeURIComponent(type)}`;
        if (overdue) url += `&is_overdue=true`;
        url += buildSortQueryString('other_mail');
    } else if (category === 'other_docs') {
        const search = document.getElementById('sub-otherdocs-search')?.value || '';
        const docType = document.getElementById('sub-otherdocs-type')?.value || '';
        const disc = document.getElementById('sub-otherdocs-discipline')?.value || '';
        const status = document.getElementById('sub-otherdocs-status')?.value || '';
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (docType) url += `&doc_type=${encodeURIComponent(docType)}`;
        if (disc) url += `&discipline=${encodeURIComponent(disc)}`;
        if (status) url += `&status=${encodeURIComponent(status)}`;
        url += buildSortQueryString('other_docs');
    }

    window.location.href = url;
}

// ==========================================
// 7. PRIMARY TABS & CONTROLS DISPATCH
// ==========================================
function switchPrimaryTab(tab) {
    if (tab === 'settings' || tab === 'sync') {
        if (typeof window.isAdminUnlocked === 'function' && !window.isAdminUnlocked()) {
            if (typeof window.promptAdminUnlock === 'function') {
                window.promptAdminUnlock(() => {
                    if (tab === 'sync') {
                        switchPrimaryTab('settings');
                        switchSettingsSubTab('sync');
                    } else {
                        switchPrimaryTab('settings');
                    }
                });
                return;
            }
        }
    }
    if (tab === 'sync') {
        switchPrimaryTab('settings');
        switchSettingsSubTab('sync');
        return;
    }
    const tabsConfig = [
        { id: 'projects', btnId: 'tab-btn-projects', viewId: 'view-projects-hub', activeClass: 'bg-sky-600 shadow-sky-600/20' },
        { id: 'daily_feed', btnId: 'tab-btn-daily-feed', viewId: 'view-daily-feed', activeClass: 'bg-amber-600 shadow-amber-600/20', onOpen: () => loadDailyFeed(1) },
        { id: 'controls', btnId: 'tab-btn-controls', viewId: 'view-project-controls', activeClass: 'bg-rose-600 shadow-rose-600/20', onOpen: initControlsTab },
        { id: 'hill_internal', btnId: 'tab-btn-hill-internal', viewId: 'view-hill-internal-controls', activeClass: 'bg-emerald-600 shadow-emerald-600/20', onOpen: loadHillTeamControls },
        { id: 'hill_ssc_direct', btnId: 'tab-btn-hill-ssc-direct', viewId: 'view-hill-ssc-direct', activeClass: 'bg-purple-600 shadow-purple-600/20', onOpen: () => loadHillSscDirect(1) },
        { id: 'ball_in_court', btnId: 'tab-btn-ball-in-court', viewId: 'view-ball-in-court', activeClass: 'bg-amber-600 shadow-amber-600/20', onOpen: () => loadBallInCourtData(1) },
        { id: 'sync', btnId: 'tab-btn-sync', viewId: 'view-sync', activeClass: 'bg-emerald-600 shadow-emerald-600/20', onOpen: loadSyncStatus },
        { id: 'discipline_safety', btnId: 'tab-btn-discipline-safety', viewId: 'view-discipline-safety', activeClass: 'bg-emerald-600 shadow-emerald-600/20', onOpen: () => loadDisciplineSafety(1) },
        { id: 'discipline_qaqc', btnId: 'tab-btn-discipline-qaqc', viewId: 'view-discipline-qaqc', activeClass: 'bg-cyan-600 shadow-cyan-600/20', onOpen: () => loadDisciplineQaqc(1) },
        { id: 'discipline_site', btnId: 'tab-btn-discipline-site', viewId: 'view-discipline-site', activeClass: 'bg-amber-600 shadow-amber-600/20', onOpen: () => loadDisciplineSite(1) },
        { id: 'discipline_tech', btnId: 'tab-btn-discipline-tech', viewId: 'view-discipline-tech', activeClass: 'bg-indigo-600 shadow-indigo-600/20', onOpen: () => loadDisciplineTech(1) },
        { id: 'discipline_contractual', btnId: 'tab-btn-discipline-contractual', viewId: 'view-discipline-contractual', activeClass: 'bg-blue-600 shadow-blue-600/20', onOpen: () => loadDisciplineContractual(1) },
        { id: 'discipline_commercial', btnId: 'tab-btn-discipline-commercial', viewId: 'view-discipline-commercial', activeClass: 'bg-emerald-600 shadow-emerald-600/20', onOpen: () => loadDisciplineCommercial(1) },
        { id: 'settings', btnId: 'tab-btn-settings', viewId: 'view-settings', activeClass: 'bg-indigo-600 shadow-indigo-600/20', onOpen: loadDispatchSettings }
    ];

    const inactiveBtnClass = 'w-full px-3.5 py-2.5 rounded-xl text-xs font-semibold bg-slate-900 text-slate-300 hover:bg-slate-800 hover:text-white border border-slate-800 flex items-center justify-between transition group text-left cursor-pointer';

    const viewProjectWorkspace = document.getElementById('view-project-workspace');

    tabsConfig.forEach(t => {
        const btn = document.getElementById(t.btnId);
        const view = document.getElementById(t.viewId);
        if (btn) {
            if (t.id === 'settings') {
                btn.className = 'w-full px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-900/90 transition flex items-center justify-between group cursor-pointer border border-transparent hover:border-slate-800';
            } else {
                btn.className = inactiveBtnClass;
            }
        }
        if (view) view.classList.add('hidden');
    });

    const activeTab = tabsConfig.find(t => t.id === tab) || tabsConfig[0];
    const activeBtn = document.getElementById(activeTab.btnId);
    const activeView = document.getElementById(activeTab.viewId);

    if (activeBtn) {
        if (activeTab.id === 'settings') {
            activeBtn.className = 'w-full px-2.5 py-1.5 rounded-lg text-xs font-bold bg-indigo-600 text-white shadow-md shadow-indigo-600/20 border border-indigo-500 flex items-center justify-between transition group cursor-pointer';
        } else {
            activeBtn.className = `w-full px-3.5 py-2.5 rounded-xl text-xs font-bold ${activeTab.activeClass} text-white flex items-center justify-between shadow-md transition group text-left cursor-pointer`;
        }
    }

    if (activeTab.id === 'projects') {
        if (activeProjectData && viewProjectWorkspace) {
            viewProjectWorkspace.classList.remove('hidden');
            if (activeView) activeView.classList.add('hidden');
        } else {
            if (viewProjectWorkspace) viewProjectWorkspace.classList.add('hidden');
            if (activeView) activeView.classList.remove('hidden');
        }
    } else {
        if (viewProjectWorkspace) viewProjectWorkspace.classList.add('hidden');
        if (activeView) activeView.classList.remove('hidden');
    }

    if (activeTab.onOpen) {
        activeTab.onOpen();
    }

    if (window.lucide) lucide.createIcons();
}

// ==========================================
// 3.1 CONTROLS TAB OVERDUE GEO-SELECTOR MAP
// ==========================================
let ctrlMasterPlanLoaded = false;
let ctrlMasterPlanScale = 1.0;
let ctrlMasterPlanPanX = 0;
let ctrlMasterPlanPanY = 0;
let isCtrlPanningMap = false;
let startCtrlPanX = 0;
let startCtrlPanY = 0;
let hasCtrlDragged = false;
let isCtrlFullscreenMap = false;

// Helper to find a project in ctrlProjectsList with robust fuzzy matching
function findCtrlProject(pid, aid) {
    if (!ctrlProjectsList || ctrlProjectsList.length === 0) return null;
    return ctrlProjectsList.find(p => 
        p.project_id === pid || 
        p.project_id === aid || 
        p.project_name === pid || 
        p.project_name === aid ||
        ((pid === 'MMS' || aid === 'MSS' || pid === 'MSS') && p.project_id.includes('Substation')) ||
        ((pid === 'RO Plant' || aid === 'RO') && p.project_id.includes('RO'))
    );
}

async function initCtrlMasterPlanMap() {
    const container = document.getElementById('ctrl-master-plan-svg-container');
    const viewport = document.getElementById('ctrl-master-plan-viewport');
    const tooltip = document.getElementById('ctrl-master-plan-tooltip');
    if (!container || !viewport || !tooltip) return;

    if (!ctrlMasterPlanLoaded) {
        try {
            const res = await fetch(`/static/images/master_plan_interactive.svg?v=${Date.now()}`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            let svgContent = await res.text();

            // Prefix internal SVG IDs to prevent duplicate ID collisions with Tab 1
            svgContent = svgContent
                .replace(/id="arrow-emerald"/g, 'id="ctrl-arrow-emerald"')
                .replace(/url\(#arrow-emerald\)/g, 'url(#ctrl-arrow-emerald)')
                .replace(/id="arrow-cyan"/g, 'id="ctrl-arrow-cyan"')
                .replace(/url\(#arrow-cyan\)/g, 'url(#ctrl-arrow-cyan)')
                .replace(/id="callout-shadow"/g, 'id="ctrl-callout-shadow"')
                .replace(/url\(#callout-shadow\)/g, 'url(#ctrl-callout-shadow)')
                .replace(/id="glow-emerald"/g, 'id="ctrl-glow-emerald"')
                .replace(/url\(#glow-emerald\)/g, 'url(#ctrl-glow-emerald)')
                .replace(/id="svgcontent"/g, 'id="ctrl-svgcontent"');

            container.innerHTML = svgContent;
            ctrlMasterPlanLoaded = true;
            if (window.lucide) lucide.createIcons();
            attachCtrlMasterPlanInteractivity(container, viewport, tooltip);
            updateCtrlMasterPlanOverdueBadges();
        } catch (err) {
            console.error('Failed to load Controls Master Plan SVG:', err);
            container.innerHTML = `
                <div class="flex flex-col items-center justify-center p-6 text-rose-400 text-xs">
                    <p class="font-bold mb-2">Failed to load interactive Controls map</p>
                    <button onclick="ctrlMasterPlanLoaded=false; initCtrlMasterPlanMap()" class="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700">Retry</button>
                </div>
            `;
            return;
        }
    } else {
        updateCtrlMasterPlanOverdueBadges();
    }
}

function updateCtrlMasterPlanOverdueBadges() {
    const container = document.getElementById('ctrl-master-plan-svg-container');
    if (!container || !ctrlProjectsList || ctrlProjectsList.length === 0) return;

    container.querySelectorAll('.callout-group').forEach(group => {
        const aid = group.getAttribute('data-area-id') || group.id;
        const pid = group.getAttribute('data-project-id') || aid;

        const pData = findCtrlProject(pid, aid);
        const texts = group.querySelectorAll('text');
        const titleTextEl = texts[0];
        const subTextEl = texts[1];
        const rectEl = group.querySelector('rect');

        const isActive = (pid === ctrlSelectedProjectId || (pData && pData.project_id === ctrlSelectedProjectId));
        const overdue = pData ? (pData.total_overdue || 0) : 0;
        const isWY = (pData && pData.category === 'Wadi Yemm') || group.classList.contains('wy-group');

        // 1. Primary Title - Bold, large, crisp white text
        if (titleTextEl) {
            titleTextEl.setAttribute('fill', '#ffffff');
            titleTextEl.setAttribute('font-weight', '900');
            titleTextEl.setAttribute('font-size', '12');
            titleTextEl.setAttribute('letter-spacing', '0.5');
            titleTextEl.style.textShadow = '0 1px 4px rgba(0,0,0,0.95)';
        }

        // 2. Subtitle - Clear overdue count or category with high contrast
        if (subTextEl) {
            if (pData) {
                if (overdue > 0) {
                    subTextEl.textContent = `${overdue} Overdue`;
                    subTextEl.setAttribute('fill', '#fda4af'); // Soft luminous coral-pink with high contrast on dark navy
                    subTextEl.setAttribute('font-weight', '800');
                    subTextEl.setAttribute('font-size', '10');
                    subTextEl.style.textShadow = '0 1px 4px rgba(0,0,0,0.95)';
                } else {
                    subTextEl.textContent = '0 Overdue';
                    subTextEl.setAttribute('fill', '#34d399'); // Emerald green
                    subTextEl.setAttribute('font-weight', '800');
                    subTextEl.setAttribute('font-size', '10');
                    subTextEl.style.textShadow = '0 1px 4px rgba(0,0,0,0.95)';
                }
            } else {
                subTextEl.textContent = isWY ? 'Wadi Yemm' : 'Infrastructure';
                subTextEl.setAttribute('fill', isWY ? '#34d399' : '#38bdf8');
                subTextEl.setAttribute('font-weight', '700');
                subTextEl.setAttribute('font-size', '9');
            }
        }

        // 3. Rect Card - ALWAYS solid dark navy slate (NEVER transparent), with vibrant border and drop shadow
        if (rectEl) {
            rectEl.setAttribute('fill', 'rgba(10, 15, 30, 0.96)');
            rectEl.removeAttribute('filter');
            rectEl.style.filter = 'drop-shadow(0 4px 8px rgba(0,0,0,0.92))';

            if (isActive) {
                rectEl.setAttribute('stroke', '#f43f5e');
                rectEl.setAttribute('stroke-width', '3');
                rectEl.style.filter = 'drop-shadow(0 0 14px rgba(244, 63, 94, 0.95)) drop-shadow(0 4px 8px rgba(0,0,0,0.95))';
                group.classList.add('active-ctrl-pkg');
            } else if (overdue > 0) {
                rectEl.setAttribute('stroke', '#f43f5e');
                rectEl.setAttribute('stroke-width', '2');
                group.classList.remove('active-ctrl-pkg');
            } else {
                rectEl.setAttribute('stroke-width', '1.8');
                rectEl.setAttribute('stroke', isWY ? '#10b981' : '#06b6d4');
                group.classList.remove('active-ctrl-pkg');
            }
        }
    });

    container.querySelectorAll('.synoptic-area').forEach(area => {
        const aid = area.getAttribute('data-area-id') || area.id;
        const pid = area.getAttribute('data-project-id') || aid;
        const pData = findCtrlProject(pid, aid);
        const isActive = (pid === ctrlSelectedProjectId || (pData && pData.project_id === ctrlSelectedProjectId));

        if (isActive) {
            area.classList.add('active-ctrl-area');
            area.style.stroke = '#f43f5e';
            area.style.strokeWidth = '3.5px';
            area.style.fill = 'rgba(244, 63, 94, 0.35)';
            area.style.filter = 'drop-shadow(0 0 14px rgba(244, 63, 94, 0.95))';
        } else {
            area.classList.remove('active-ctrl-area');
            area.style.stroke = '';
            area.style.strokeWidth = '';
            area.style.fill = '';
            area.style.filter = '';
        }
    });
}

function attachCtrlMasterPlanInteractivity(container, viewport, tooltip) {
    const interactiveElements = container.querySelectorAll('.synoptic-area, .callout-group');
    if (interactiveElements.length === 0) return;

    interactiveElements.forEach(el => {
        if (el._hasCtrlMasterPlanListener) return;
        el._hasCtrlMasterPlanListener = true;

        el.addEventListener('mouseenter', (e) => handleCtrlMasterPlanHover(e, el, viewport, tooltip));
        el.addEventListener('mousemove', (e) => positionCtrlMasterPlanTooltip(e, viewport, tooltip));
        el.addEventListener('mouseleave', () => handleCtrlMasterPlanLeave(tooltip));

        el.addEventListener('click', (e) => {
            e.stopPropagation();
            const aid = el.getAttribute('data-area-id') || el.id;
            let pid = el.getAttribute('data-project-id') || aid;
            if (pid === 'Ring Road' || pid === 'Ring_x20_Road' || aid === 'Ring_x20_Road') {
                pid = 'Infra';
            }
            onCtrlMapSelectProject(pid, aid);
        });
    });
}

function onCtrlMapSelectProject(pid, aid) {
    const pData = findCtrlProject(pid, aid);
    if (!pData) return;

    if (pData.category && pData.category !== ctrlSelectedCategory) {
        ctrlSelectedCategory = pData.category;
        const catSelect = document.getElementById('ctrl-category-select');
        if (catSelect) catSelect.value = pData.category;
        renderCtrlProjectsSelector();
    }

    selectCtrlProject(pData.project_id);
    updateCtrlMasterPlanOverdueBadges();

    const targetSection = document.getElementById('ctrl-active-pkg-pill') || document.getElementById('ctrl-project-dashboard');
    if (targetSection) {
        targetSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function handleCtrlMasterPlanHover(e, el, viewport, tooltip) {
    const aid = el.getAttribute('data-area-id') || el.id;
    const pid = el.getAttribute('data-project-id') || aid;
    const code = el.getAttribute('data-code') || aid;
    const title = el.getAttribute('data-title') || aid;
    const cno = el.getAttribute('data-contract') || '';
    const ctor = el.getAttribute('data-contractor') || 'Pending';
    const cat = el.getAttribute('data-category') || 'Wadi Yemm';

    document.querySelectorAll(`#ctrl-master-plan-svg-container [data-area-id="${aid}"]`).forEach(node => {
        node.classList.add('is-hovered');
    });

    const pData = findCtrlProject(pid, aid) || {};
    const overdueWf = pData.overdue_workflows || 0;
    const overdueMails = pData.overdue_mails || 0;
    const overdueRfis = pData.overdue_rfis || 0;
    const totalOverdue = pData.total_overdue || 0;
    const isWY = cat === 'Wadi Yemm';

    tooltip.innerHTML = `
        <div class="flex items-center justify-between gap-2 mb-2 pb-2 border-b border-slate-800">
            <span class="text-sm font-black text-rose-400 tracking-wide">${code}</span>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${isWY ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30' : 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'}">
                ${cat}
            </span>
        </div>
        <div class="text-xs font-bold text-white mb-1.5 leading-snug">${title}</div>
        <div class="text-[11px] text-slate-400 mb-0.5">Contractor: <span class="text-slate-200 font-semibold">${ctor}</span></div>
        ${cno ? `<div class="text-[11px] text-slate-400 mb-2">Contract: <span class="text-rose-300 font-mono">${cno}</span></div>` : ''}

        <div class="grid grid-cols-3 gap-1.5 pt-2 border-t border-slate-800 text-center">
            <div class="bg-slate-950/70 rounded p-1.5 border border-slate-800">
                <div class="text-[9.5px] text-slate-400 font-medium">Overdue WFs</div>
                <div class="text-xs font-black text-rose-400 font-mono">${overdueWf}</div>
            </div>
            <div class="bg-slate-950/70 rounded p-1.5 border border-slate-800">
                <div class="text-[9.5px] text-slate-400 font-medium">Overdue Mails</div>
                <div class="text-xs font-black text-amber-400 font-mono">${overdueMails}</div>
            </div>
            <div class="bg-slate-950/70 rounded p-1.5 border border-slate-800">
                <div class="text-[9.5px] text-slate-400 font-medium">Total Overdue</div>
                <div class="text-xs font-black ${totalOverdue > 0 ? 'text-rose-400 animate-pulse' : 'text-emerald-400'} font-mono">${totalOverdue}</div>
            </div>
        </div>

        <div class="mt-2.5 py-1 px-2 rounded-lg bg-rose-500/15 border border-rose-500/30 text-rose-300 text-[10.5px] font-bold text-center flex items-center justify-center gap-1.5 shadow-sm">
            <span>👉 Click to select for Overdue Email Dispatch</span>
            <i data-lucide="mail-warning" class="w-3 h-3"></i>
        </div>
    `;

    if (window.lucide) lucide.createIcons();
    positionCtrlMasterPlanTooltip(e, viewport, tooltip);
    tooltip.classList.remove('hidden');
}

function positionCtrlMasterPlanTooltip(e, viewport, tooltip) {
    const vpRect = viewport.getBoundingClientRect();
    let left = e.clientX - vpRect.left + 16;
    let top = e.clientY - vpRect.top + 16;

    const tooltipWidth = 288;
    const tooltipHeight = 220;
    if (left + tooltipWidth > vpRect.width) {
        left = left - tooltipWidth - 24;
    }
    if (top + tooltipHeight > vpRect.height) {
        top = top - tooltipHeight - 20;
    }
    if (left < 10) left = 10;
    if (top < 10) top = 10;

    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
}

function handleCtrlMasterPlanLeave(tooltip) {
    document.querySelectorAll('#ctrl-master-plan-svg-container .is-hovered').forEach(node => {
        node.classList.remove('is-hovered');
    });
    if (tooltip) tooltip.classList.add('hidden');
}

function zoomCtrlMasterPlan(factor) {
    ctrlMasterPlanScale = Math.min(3.5, Math.max(0.75, ctrlMasterPlanScale * factor));
    updateCtrlMasterPlanTransform();
}

function resetCtrlMasterPlanZoom() {
    ctrlMasterPlanScale = 1.0;
    ctrlMasterPlanPanX = 0;
    ctrlMasterPlanPanY = 0;
    updateCtrlMasterPlanTransform();
}

function updateCtrlMasterPlanTransform() {
    const svgEl = document.querySelector('#ctrl-master-plan-svg-container svg');
    if (svgEl) {
        svgEl.style.transform = `translate(${ctrlMasterPlanPanX}px, ${ctrlMasterPlanPanY}px) scale(${ctrlMasterPlanScale})`;
        svgEl.style.transformOrigin = 'center center';
        svgEl.style.transition = isCtrlPanningMap ? 'none' : 'transform 0.15s ease-out';
    }
}

function toggleCtrlMasterPlanFullscreen() {
    const card = document.getElementById('ctrl-master-plan-card');
    const viewport = document.getElementById('ctrl-master-plan-viewport');
    if (!card || !viewport) return;

    isCtrlFullscreenMap = !isCtrlFullscreenMap;
    if (isCtrlFullscreenMap) {
        card.classList.add('fixed', 'inset-0', 'z-50', 'm-0', 'rounded-none', 'h-screen', 'flex', 'flex-col', 'p-4');
        viewport.style.aspectRatio = 'auto';
        viewport.classList.remove('max-h-[480px]');
        viewport.classList.add('flex-1', 'h-full');
    } else {
        card.classList.remove('fixed', 'inset-0', 'z-50', 'm-0', 'rounded-none', 'h-screen', 'flex', 'flex-col', 'p-4');
        viewport.style.aspectRatio = '1568 / 672';
        viewport.classList.remove('flex-1', 'h-full');
        viewport.classList.add('max-h-[480px]');
    }
}

async function initControlsTab(force = false) {
    if (ctrlProjectsList.length > 0 && !force) {
        renderCtrlProjectsSelector();
        initCtrlMasterPlanMap();
        if (!ctrlSelectedProjectId && ctrlProjectsList.length > 0) {
            const sortedList = [...ctrlProjectsList].sort((a,b) => (a.sort_order || 999) - (b.sort_order || 999));
            selectCtrlProject(sortedList[0].project_id);
        }
        return;
    }

    const pkgSelect = document.getElementById('ctrl-package-select');
    if (pkgSelect) pkgSelect.innerHTML = '<option value="">Loading packages with overdue items...</option>';

    try {
        const fromDate = (document.getElementById('ctrl-ssc-from-date')?.value || '').trim();
        const toDate = (document.getElementById('ctrl-ssc-to-date')?.value || '').trim();
        const qp = new URLSearchParams();
        if (fromDate) qp.append('from_date', fromDate);
        if (toDate) qp.append('to_date', toDate);
        const qStr = qp.toString() ? `?${qp.toString()}` : '';

        const res = await fetch(`/api/controls/projects${qStr}`);
        const json = await res.json();
        ctrlProjectsList = json.data || json.projects || [];

        const totalSscOverdue = ctrlProjectsList.reduce((acc, p) => acc + (p.total_overdue || p.overdue_items || 0), 0);
        const sscBadge = document.getElementById('badge-subtab-ssc-count');
        if (sscBadge) sscBadge.textContent = `${totalSscOverdue.toLocaleString()} Overdue`;

        renderCtrlProjectsSelector();
        initCtrlMasterPlanMap();

        if (ctrlProjectsList.length > 0) {
            const filtered = getFilteredCtrlProjects();
            let def = filtered.find(p => p.project_id === ctrlSelectedProjectId);
            if (!def) {
                def = filtered[0] || ctrlProjectsList[0];
            }
            if (def) selectCtrlProject(def.project_id);
        }
    } catch (err) {
        if (pkgSelect) pkgSelect.innerHTML = `<option value="">Failed to load: ${err.message}</option>`;
    }
}

function onCtrlCategorySelectChange(cat) {
    ctrlSelectedCategory = cat;
    renderCtrlProjectsSelector();
    const filtered = getFilteredCtrlProjects();
    if (filtered.length > 0) {
        const exists = filtered.find(p => p.project_id === ctrlSelectedProjectId);
        if (exists) {
            selectCtrlProject(exists.project_id);
        } else {
            selectCtrlProject(filtered[0].project_id);
        }
    } else {
        const container = document.getElementById('ctrl-project-dashboard');
        if (container) {
            container.innerHTML = `
                <div class="py-16 text-center text-slate-500 bg-slate-900 rounded-2xl border border-slate-800">
                    <p class="text-sm font-bold text-slate-400">No packages match the selected category.</p>
                </div>
            `;
        }
    }
}

function onCtrlProjectSearchInput(term) {
    ctrlProjectSearchTerm = (term || '').trim().toLowerCase();
    renderCtrlProjectsSelector();
}

function getFilteredCtrlProjects() {
    return ctrlProjectsList.filter(p => {
        if (ctrlSelectedCategory !== 'all' && p.category !== ctrlSelectedCategory) return false;
        if (ctrlProjectSearchTerm) {
            const text = `${p.project_id || ''} ${p.project_title || ''} ${p.k_package_no || ''} ${p.contractor_name || ''}`.toLowerCase();
            if (!text.includes(ctrlProjectSearchTerm)) return false;
        }
        return true;
    }).sort((a, b) => (a.sort_order || 999) - (b.sort_order || 999));
}

function renderCtrlProjectsSelector() {
    const pkgSelect = document.getElementById('ctrl-package-select');
    if (!pkgSelect) return;

    const filtered = getFilteredCtrlProjects();
    if (filtered.length === 0) {
        pkgSelect.innerHTML = '<option value="">No packages match criteria</option>';
        return;
    }

    let html = '';
    filtered.forEach(p => {
        const pid = p.project_id || '';
        const kcode = (p.k_package_no || '').split('/')[0].trim();
        const displayCode = (kcode && kcode !== pid) ? `${pid} • ${kcode}` : (pid || kcode);
        const overdueBadge = (p.total_overdue > 0) ? `(${p.total_overdue} Overdue)` : `(Clear)`;
        const isSelected = p.project_id === ctrlSelectedProjectId ? 'selected' : '';
        html += `<option value="${p.project_id}" ${isSelected}>[${displayCode}] ${p.project_title || p.project_name} ${overdueBadge}</option>`;
    });
    pkgSelect.innerHTML = html;

    // Update active package summary pill
    const curPkg = ctrlProjectsList.find(p => p.project_id === ctrlSelectedProjectId);
    const pill = document.getElementById('ctrl-active-pkg-pill');
    if (pill && curPkg) {
        pill.classList.remove('hidden');
        const codeEl = document.getElementById('ctrl-active-pkg-code');
        const badgeEl = document.getElementById('ctrl-active-pkg-badge');
        const pid = curPkg.project_id || '';
        const kcode = (curPkg.k_package_no || '').split('/')[0].trim();
        if (codeEl) codeEl.innerText = (kcode && kcode !== pid) ? `${pid} • ${kcode}` : pid;
        if (badgeEl) {
            badgeEl.innerText = `${curPkg.total_overdue || 0} Overdue`;
            badgeEl.className = curPkg.total_overdue > 0
                ? 'px-2 py-0.5 rounded text-[11px] font-bold font-mono bg-rose-500/20 text-rose-300 border border-rose-500/30'
                : 'px-2 py-0.5 rounded text-[11px] font-bold font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
        }
    }
}

async function selectCtrlProject(projectId) {
    if (!projectId) return;
    ctrlSelectedProjectId = projectId;

    const pkgSelect = document.getElementById('ctrl-package-select');
    if (pkgSelect && pkgSelect.value !== projectId) {
        pkgSelect.value = projectId;
    }

    const curPkg = ctrlProjectsList.find(p => p.project_id === ctrlSelectedProjectId);
    const pill = document.getElementById('ctrl-active-pkg-pill');
    if (pill && curPkg) {
        pill.classList.remove('hidden');
        const codeEl = document.getElementById('ctrl-active-pkg-code');
        const badgeEl = document.getElementById('ctrl-active-pkg-badge');
        const pid = curPkg.project_id || '';
        const kcode = (curPkg.k_package_no || '').split('/')[0].trim();
        if (codeEl) codeEl.innerText = (kcode && kcode !== pid) ? `${pid} • ${kcode}` : pid;
        if (badgeEl) {
            badgeEl.innerText = `${curPkg.total_overdue || 0} Overdue`;
            badgeEl.className = curPkg.total_overdue > 0
                ? 'px-2 py-0.5 rounded text-[11px] font-bold font-mono bg-rose-500/20 text-rose-300 border border-rose-500/30'
                : 'px-2 py-0.5 rounded text-[11px] font-bold font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
        }
    }

    updateCtrlMasterPlanOverdueBadges();

    const container = document.getElementById('ctrl-project-dashboard');
    if (!container) return;

    container.innerHTML = `
        <div class="py-20 text-center text-slate-400 bg-slate-900 rounded-2xl border border-slate-800">
            <div class="inline-block animate-spin w-8 h-8 border-2 border-rose-500 border-t-transparent rounded-full mb-3"></div>
            <p class="text-sm font-semibold text-slate-300">Extracting overdue review workflows, correspondence, and resolving Shaker/ECG/Hill contacts...</p>
            <p class="text-xs text-slate-500 mt-1">Package: ${projectId}</p>
        </div>
    `;

    try {
        const fromDate = (document.getElementById('ctrl-ssc-from-date')?.value || '').trim();
        const toDate = (document.getElementById('ctrl-ssc-to-date')?.value || '').trim();
        const qp = new URLSearchParams();
        if (fromDate) qp.append('from_date', fromDate);
        if (toDate) qp.append('to_date', toDate);
        const qStr = qp.toString() ? `?${qp.toString()}` : '';

        const res = await fetch(`/api/controls/projects/${encodeURIComponent(projectId)}/overdue${qStr}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load`);
        const data = await res.json();
        ctrlActiveReport = data;
        ctrlTablePage = 1;
        ctrlTableTypeFilter = '';

        // Default Scope: Workflows, RFIs, and SCRs are selected; Letters are optional (unchecked by default)
        ctrlSectionScope = { workflows: true, mail: false, rfis: true, scrs: true };
        ctrlSelectedKeys = new Set();
        (data.workflows || []).forEach(w => ctrlSelectedKeys.add(`Workflow:${w.workflow_no}`));
        (data.rfis || []).forEach(r => ctrlSelectedKeys.add(`RFI:${r.rfi_no || r.mail_no}`));
        (data.scrs || []).forEach(s => ctrlSelectedKeys.add(`SCR:${s.mail_no}`));
        // Notice: Official Letters are NOT added to ctrlSelectedKeys by default

        renderCtrlDashboard(data);
    } catch (err) {
        container.innerHTML = `<div class="py-12 text-center text-rose-400 bg-rose-500/10 rounded-2xl p-6 font-bold">Error: ${err.message}</div>`;
    }
}

// 8. Render Controls Dashboard with Manual Email Recipients
function renderCtrlDashboard(data) {
    const container = document.getElementById('ctrl-project-dashboard');
    if (!container) return;

    const toEmails = data.to_emails || [];
    const ccEmails = data.cc_emails || [];
    const isDP01 = data.project_id === 'DP01';
    const rfiTitle = isDP01 ? 'Site Clarifications (SCR)' : 'Technical RFIs';
    const rfiBadge = isDP01 ? 'SCR' : 'RFIs';

    container.innerHTML = `
        <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
            <div class="flex flex-col 2xl:flex-row 2xl:items-center justify-between gap-4 pb-6 border-b border-slate-800">
                <div class="space-y-2">
                    <div class="flex items-center gap-2.5">
                        <span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-rose-500/20 text-rose-400 border border-rose-500/30 font-mono">
                            ${data.project_id}${data.k_package_no && data.k_package_no !== data.project_id ? ' • ' + data.k_package_no : ''}
                        </span>
                        <span class="px-2.5 py-1 text-xs font-bold rounded-lg bg-slate-800 text-slate-300 border border-slate-700">
                            ${data.category}
                        </span>
                    </div>
                    <h2 class="text-2xl font-black text-white tracking-tight">${data.project_title}</h2>
                    <div class="flex flex-wrap items-center gap-y-1 gap-x-4 text-xs text-slate-400">
                        <div>Main Contractor: <strong class="text-slate-200">${data.contractor_name}</strong></div>
                        <span class="text-slate-600">•</span>
                        <div>Contract: <span class="font-mono text-slate-300">${data.contract_no}</span></div>
                    </div>
                </div>

                <div class="flex flex-wrap items-center gap-2 flex-shrink-0">
                    <button onclick="openCtrlOutlookDraftWithAttachment()" class="px-3.5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-sky-600/20 transition whitespace-nowrap">
                        <i data-lucide="mail-plus" class="w-4 h-4"></i>
                        <span>Open in Outlook (with Attached Excel)</span>
                    </button>
                    <button onclick="copyCtrlHtmlEmail()" class="px-3.5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-indigo-600/20 transition whitespace-nowrap">
                        <i data-lucide="clipboard-copy" class="w-4 h-4"></i>
                        <span>Copy HTML Email</span>
                    </button>
                    <button onclick="exportCtrlOverdueExcel()" class="px-3.5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-emerald-600/20 transition whitespace-nowrap">
                        <i data-lucide="download" class="w-4 h-4"></i>
                        <span>Download Excel Register</span>
                    </button>
                </div>
            </div>

            <!-- Manual Email Recipients Panel (TO & CC tags + Add Input) -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <!-- TO Recipients -->
                <div class="bg-slate-950/70 rounded-xl p-4 border border-slate-800 space-y-3">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2 text-xs font-bold text-rose-400">
                            <i data-lucide="user-check" class="w-4 h-4"></i>
                            <span>TO: Document Controllers (<span id="ctrl-to-count">${toEmails.length}</span>)</span>
                        </div>
                        <button onclick="copyCtrlRecipients('to')" class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center gap-1 transition">
                            <i data-lucide="copy" class="w-3 h-3"></i>
                            <span>Copy TO</span>
                        </button>
                    </div>

                    <!-- Email Tags with Delete Buttons -->
                    <div id="ctrl-to-tags-container" class="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto custom-scrollbar p-1">
                        ${renderRecipientTags('to', toEmails)}
                    </div>

                    <!-- Add Email Input Box -->
                    <div class="flex items-center gap-2 pt-1 border-t border-slate-800/80">
                        <input type="email" id="ctrl-add-to-input" placeholder="Type email and press Add..." onkeydown="if(event.key==='Enter') addCtrlRecipient('to')" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-white placeholder-slate-500 flex-1 focus:outline-none focus:border-rose-500">
                        <button onclick="addCtrlRecipient('to')" class="px-3 py-1 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-bold transition flex items-center gap-1">
                            <span>+ Add</span>
                        </button>
                    </div>
                </div>

                <!-- CC Recipients -->
                <div class="bg-slate-950/70 rounded-xl p-4 border border-slate-800 space-y-3">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2 text-xs font-bold text-indigo-400">
                            <i data-lucide="users" class="w-4 h-4"></i>
                            <span>CC: Supervision & Hill PMC (<span id="ctrl-cc-count">${ccEmails.length}</span>)</span>
                        </div>
                        <button onclick="copyCtrlRecipients('cc')" class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center gap-1 transition">
                            <i data-lucide="copy" class="w-3 h-3"></i>
                            <span>Copy CC</span>
                        </button>
                    </div>

                    <!-- Email Tags with Delete Buttons -->
                    <div id="ctrl-cc-tags-container" class="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto custom-scrollbar p-1">
                        ${renderRecipientTags('cc', ccEmails)}
                    </div>

                    <!-- Add Email Input Box -->
                    <div class="flex items-center gap-2 pt-1 border-t border-slate-800/80">
                        <input type="email" id="ctrl-add-cc-input" placeholder="Type email and press Add..." onkeydown="if(event.key==='Enter') addCtrlRecipient('cc')" class="bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-white placeholder-slate-500 flex-1 focus:outline-none focus:border-indigo-500">
                        <button onclick="addCtrlRecipient('cc')" class="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold transition flex items-center gap-1">
                            <span>+ Add</span>
                        </button>
                    </div>
                </div>
            </div>

            <!-- Scope Switches -->
            <div class="bg-slate-950/80 rounded-xl p-4 border border-slate-800 space-y-3">
                <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div>
                        <div class="flex items-center gap-2">
                            <i data-lucide="sliders" class="w-4 h-4 text-rose-400"></i>
                            <h3 class="text-xs font-bold text-white uppercase tracking-wider">Email & Excel Dispatch Scope</h3>
                            <span id="ctrl-scope-summary-badge" class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono">
                                Calculating...
                            </span>
                        </div>
                    </div>

                    <div class="flex items-center gap-2">
                        <button onclick="ctrlSelectAll(true)" class="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1 transition">
                            <i data-lucide="check-square" class="w-3.5 h-3.5 text-emerald-400"></i>
                            <span>Select All</span>
                        </button>
                        <button onclick="ctrlSelectAll(false)" class="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1 transition">
                            <i data-lucide="square" class="w-3.5 h-3.5 text-slate-400"></i>
                            <span>Deselect All</span>
                        </button>
                        <button onclick="ctrlInvertSelection()" class="px-2.5 py-1.5 rounded-lg text-xs font-bold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1 transition">
                            <i data-lucide="shuffle" class="w-3.5 h-3.5 text-amber-400"></i>
                            <span>Invert Selection</span>
                        </button>
                    </div>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-2 border-t border-slate-800/80">
                    <label class="flex items-center justify-between p-3 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 cursor-pointer transition select-none">
                        <div class="flex items-center gap-3">
                            <input type="checkbox" id="ctrl-scope-wf" onchange="toggleCtrlSectionScope('workflows')" checked class="w-4 h-4 rounded text-rose-600 focus:ring-0 bg-slate-950 border-slate-700 cursor-pointer">
                            <div>
                                <div class="text-xs font-bold text-slate-200">Review Workflows</div>
                                <div class="text-[11px] text-slate-400" id="ctrl-scope-wf-count">...</div>
                            </div>
                        </div>
                        <span class="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-indigo-500/20 text-indigo-400">Workflows</span>
                    </label>

                    <label class="flex items-center justify-between p-3 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 cursor-pointer transition select-none">
                        <div class="flex items-center gap-3">
                            <input type="checkbox" id="ctrl-scope-mail" onchange="toggleCtrlSectionScope('mail')" ${ctrlSectionScope.mail ? 'checked' : ''} class="w-4 h-4 rounded text-rose-600 focus:ring-0 bg-slate-950 border-slate-700 cursor-pointer">
                            <div>
                                <div class="text-xs font-bold text-slate-200">Official Letters (Optional)</div>
                                <div class="text-[11px] text-slate-400" id="ctrl-scope-mail-count">...</div>
                            </div>
                        </div>
                        <span class="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-sky-500/20 text-sky-400">Letters</span>
                    </label>

                    <label class="flex items-center justify-between p-3 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 cursor-pointer transition select-none">
                        <div class="flex items-center gap-3">
                            <input type="checkbox" id="ctrl-scope-rfis" onchange="toggleCtrlSectionScope('rfis')" checked class="w-4 h-4 rounded text-rose-600 focus:ring-0 bg-slate-950 border-slate-700 cursor-pointer">
                            <div>
                                <div class="text-xs font-bold text-slate-200">Technical RFIs</div>
                                <div class="text-[11px] text-slate-400" id="ctrl-scope-rfis-count">...</div>
                            </div>
                        </div>
                        <span class="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-amber-500/20 text-amber-400">RFIs</span>
                    </label>

                    <label class="flex items-center justify-between p-3 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 cursor-pointer transition select-none">
                        <div class="flex items-center gap-3">
                            <input type="checkbox" id="ctrl-scope-scrs" onchange="toggleCtrlSectionScope('scrs')" ${ctrlSectionScope.scrs ? 'checked' : ''} class="w-4 h-4 rounded text-rose-600 focus:ring-0 bg-slate-950 border-slate-700 cursor-pointer">
                            <div>
                                <div class="text-xs font-bold text-slate-200">Site Clarifications (SCR)</div>
                                <div class="text-[11px] text-slate-400" id="ctrl-scope-scrs-count">...</div>
                            </div>
                        </div>
                        <span class="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-emerald-500/20 text-emerald-400">SCR</span>
                    </label>
                </div>
            </div>

            <!-- Overdue Items Register & Live Email Tabs -->
            <div class="bg-slate-900 rounded-2xl border border-slate-800 p-4 space-y-4">
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-3 border-b border-slate-800">
                    <div class="flex items-center gap-2 bg-slate-950 p-1 rounded-xl border border-slate-800">
                        <button id="ctrl-btn-view-report" onclick="setCtrlViewMode('report')" class="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-rose-600 text-white shadow-md transition flex items-center gap-1.5">
                            <i data-lucide="list" class="w-3.5 h-3.5"></i>
                            <span>Overdue Items Register</span>
                        </button>
                        <button id="ctrl-btn-view-email" onclick="setCtrlViewMode('email')" class="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5">
                            <i data-lucide="mail" class="w-3.5 h-3.5"></i>
                            <span>HTML Email Preview</span>
                        </button>
                    </div>
                </div>

                <!-- OVERDUE TABLE REGISTER -->
                <div id="ctrl-view-section-report" class="space-y-4">
                    <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                        <div class="flex flex-wrap items-center gap-2">
                            <button id="ctrl-tab-cat-all" onclick="setCtrlTableCategory('all')" class="px-3 py-1.5 rounded-lg text-xs font-bold bg-rose-600 text-white transition">
                                All Overdue (${data.total_overdue})
                            </button>
                            <button id="ctrl-tab-cat-workflows" onclick="setCtrlTableCategory('workflows')" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-950 text-slate-400 hover:text-white border border-slate-800 transition">
                                Workflows (${data.workflows_count})
                            </button>
                            <button id="ctrl-tab-cat-mail" onclick="setCtrlTableCategory('mail')" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-950 text-slate-400 hover:text-white border border-slate-800 transition">
                                Letters (${data.mails_count})
                            </button>
                            <button id="ctrl-tab-cat-rfis" onclick="setCtrlTableCategory('rfis')" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-950 text-slate-400 hover:text-white border border-slate-800 transition">
                                RFIs (${data.rfis_count || 0})
                            </button>
                            <button id="ctrl-tab-cat-scrs" onclick="setCtrlTableCategory('scrs')" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-950 text-slate-400 hover:text-white border border-slate-800 transition">
                                SCR (${data.scrs_count || 0})
                            </button>
                        </div>

                        <div class="flex items-center gap-2.5">
                            <select id="ctrl-table-type-filter" onchange="onCtrlTypeFilterChange(this.value)" class="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-rose-500">
                                <option value="">All Deliverable Types</option>
                                ${renderCtrlTypeFilterOptions(data)}
                            </select>
                            <input type="text" id="ctrl-table-search" oninput="onCtrlTableSearch(this.value)" placeholder="Search deliverables..." class="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 w-52 focus:outline-none focus:border-rose-500">
                        </div>
                    </div>

                    <div class="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900 shadow-xl">
                        <table class="w-full table-auto text-left text-xs" id="table-ctrl-overdue">
                            <thead class="bg-slate-950/90 text-slate-400 font-semibold border-b border-slate-800">
                                <tr>
                                    <th class="p-3 w-10 text-center">
                                        <input type="checkbox" id="ctrl-th-select-all" onchange="toggleCtrlMasterCheckbox(this.checked)" class="w-3.5 h-3.5 rounded text-rose-600 bg-slate-900 border-slate-700 focus:ring-0 cursor-pointer">
                                    </th>
                                    <th class="p-3 w-28">Type</th>
                                    <th class="p-3 w-44">Deliverable ID</th>
                                    <th class="p-3 w-40">Reference Code</th>
                                    <th class="p-3">Title / Subject</th>
                                    <th class="p-3 w-56">Current Step / Action</th>
                                    <th class="p-3 w-28">Due Date</th>
                                    <th class="p-3 w-28">Days Late</th>
                                </tr>
                            </thead>
                            <tbody id="ctrl-table-body" class="divide-y divide-slate-800/60"></tbody>
                        </table>
                    </div>

                    <div class="flex items-center justify-between pt-2">
                        <div class="text-xs text-slate-400" id="ctrl-table-page-info">Showing 0 of 0</div>
                        <div class="flex items-center gap-2">
                            <button id="ctrl-btn-prev-page" onclick="changeCtrlPage(-1)" disabled class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 font-bold text-xs transition">Previous</button>
                            <button id="ctrl-btn-next-page" onclick="changeCtrlPage(1)" disabled class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 font-bold text-xs transition">Next</button>
                        </div>
                    </div>
                </div>

                <!-- HTML EMAIL DISPATCH PREVIEW -->
                <div id="ctrl-view-section-email" class="space-y-4 hidden">
                    <div class="p-3 bg-slate-950/70 rounded-xl border border-slate-800 text-xs flex items-center gap-2">
                        <span class="text-slate-500 font-bold">Subject:</span>
                        <span class="font-bold text-slate-200 font-mono select-all" id="ctrl-email-preview-subject">${data.email_subject}</span>
                    </div>

                    <div id="ctrl-email-preview-body" class="rounded-xl border border-slate-800 bg-white overflow-hidden shadow-2xl p-6 text-slate-900" style="min-height: 400px; max-height: 800px; overflow-y: auto;">
                    </div>
                </div>
            </div>
        </div>
    `;

    updateCtrlStateAndUI();
    if (window.lucide) lucide.createIcons();
}

function renderRecipientTags(type, emails) {
    if (!emails || !emails.length) return '<span class="text-xs text-slate-500 italic">No recipients registered</span>';
    const tagBg = type === 'to' ? 'bg-rose-500/10 text-rose-300 border-rose-500/20' : 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20';
    return emails.map(email => `
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono border ${tagBg}">
            <span>${email}</span>
            <button onclick="removeCtrlRecipient('${type}', '${email}')" class="text-slate-400 hover:text-white font-bold ml-1 text-sm leading-none" title="Remove recipient">&times;</button>
        </span>
    `).join('');
}

function addCtrlRecipient(type) {
    if (!ctrlActiveReport) return;
    const input = document.getElementById(`ctrl-add-${type}-input`);
    const val = (input?.value || '').trim();
    if (!val || !val.includes('@')) {
        showToast('Please enter a valid email address.', 'error');
        return;
    }
    const arrKey = type === 'to' ? 'to_emails' : 'cc_emails';
    if (!ctrlActiveReport[arrKey]) ctrlActiveReport[arrKey] = [];
    if (!ctrlActiveReport[arrKey].includes(val)) {
        ctrlActiveReport[arrKey].push(val);
        input.value = '';
        refreshRecipientTagsUI(type);
        updateCtrlLiveEmailPreview();
        showToast(`Added ${val} to ${type.toUpperCase()}`, 'success');
    } else {
        showToast('Email address already exists in list', 'info');
    }
}

function removeCtrlRecipient(type, email) {
    if (!ctrlActiveReport) return;
    const arrKey = type === 'to' ? 'to_emails' : 'cc_emails';
    ctrlActiveReport[arrKey] = (ctrlActiveReport[arrKey] || []).filter(e => e !== email);
    refreshRecipientTagsUI(type);
    updateCtrlLiveEmailPreview();
    showToast(`Removed ${email} from ${type.toUpperCase()}`, 'info');
}

function refreshRecipientTagsUI(type) {
    const arrKey = type === 'to' ? 'to_emails' : 'cc_emails';
    const container = document.getElementById(`ctrl-${type}-tags-container`);
    const countEl = document.getElementById(`ctrl-${type}-count`);
    if (container) container.innerHTML = renderRecipientTags(type, ctrlActiveReport[arrKey]);
    if (countEl) countEl.innerText = ctrlActiveReport[arrKey]?.length || 0;
}

// 9. Table Selection & Search in Controls
function onCtrlTableSearch(q) {
    ctrlTableSearchQuery = q.toLowerCase();
    ctrlTablePage = 1;
    renderCtrlTable();
}

function changeCtrlPage(delta) {
    ctrlTablePage += delta;
    renderCtrlTable();
}

function setCtrlViewMode(mode) {
    ctrlViewMode = mode;
    const btnReport = document.getElementById('ctrl-btn-view-report');
    const btnEmail = document.getElementById('ctrl-btn-view-email');
    const secReport = document.getElementById('ctrl-view-section-report');
    const secEmail = document.getElementById('ctrl-view-section-email');

    if (mode === 'email') {
        if (btnReport) btnReport.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition';
        if (btnEmail) btnEmail.className = 'px-3.5 py-1.5 rounded-lg text-xs font-bold bg-rose-600 text-white shadow-md shadow-rose-600/20 transition';
        if (secReport) secReport.classList.add('hidden');
        if (secEmail) secEmail.classList.remove('hidden');
    } else {
        if (btnReport) btnReport.className = 'px-3.5 py-1.5 rounded-lg text-xs font-bold bg-rose-600 text-white shadow-md shadow-rose-600/20 transition';
        if (btnEmail) btnEmail.className = 'px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition';
        if (secReport) secReport.classList.remove('hidden');
        if (secEmail) secEmail.classList.add('hidden');
    }
}

function setCtrlTableCategory(cat) {
    ctrlTableCategory = cat;
    ctrlTablePage = 1;
    ['all', 'workflows', 'mail', 'rfis', 'scrs'].forEach(c => {
        const el = document.getElementById(`ctrl-tab-cat-${c}`);
        if (el) {
            el.className = (c === cat)
                ? 'px-3 py-1.5 rounded-lg text-xs font-bold bg-rose-600 text-white transition'
                : 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-950 text-slate-400 hover:text-white border border-slate-800 transition';
        }
    });
    renderCtrlTable();
}

function toggleCtrlItemSelection(key) {
    if (ctrlSelectedKeys.has(key)) ctrlSelectedKeys.delete(key);
    else ctrlSelectedKeys.add(key);
    updateCtrlStateAndUI();
}

function toggleCtrlSectionScope(sec) {
    ctrlSectionScope[sec] = !ctrlSectionScope[sec];
    if (ctrlActiveReport) {
        if (ctrlSectionScope[sec]) {
            if (sec === 'workflows') (ctrlActiveReport.workflows || []).forEach(w => ctrlSelectedKeys.add(`Workflow:${w.workflow_no}`));
            if (sec === 'mail') (ctrlActiveReport.mails || []).forEach(m => ctrlSelectedKeys.add(`Letter:${m.mail_no}`));
            if (sec === 'rfis') (ctrlActiveReport.rfis || []).forEach(r => ctrlSelectedKeys.add(`RFI:${r.rfi_no || r.mail_no}`));
            if (sec === 'scrs') (ctrlActiveReport.scrs || []).forEach(s => ctrlSelectedKeys.add(`SCR:${s.mail_no}`));
        } else {
            if (sec === 'workflows') (ctrlActiveReport.workflows || []).forEach(w => ctrlSelectedKeys.delete(`Workflow:${w.workflow_no}`));
            if (sec === 'mail') (ctrlActiveReport.mails || []).forEach(m => ctrlSelectedKeys.delete(`Letter:${m.mail_no}`));
            if (sec === 'rfis') (ctrlActiveReport.rfis || []).forEach(r => ctrlSelectedKeys.delete(`RFI:${r.rfi_no || r.mail_no}`));
            if (sec === 'scrs') (ctrlActiveReport.scrs || []).forEach(s => ctrlSelectedKeys.delete(`SCR:${s.mail_no}`));
        }
    }
    updateCtrlStateAndUI();
}

function renderCtrlTypeFilterOptions(data) {
    if (!data) return '';
    const types = new Set();
    (data.workflows || []).forEach(w => types.add('Workflow'));
    (data.mails || []).forEach(m => types.add(m.type || 'Letter'));
    (data.rfis || []).forEach(r => types.add(r.type || 'RFI'));
    (data.scrs || []).forEach(s => types.add('SCR'));
    return Array.from(types).sort().map(t => `<option value="${t}">${t}</option>`).join('');
}

function onCtrlTypeFilterChange(type) {
    ctrlTableTypeFilter = type;
    ctrlTablePage = 1;
    renderCtrlTable();
}

function ctrlSelectAll(sel) {
    if (!ctrlActiveReport) return;
    if (sel) {
        (ctrlActiveReport.workflows || []).forEach(w => ctrlSelectedKeys.add(`Workflow:${w.workflow_no}`));
        (ctrlActiveReport.mails || []).forEach(m => ctrlSelectedKeys.add(`Letter:${m.mail_no}`));
        (ctrlActiveReport.rfis || []).forEach(r => ctrlSelectedKeys.add(`RFI:${r.rfi_no || r.mail_no}`));
        (ctrlActiveReport.scrs || []).forEach(s => ctrlSelectedKeys.add(`SCR:${s.mail_no}`));
    } else {
        ctrlSelectedKeys.clear();
    }
    updateCtrlStateAndUI();
}

function ctrlInvertSelection() {
    if (!ctrlActiveReport) return;
    const all = [];
    (ctrlActiveReport.workflows || []).forEach(w => all.push(`Workflow:${w.workflow_no}`));
    (ctrlActiveReport.mails || []).forEach(m => all.push(`Letter:${m.mail_no}`));
    (ctrlActiveReport.rfis || []).forEach(r => all.push(`RFI:${r.rfi_no || r.mail_no}`));
    (ctrlActiveReport.scrs || []).forEach(s => all.push(`SCR:${s.mail_no}`));

    all.forEach(k => {
        if (ctrlSelectedKeys.has(k)) ctrlSelectedKeys.delete(k);
        else ctrlSelectedKeys.add(k);
    });
    updateCtrlStateAndUI();
}

function toggleCtrlMasterCheckbox(checked) {
    const items = getCtrlFilteredItems();
    items.forEach(it => {
        if (checked) ctrlSelectedKeys.add(it.key);
        else ctrlSelectedKeys.delete(it.key);
    });
    updateCtrlStateAndUI();
}

function getCtrlFilteredItems() {
    if (!ctrlActiveReport) return [];
    const list = [];
    (ctrlActiveReport.workflows || []).forEach(w => {
        list.push({
            key: `Workflow:${w.workflow_no}`, type: 'Workflow',
            ref: w.workflow_no, doc_no: w.document_no || '-',
            title: w.document_title || w.workflow_name || '-',
            step_info: `${w.step_name || 'Review'} (${w.assigned_to_organization || w.assigned_org || '-'})`,
            due_date: w.due_date || w.date_due || '-', days_late: w.days_late || 0,
            aconex_url: w.aconex_url, doc_aconex_url: w.doc_aconex_url || w.aconex_url, sec: 'workflows'
        });
    });
    (ctrlActiveReport.mails || []).forEach(m => {
        list.push({
            key: `Letter:${m.mail_no}`, type: m.type || 'Letter',
            ref: m.mail_no, doc_no: m.reference_number || '-',
            title: m.subject || '-',
            step_info: `From ${m.from_organization || m.from_org || '-'} to ${m.to_organization || m.to_org || '-'}`,
            due_date: m.due_date || '-', days_late: m.days_late || 0,
            aconex_url: m.aconex_url, sec: 'mail'
        });
    });
    (ctrlActiveReport.rfis || []).forEach(r => {
        list.push({
            key: `RFI:${r.rfi_no || r.mail_no}`, type: r.type || 'RFI',
            ref: r.rfi_no || r.mail_no, doc_no: r.reference_number || '-',
            title: r.subject || '-',
            step_info: `Originator: ${r.from_organization || r.from_org || '-'}`,
            due_date: r.due_date || '-', days_late: r.days_late || 0,
            aconex_url: r.aconex_url, sec: 'rfis'
        });
    });
    (ctrlActiveReport.scrs || []).forEach(s => {
        list.push({
            key: `SCR:${s.mail_no}`, type: 'SCR',
            ref: s.mail_no, doc_no: s.reference_number || '-',
            title: s.subject || '-',
            step_info: s.step_info || `To Consultant: ${s.to_org || 'ECG'} (Response Pending)`,
            due_date: s.due_date || '-', days_late: s.days_late || 0,
            aconex_url: s.aconex_url, sec: 'scrs'
        });
    });

    return list.filter(it => {
        if (ctrlTableCategory !== 'all') {
            if (ctrlTableCategory === 'workflows' && it.sec !== 'workflows') return false;
            if (ctrlTableCategory === 'mail' && it.sec !== 'mail') return false;
            if (ctrlTableCategory === 'rfis' && it.sec !== 'rfis') return false;
            if (ctrlTableCategory === 'scrs' && it.sec !== 'scrs') return false;
        }
        if (ctrlTableTypeFilter) {
            if (it.type !== ctrlTableTypeFilter) return false;
        }
        if (ctrlTableSearchQuery) {
            const str = `${it.ref} ${it.doc_no} ${it.title} ${it.step_info}`.toLowerCase();
            if (!str.includes(ctrlTableSearchQuery)) return false;
        }
        return true;
    });
}

function renderCtrlTable() {
    const tbody = document.getElementById('ctrl-table-body');
    if (!tbody) return;

    const items = getCtrlFilteredItems();
    const total = items.length;
    const start = (ctrlTablePage - 1) * ctrlTablePageSize;
    const paged = items.slice(start, start + ctrlTablePageSize);

    const infoEl = document.getElementById('ctrl-table-page-info');
    if (infoEl) infoEl.innerText = `Showing ${total === 0 ? 0 : start + 1} - ${Math.min(total, start + ctrlTablePageSize)} of ${total}`;

    const prevBtn = document.getElementById('ctrl-btn-prev-page');
    const nextBtn = document.getElementById('ctrl-btn-next-page');
    if (prevBtn) prevBtn.disabled = ctrlTablePage <= 1;
    if (nextBtn) nextBtn.disabled = (start + ctrlTablePageSize) >= total;

    if (paged.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-slate-500">No overdue items match filters</td></tr>';
        return;
    }

    tbody.innerHTML = paged.map(it => {
        const isSelected = ctrlSelectedKeys.has(it.key);
        const typeBg = it.type === 'Workflow' ? 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30' :
                       (it.type === 'Letter' ? 'bg-sky-500/20 text-sky-400 border-sky-500/30' :
                       (it.type === 'SCR' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border-amber-500/30'));

        return `
            <tr class="hover:bg-slate-800/40 transition ${isSelected ? '' : 'opacity-40'}">
                <td class="p-3 text-center">
                    <input type="checkbox" onchange="toggleCtrlItemSelection('${it.key}')" ${isSelected ? 'checked' : ''} class="w-3.5 h-3.5 rounded text-rose-600 bg-slate-900 border-slate-700 cursor-pointer">
                </td>
                <td class="p-3">
                    <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${typeBg}">${it.type}</span>
                </td>
                <td class="p-3">
                    <a href="${it.aconex_url}" target="_blank" class="font-mono font-bold text-sky-400 hover:underline">
                        ${it.ref}
                    </a>
                </td>
                <td class="p-3 font-mono text-slate-300 text-xs">${it.doc_no && it.doc_no !== '-' && (it.doc_aconex_url || it.aconex_url) ? `<a href="${it.doc_aconex_url || it.aconex_url}" target="_blank" class="text-sky-300 hover:underline font-semibold" title="Open Document in Aconex">${it.doc_no}</a>` : it.doc_no}</td>
                <td class="p-3 text-slate-200 font-medium">${it.title}</td>
                <td class="p-3 text-slate-400 text-xs">${it.step_info}</td>
                <td class="p-3 font-mono text-slate-400 text-xs whitespace-nowrap">${formatAppDate(it.due_date)}</td>
                <td class="p-3">
                    <span class="px-2 py-0.5 rounded font-mono font-bold text-[10px] bg-rose-500/20 text-rose-400 border border-rose-500/30">
                        +${it.days_late}d
                    </span>
                </td>
            </tr>
        `;
    }).join('');
}

function updateCtrlStateAndUI() {
    renderCtrlTable();
    updateCtrlLiveEmailPreview();
}

function updateCtrlLiveEmailPreview() {
    if (!ctrlActiveReport) return;
    const activeWf = ctrlSectionScope.workflows ? (ctrlActiveReport.workflows || []).filter(w => ctrlSelectedKeys.has('Workflow:' + w.workflow_no)) : [];
    const activeMails = ctrlSectionScope.mail ? (ctrlActiveReport.mails || []).filter(m => ctrlSelectedKeys.has('Letter:' + m.mail_no)) : [];
    const activeRfis = ctrlSectionScope.rfis ? (ctrlActiveReport.rfis || []).filter(r => ctrlSelectedKeys.has('RFI:' + (r.rfi_no || r.mail_no))) : [];
    const activeScrs = ctrlSectionScope.scrs ? (ctrlActiveReport.scrs || []).filter(s => ctrlSelectedKeys.has('SCR:' + s.mail_no)) : [];
    const totalActive = activeWf.length + activeMails.length + activeRfis.length + activeScrs.length;

    const badge = document.getElementById('ctrl-scope-summary-badge');
    if (badge) badge.innerText = `${totalActive} Deliverables Active`;

    const setCnt = (id, str) => { const el = document.getElementById(id); if (el) el.innerText = str; };
    setCnt('ctrl-scope-wf-count', `${activeWf.length} included`);
    setCnt('ctrl-scope-mail-count', `${activeMails.length} included`);
    setCnt('ctrl-scope-rfis-count', `${activeRfis.length} included`);
    setCnt('ctrl-scope-scrs-count', `${activeScrs.length} included`);

    const subjEl = document.getElementById('ctrl-email-preview-subject');
    if (subjEl) subjEl.innerText = `[OVERDUE NOTICE] ${ctrlActiveReport.project_title} (${ctrlActiveReport.k_package_no || ctrlActiveReport.project_id}) - ${totalActive} Deliverables Overdue`;

    const bodyEl = document.getElementById('ctrl-email-preview-body');
    if (bodyEl) {
        bodyEl.innerHTML = generateEmailHtml(ctrlActiveReport, activeWf, activeMails, activeRfis, activeScrs);
    }
}

function generateEmailHtml(report, wfs, mails, rfis, scrs = []) {
    const toStr = (report.to_emails || []).join(', ') || 'Document Controllers';
    const ccStr = (report.cc_emails || []).join(', ') || 'Supervision & Hill PMC';
    const nowStr = new Date().toLocaleString('en-GB');

    let html = `
        <div style="font-family: Arial, sans-serif; max-width: 850px; margin: 0 auto; color: #0f172a;">
            <div style="background: #0f172a; color: white; padding: 20px; border-radius: 8px;">
                <div style="font-size: 11px; color: #38bdf8; font-weight: bold;">RAS EL HEKMA PROJECT CONTROLS</div>
                <h2 style="margin: 5px 0 0 0;">OFFICIAL OVERDUE DELIVERABLES NOTICE</h2>
                <div style="font-size: 12px; color: #94a3b8; margin-top: 5px;">Package: ${report.project_title} (${report.k_package_no || report.project_id})</div>
            </div>
            <div style="background: #f8fafc; padding: 12px 20px; border: 1px solid #e2e8f0; font-size: 12px; margin-bottom: 20px;">
                <div><strong>TO:</strong> ${toStr}</div>
                <div style="margin-top: 4px;"><strong>CC:</strong> ${ccStr}</div>
            </div>
            <p style="font-size: 13px;">Dear Teams, according to Oracle Aconex project controls records generated on <strong>${nowStr}</strong>, the following deliverables have exceeded turnaround limits:</p>
    `;

    if (wfs.length > 0) {
        html += `<h3 style="font-size: 14px; border-bottom: 2px solid #0f172a; padding-bottom: 4px;">1. Review Workflows (${wfs.length})</h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 15px;">
            <tr style="background: #1e293b; color: white;"><th style="padding: 6px; text-align: left;">Workflow No</th><th style="padding: 6px; text-align: left;">Document No</th><th style="padding: 6px; text-align: left;">Title</th><th style="padding: 6px; text-align: left;">Assignee</th><th style="padding: 6px;">Due</th><th style="padding: 6px;">Late</th></tr>`;
        wfs.forEach(w => {
            const docUrl = w.doc_aconex_url || w.aconex_url;
            const docCell = w.document_no && w.document_no !== '-' ? `<a href="${docUrl}" target="_blank" style="color: #0284c7; font-weight: bold; text-decoration: underline;">${w.document_no}</a>` : '-';
            html += `<tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 6px;"><a href="${w.aconex_url}" target="_blank" style="color: #0284c7; font-weight: bold;">${w.workflow_no}</a></td><td style="padding: 6px; font-family: monospace;">${docCell}</td><td style="padding: 6px;">${w.document_title || w.workflow_name || '-'}</td><td style="padding: 6px;">${w.assigned_to_organization || w.assigned_org || '-'}</td><td style="padding: 6px; text-align: center;">${w.due_date || '-'}</td><td style="padding: 6px; text-align: center; color: #dc2626; font-weight: bold;">+${w.days_late || 0}d</td></tr>`;
        });
        html += `</table>`;
    }

    if (mails.length > 0) {
        html += `<h3 style="font-size: 14px; border-bottom: 2px solid #0f172a; padding-bottom: 4px;">2. Official Letters (${mails.length})</h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 15px;">
            <tr style="background: #1e293b; color: white;"><th style="padding: 6px; text-align: left;">Mail No</th><th style="padding: 6px; text-align: left;">Subject</th><th style="padding: 6px; text-align: left;">From / To</th><th style="padding: 6px;">Due</th><th style="padding: 6px;">Late</th></tr>`;
        mails.forEach(m => {
            html += `<tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 6px;"><a href="${m.aconex_url}" style="color: #0284c7; font-weight: bold;">${m.mail_no}</a></td><td style="padding: 6px;">${m.subject || '-'}</td><td style="padding: 6px;">${m.from_organization || m.from_org || '-'} &rarr; ${m.to_organization || m.to_org || '-'}</td><td style="padding: 6px; text-align: center;">${m.due_date || '-'}</td><td style="padding: 6px; text-align: center; color: #dc2626; font-weight: bold;">+${m.days_late || 0}d</td></tr>`;
        });
        html += `</table>`;
    }

    if (rfis.length > 0) {
        const isDP01 = report.project_id === 'DP01';
        const secTitle = isDP01 ? `3. Site Clarification Requests / Responses (${rfis.length})` : `3. Technical RFIs (${rfis.length})`;
        const colTitle = isDP01 ? 'SCR / RTCL No' : 'RFI No';
        html += `<h3 style="font-size: 14px; border-bottom: 2px solid #0f172a; padding-bottom: 4px;">${secTitle}</h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 15px;">
            <tr style="background: #1e293b; color: white;"><th style="padding: 6px; text-align: left;">${colTitle}</th><th style="padding: 6px; text-align: left;">Subject</th><th style="padding: 6px; text-align: left;">From Org</th><th style="padding: 6px;">Due</th><th style="padding: 6px;">Late</th></tr>`;
        rfis.forEach(r => {
            html += `<tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 6px;"><a href="${r.aconex_url}" style="color: #0284c7; font-weight: bold;">${r.rfi_no || r.mail_no}</a></td><td style="padding: 6px;">${r.subject || '-'}</td><td style="padding: 6px;">${r.from_organization || r.from_org || '-'}</td><td style="padding: 6px; text-align: center;">${r.due_date || '-'}</td><td style="padding: 6px; text-align: center; color: #dc2626; font-weight: bold;">+${r.days_late || 0}d</td></tr>`;
        });
        html += `</table>`;
    }

    if (scrs && scrs.length > 0) {
        html += `<h3 style="font-size: 14px; border-bottom: 2px solid #0f172a; padding-bottom: 4px;">4. Site Clarification Requests (SCR) - Overdue on Consultants (${scrs.length})</h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 11px; margin-bottom: 15px;">
            <tr style="background: #1e293b; color: white;"><th style="padding: 6px; text-align: left;">SCR No</th><th style="padding: 6px; text-align: left;">Subject</th><th style="padding: 6px; text-align: left;">Assigned Consultant</th><th style="padding: 6px;">Due</th><th style="padding: 6px;">Late</th></tr>`;
        scrs.forEach(s => {
            html += `<tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 6px;"><a href="${s.aconex_url}" style="color: #059669; font-weight: bold;">${s.mail_no}</a></td><td style="padding: 6px;">${s.subject || '-'}</td><td style="padding: 6px; font-weight: bold; color: #0284c7;">${s.to_organization || s.to_org || 'ECG'}</td><td style="padding: 6px; text-align: center;">${s.due_date || '-'}</td><td style="padding: 6px; text-align: center; color: #dc2626; font-weight: bold;">+${s.days_late || 0}d</td></tr>`;
        });
        html += `</table>`;
    }

    html += `
        <div style="background: #fffbeb; border: 1px solid #fde68a; padding: 12px; font-size: 11px; color: #92400e; margin-top: 20px;">
            <strong>ACTION REQUIRED:</strong> Please resolve pending action items in Oracle Aconex before the end of the current working week.
        </div>
    </div>`;

    return html;
}

// 10. EML & Excel Dispatch Actions
function buildCtrlExportPayload() {
    if (!ctrlActiveReport) return {};
    const wfList = (ctrlActiveReport.workflows || []).filter(w => ctrlSelectedKeys.has('Workflow:' + w.workflow_no)).map(w => w.workflow_no);
    const mailList = (ctrlActiveReport.mails || []).filter(m => ctrlSelectedKeys.has('Letter:' + m.mail_no)).map(m => m.mail_no);
    const rfiList = (ctrlActiveReport.rfis || []).filter(r => ctrlSelectedKeys.has('RFI:' + (r.rfi_no || r.mail_no))).map(r => r.rfi_no || r.mail_no);
    const scrsList = (ctrlActiveReport.scrs || []).filter(s => ctrlSelectedKeys.has('SCR:' + s.mail_no)).map(s => s.mail_no);

    return {
        include_workflows: !!ctrlSectionScope.workflows,
        include_mails: !!ctrlSectionScope.mail,
        include_rfis: !!ctrlSectionScope.rfis,
        include_scrs: !!ctrlSectionScope.scrs,
        selected_workflows: wfList,
        selected_mails: mailList,
        selected_rfis: rfiList,
        selected_scrs: scrsList,
        to_emails: ctrlActiveReport.to_emails || [],
        cc_emails: ctrlActiveReport.cc_emails || [],
        from_date: (document.getElementById('ctrl-ssc-from-date')?.value || '').trim() || null,
        to_date: (document.getElementById('ctrl-ssc-to-date')?.value || '').trim() || null
    };
}

async function copyCtrlHtmlEmail() {
    const bodyEl = document.getElementById('ctrl-email-preview-body');
    if (!bodyEl) return;
    const htmlToCopy = bodyEl.innerHTML;

    try {
        const blobHtml = new Blob([htmlToCopy], { type: 'text/html' });
        const blobText = new Blob([htmlToCopy.replace(/<[^>]+>/g, ' ')], { type: 'text/plain' });
        const item = new ClipboardItem({ 'text/html': blobHtml, 'text/plain': blobText });
        await navigator.clipboard.write([item]);
        showToast('HTML Email table copied to clipboard! Paste directly into Outlook.', 'success');
    } catch (e) {
        navigator.clipboard.writeText(htmlToCopy);
        showToast('HTML code copied to clipboard.', 'info');
    }
}

async function openCtrlOutlookDraftWithAttachment() {
    if (!ctrlActiveReport || !ctrlActiveReport.project_id) return;
    const pid = ctrlActiveReport.project_id;
    const payload = buildCtrlExportPayload();
    showToast('Generating Outlook draft with attached Excel...', 'info');

    try {
        const res = await fetch(`/api/controls/projects/${encodeURIComponent(pid)}/download_eml`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `OVERDUE_NOTICE_${pid}.eml`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('Outlook draft downloaded! Open file to launch Outlook.', 'success');
    } catch (err) {
        showToast(`Failed to generate draft: ${err.message}`, 'error');
    }
}

async function exportCtrlOverdueExcel() {
    if (!ctrlActiveReport || !ctrlActiveReport.project_id) return;
    const pid = ctrlActiveReport.project_id;
    const payload = buildCtrlExportPayload();
    showToast('Downloading Excel overdue register...', 'info');

    try {
        const res = await fetch(`/api/controls/projects/${encodeURIComponent(pid)}/export_overdue_excel`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `OVERDUE_REGISTER_${pid}.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast('Excel register downloaded successfully!', 'success');
    } catch (err) {
        showToast(`Export failed: ${err.message}`, 'error');
    }
}

function copyCtrlRecipients(type) {
    if (!ctrlActiveReport) return;
    const list = type === 'to' ? (ctrlActiveReport.to_emails || []) : (ctrlActiveReport.cc_emails || []);
    if (!list.length) { showToast(`No ${type.toUpperCase()} emails registered`, 'info'); return; }
    navigator.clipboard.writeText(list.join('; '));
    showToast(`Copied ${list.length} ${type.toUpperCase()} recipient(s) to clipboard!`, 'success');
}

// 11. Modal Timelines (Letters & RFIs)
async function openLetterThreadModal(mailNo, refNo = '') {
    const modal = document.getElementById('modal-rfi-thread');
    const body = document.getElementById('modal-th-body');
    if (!modal) return;
    modal.classList.remove('hidden');

    const pkg = activeProjectData?.info?.k_package_no || activeProjectData?.info?.project_id || 'Hill & SSC Direct';
    document.getElementById('modal-th-title').textContent = mailNo;
    const refBadge = document.getElementById('modal-th-ref');
    if (refBadge) {
        refBadge.textContent = `Ref: ${refNo || mailNo}`;
        refBadge.classList.remove('hidden');
    }
    document.getElementById('modal-th-subj').textContent = 'Loading correspondence thread & actions...';
    document.getElementById('modal-th-pkg').textContent = pkg;

    // Hide RFI filter pills toolbar when viewing letters
    const filterToolbar = document.getElementById('th-filter-toolbar');
    if (filterToolbar) filterToolbar.classList.add('hidden');

    // Reset badges while loading
    const statusBadge = document.getElementById('modal-th-status-badge');
    if (statusBadge) statusBadge.className = 'hidden';
    const turnaroundEl = document.getElementById('modal-th-turnaround');
    if (turnaroundEl) turnaroundEl.textContent = 'Calculating timeline...';
    const partiesEl = document.getElementById('modal-th-parties');
    if (partiesEl) partiesEl.textContent = 'Mapping correspondence parties...';

    body.innerHTML = `
        <div class="py-16 text-center text-slate-400">
            <div class="inline-block animate-spin w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full mb-3"></div>
            <p class="text-sm font-semibold text-slate-300">Tracing correspondence history, references & responses...</p>
            <p class="text-xs text-slate-500 mt-1">Cross-referencing incoming/outgoing letters & actions</p>
        </div>
    `;

    try {
        const res = await fetch(`/api/mail/thread?mail_no=${encodeURIComponent(mailNo)}&reference_number=${encodeURIComponent(refNo)}`);
        const data = await res.json();

        document.getElementById('modal-th-title').textContent = data.mail_no || mailNo;
        if (refBadge) {
            refBadge.textContent = `Ref: ${data.reference_number || refNo || '-'}`;
            refBadge.classList.remove('hidden');
        }
        document.getElementById('modal-th-subj').textContent = data.subject || 'No Subject';
        if (data.project_package) {
            document.getElementById('modal-th-pkg').textContent = data.project_package;
        }
        const aconexLink = document.getElementById('modal-th-aconex-link');
        if (aconexLink) {
            aconexLink.href = data.aconex_url || '#';
        }

        // Header Metrics
        if (statusBadge) {
            statusBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold font-mono border';
            const st = (data.status || 'Open').toLowerCase();
            if (st.includes('closed') || st.includes('responded')) {
                statusBadge.classList.add('bg-emerald-500/20', 'text-emerald-300', 'border-emerald-500/30');
            } else if (st.includes('overdue')) {
                statusBadge.classList.add('bg-rose-500/20', 'text-rose-300', 'border-rose-500/30');
            } else {
                statusBadge.classList.add('bg-purple-500/20', 'text-purple-300', 'border-purple-500/30');
            }
            statusBadge.textContent = data.status || 'Open';
        }

        if (turnaroundEl) {
            turnaroundEl.textContent = `${data.turnaround_days || 0} days turnaround`;
        }
        if (partiesEl) {
            partiesEl.textContent = `${data.parties_count || 1} parties involved`;
        }

        const steps = data.thread_steps || [];
        if (steps.length === 0) {
            body.innerHTML = `
                <div class="py-12 text-center text-slate-500 bg-slate-950/40 rounded-xl border border-slate-800">
                    <i data-lucide="inbox" class="w-8 h-8 mx-auto mb-2 opacity-40"></i>
                    <p class="text-xs">No linked correspondence steps found.</p>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
            return;
        }

        let html = '<div class="space-y-4 relative before:absolute before:inset-0 before:left-5 before:w-0.5 before:bg-slate-800">';
        steps.forEach((s, idx) => {
            const isTarget = s.mail_no === mailNo;
            const targetRing = isTarget ? 'ring-2 ring-purple-500/80 bg-purple-950/10' : '';
            const aconexUrl = s.aconex_url || `https://mea.aconex.com/authentication/index.html?Action=View&MENU_TARGET=MAIL-SEARCH&ENTITY=PROJECT&ID=1744833878&searchQuery=mailNumber%3A${encodeURIComponent(s.mail_no)}`;
            
            html += `
                <div class="relative pl-12">
                    <!-- Timeline Node -->
                    <div class="absolute left-3 top-4 -translate-x-1/2 w-6 h-6 rounded-full bg-slate-900 border-2 ${isTarget ? 'border-purple-400 bg-purple-500/30 text-purple-200' : 'border-slate-700 text-slate-400'} flex items-center justify-center text-[10px] font-bold font-mono shadow-sm">
                        ${s.step_number || (idx + 1)}
                    </div>

                    <!-- Step Content Card -->
                    <div class="bg-slate-950/80 p-4 rounded-xl border border-slate-800/80 hover:border-slate-700 space-y-2.5 transition shadow-sm ${targetRing}">
                        <div class="flex flex-wrap items-center justify-between gap-2 text-xs">
                            <div class="flex items-center gap-2">
                                <a href="${aconexUrl}" target="_blank" class="font-bold text-sky-400 hover:text-sky-300 hover:underline font-mono text-sm flex items-center gap-1.5" title="Open in Aconex">
                                    <span>${s.mail_no}</span>
                                    <i data-lucide="external-link" class="w-3 h-3 opacity-60"></i>
                                </a>
                                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">${s.mail_type || 'Letter'}</span>
                                ${s.action_taken ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-${s.badge_color || 'purple'}-500/10 text-${s.badge_color || 'purple'}-400 border border-${s.badge_color || 'purple'}-500/20">${s.action_taken}</span>` : ''}
                            </div>
                            <div class="flex items-center gap-2 font-mono text-slate-400 text-[11px]">
                                <i data-lucide="calendar" class="w-3.5 h-3.5 text-slate-500"></i>
                                <span>${formatAppDate(s.sent_date)}</span>
                                ${s.days_from_start > 0 ? `<span class="text-slate-500">(+${s.days_from_start}d)</span>` : ''}
                            </div>
                        </div>

                        <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
                            <div>From: <strong class="text-slate-200">${s.from_org}</strong>${s.from_name ? ` <span class="text-slate-500">(${s.from_name})</span>` : ''}</div>
                            <span class="text-slate-700">➔</span>
                            <div>To: <strong class="text-slate-200">${s.to_org}</strong></div>
                            ${s.reference_number && s.reference_number !== s.mail_no ? `<span class="text-slate-600">•</span><div>Ref: <span class="font-mono text-slate-300">${s.reference_number}</span></div>` : ''}
                        </div>

                        <div class="text-xs font-medium text-slate-200 leading-relaxed bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/50">
                            ${s.subject || '-'}
                        </div>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        body.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        body.innerHTML = `<div class="text-rose-400 py-8 text-center font-bold">Error loading letter thread: ${err.message}</div>`;
    }
}

let currentRfiThreadSteps = [];
let currentRfiThreadFilter = 'all';

async function openRfiThreadModal(mailNo) {
    const modal = document.getElementById('modal-rfi-thread');
    const body = document.getElementById('modal-th-body');
    if (!modal) return;
    modal.classList.remove('hidden');

    const pkg = activeProjectData?.info?.k_package_no || activeProjectData?.info?.project_id || 'Project';
    document.getElementById('modal-th-title').textContent = mailNo;
    const refBadge = document.getElementById('modal-th-ref');
    if (refBadge) refBadge.classList.add('hidden');
    document.getElementById('modal-th-subj').textContent = 'Loading RFI response thread...';
    document.getElementById('modal-th-pkg').textContent = pkg;

    // Show RFI filter pills toolbar
    const filterToolbar = document.getElementById('th-filter-toolbar');
    if (filterToolbar) filterToolbar.classList.remove('hidden');

    // Reset badges while loading
    const statusBadge = document.getElementById('modal-th-status-badge');
    if (statusBadge) statusBadge.className = 'hidden';
    const turnaroundEl = document.getElementById('modal-th-turnaround');
    if (turnaroundEl) turnaroundEl.textContent = 'Calculating turnaround...';
    const partiesEl = document.getElementById('modal-th-parties');
    if (partiesEl) partiesEl.textContent = 'Analyzing communication parties...';

    body.innerHTML = `
        <div class="py-16 text-center text-slate-400">
            <div class="inline-block animate-spin w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full mb-3"></div>
            <p class="text-sm font-semibold text-slate-300">Tracing multi-party RFI communication chain...</p>
            <p class="text-xs text-slate-500 mt-1">Contractor ➔ PMC Coordination ➔ Consultant Advice ➔ Final Response</p>
        </div>
    `;

    try {
        const res = await fetch(`/api/rfi_explore/thread?mail_no=${encodeURIComponent(mailNo)}`);
        const data = await res.json();

        document.getElementById('modal-th-title').textContent = data.rfi_no || mailNo;
        document.getElementById('modal-th-subj').textContent = data.subject || 'No Subject';
        document.getElementById('modal-th-pkg').textContent = data.project_package || pkg;
        document.getElementById('modal-th-aconex-link').href = data.aconex_url || getAconexMailUrl(data);

        // Header Metrics
        if (statusBadge) {
            statusBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold font-mono border';
            const st = (data.status || 'Outstanding').toLowerCase();
            if (st.includes('closed') || st.includes('responded')) {
                statusBadge.classList.add('bg-emerald-500/20', 'text-emerald-300', 'border-emerald-500/30');
            } else if (st.includes('overdue')) {
                statusBadge.classList.add('bg-rose-500/20', 'text-rose-300', 'border-rose-500/30');
            } else {
                statusBadge.classList.add('bg-amber-500/20', 'text-amber-300', 'border-amber-500/30');
            }
            statusBadge.textContent = data.status || 'Outstanding';
        }

        if (turnaroundEl) {
            turnaroundEl.textContent = `${data.turnaround_days || 0} days turnaround`;
        }
        if (partiesEl) {
            partiesEl.textContent = `${data.parties_count || 1} parties involved`;
        }

        currentRfiThreadSteps = data.thread_steps || [];

        // Count category breakdown for filter pills
        const cntAll = currentRfiThreadSteps.length;
        const cntInitiator = currentRfiThreadSteps.filter(s => s.category === 'initiator').length;
        const cntConsultant = currentRfiThreadSteps.filter(s => s.category === 'consultant').length;
        const cntInternal = currentRfiThreadSteps.filter(s => s.category === 'internal_hill').length;
        const cntResponse = currentRfiThreadSteps.filter(s => s.category === 'response').length;

        const elCntAll = document.getElementById('th-cnt-all');
        if (elCntAll) elCntAll.textContent = cntAll;
        const elCntInit = document.getElementById('th-cnt-initiator');
        if (elCntInit) elCntInit.textContent = cntInitiator;
        const elCntCons = document.getElementById('th-cnt-consultant');
        if (elCntCons) elCntCons.textContent = cntConsultant;
        const elCntInt = document.getElementById('th-cnt-internal_hill');
        if (elCntInt) elCntInt.textContent = cntInternal;
        const elCntResp = document.getElementById('th-cnt-response');
        if (elCntResp) elCntResp.textContent = cntResponse;

        filterRfiThreadSteps('all');
    } catch (err) {
        body.innerHTML = `<div class="text-rose-400 py-8 text-center">Error loading thread: ${err.message}</div>`;
    }
}

function filterRfiThreadSteps(category = 'all') {
    currentRfiThreadFilter = category;
    const body = document.getElementById('modal-th-body');
    if (!body) return;

    // Update Pill Buttons Styling
    const pills = [
        { id: 'th-filter-btn-all', cat: 'all' },
        { id: 'th-filter-btn-initiator', cat: 'initiator' },
        { id: 'th-filter-btn-consultant', cat: 'consultant' },
        { id: 'th-filter-btn-internal_hill', cat: 'internal_hill' },
        { id: 'th-filter-btn-response', cat: 'response' }
    ];

    pills.forEach(p => {
        const btn = document.getElementById(p.id);
        if (btn) {
            if (p.cat === category) {
                btn.className = 'th-filter-pill px-2.5 py-1 rounded-lg bg-sky-600 text-white font-bold transition';
            } else {
                btn.className = 'th-filter-pill px-2.5 py-1 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 font-semibold transition';
            }
        }
    });

    const filtered = (category === 'all')
        ? currentRfiThreadSteps
        : currentRfiThreadSteps.filter(s => s.category === category);

    if (filtered.length === 0) {
        body.innerHTML = `
            <div class="py-12 text-center text-slate-500 bg-slate-950/40 rounded-xl border border-slate-800">
                <i data-lucide="inbox" class="w-8 h-8 mx-auto mb-2 opacity-40"></i>
                <p class="text-xs">No correspondence steps match category "<strong>${category}</strong>".</p>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    let html = '<div class="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-800">';
    filtered.forEach(s => {
        const aconexLink = s.aconex_url || getAconexMailUrl(s);
        
        // Determine border and accent styling by category
        let cardBorder = 'border-slate-800 bg-slate-950/80';
        let phaseBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">Correspondence</span>';
        let stepDotColor = 'bg-slate-500';

        if (s.category === 'initiator') {
            cardBorder = 'border-blue-500/40 bg-blue-950/15 border-l-4 border-l-blue-500';
            phaseBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">1. Initiator Request</span>';
            stepDotColor = 'bg-blue-400';
        } else if (s.category === 'internal_hill') {
            cardBorder = 'border-sky-500/40 bg-sky-950/20 border-l-4 border-l-sky-500';
            phaseBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30">Internal Hill Coordination</span>';
            stepDotColor = 'bg-sky-400';
        } else if (s.category === 'consultant') {
            cardBorder = 'border-purple-500/40 bg-purple-950/20 border-l-4 border-l-purple-500';
            phaseBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">${s.phase || 'Consultant Advice'}</span>`;
            stepDotColor = 'bg-purple-400';
        } else if (s.category === 'response') {
            cardBorder = 'border-emerald-500/40 bg-emerald-950/20 border-l-4 border-l-emerald-500';
            phaseBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">4. Official PMC Response</span>';
            stepDotColor = 'bg-emerald-400';
        }

        const statusBadge = getRfiStatusBadge(s.status, s.status === 'Overdue');
        const daysBadge = s.days_from_start > 0 ? `<span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-800 text-slate-300 border border-slate-700">+${s.days_from_start}d turnaround</span>` : '';

        html += `
            <div class="relative">
                <div class="absolute -left-6 top-3 w-3 h-3 rounded-full ${stepDotColor} ring-4 ring-slate-900"></div>
                <div class="rounded-xl border ${cardBorder} p-4 space-y-3 shadow-lg">
                    <div class="flex flex-wrap items-center justify-between gap-2">
                        <div class="flex flex-wrap items-center gap-2">
                            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-900 text-slate-400 border border-slate-800">Step #${s.step_number}</span>
                            ${phaseBadge}
                            <a href="${aconexLink}" target="_blank" class="font-mono font-bold text-sky-400 hover:underline text-xs flex items-center gap-1">
                                <span>${s.mail_no}</span>
                                <i data-lucide="external-link" class="w-3 h-3"></i>
                            </a>
                            <span class="px-1.5 py-0.5 rounded text-[10px] font-mono text-slate-400 bg-slate-900 border border-slate-800">${s.mail_type}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            ${daysBadge}
                            ${statusBadge}
                            <span class="text-xs font-mono text-slate-400 whitespace-nowrap">${formatAppDate(s.sent_date)}</span>
                        </div>
                    </div>

                    <div class="text-xs text-slate-300 bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/80 flex flex-wrap items-center justify-between gap-2">
                        <div>From: <strong class="text-white">${s.from_org}</strong> <span class="text-slate-400">${s.from_name ? '(' + s.from_name + ')' : ''}</span></div>
                        <div class="text-slate-500">➔</div>
                        <div>To: <strong class="text-white">${s.to_org}</strong></div>
                    </div>

                    <div class="text-xs font-medium text-slate-100 leading-relaxed">
                        ${s.subject || '-'}
                    </div>
                </div>
            </div>
        `;
    });
    html += '</div>';

    body.innerHTML = html;
    if (window.lucide) lucide.createIcons();
}

function closeRfiThreadModal() {
    const modal = document.getElementById('modal-rfi-thread');
    if (modal) modal.classList.add('hidden');
}
window.openLetterThreadModal = openLetterThreadModal;
window.openRfiThreadModal = openRfiThreadModal;
window.closeRfiThreadModal = closeRfiThreadModal;
window.filterRfiThreadSteps = filterRfiThreadSteps;

function showToast(msg, type = 'info') {
    let box = document.getElementById('app-toast-box');
    if (!box) {
        box = document.createElement('div');
        box.id = 'app-toast-box';
        box.className = 'fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none';
        document.body.appendChild(box);
    }
    const t = document.createElement('div');
    const bg = type === 'success' ? 'bg-emerald-600 text-white' : (type === 'error' ? 'bg-rose-600 text-white' : 'bg-slate-800 text-slate-200 border border-slate-700');
    t.className = `${bg} pointer-events-auto px-4 py-2.5 rounded-xl shadow-2xl text-xs font-semibold`;
    t.innerText = msg;
    box.appendChild(t);
    setTimeout(() => t.remove(), 4000);
}

// ==========================================
// 12. HILL INTERNATIONAL PMC INTERNAL ACTIONS
// ==========================================
let hillAllEngineers = [];
let hillTeamData = [];
let hillActivePackage = 'all';
let hillViewMode = 'grid';
let hillPackageStats = {};
let activeHillDossier = null;

async function loadHillTeamControls(forceRefresh = false, targetPackage = null) {
    if (targetPackage !== null) {
        hillActivePackage = targetPackage;
    }

    const grid = document.getElementById('hill-engineers-grid');
    const tableBody = document.getElementById('hill-engineers-table-tbody');

    if (grid && (!hillTeamData.length || forceRefresh)) {
        grid.innerHTML = `
            <div class="col-span-full py-16 text-center text-slate-400 bg-slate-900 rounded-2xl border border-slate-800">
                <div class="inline-block animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full mb-3"></div>
                <p class="text-sm font-semibold text-slate-300">Extracting Hill International direct action backlog &amp; SLAs...</p>
                <p class="text-xs text-slate-500 mt-1">Filtering direct review assignees &amp; addressees (Strictly excluding CC/FYI)</p>
            </div>
        `;
    }
    if (tableBody && (!hillTeamData.length || forceRefresh)) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="py-12 text-center text-slate-400">
                    <div class="inline-block animate-spin w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full mb-2"></div>
                    <p class="text-xs">Loading Hill review steps &amp; assignees...</p>
                </td>
            </tr>
        `;
    }

    try {
        let url = '/api/controls/hill_team';
        if (hillActivePackage && hillActivePackage !== 'all') {
            url += `?package=${encodeURIComponent(hillActivePackage)}`;
        }

        const res = await fetch(url);
        const json = await res.json();
        const incomingData = json.data || [];
        hillTeamData = incomingData;

        // If loading all packages, cache allEngineers and build package statistics
        if (hillActivePackage === 'all') {
            hillAllEngineers = incomingData;
            hillPackageStats = {};
            hillAllEngineers.forEach(e => {
                (e.packages || []).forEach(p => {
                    hillPackageStats[p] = (hillPackageStats[p] || 0) + 1;
                });
            });
            renderHillPackageOptionsAndPills();
        }

        // Calculate KPIs for currently active scope
        let totalOverdueSteps = 0;
        let totalCurrentSteps = 0;
        let totalOverdueMails = 0;

        hillTeamData.forEach(e => {
            totalOverdueSteps += (e.overdue_steps || 0);
            totalCurrentSteps += (e.current_steps || 0);
            totalOverdueMails += (e.overdue_mails || 0);
        });

        const totalActions = totalOverdueSteps + totalOverdueMails;

        // Update Stat Cards
        const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
        setTxt('stat-hill-total-engineers', hillTeamData.length.toLocaleString());
        setTxt('stat-hill-overdue-steps', totalOverdueSteps.toLocaleString());
        setTxt('stat-hill-current-steps', totalCurrentSteps.toLocaleString());
        setTxt('stat-hill-overdue-mails', totalOverdueMails.toLocaleString());

        // Update Sidebar Badge when global scope
        if (hillActivePackage === 'all') {
            const sideBadge = document.getElementById('badge-hill-internal-count');
            if (sideBadge) sideBadge.innerText = `${totalActions.toLocaleString()} Overdue`;
        }

        // Update active indicator
        const indicator = document.getElementById('hill-active-filter-indicator');
        if (indicator) {
            indicator.innerText = `Showing: ${hillTeamData.length} Engineer${hillTeamData.length === 1 ? '' : 's'} in ${hillActivePackage === 'all' ? 'All Projects' : hillActivePackage}`;
        }

        // Update package select value
        const pkgSelect = document.getElementById('hill-package-filter');
        if (pkgSelect && pkgSelect.value !== hillActivePackage) {
            pkgSelect.value = hillActivePackage;
        }

        // Update pills active state
        updateHillPackagePillsActiveState();

        filterHillTeamEngineers();
    } catch (err) {
        console.error('Error loading Hill team backlog:', err);
        if (grid) {
            grid.innerHTML = `
                <div class="col-span-full py-12 text-center text-rose-400 bg-rose-500/10 rounded-2xl border border-rose-500/20 p-6">
                    <p class="font-bold">Error loading Hill team portfolio: ${err.message}</p>
                    <button onclick="loadHillTeamControls(true)" class="mt-4 px-4 py-2 bg-rose-600 text-white rounded-lg text-xs font-bold">Retry</button>
                </div>
            `;
        }
    }
}

function renderHillPackageOptionsAndPills() {
    const pkgSelect = document.getElementById('hill-package-filter');
    const pillsContainer = document.getElementById('hill-project-pills-container');

    const sortedPkgs = Object.keys(hillPackageStats).sort((a, b) => {
        return (hillPackageStats[b] || 0) - (hillPackageStats[a] || 0);
    });

    if (pkgSelect) {
        let optHtml = `<option value="all">All Packages (${hillAllEngineers.length} Engineers)</option>`;
        sortedPkgs.forEach(pkg => {
            const count = hillPackageStats[pkg] || 0;
            optHtml += `<option value="${pkg}">${pkg} (${count} Engineers)</option>`;
        });
        pkgSelect.innerHTML = optHtml;
        pkgSelect.value = hillActivePackage;
    }

    if (pillsContainer) {
        let pillsHtml = `
            <button type="button" onclick="selectHillPackage('all')" id="hill-pill-all" class="hill-pkg-pill px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${hillActivePackage === 'all' ? 'bg-emerald-600 text-white shadow-md' : 'bg-slate-950 text-slate-300 hover:bg-slate-800 border border-slate-800'}">
                <span>All Projects</span>
                <span class="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-900 text-emerald-300 font-mono">${hillAllEngineers.length}</span>
            </button>
        `;

        sortedPkgs.forEach(pkg => {
            const count = hillPackageStats[pkg] || 0;
            const isAct = hillActivePackage === pkg;
            pillsHtml += `
                <button type="button" onclick="selectHillPackage('${pkg}')" id="hill-pill-${encodeURIComponent(pkg)}" class="hill-pkg-pill px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${isAct ? 'bg-emerald-600 text-white shadow-md' : 'bg-slate-950 text-slate-300 hover:bg-slate-800 border border-slate-800'}">
                    <span>${pkg}</span>
                    <span class="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-900 text-slate-400 font-mono">${count}</span>
                </button>
            `;
        });
        pillsContainer.innerHTML = pillsHtml;
    }
}

function updateHillPackagePillsActiveState() {
    const pills = document.querySelectorAll('.hill-pkg-pill');
    pills.forEach(pill => {
        pill.className = 'hill-pkg-pill px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-950 text-slate-300 hover:bg-slate-800 border border-slate-800';
    });

    if (hillActivePackage === 'all') {
        const el = document.getElementById('hill-pill-all');
        if (el) el.className = 'hill-pkg-pill px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-emerald-600 text-white shadow-md';
    } else {
        const el = document.getElementById(`hill-pill-${encodeURIComponent(hillActivePackage)}`);
        if (el) el.className = 'hill-pkg-pill px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-emerald-600 text-white shadow-md';
    }
}

function selectHillPackage(pkg) {
    hillActivePackage = pkg;
    const pkgSelect = document.getElementById('hill-package-filter');
    if (pkgSelect) pkgSelect.value = pkg;
    loadHillTeamControls(true, pkg);
}

function onHillPackageFilterChange() {
    const pkg = document.getElementById('hill-package-filter')?.value || 'all';
    selectHillPackage(pkg);
}

function setHillViewMode(mode) {
    hillViewMode = mode;
    const btnGrid = document.getElementById('btn-hill-view-grid');
    const btnTable = document.getElementById('btn-hill-view-table');
    const gridCont = document.getElementById('hill-engineers-grid');
    const tableCont = document.getElementById('hill-engineers-table-container');

    if (mode === 'grid') {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5';
        if (gridCont) gridCont.classList.remove('hidden');
        if (tableCont) tableCont.classList.add('hidden');
    } else {
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm';
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5';
        if (tableCont) tableCont.classList.remove('hidden');
        if (gridCont) gridCont.classList.add('hidden');
    }

    filterHillTeamEngineers();
}

function filterHillTeamEngineers() {
    const sevFilter = document.getElementById('hill-severity-filter')?.value || 'all';
    const searchQ = (document.getElementById('hill-engineer-search')?.value || '').trim().toLowerCase();

    let filtered = hillTeamData.filter(eng => {
        const engName = eng.name || eng.engineer_name || '';
        const engPkgs = eng.packages || eng.top_packages || [];
        const engPosition = eng.position || eng.job_title || '';
        const engEmail = eng.email || '';

        // Severity Filter
        const directOverdue = (eng.overdue_steps || 0) + (eng.overdue_mails || 0);
        if (sevFilter === 'overdue_only' && directOverdue === 0) return false;
        if (sevFilter === 'critical' && directOverdue < 20) return false;

        // Search Query
        if (searchQ) {
            const str = `${engName} ${engEmail} ${engPosition} ${engPkgs.join(' ')}`.toLowerCase();
            if (!str.includes(searchQ)) return false;
        }

        return true;
    });

    // Sort: highest overdue first, then by current steps
    filtered.sort((a, b) => {
        const overdueA = (a.overdue_steps || 0) + (a.overdue_mails || 0);
        const overdueB = (b.overdue_steps || 0) + (b.overdue_mails || 0);
        if (overdueB !== overdueA) return overdueB - overdueA;
        return (b.current_steps || 0) - (a.current_steps || 0);
    });

    if (hillViewMode === 'table') {
        renderHillTeamTable(filtered);
    } else {
        renderHillTeamEngineers(filtered);
    }
}

function renderHillTeamTable(engineers) {
    const tbody = document.getElementById('hill-engineers-table-tbody');
    if (!tbody) return;

    if (!engineers.length) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="py-16 text-center text-slate-500 bg-slate-900/40">
                    <i data-lucide="user-x" class="w-10 h-10 mx-auto text-slate-600 mb-2"></i>
                    <p class="text-sm font-bold text-slate-400">No Hill engineers match the selected criteria</p>
                    <p class="text-xs text-slate-600 mt-1">Adjust project scope or search filter to view team roster</p>
                </td>
            </tr>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    let html = '';
    engineers.forEach((eng, idx) => {
        const engName = eng.name || eng.engineer_name || 'Hill User';
        const engPosition = eng.position || eng.job_title || 'PMC Engineer';
        const engPkgs = eng.packages || eng.top_packages || [];
        const directOverdue = (eng.overdue_steps || 0) + (eng.overdue_mails || 0);
        const hasOverdue = directOverdue > 0;
        const maxDelay = eng.max_delay_days || eng.max_step_delay || 0;
        const parts = engName.split(' ').filter(Boolean);
        const initials = parts.slice(0, 2).map(p => p[0]).join('').toUpperCase() || 'H';
        const safeEncName = encodeURIComponent(engName);

        const pkgBadges = engPkgs.slice(0, 3).map(pkg => `
            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-950 text-sky-400 border border-slate-800">
                ${pkg}
            </span>
        `).join('');

        const overdueBadge = hasOverdue
            ? `<span class="px-2.5 py-1 rounded-lg text-xs font-mono font-black bg-rose-500/20 text-rose-400 border border-rose-500/30">+${directOverdue} Late</span>`
            : `<span class="px-2.5 py-1 rounded-lg text-xs font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">On Track</span>`;

        const inSlaBadge = (eng.current_steps || 0) > 0
            ? `<span class="font-bold text-sky-400">${(eng.current_steps || 0).toLocaleString()} Active</span>`
            : `<span class="text-slate-500">0</span>`;

        html += `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="p-3">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-lg ${hasOverdue ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'} flex items-center justify-center font-bold text-xs flex-shrink-0">
                            ${initials}
                        </div>
                        <div class="min-w-0">
                            <div class="text-sm font-bold text-white hover:text-sky-400 transition cursor-pointer truncate" onclick="openHillDossier('${safeEncName}')" title="${engName}">
                                ${engName}
                            </div>
                            <div class="text-[11px] text-slate-400 font-mono truncate">${eng.email || 'No email registered'}</div>
                        </div>
                    </div>
                </td>
                <td class="p-3 text-slate-300 font-sans text-xs">${engPosition}</td>
                <td class="p-3">
                    <div class="flex items-center gap-1 flex-wrap">${pkgBadges || '<span class="text-slate-500 text-[11px]">General</span>'}</div>
                </td>
                <td class="p-3 text-center whitespace-nowrap">${overdueBadge}</td>
                <td class="p-3 text-center whitespace-nowrap">${inSlaBadge}</td>
                <td class="p-3 text-right font-mono ${maxDelay > 0 ? 'text-rose-400 font-bold' : 'text-emerald-400'} whitespace-nowrap">${maxDelay > 0 ? `+${maxDelay}d` : '0d'}</td>
                <td class="p-3 text-center">
                    <div class="inline-flex items-center gap-1.5">
                        <button onclick="openHillDossier('${safeEncName}')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-emerald-600 text-slate-200 hover:text-white text-xs font-bold flex items-center gap-1 border border-slate-700 transition" title="Open Action Dossier">
                            <i data-lucide="file-text" class="w-3.5 h-3.5 text-emerald-400"></i>
                            <span>Dossier</span>
                        </button>
                        <button onclick="downloadHillEml('${safeEncName}')" title="Generate Outlook Reminder (.eml)" class="p-1.5 rounded-lg bg-slate-950 hover:bg-indigo-600 text-slate-400 hover:text-white border border-slate-800 transition">
                            <i data-lucide="mail" class="w-3.5 h-3.5"></i>
                        </button>
                        <button onclick="downloadHillExcel('${safeEncName}')" title="Download Excel Backlog Register" class="p-1.5 rounded-lg bg-slate-950 hover:bg-emerald-600 text-slate-400 hover:text-white border border-slate-800 transition">
                            <i data-lucide="download" class="w-3.5 h-3.5"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
    if (window.AntigravityTableEngine) {
        AntigravityTableEngine.initTable('feed-table');
        AntigravityTableEngine.applyColumnVisibility('feed-table');
    }
    if (window.lucide) lucide.createIcons();
}

function renderHillTeamEngineers(engineers) {
    const grid = document.getElementById('hill-engineers-grid');
    if (!grid) return;

    if (!engineers.length) {
        grid.innerHTML = `
            <div class="col-span-full py-16 text-center text-slate-500 bg-slate-900/40 rounded-2xl border border-slate-800">
                <i data-lucide="user-x" class="w-12 h-12 mx-auto text-slate-600 mb-3"></i>
                <p class="text-sm font-bold text-slate-400">No Hill engineers match the selected criteria</p>
                <p class="text-xs text-slate-600 mt-1">Adjust search or severity filter to view full roster</p>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    let html = '';
    engineers.forEach(eng => {
        const engName = eng.name || eng.engineer_name || 'Hill User';
        const engPosition = eng.position || eng.job_title || 'Hill International PMC';
        const engPkgs = eng.packages || eng.top_packages || [];
        const directOverdue = (eng.overdue_steps || 0) + (eng.overdue_mails || 0);
        const hasOverdue = directOverdue > 0;
        const maxDelay = eng.max_delay_days || eng.max_step_delay || 0;

        // Initials avatar
        const parts = engName.split(' ').filter(Boolean);
        const initials = parts.slice(0, 2).map(p => p[0]).join('').toUpperCase() || 'H';

        const safeEncName = encodeURIComponent(engName);

        // Package chips
        const pkgBadges = engPkgs.slice(0, 3).map(pkg => `
            <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-950 text-sky-400 border border-slate-800">
                ${pkg}
            </span>
        `).join('');

        html += `
            <div class="bg-slate-900 rounded-2xl border ${hasOverdue ? 'border-slate-800 hover:border-rose-500/50' : 'border-slate-800/80 hover:border-emerald-500/50'} p-5 flex flex-col justify-between transition-all duration-200 hover:shadow-xl hover:shadow-sky-500/5 group">
                <div>
                    <!-- Card Top: Avatar, Name, Direct Overdue Pill -->
                    <div class="flex items-start justify-between gap-3 mb-3">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 rounded-xl ${hasOverdue ? 'bg-gradient-to-tr from-rose-900/60 to-rose-700/40 text-rose-300 border border-rose-500/30' : 'bg-gradient-to-tr from-emerald-900/60 to-emerald-700/40 text-emerald-300 border border-emerald-500/30'} flex items-center justify-center font-black text-sm flex-shrink-0 shadow-md">
                                ${initials}
                            </div>
                            <div class="min-w-0">
                                <h3 class="text-sm font-extrabold text-white group-hover:text-sky-400 transition truncate leading-snug cursor-pointer" onclick="openHillDossier('${safeEncName}')" title="${engName}">
                                    ${engName}
                                </h3>
                                <div class="text-[11px] text-slate-400 truncate">${engPosition}</div>
                            </div>
                        </div>

                        ${hasOverdue ? `
                            <span class="px-2.5 py-1 rounded-lg text-[11px] font-mono font-black bg-rose-500/20 text-rose-400 border border-rose-500/30 flex-shrink-0">
                                +${directOverdue} Late
                            </span>
                        ` : `
                            <span class="px-2.5 py-1 rounded-lg text-[11px] font-mono font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex-shrink-0">
                                On Track
                            </span>
                        `}
                    </div>

                    <!-- Email Contact Line -->
                    <div class="flex items-center gap-1.5 text-xs font-mono text-sky-400/90 mb-4 bg-slate-950/60 px-2.5 py-1.5 rounded-lg border border-slate-800/70 truncate">
                        <i data-lucide="mail" class="w-3.5 h-3.5 text-slate-500 flex-shrink-0"></i>
                        <span class="truncate">${eng.email || 'No email registered'}</span>
                    </div>

                    <!-- Direct Backlog Numbers Grid -->
                    <div class="grid grid-cols-3 gap-2 p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 mb-4 text-center">
                        <div>
                            <span class="text-[10px] text-slate-400 block">Overdue Reviews</span>
                            <span class="text-sm font-mono font-bold ${eng.overdue_steps > 0 ? 'text-rose-400' : 'text-slate-400'}">${(eng.overdue_steps || 0).toLocaleString()}</span>
                        </div>
                        <div>
                            <span class="text-[10px] text-slate-400 block">In-SLA Reviews</span>
                            <span class="text-sm font-mono font-bold text-sky-400">${(eng.current_steps || 0).toLocaleString()}</span>
                        </div>
                        <div>
                            <span class="text-[10px] text-slate-400 block">Max Delay</span>
                            <span class="text-sm font-mono font-bold ${maxDelay > 0 ? 'text-rose-400' : 'text-emerald-400'}">${maxDelay > 0 ? `+${maxDelay}d` : '0d'}</span>
                        </div>
                    </div>

                    <!-- Packages List -->
                    <div class="flex items-center gap-1.5 flex-wrap mb-4">
                        <span class="text-[10px] text-slate-400 font-semibold mr-0.5">Scopes:</span>
                        ${pkgBadges || '<span class="text-[10px] text-slate-500">General</span>'}
                    </div>
                </div>

                <!-- Action Controls: Open Dossier + Quick EML / Excel -->
                <div class="flex items-center gap-2 pt-2 border-t border-slate-800/80">
                    <button onclick="openHillDossier('${safeEncName}')" class="flex-1 py-2 px-3 rounded-xl bg-slate-800 hover:bg-emerald-600 text-slate-200 hover:text-white text-xs font-bold flex items-center justify-center gap-2 border border-slate-700/60 hover:border-transparent transition-all shadow-sm">
                        <i data-lucide="file-text" class="w-3.5 h-3.5 text-emerald-400 group-hover:text-white"></i>
                        <span>Action Dossier</span>
                    </button>
                    <button onclick="downloadHillEml('${safeEncName}')" title="Generate Outlook Reminder (.eml)" class="p-2 rounded-xl bg-slate-950 hover:bg-indigo-600 text-slate-400 hover:text-white border border-slate-800 transition">
                        <i data-lucide="mail" class="w-3.5 h-3.5"></i>
                    </button>
                    <button onclick="downloadHillExcel('${safeEncName}')" title="Download Excel Backlog Register" class="p-2 rounded-xl bg-slate-950 hover:bg-emerald-600 text-slate-400 hover:text-white border border-slate-800 transition">
                        <i data-lucide="download" class="w-3.5 h-3.5"></i>
                    </button>
                </div>
            </div>
        `;
    });

    grid.innerHTML = html;
    if (window.lucide) lucide.createIcons();
}

// 13. Hill Engineer Direct Action Dossier Modal & Export Handlers
async function openHillDossier(encodedName) {
    const engineerName = decodeURIComponent(encodedName);
    const modal = document.getElementById('modal-hill-dossier');
    const body = document.getElementById('modal-hill-body');
    if (!modal) return;

    modal.classList.remove('hidden');
    document.getElementById('modal-hill-name').innerText = engineerName;
    document.getElementById('modal-hill-pos').innerText = 'Hill International PMC';
    document.getElementById('modal-hill-email').innerText = 'Loading...';
    document.getElementById('modal-hill-summary-line').innerText = 'Fetching individual portfolio...';

    body.innerHTML = `
        <div class="py-20 text-center text-slate-400">
            <div class="inline-block animate-spin w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full mb-3"></div>
            <p class="text-sm font-semibold text-slate-300">Loading direct review items & correspondence for ${engineerName}...</p>
            <p class="text-xs text-slate-500 mt-1">Filtering strictly by assigned_to_name (Zero CC transmittal noise)</p>
        </div>
    `;

    try {
        const pkgFilter = document.getElementById('hill-package-filter')?.value || 'all';
        let url = `/api/controls/hill_team/${encodeURIComponent(engineerName)}/dossier`;
        if (pkgFilter !== 'all') url += `?package=${encodeURIComponent(pkgFilter)}`;

        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load`);
        const data = await res.json();
        activeHillDossier = data;

        const engInfo = data.engineer || {};
        const summary = data.summary || {};
        const steps = data.steps || [];
        const mails = data.mails || [];

        const overdueSteps = steps.filter(s => s.is_overdue || s.step_status === 'Overdue');
        const currentSteps = steps.filter(s => !s.is_overdue && s.step_status !== 'Overdue');
        const overdueMails = mails;

        const maxDelay = Math.max(
            0,
            ...overdueSteps.map(s => s.days_late || 0),
            ...overdueMails.map(m => m.days_late || 0)
        );

        document.getElementById('modal-hill-pos').innerText = engInfo.position || 'Hill International PMC';
        document.getElementById('modal-hill-email').innerText = engInfo.email || 'No email registered';
        document.getElementById('modal-hill-summary-line').innerText = `${summary.total_overdue || (overdueSteps.length + overdueMails.length)} Direct overdue item(s) | Max delay: +${maxDelay}d | SLA Target: Clearance required`;

        let html = `
            <!-- Top Summary KPIs -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div class="bg-slate-950/80 rounded-xl p-3 border border-slate-800">
                    <span class="text-[10px] text-slate-400 block">Direct Overdue Reviews</span>
                    <span class="text-xl font-mono font-black ${overdueSteps.length > 0 ? 'text-rose-400' : 'text-slate-300'}">${overdueSteps.length}</span>
                </div>
                <div class="bg-slate-950/80 rounded-xl p-3 border border-slate-800">
                    <span class="text-[10px] text-slate-400 block">In-SLA Active Reviews</span>
                    <span class="text-xl font-mono font-black text-sky-400">${currentSteps.length}</span>
                </div>
                <div class="bg-slate-950/80 rounded-xl p-3 border border-slate-800">
                    <span class="text-[10px] text-slate-400 block">Direct Overdue Letters/RFIs</span>
                    <span class="text-xl font-mono font-black ${overdueMails.length > 0 ? 'text-amber-400' : 'text-slate-300'}">${overdueMails.length}</span>
                </div>
                <div class="bg-slate-950/80 rounded-xl p-3 border border-slate-800">
                    <span class="text-[10px] text-slate-400 block">Max Overdue Delay</span>
                    <span class="text-xl font-mono font-black ${maxDelay > 0 ? 'text-rose-400' : 'text-emerald-400'}">+${maxDelay}d</span>
                </div>
            </div>
        `;

        // Section 1: Overdue Steps
        if (overdueSteps.length > 0) {
            html += `
                <div class="space-y-2 pt-2">
                    <div class="flex items-center gap-2 text-xs font-bold text-rose-400">
                        <i data-lucide="alert-triangle" class="w-4 h-4"></i>
                        <span>1. Direct Overdue Workflow Reviews (${overdueSteps.length})</span>
                    </div>
                    <div class="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/80">
                        <table class="w-full text-left text-xs">
                            <thead class="bg-slate-900/90 text-slate-400 font-semibold border-b border-slate-800">
                                <tr>
                                    <th class="p-2.5 w-36">Workflow No</th>
                                    <th class="p-2.5 w-36">Document No</th>
                                    <th class="p-2.5">Document Title / Submittal</th>
                                    <th class="p-2.5 w-44">Step Name</th>
                                    <th class="p-2.5 w-24">Due Date</th>
                                    <th class="p-2.5 w-24">Days Late</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-800/60 font-medium">
                                ${overdueSteps.map(s => `
                                    <tr class="hover:bg-slate-800/40 transition">
                                        <td class="p-2.5 font-mono">
                                            <a href="${s.aconex_url}" target="_blank" class="text-sky-400 hover:underline font-bold">${s.workflow_no}</a>
                                        </td>
                                        <td class="p-2.5 font-mono text-slate-300">${s.document_no && s.document_no !== '-' ? `<a href="${s.doc_aconex_url || s.aconex_url}" target="_blank" class="text-sky-300 hover:underline font-bold" title="Open Document in Aconex">${s.document_no}</a>` : '-'}</td>
                                        <td class="p-2.5 text-white">${s.document_title || '-'}</td>
                                        <td class="p-2.5 text-slate-300">${s.step_name || 'Review Step'}</td>
                                        <td class="p-2.5 font-mono text-slate-400 whitespace-nowrap">${formatAppDate(s.date_due)}</td>
                                        <td class="p-2.5 font-mono font-bold text-rose-400">+${s.days_late || 0}d</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }

        // Section 2: Active Reviews (In SLA)
        if (currentSteps.length > 0) {
            html += `
                <div class="space-y-2 pt-2">
                    <div class="flex items-center gap-2 text-xs font-bold text-sky-400">
                        <i data-lucide="clock" class="w-4 h-4"></i>
                        <span>2. Active Workflow Reviews Within SLA (${currentSteps.length})</span>
                    </div>
                    <div class="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/80">
                        <table class="w-full text-left text-xs">
                            <thead class="bg-slate-900/90 text-slate-400 font-semibold border-b border-slate-800">
                                <tr>
                                    <th class="p-2.5 w-36">Workflow No</th>
                                    <th class="p-2.5 w-36">Document No</th>
                                    <th class="p-2.5">Document Title / Submittal</th>
                                    <th class="p-2.5 w-44">Step Name</th>
                                    <th class="p-2.5 w-24">Due Date</th>
                                    <th class="p-2.5 w-24">Status</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-800/60 font-medium">
                                ${currentSteps.map(s => `
                                    <tr class="hover:bg-slate-800/40 transition">
                                        <td class="p-2.5 font-mono">
                                            <a href="${s.aconex_url}" target="_blank" class="text-sky-400 hover:underline font-bold">${s.workflow_no}</a>
                                        </td>
                                        <td class="p-2.5 font-mono text-slate-300">${s.document_no && s.document_no !== '-' ? `<a href="${s.doc_aconex_url || s.aconex_url}" target="_blank" class="text-sky-300 hover:underline font-bold" title="Open Document in Aconex">${s.document_no}</a>` : '-'}</td>
                                        <td class="p-2.5 text-white">${s.document_title || '-'}</td>
                                        <td class="p-2.5 text-slate-300">${s.step_name || 'Review Step'}</td>
                                        <td class="p-2.5 font-mono text-slate-400 whitespace-nowrap">${formatAppDate(s.date_due)}</td>
                                        <td class="p-2.5 font-mono text-sky-400 font-bold">${s.step_status || 'Current'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }

        // Section 3: Direct Overdue Mails
        if (overdueMails.length > 0) {
            html += `
                <div class="space-y-2 pt-2">
                    <div class="flex items-center gap-2 text-xs font-bold text-amber-400">
                        <i data-lucide="mail" class="w-4 h-4"></i>
                        <span>3. Direct Overdue Correspondence & RFIs (${overdueMails.length})</span>
                    </div>
                    <div class="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/80">
                        <table class="w-full text-left text-xs">
                            <thead class="bg-slate-900/90 text-slate-400 font-semibold border-b border-slate-800">
                                <tr>
                                    <th class="p-2.5 w-36">Mail No</th>
                                    <th class="p-2.5 w-28">Type</th>
                                    <th class="p-2.5">Subject</th>
                                    <th class="p-2.5 w-44">From Org</th>
                                    <th class="p-2.5 w-24">Due Date</th>
                                    <th class="p-2.5 w-24">Days Late</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-800/60 font-medium">
                                ${overdueMails.map(m => `
                                    <tr class="hover:bg-slate-800/40 transition">
                                        <td class="p-2.5 font-mono">
                                            <a href="${m.aconex_url}" target="_blank" class="text-amber-400 hover:underline font-bold">${m.mail_no}</a>
                                        </td>
                                        <td class="p-2.5 text-slate-300">${m.mail_type || 'Mail'}</td>
                                        <td class="p-2.5 text-white">${m.subject || '-'}</td>
                                        <td class="p-2.5 text-slate-300">${m.from_org || m.from_organization || '-'}</td>
                                        <td class="p-2.5 font-mono text-slate-400 whitespace-nowrap">${formatAppDate(m.due_date)}</td>
                                        <td class="p-2.5 font-mono font-bold text-rose-400">+${m.days_late || 0}d</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }

        if (overdueSteps.length === 0 && currentSteps.length === 0 && overdueMails.length === 0) {
            html += `
                <div class="py-12 text-center text-emerald-400 bg-emerald-500/10 rounded-xl border border-emerald-500/20 p-6">
                    <p class="font-bold">No pending review actions or overdue correspondence currently assigned to ${engineerName}!</p>
                </div>
            `;
        }

        body.innerHTML = html;
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        body.innerHTML = `<div class="py-12 text-center text-rose-400 bg-rose-500/10 rounded-xl p-6 font-bold">Error: ${err.message}</div>`;
    }
}

function closeHillDossierModal() {
    const modal = document.getElementById('modal-hill-dossier');
    if (modal) modal.classList.add('hidden');
    activeHillDossier = null;
}

async function copyHillEmailHtml() {
    if (!activeHillDossier || !activeHillDossier.email_html) {
        showToast('No dossier loaded to copy.', 'error');
        return;
    }
    const htmlToCopy = activeHillDossier.email_html;
    const engName = activeHillDossier.engineer?.name || 'Engineer';

    try {
        const blobHtml = new Blob([htmlToCopy], { type: 'text/html' });
        const blobText = new Blob([htmlToCopy.replace(/<[^>]+>/g, ' ')], { type: 'text/plain' });
        const item = new ClipboardItem({ 'text/html': blobHtml, 'text/plain': blobText });
        await navigator.clipboard.write([item]);
        showToast(`Personalized reminder table for ${engName} copied! Paste directly into Outlook.`, 'success');
    } catch (e) {
        navigator.clipboard.writeText(htmlToCopy);
        showToast('HTML reminder body copied to clipboard.', 'info');
    }
}

function downloadHillExcel(targetName) {
    const name = targetName ? decodeURIComponent(targetName) : (activeHillDossier?.engineer?.name || null);
    if (!name) {
        showToast('No engineer selected for Excel export', 'error');
        return;
    }
    const pkgFilter = document.getElementById('hill-package-filter')?.value || 'all';
    let url = `/api/controls/hill_team/${encodeURIComponent(name)}/export_excel`;
    if (pkgFilter !== 'all') url += `?package=${encodeURIComponent(pkgFilter)}`;
    window.location.href = url;
    showToast(`Downloading Excel register for ${name}...`, 'success');
}

function downloadHillEml(targetName) {
    const name = targetName ? decodeURIComponent(targetName) : (activeHillDossier?.engineer?.name || null);
    if (!name) {
        showToast('No engineer selected for Outlook draft', 'error');
        return;
    }
    const pkgFilter = document.getElementById('hill-package-filter')?.value || 'all';
    let url = `/api/controls/hill_team/${encodeURIComponent(name)}/download_eml`;
    if (pkgFilter !== 'all') url += `?package=${encodeURIComponent(pkgFilter)}`;
    window.location.href = url;
    showToast(`Downloading Outlook .eml reminder draft for ${name}...`, 'success');
}

// ==========================================
// 12. HILL & SSC DIRECT EXECUTIVE LETTERS
// ==========================================
async function loadHillSscDirect(page = 1) {
    hsdCurrentPage = page;
    const tbody = document.getElementById('hsd-tbody');
    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-10 text-slate-400">Loading direct correspondence...</td></tr>';
    }

    try {
        let url = `/api/hill_ssc/direct?direction=${encodeURIComponent(hsdCurrentDirection)}&page=${page}&page_size=${hsdPageSize}&sort_col=${encodeURIComponent(hsdSortCol)}&sort_dir=${encodeURIComponent(hsdSortDir)}`;
        if (hsdSearchQuery) {
            url += `&search=${encodeURIComponent(hsdSearchQuery)}`;
        }

        const res = await fetch(url);
        const data = await res.json();

        // Update Stat Counters & Badges
        const total = data.total || 0;
        const inCnt = data.inbound_count || 0;
        const outCnt = data.outbound_count || 0;

        const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
        setTxt('stat-hsd-total', total.toLocaleString());
        setTxt('stat-hsd-inbound', inCnt.toLocaleString());
        setTxt('stat-hsd-outbound', outCnt.toLocaleString());
        setTxt('hsd-pill-count-all', total);
        setTxt('hsd-pill-count-in', inCnt);
        setTxt('hsd-pill-count-out', outCnt);

        const badge = document.getElementById('badge-hill-ssc-direct-count');
        if (badge) badge.innerText = `${total} Letters`;

        renderHillSscDirectTable(data);
    } catch (err) {
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-rose-400">Error loading direct letters: ${err.message}</td></tr>`;
        }
    }
}

function renderHillSscDirectTable(data) {
    const tbody = document.getElementById('hsd-tbody');
    if (!tbody) return;

    const items = data.data || [];
    const total = data.total || 0;
    const page = data.page || 1;
    const pageSize = data.page_size || 25;
    const totalPages = data.total_pages || 1;

    // Update Pagination Indicators
    const startIdx = total === 0 ? 0 : (page - 1) * pageSize + 1;
    const endIdx = Math.min(page * pageSize, total);
    const pageInfoStr = `Showing ${startIdx} to ${endIdx} of ${total} direct letters`;

    ['top', 'bottom'].forEach(pos => {
        const infoEl = document.getElementById(`hsd-pagination-info-${pos}`);
        if (infoEl) infoEl.innerText = pageInfoStr;

        const indEl = document.getElementById(`hsd-page-indicator-${pos}`);
        if (indEl) indEl.innerText = `Page ${page} of ${totalPages}`;

        const prevBtn = document.getElementById(`hsd-prev-btn-${pos}`);
        if (prevBtn) prevBtn.disabled = page <= 1;

        const nextBtn = document.getElementById(`hsd-next-btn-${pos}`);
        if (nextBtn) nextBtn.disabled = page >= totalPages;
    });

    if (items.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-12 text-slate-500 bg-slate-950/40">
                    <i data-lucide="inbox" class="w-8 h-8 mx-auto mb-2 opacity-40"></i>
                    <p class="text-sm font-bold text-slate-400">No direct Hill &amp; SSC letters match search criteria</p>
                </td>
            </tr>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    let html = '';
    items.forEach((m, idx) => {
        const rowNo = startIdx + idx;
        const aconexUrl = getAconexMailUrl(m);
        const isIn = (m.direction || '').toLowerCase().includes('inbound') || (m.from_org || '').includes('Shaker') || (m.from_org || '').includes('ECG');
        const dirBadge = isIn
            ? `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 whitespace-nowrap">Inbound (From SSC)</span>`
            : `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20 whitespace-nowrap">Outbound (From Hill)</span>`;

        html += `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="py-3 px-3 text-center text-slate-500 font-mono text-[11px]">${rowNo}</td>
                <td class="py-3 px-4 overflow-hidden">
                    <div class="flex items-center justify-between gap-1.5">
                        <a href="${aconexUrl}" target="_blank" class="font-mono font-bold text-purple-400 hover:text-purple-300 hover:underline truncate" title="Open in Aconex: ${m.mail_no}">
                            ${m.mail_no}
                        </a>
                        <button onclick="openLetterThreadModal('${m.mail_no}', '${m.ref_no || ''}')" title="Explore Full Correspondence Thread" class="px-2 py-0.5 rounded bg-indigo-500/10 hover:bg-indigo-500 text-indigo-400 hover:text-white border border-indigo-500/20 text-[10px] font-bold flex-shrink-0 flex items-center gap-1 transition">
                            <i data-lucide="git-merge" class="w-3 h-3"></i>
                            <span>Thread</span>
                        </button>
                    </div>
                </td>
                <td class="py-3 px-3 text-center overflow-hidden">${dirBadge}</td>
                <td class="py-3 px-4 text-slate-300 overflow-hidden">
                    <div class="font-semibold text-slate-200 truncate">${m.from_org || '-'}</div>
                    ${m.from_name ? `<div class="text-[10px] text-slate-400 truncate">${m.from_name}</div>` : ''}
                </td>
                <td class="py-3 px-4 text-slate-300 overflow-hidden">
                    <div class="font-semibold text-slate-200 truncate">${m.to_org || '-'}</div>
                    ${m.to_name ? `<div class="text-[10px] text-slate-400 truncate">${m.to_name}</div>` : ''}
                </td>
                <td class="py-3 px-4 font-medium text-slate-200 whitespace-normal break-words leading-relaxed">${m.subject || '-'}</td>
                <td class="py-3 px-3 text-slate-400 font-mono text-[11px] whitespace-nowrap">${formatAppDate(m.sent_date)}</td>
                <td class="py-3 px-3 text-center">
                    <a href="${aconexUrl}" target="_blank" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-sky-400 hover:text-white border border-slate-700 text-[11px] font-bold transition" title="Open Official Letter in Aconex">
                        <i data-lucide="external-link" class="w-3 h-3"></i>
                        <span>Open</span>
                    </a>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
    if (window.AntigravityTableEngine) {
        AntigravityTableEngine.initTable('feed-table');
        AntigravityTableEngine.applyColumnVisibility('feed-table');
    }
    if (window.lucide) lucide.createIcons();
}

function setHillSscDirectDirection(dir) {
    hsdCurrentDirection = dir;
    ['all', 'inbound', 'outbound'].forEach(d => {
        const btn = document.getElementById(`hsd-btn-dir-${d}`);
        if (btn) {
            if (d === dir) {
                btn.className = 'hsd-dir-btn px-3.5 py-1.5 rounded-xl text-xs font-bold bg-purple-600 text-white shadow-md shadow-purple-600/20 transition';
            } else {
                btn.className = 'hsd-dir-btn px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition';
            }
        }
    });
    loadHillSscDirect(1);
}

function onHillSscDirectSearch(term) {
    hsdSearchQuery = (term || '').trim();
    loadHillSscDirect(1);
}

function sortHillSscDirect(col) {
    if (hsdSortCol === col) {
        hsdSortDir = hsdSortDir === 'asc' ? 'desc' : 'asc';
    } else {
        hsdSortCol = col;
        hsdSortDir = (col === 'sent_date') ? 'desc' : 'asc';
    }
    loadHillSscDirect(1);
}

function prevHillSscDirectPage() {
    if (hsdCurrentPage > 1) {
        loadHillSscDirect(hsdCurrentPage - 1);
    }
}

function nextHillSscDirectPage() {
    loadHillSscDirect(hsdCurrentPage + 1);
}

function exportHillSscDirect() {
    let url = `/api/hill_ssc/direct/export?direction=${encodeURIComponent(hsdCurrentDirection)}`;
    if (hsdSearchQuery) {
        url += `&search=${encodeURIComponent(hsdSearchQuery)}`;
    }
    window.location.href = url;
    showToast('Downloading Direct Hill & SSC Letters register (Excel)...', 'success');
}

// ==========================================
// 8. BALL IN COURT SLA & PROCESS GOVERNANCE
// ==========================================
let bicCurrentPage = 1;
let bicLimit = 50;
let bicTotal = 0;
let bicFilterFileType = 'all';
let bicSelectedFileTypes = new Set(['all']);
let bicFilterDiscipline = 'all';
let bicFilterConsultant = 'all';
let bicFilterParty = 'all';
let bicFilterAction = 'all';
let bicFilterStatus = 'all';
let bicFilterPkg = 'all';
let bicSearchQuery = '';
let bicFilterOptionsLoaded = false;
let bicPartiesLoaded = false;
let bicWrapText = true;
let bicShowTime = false;
let lastBicDataRows = [];

async function loadBallInCourtData(page = 1) {
    bicCurrentPage = page;
    const tbody = document.getElementById('bic-tbody');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="12" class="text-center py-12 text-slate-500">
                    <div class="flex items-center justify-center gap-2">
                        <i data-lucide="loader" class="w-5 h-5 animate-spin text-amber-400"></i>
                        <span>Loading Ball in Court processes &amp; SLA bottlenecks across 5 categories...</span>
                    </div>
                </td>
            </tr>
        `;
        if (window.lucide) lucide.createIcons();
    }

    const params = new URLSearchParams({
        page: bicCurrentPage,
        limit: bicLimit
    });

    if (bicFilterFileType && bicFilterFileType !== 'all') params.append('file_type', bicFilterFileType);
    if (bicFilterDiscipline && bicFilterDiscipline !== 'all') params.append('discipline', bicFilterDiscipline);
    if (bicFilterConsultant && bicFilterConsultant !== 'all') params.append('consultant', bicFilterConsultant);
    if (bicFilterParty && bicFilterParty !== 'all') params.append('ball_in_court', bicFilterParty);
    if (bicFilterAction && bicFilterAction !== 'all') params.append('action', bicFilterAction);
    if (bicFilterStatus && bicFilterStatus !== 'all') params.append('process_status', bicFilterStatus);
    if (bicFilterPkg && bicFilterPkg !== 'all') params.append('package', bicFilterPkg);
    if (bicSearchQuery && bicSearchQuery.trim()) params.append('search', bicSearchQuery.trim());

    try {
        const res = await fetch(`/api/ball_in_court/processes?${params.toString()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();

        bicTotal = json.total || 0;
        lastBicDataRows = json.data || [];
        renderBallInCourtKPIs(json.kpis || {});

        if (json.file_types) {
            renderFileTypeTabs(json.file_types, json.total);
        }

        if (json.consultants) {
            renderConsultantChips(json.consultants);
        }

        if (json.parties) {
            renderPartySlicerOptions(json.parties);
            bicPartiesLoaded = true;
        }

        if (!bicFilterOptionsLoaded && json.filter_options) {
            renderBallInCourtFilterOptions(json.filter_options);
            bicFilterOptionsLoaded = true;
        }

        renderBallInCourtTable(lastBicDataRows);
        updateBallInCourtPagination(json.page, json.limit, json.total);
        renderBallInCourtActiveTags();

        const badge = document.getElementById('badge-bic-total-count');
        if (badge) badge.innerText = `${(json.kpis?.total_overdue || json.total || 0)} Overdue`;
    } catch (err) {
        console.error('Failed to load Ball in Court data:', err);
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="12" class="text-center py-8 text-rose-400 font-semibold">
                        Failed to load processes: ${err.message}.
                        <button onclick="loadBallInCourtData(bicCurrentPage)" class="ml-2 underline text-sky-400">Retry</button>
                    </td>
                </tr>
            `;
        }
    }
}

function selectBicFileType(typeCode, event) {
    const isCtrl = Boolean(event && (event.ctrlKey || event.metaKey));
    if (isCtrl) {
        if (typeCode === 'all') {
            bicSelectedFileTypes.clear();
            bicSelectedFileTypes.add('all');
        } else {
            bicSelectedFileTypes.delete('all');
            if (bicSelectedFileTypes.has(typeCode)) {
                bicSelectedFileTypes.delete(typeCode);
                if (bicSelectedFileTypes.size === 0) {
                    bicSelectedFileTypes.add('all');
                }
            } else {
                bicSelectedFileTypes.add(typeCode);
            }
        }
    } else {
        bicSelectedFileTypes.clear();
        bicSelectedFileTypes.add(typeCode);
    }

    if (bicSelectedFileTypes.has('all')) {
        bicFilterFileType = 'all';
    } else {
        bicFilterFileType = Array.from(bicSelectedFileTypes).join(',');
    }

    const sel = document.getElementById('bic-filter-file-type');
    if (sel) {
        sel.value = bicSelectedFileTypes.size === 1 ? Array.from(bicSelectedFileTypes)[0] : 'all';
    }

    updateBicTypeTabButtons();
    loadBallInCourtData(1);
}

function updateBicTypeTabButtons() {
    const typeCodes = ['all', 'RFI', 'TRANSMITTAL', 'HSE', 'NCR', 'HSNCR'];
    const colors = {
        'all': 'bg-sky-500 text-slate-950 font-black shadow-md',
        'RFI': 'bg-sky-500 text-slate-950 font-black shadow-md',
        'TRANSMITTAL': 'bg-indigo-500 text-white font-black shadow-md',
        'HSE': 'bg-amber-500 text-slate-950 font-black shadow-md',
        'NCR': 'bg-rose-500 text-white font-black shadow-md',
        'HSNCR': 'bg-red-600 text-white font-black shadow-md'
    };

    typeCodes.forEach(code => {
        const btn = document.getElementById(`bic-tab-type-${code}`);
        if (!btn) return;
        const isSelected = bicSelectedFileTypes.has(code);
        if (isSelected) {
            btn.className = `bic-type-btn px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 transition transform scale-[1.02] ${colors[code] || 'bg-sky-500 text-slate-950 font-black'}`;
        } else {
            btn.className = 'bic-type-btn px-3 py-1.5 rounded-xl text-xs font-semibold bg-slate-950 text-slate-300 hover:bg-slate-900 border border-slate-800 flex items-center gap-1.5 transition';
        }
    });
}

function renderFileTypeTabs(fileTypes, currentTotal) {
    fileTypes.forEach(ft => {
        const el = document.getElementById(`bic-count-type-${ft.file_type}`);
        if (el) el.innerText = (ft.total || 0).toLocaleString();
    });
}

function renderBallInCourtKPIs(kpis) {
    const elTot = document.getElementById('bic-kpi-total');
    const elOv = document.getElementById('bic-kpi-overdue');
    const elHill = document.getElementById('bic-kpi-hill');
    const elShk = document.getElementById('bic-kpi-shaker');

    if (elTot) elTot.innerText = (kpis.total_processes || 0).toLocaleString();
    if (elOv) elOv.innerText = (kpis.total_overdue || 0).toLocaleString();
    if (elHill) elHill.innerText = (kpis.on_hill || 0).toLocaleString();
    if (elShk) elShk.innerText = (kpis.on_shaker_ecg || 0).toLocaleString();
}

function renderConsultantChips(consultants) {
    const container = document.getElementById('bic-consultant-chips-container');
    const indicator = document.getElementById('bic-consultant-active-indicator');
    if (!container) return;

    const list = [
        { id: 'all', label: 'All Parties', count: consultants.all?.total || 0, color: 'text-slate-200' },
        { id: 'Shaker_ECG', label: 'Shaker-ECG', count: consultants.Shaker_ECG?.total || 0, color: 'text-emerald-400', border: 'border-emerald-500/30' },
        { id: 'EGIS', label: 'EGIS', count: consultants.EGIS?.total || 0, color: 'text-indigo-400', border: 'border-indigo-500/30' },
        { id: 'Aedas', label: 'Aedas', count: consultants.Aedas?.total || 0, color: 'text-pink-400', border: 'border-pink-500/30' },
        { id: 'DAR AL HANDASAH', label: 'Dar Al Handasah', count: consultants['DAR AL HANDASAH']?.total || 0, color: 'text-purple-400', border: 'border-purple-500/30' },
        { id: 'OBMI', label: 'OBMI', count: consultants.OBMI?.total || 0, color: 'text-amber-400', border: 'border-amber-500/30' },
        { id: 'NACO', label: 'NACO', count: consultants.NACO?.total || 0, color: 'text-cyan-400', border: 'border-cyan-500/30' },
        { id: 'Royal HaskoningDHV', label: 'Royal Haskoning', count: consultants['Royal HaskoningDHV']?.total || 0, color: 'text-teal-400', border: 'border-teal-500/30' },
        { id: 'Modon', label: 'Modon', count: consultants.Modon?.total || 0, color: 'text-sky-400', border: 'border-sky-500/30' },
        { id: 'Hill_Only', label: 'Hill Direct', count: consultants.Hill_Only?.total || 0, color: 'text-slate-300', border: 'border-slate-700' }
    ];

    let html = '';
    list.forEach(c => {
        const isActive = bicFilterConsultant === c.id;
        const activeClass = isActive 
            ? 'bg-amber-500 text-slate-950 font-black shadow-md' 
            : `bg-slate-950 hover:bg-slate-800 ${c.color} border ${c.border || 'border-slate-800'} font-semibold`;
        html += `
            <button type="button" onclick="selectBicConsultant('${c.id}')" class="bic-chip px-2.5 py-1 rounded-lg text-xs transition flex items-center gap-1.5 ${activeClass}">
                <span>${c.label}</span>
                <span class="px-1.5 py-0.2 rounded-full text-[10px] ${isActive ? 'bg-slate-900 text-amber-300 font-bold' : 'bg-slate-900 text-slate-400 font-mono'}">${c.count}</span>
            </button>
        `;
    });
    container.innerHTML = html;

    if (indicator) {
        const activeObj = list.find(x => x.id === bicFilterConsultant);
        indicator.innerText = `Showing: ${activeObj ? activeObj.label : 'All Entities'}`;
    }
}

function selectBicConsultant(cCode) {
    bicFilterConsultant = cCode;
    const selCons = document.getElementById('bic-filter-consultant');
    if (selCons) selCons.value = cCode;
    loadBallInCourtData(1);
}

function renderPartySlicerOptions(parties) {
    const sel = document.getElementById('bic-filter-party');
    const container = document.getElementById('bic-slicer-checkboxes-container');

    if (sel) {
        let optHtml = '<option value="all">All Parties (All Chains)</option>';
        parties.forEach(p => {
            optHtml += `<option value="${p.party}">${p.party} (${p.total})</option>`;
        });
        sel.innerHTML = optHtml;
        if (bicFilterParty) sel.value = bicFilterParty;
    }

    if (container) {
        let cbHtml = '';
        parties.forEach((p, idx) => {
            const id = `bic-cb-party-${idx}`;
            cbHtml += `
                <label for="${id}" class="flex items-start gap-2 p-1.5 rounded-lg hover:bg-slate-900 border border-transparent hover:border-slate-800 text-xs text-slate-300 cursor-pointer transition select-none">
                    <input type="checkbox" id="${id}" value="${p.party}" checked class="bic-slicer-cb mt-0.5 rounded bg-slate-900 border-slate-700 text-amber-500 focus:ring-0">
                    <div class="flex-1 truncate">
                        <span class="text-slate-200 font-mono text-[11px]">${p.party}</span>
                        <span class="text-slate-500 text-[10px] ml-1">(${p.total})</span>
                    </div>
                </label>
            `;
        });
        container.innerHTML = cbHtml;
    }
}

function toggleBicSlicerPanel() {
    const p = document.getElementById('bic-slicer-panel');
    if (p) {
        p.classList.toggle('hidden');
    }
}

function toggleAllBicSlicerCheckboxes(selectAll) {
    const cbs = document.querySelectorAll('.bic-slicer-cb');
    cbs.forEach(cb => cb.checked = !!selectAll);
}

function applyBicSlicerChecklist() {
    const cbs = document.querySelectorAll('.bic-slicer-cb:checked');
    const totalCbs = document.querySelectorAll('.bic-slicer-cb');
    
    if (cbs.length === 0 || cbs.length === totalCbs.length) {
        bicFilterParty = 'all';
        const sel = document.getElementById('bic-filter-party');
        if (sel) sel.value = 'all';
    } else if (cbs.length === 1) {
        bicFilterParty = cbs[0].value;
        const sel = document.getElementById('bic-filter-party');
        if (sel) sel.value = bicFilterParty;
    } else {
        const vals = Array.from(cbs).map(cb => cb.value);
        bicFilterParty = vals.join('|||');
        const sel = document.getElementById('bic-filter-party');
        if (sel) {
            let hasOpt = Array.from(sel.options).some(o => o.value === bicFilterParty);
            if (!hasOpt) {
                const opt = document.createElement('option');
                opt.value = bicFilterParty;
                opt.innerText = `Custom Multi-Select (${cbs.length} Parties)`;
                sel.appendChild(opt);
            }
            sel.value = bicFilterParty;
        }
    }
    toggleBicSlicerPanel();
    loadBallInCourtData(1);
}

function renderBallInCourtFilterOptions(opts) {
    const pkgSelect = document.getElementById('bic-filter-pkg');
    if (pkgSelect && opts.packages) {
        const cur = pkgSelect.value;
        let html = '<option value="all">All Packages</option>';
        opts.packages.forEach(p => {
            html += `<option value="${p}">${p}</option>`;
        });
        pkgSelect.innerHTML = html;
        if (cur) pkgSelect.value = cur;
    }
    const discSelect = document.getElementById('bic-filter-discipline');
    if (discSelect && opts.disciplines) {
        const cur = discSelect.value;
        let html = '<option value="all">All Disciplines</option>';
        opts.disciplines.forEach(d => {
            html += `<option value="${d}">${d}</option>`;
        });
        discSelect.innerHTML = html;
        if (cur) discSelect.value = cur;
    }
}

function renderBallInCourtTable(rows) {
    const tbody = document.getElementById('bic-tbody');
    if (!tbody) return;

    if (!rows || rows.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="12" class="text-center py-12 text-slate-500 font-medium">
                    No matching Ball in Court processes found for selected criteria.
                </td>
            </tr>
        `;
        return;
    }

    const textCls = bicWrapText ? 'whitespace-normal break-words leading-relaxed' : 'truncate';

    let html = '';
    rows.forEach(r => {
        const isOv = r.process_status === 'Overdue' || r.mail_status === 'Overdue';
        const pStatusBadge = r.process_status === 'Overdue'
            ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-rose-500/20 text-rose-400 border border-rose-500/30 font-mono">Overdue</span>`
            : (r.process_status === 'Outstanding'
                ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono">Outstanding</span>`
                : `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">${r.process_status || 'N/A'}</span>`);

        const mStatusBadge = r.mail_status === 'Overdue'
            ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-rose-500/20 text-rose-400 border border-rose-500/30 font-mono">Overdue</span>`
            : (r.mail_status === 'Outstanding'
                ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono">Outstanding</span>`
                : `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700 font-mono">${r.mail_status || 'N/A'}</span>`);

        const actionBadge = r.action === 'To Respond'
            ? `<span class="px-2.5 py-0.5 rounded-lg text-[10px] font-black bg-rose-600/20 text-rose-300 border border-rose-500/30 flex items-center justify-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-rose-400 animate-pulse"></span>To Respond</span>`
            : `<span class="px-2 py-0.5 rounded-lg text-[10px] font-semibold bg-sky-500/15 text-sky-300 border border-sky-500/30">${r.action || 'Expecting Response'}</span>`;

        // Process Type Badge
        let typeBadge = '';
        if (r.file_type === 'RFI') {
            typeBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] font-black bg-sky-500/20 text-sky-300 border border-sky-500/30">RFI</span>`;
        } else if (r.file_type === 'TRANSMITTAL') {
            typeBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] font-black bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Transmittal</span>`;
        } else if (r.file_type === 'HSE') {
            typeBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] font-black bg-amber-500/20 text-amber-300 border border-amber-500/30">HSE</span>`;
        } else if (r.file_type === 'NCR') {
            typeBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] font-black bg-rose-500/20 text-rose-300 border border-rose-500/30">NCR</span>`;
        } else if (r.file_type === 'HSNCR') {
            typeBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] font-black bg-red-600/20 text-red-300 border border-red-500/30">HSNCR</span>`;
        }

        // Consultant Tag Badge
        let consultantBadge = '';
        const pCons = r.primary_consultant || 'Hill Inter';
        if (pCons.includes('DAR')) {
            consultantBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30 mr-1">DAR AL HANDASAH</span>`;
        } else if (pCons.includes('OBMI')) {
            consultantBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 mr-1">OBMI</span>`;
        } else if (pCons.includes('NACO')) {
            consultantBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 mr-1">NACO</span>`;
        } else if (pCons.includes('Haskoning')) {
            consultantBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-teal-500/20 text-teal-300 border border-teal-500/30 mr-1">Royal Haskoning</span>`;
        } else if (pCons.includes('EGIS')) {
            consultantBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 mr-1">EGIS</span>`;
        } else if (pCons.includes('Aedas')) {
            consultantBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-pink-500/20 text-pink-300 border border-pink-500/30 mr-1">Aedas</span>`;
        } else if (pCons.includes('Shaker') || pCons.includes('ECG')) {
            consultantBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 mr-1">Shaker-ECG</span>`;
        } else if (pCons.includes('Modon')) {
            consultantBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30 mr-1">Modon</span>`;
        }

        let bicColor = 'text-slate-200';
        if (r.ball_in_court.includes('Hill')) bicColor = 'text-sky-300 font-bold';
        if (r.ball_in_court.includes('Shaker') || r.ball_in_court.includes('ECG')) bicColor = 'text-emerald-300 font-bold';
        if (r.ball_in_court.includes('Modon')) bicColor = 'text-amber-300 font-bold';

        const rowBg = isOv ? 'hover:bg-rose-950/20 transition' : 'hover:bg-slate-800/40 transition';
        const dateStr = bicShowTime ? (r.initiated_on || '-') : (r.initiated_on ? r.initiated_on.split(' ')[0] : '-');

        html += `
            <tr class="${rowBg}">
                <td class="p-3 font-mono font-bold text-sky-400 whitespace-nowrap">
                    <div class="flex items-center gap-1.5 mb-1">
                        ${typeBadge}
                        <a href="/api/aconex/mail?mail_no=${encodeURIComponent(r.mail_no || r.process_ref)}" target="_blank" class="hover:underline flex items-center gap-1 group" title="Open directly in Aconex">
                            <span>${r.process_ref || '-'}</span>
                            <i data-lucide="external-link" class="w-3 h-3 opacity-0 group-hover:opacity-100 transition text-sky-400"></i>
                        </a>
                    </div>
                    <div class="text-[10px] font-sans font-normal text-slate-500 truncate mt-0.5">${r.project_package || ''}</div>
                </td>
                <td class="p-3 text-center font-mono text-slate-300 whitespace-nowrap">${dateStr}</td>
                <td class="p-3 text-center whitespace-nowrap">${pStatusBadge}</td>
                <td class="p-3 text-right font-mono text-slate-300 whitespace-nowrap">${r.duration != null ? r.duration.toFixed(2) : '-'}</td>
                <td class="p-3 text-right font-mono ${r.delay ? 'text-rose-400 font-bold' : 'text-slate-400'} whitespace-nowrap">${r.delay != null ? r.delay.toFixed(2) : '-'}</td>
                <td class="p-3 text-slate-300 text-[11px] max-w-xs ${textCls}">${r.latest_activity || '-'}</td>
                <td class="p-3 text-slate-300 text-xs whitespace-nowrap">
                    <span class="px-2 py-0.5 rounded bg-slate-800/90 text-slate-300 border border-slate-700 font-mono text-[11px]">${r.discipline || 'General'}</span>
                </td>

                <td class="p-3 text-center whitespace-nowrap border-l border-slate-800/80">${mStatusBadge}</td>
                <td class="p-3 text-xs leading-snug max-w-sm ${textCls}">
                    <div class="flex items-center flex-wrap gap-1 mb-1">${consultantBadge}</div>
                    <div class="${bicColor} text-[11px] font-mono leading-tight">${r.ball_in_court || 'Hill Inter'}</div>
                </td>
                <td class="p-3 text-center whitespace-nowrap">${actionBadge}</td>
                <td class="p-3 text-right font-mono ${r.overdue_days ? 'text-rose-400 font-black' : 'text-slate-500'} whitespace-nowrap">
                    ${r.overdue_days != null ? r.overdue_days.toFixed(2) : '-'}
                </td>
                <td class="p-3 font-mono text-indigo-400 text-xs whitespace-nowrap">
                    ${r.aconex_url 
                        ? `<a href="${r.aconex_url}" target="_blank" class="hover:underline hover:text-indigo-300 flex items-center gap-1">
                             <span>${r.mail_no || '-'}</span>
                             <i data-lucide="external-link" class="w-3 h-3 opacity-60"></i>
                           </a>`
                        : (r.mail_no || '-')}
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
    if (window.AntigravityTableEngine) {
        AntigravityTableEngine.initTable('feed-table');
        AntigravityTableEngine.applyColumnVisibility('feed-table');
    }
    if (window.lucide) lucide.createIcons();
}

function toggleBicWrapText() {
    const chk = document.getElementById('bic-wrap-text-toggle');
    bicWrapText = chk ? chk.checked : true;
    renderBallInCourtTable(lastBicDataRows || []);
}

function toggleBicShowTime() {
    const chk = document.getElementById('bic-show-time-toggle');
    bicShowTime = chk ? chk.checked : false;
    renderBallInCourtTable(lastBicDataRows || []);
}

function updateBallInCourtPagination(page, limit, total) {
    const elRange = document.getElementById('bic-showing-range');
    const elPage = document.getElementById('bic-page-indicator');
    const btnPrev = document.getElementById('bic-btn-prev');
    const btnNext = document.getElementById('bic-btn-next');

    const elRangeTop = document.getElementById('bic-showing-range-top');
    const elPageTop = document.getElementById('bic-page-indicator-top');
    const btnPrevTop = document.getElementById('bic-btn-prev-top');
    const btnNextTop = document.getElementById('bic-btn-next-top');

    const totalPages = Math.ceil(total / limit) || 1;
    const start = total === 0 ? 0 : (page - 1) * limit + 1;
    const end = Math.min(total, page * limit);
    const rangeText = `Showing ${start}-${end} of ${total.toLocaleString()}`;
    const pageText = `Page ${page} of ${totalPages}`;

    if (elRange) elRange.innerText = rangeText;
    if (elRangeTop) elRangeTop.innerText = rangeText;
    if (elPage) elPage.innerText = pageText;
    if (elPageTop) elPageTop.innerText = pageText;

    const isPrevDisabled = page <= 1;
    const isNextDisabled = end >= total;

    if (btnPrev) btnPrev.disabled = isPrevDisabled;
    if (btnPrevTop) btnPrevTop.disabled = isPrevDisabled;
    if (btnNext) btnNext.disabled = isNextDisabled;
    if (btnNextTop) btnNextTop.disabled = isNextDisabled;
}

function applyBallInCourtFilters() {
    const selType = document.getElementById('bic-filter-file-type');
    const selCons = document.getElementById('bic-filter-consultant');
    const selParty = document.getElementById('bic-filter-party');
    const selAction = document.getElementById('bic-filter-action');
    const selStatus = document.getElementById('bic-filter-status');
    const selPkg = document.getElementById('bic-filter-pkg');
    const selDisc = document.getElementById('bic-filter-discipline');

    if (selType) {
        bicFilterFileType = selType.value;
        bicSelectedFileTypes.clear();
        bicSelectedFileTypes.add(bicFilterFileType);
    }
    if (selCons) bicFilterConsultant = selCons.value;
    if (selParty) bicFilterParty = selParty.value;
    if (selAction) bicFilterAction = selAction.value;
    if (selStatus) bicFilterStatus = selStatus.value;
    if (selPkg) bicFilterPkg = selPkg.value;
    if (selDisc) bicFilterDiscipline = selDisc.value;

    updateBicTypeTabButtons();
    renderBallInCourtActiveTags();
    loadBallInCourtData(1);
}

function resetBallInCourtFilters() {
    bicFilterFileType = 'all';
    bicSelectedFileTypes.clear();
    bicSelectedFileTypes.add('all');
    bicFilterDiscipline = 'all';
    bicFilterConsultant = 'all';
    bicFilterParty = 'all';
    bicFilterAction = 'all';
    bicFilterStatus = 'all';
    bicFilterPkg = 'all';
    bicSearchQuery = '';

    const selType = document.getElementById('bic-filter-file-type');
    const selCons = document.getElementById('bic-filter-consultant');
    const selParty = document.getElementById('bic-filter-party');
    const selAction = document.getElementById('bic-filter-action');
    const selStatus = document.getElementById('bic-filter-status');
    const selPkg = document.getElementById('bic-filter-pkg');
    const selDisc = document.getElementById('bic-filter-discipline');
    const inpSearch = document.getElementById('bic-search-input');
    const clearBtn = document.getElementById('bic-search-clear-btn');

    if (selType) selType.value = 'all';
    if (selCons) selCons.value = 'all';
    if (selParty) selParty.value = 'all';
    if (selAction) selAction.value = 'all';
    if (selStatus) selStatus.value = 'all';
    if (selPkg) selPkg.value = 'all';
    if (selDisc) selDisc.value = 'all';
    if (inpSearch) inpSearch.value = '';
    if (clearBtn) clearBtn.classList.add('hidden');

    updateBicTypeTabButtons();
    toggleAllBicSlicerCheckboxes(true);
    renderBallInCourtActiveTags();
    loadBallInCourtData(1);
}

let bicSearchTimer = null;
function handleBicSearchKeyup(e) {
    const val = (e.target.value || '').trim();
    const clearBtn = document.getElementById('bic-search-clear-btn');
    if (clearBtn) {
        if (val) {
            clearBtn.classList.remove('hidden');
        } else {
            clearBtn.classList.add('hidden');
        }
    }

    clearTimeout(bicSearchTimer);
    bicSearchTimer = setTimeout(() => {
        bicSearchQuery = e.target.value;
        renderBallInCourtActiveTags();
        loadBallInCourtData(1);
    }, 300);
}

function clearBicSearch() {
    const inpSearch = document.getElementById('bic-search-input');
    const clearBtn = document.getElementById('bic-search-clear-btn');
    if (inpSearch) inpSearch.value = '';
    if (clearBtn) clearBtn.classList.add('hidden');
    bicSearchQuery = '';
    renderBallInCourtActiveTags();
    loadBallInCourtData(1);
}

function renderBallInCourtActiveTags() {
    const container = document.getElementById('bic-active-tags-container');
    const countBadge = document.getElementById('bic-active-filters-count');
    if (!container) return;

    const tags = [];

    if (bicFilterFileType && bicFilterFileType !== 'all') {
        tags.push({ key: 'file_type', label: `Type: ${bicFilterFileType}`, color: 'bg-sky-500/20 text-sky-300 border-sky-500/30' });
    }
    if (bicFilterPkg && bicFilterPkg !== 'all') {
        tags.push({ key: 'package', label: `Package: ${bicFilterPkg}`, color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' });
    }
    if (bicFilterConsultant && bicFilterConsultant !== 'all') {
        tags.push({ key: 'consultant', label: `Consultant: ${bicFilterConsultant}`, color: 'bg-amber-500/20 text-amber-300 border-amber-500/30' });
    }
    if (bicFilterParty && bicFilterParty !== 'all') {
        const partyLabel = bicFilterParty.includes('|||') ? `Parties (${bicFilterParty.split('|||').length})` : `Party: ${bicFilterParty}`;
        tags.push({ key: 'party', label: partyLabel, color: 'bg-purple-500/20 text-purple-300 border-purple-500/30' });
    }
    if (bicFilterDiscipline && bicFilterDiscipline !== 'all') {
        tags.push({ key: 'discipline', label: `Discipline: ${bicFilterDiscipline}`, color: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30' });
    }
    if (bicFilterAction && bicFilterAction !== 'all') {
        tags.push({ key: 'action', label: `Action: ${bicFilterAction}`, color: 'bg-rose-500/20 text-rose-300 border-rose-500/30' });
    }
    if (bicFilterStatus && bicFilterStatus !== 'all') {
        tags.push({ key: 'status', label: `Status: ${bicFilterStatus}`, color: 'bg-teal-500/20 text-teal-300 border-teal-500/30' });
    }
    if (bicSearchQuery && bicSearchQuery.trim()) {
        tags.push({ key: 'search', label: `Search: "${bicSearchQuery.trim()}"`, color: 'bg-slate-800 text-slate-200 border-slate-700' });
    }

    if (countBadge) {
        if (tags.length > 0) {
            countBadge.innerText = `${tags.length} Filter${tags.length > 1 ? 's' : ''} Active`;
            countBadge.classList.remove('hidden');
        } else {
            countBadge.classList.add('hidden');
        }
    }

    if (tags.length === 0) {
        container.classList.add('hidden');
        container.innerHTML = '<span class="text-[10px] text-slate-400 font-semibold mr-1">Active Filters:</span>';
        return;
    }

    container.classList.remove('hidden');
    let html = '<span class="text-[10px] text-slate-400 font-semibold mr-1">Active Filters:</span>';
    tags.forEach(t => {
        html += `
            <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-lg text-[11px] font-medium border ${t.color}">
                <span>${t.label}</span>
                <button type="button" onclick="removeBicFilter('${t.key}')" class="hover:text-white transition font-bold" title="Remove this filter">
                    &times;
                </button>
            </span>
        `;
    });
    html += `
        <button type="button" onclick="resetBallInCourtFilters()" class="text-[10px] text-rose-400 hover:text-rose-300 font-semibold hover:underline ml-2">
            Clear All
        </button>
    `;
    container.innerHTML = html;
}

function removeBicFilter(key) {
    if (key === 'file_type') {
        bicFilterFileType = 'all';
        bicSelectedFileTypes.clear();
        bicSelectedFileTypes.add('all');
        const el = document.getElementById('bic-filter-file-type');
        if (el) el.value = 'all';
        updateBicTypeTabButtons();
    } else if (key === 'package') {
        bicFilterPkg = 'all';
        const el = document.getElementById('bic-filter-pkg');
        if (el) el.value = 'all';
    } else if (key === 'consultant') {
        bicFilterConsultant = 'all';
        const el = document.getElementById('bic-filter-consultant');
        if (el) el.value = 'all';
    } else if (key === 'party') {
        bicFilterParty = 'all';
        const el = document.getElementById('bic-filter-party');
        if (el) el.value = 'all';
        toggleAllBicSlicerCheckboxes(true);
    } else if (key === 'discipline') {
        bicFilterDiscipline = 'all';
        const el = document.getElementById('bic-filter-discipline');
        if (el) el.value = 'all';
    } else if (key === 'action') {
        bicFilterAction = 'all';
        const el = document.getElementById('bic-filter-action');
        if (el) el.value = 'all';
    } else if (key === 'status') {
        bicFilterStatus = 'all';
        const el = document.getElementById('bic-filter-status');
        if (el) el.value = 'all';
    } else if (key === 'search') {
        clearBicSearch();
        return;
    }
    renderBallInCourtActiveTags();
    loadBallInCourtData(1);
}

function changeBicPageLimit(val) {
    bicLimit = parseInt(val, 10) || 50;
    loadBallInCourtData(1);
}

function changeBicPage(delta) {
    const newPage = bicCurrentPage + delta;
    if (newPage >= 1 && (newPage - 1) * bicLimit < bicTotal) {
        loadBallInCourtData(newPage);
    }
}

function exportBallInCourtFilteredExcel() {
    exportBallInCourtExcel();
}

function exportBallInCourtExcel() {
    const params = new URLSearchParams();
    if (bicFilterFileType && bicFilterFileType !== 'all') params.append('file_type', bicFilterFileType);
    if (bicFilterDiscipline && bicFilterDiscipline !== 'all') params.append('discipline', bicFilterDiscipline);
    if (bicFilterConsultant && bicFilterConsultant !== 'all') params.append('consultant', bicFilterConsultant);
    if (bicFilterParty && bicFilterParty !== 'all') params.append('ball_in_court', bicFilterParty);
    if (bicFilterAction && bicFilterAction !== 'all') params.append('action', bicFilterAction);
    if (bicFilterStatus && bicFilterStatus !== 'all') params.append('process_status', bicFilterStatus);
    if (bicFilterPkg && bicFilterPkg !== 'all') params.append('package', bicFilterPkg);
    if (bicSearchQuery && bicSearchQuery.trim()) params.append('search', bicSearchQuery.trim());

    window.open(`/api/ball_in_court/export_excel?${params.toString()}`, '_blank');
}

async function refreshBallInCourtData() {
    try {
        const res = await fetch('/api/ball_in_court/refresh', { method: 'POST' });
        const json = await res.json();
        alert(json.message || 'Ball in Court dataset refreshed!');
        loadBallInCourtData(bicCurrentPage);
    } catch (err) {
        alert(`Failed to refresh: ${err.message}`);
    }
}

function printBallInCourtReport() {
    const params = new URLSearchParams({
        page: 1,
        limit: 1000
    });
    if (bicFilterParty && bicFilterParty !== 'all') params.append('ball_in_court', bicFilterParty);
    if (bicFilterAction && bicFilterAction !== 'all') params.append('action', bicFilterAction);
    if (bicFilterStatus && bicFilterStatus !== 'all') params.append('process_status', bicFilterStatus);
    if (bicFilterPkg && bicFilterPkg !== 'all') params.append('package', bicFilterPkg);
    if (bicSearchQuery && bicSearchQuery.trim()) params.append('search', bicSearchQuery.trim());

    const printWin = window.open('', '_blank', 'width=1200,height=800');
    if (!printWin) {
        alert('Please allow popups to open the print report.');
        return;
    }

    printWin.document.write('<html><head><title>Loading Report...</title></head><body style="font-family:sans-serif;padding:40px;">Generating printable report...</body></html>');

    fetch(`/api/ball_in_court/processes?${params.toString()}`)
        .then(r => r.json())
        .then(data => {
            const items = data.data || [];
            let rowsHtml = '';
            items.forEach(r => {
                const isOv = r.process_status === 'Overdue' || r.mail_status === 'Overdue';
                rowsHtml += `
                    <tr>
                        <td style="font-family:monospace;font-weight:bold;color:#0284c7;">${r.process_ref || '-'}</td>
                        <td style="text-align:center;">${r.initiated_on || '-'}</td>
                        <td style="text-align:center;font-weight:bold;color:${isOv ? '#dc2626' : '#16a34a'};">${r.process_status || '-'}</td>
                        <td style="text-align:right;">${r.duration != null ? r.duration.toFixed(2) : '-'}</td>
                        <td style="text-align:right;color:${r.delay ? '#dc2626' : '#64748b'};">${r.delay != null ? r.delay.toFixed(2) : '-'}</td>
                        <td>${r.latest_activity || '-'}</td>
                        <td style="text-align:center;font-weight:bold;color:${r.mail_status === 'Overdue' ? '#dc2626' : '#16a34a'};">${r.mail_status || '-'}</td>
                        <td style="font-weight:600;">${r.ball_in_court || '-'}</td>
                        <td style="text-align:center;color:${r.action === 'To Respond' ? '#dc2626' : '#0284c7'};font-weight:bold;">${r.action || '-'}</td>
                        <td style="text-align:right;font-weight:bold;color:#dc2626;">${r.overdue_days != null ? r.overdue_days.toFixed(2) : '-'}</td>
                        <td style="font-family:monospace;color:#4f46e5;">${r.mail_no || '-'}</td>
                    </tr>
                `;
            });

            printWin.document.open();
            printWin.document.write(`
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Ball in Court Process Details - Report</title>
                    <style>
                        @page { size: landscape; margin: 12mm; }
                        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 10px; color: #1e293b; margin: 0; padding: 15px; }
                        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0f172a; padding-bottom: 8px; margin-bottom: 12px; }
                        .title { font-size: 16px; font-weight: 900; color: #0f172a; }
                        .subtitle { font-size: 11px; color: #64748b; margin-top: 2px; }
                        .telemetry { font-size: 11px; font-weight: bold; color: #0284c7; }
                        table { width: 100%; border-collapse: collapse; margin-top: 5px; }
                        th, td { border: 1px solid #cbd5e1; padding: 5px 6px; font-size: 9.5px; }
                        th { background-color: #f1f5f9; font-weight: 800; text-transform: uppercase; font-size: 9px; }
                        .super-th { background-color: #0f172a; color: #ffffff; text-align: center; font-size: 11px; font-weight: 900; }
                        tr:nth-child(even) { background-color: #f8fafc; }
                    </style>
                </head>
                <body>
                    <div class="header">
                        <div>
                            <div class="title">Ras El Hekma Project - Ball in Court SLA &amp; Process Report</div>
                            <div class="subtitle">Generated on ${new Date().toLocaleString()} | Filter: ${bicFilterParty} | Action: ${bicFilterAction}</div>
                        </div>
                        <div class="telemetry">
                            Total Records: ${items.length} | Overdue: ${data.kpis?.total_overdue || 0}
                        </div>
                    </div>
                    <table>
                        <thead>
                            <tr>
                                <th colspan="6" class="super-th" style="background:#0f172a;">Processes</th>
                                <th colspan="5" class="super-th" style="background:#1e293b;">Mails</th>
                            </tr>
                            <tr>
                                <th>Process Reference</th>
                                <th style="text-align:center;">Initiated On</th>
                                <th style="text-align:center;">Process Status</th>
                                <th style="text-align:right;">Duration</th>
                                <th style="text-align:right;">Delay</th>
                                <th>Latest Activity</th>
                                <th style="text-align:center;">Mail Status</th>
                                <th>Ball in Court</th>
                                <th style="text-align:center;">Action</th>
                                <th style="text-align:right;">Overdue</th>
                                <th>Mail No.</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rowsHtml}
                        </tbody>
                    </table>
                    <script>
                        window.onload = function() { window.print(); }
                    </script>
                </body>
                </html>
            `);
            printWin.document.close();
        })
        .catch(err => {
            alert(`Failed to generate report: ${err.message}`);
            printWin.close();
        });
}

// =========================================================================
// AI COPILOT & ASSISTANT INTELLIGENCE ENGINE (BILINGUAL EN/AR)
// =========================================================================
let aiCopilotOpen = false;
let aiChatHistory = [];
let isAiThinking = false;
let aiTableCounter = 0;

let lastAiToggleTime = 0;

function toggleAiCopilot(forceOpen) {
    const now = Date.now();
    if (typeof forceOpen !== 'boolean' && now - lastAiToggleTime < 250) {
        return; // Debounce rapid duplicate click events
    }
    lastAiToggleTime = now;

    if (typeof forceOpen === 'boolean') {
        aiCopilotOpen = forceOpen;
    } else {
        aiCopilotOpen = !aiCopilotOpen;
    }
    const drawer = document.getElementById('ai-copilot-drawer');
    const backdrop = document.getElementById('ai-copilot-backdrop');
    if (!drawer || !backdrop) {
        console.error("AI Copilot elements missing from DOM");
        return;
    }

    if (aiCopilotOpen) {
        backdrop.style.display = 'block';
        drawer.style.display = 'flex';
        // Force reflow
        void drawer.offsetWidth;
        backdrop.classList.remove('hidden');
        backdrop.style.opacity = '1';
        drawer.style.transform = 'translateX(0%)';
        setTimeout(() => {
            const input = document.getElementById('ai-chat-input');
            if (input) input.focus();
        }, 150);
    } else {
        drawer.style.transform = 'translateX(100%)';
        backdrop.style.opacity = '0';
        setTimeout(() => {
            if (!aiCopilotOpen) {
                backdrop.style.display = 'none';
                drawer.style.display = 'none';
                backdrop.classList.add('hidden');
            }
        }, 300);
    }
    if (window.lucide) lucide.createIcons();
}
window.toggleAiCopilot = toggleAiCopilot;

function submitAiPrompt(promptText) {
    const input = document.getElementById('ai-chat-input');
    if (input) input.value = promptText;
    if (!aiCopilotOpen) toggleAiCopilot(true);
    sendAiChatMessage(promptText);
}

function handleAiChatSubmit(e) {
    if (e) e.preventDefault();
    const input = document.getElementById('ai-chat-input');
    if (!input) return;
    const msg = (input.value || '').trim();
    if (!msg) return;
    if (!aiCopilotOpen) toggleAiCopilot(true);
    sendAiChatMessage(msg);
}

function handleAiInputKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleAiChatSubmit(e);
    }
}

function clearAiChatHistory() {
    aiChatHistory = [];
    const container = document.getElementById('ai-chat-messages');
    if (!container) return;
    container.innerHTML = `
        <div class="flex items-start gap-3">
            <div class="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/40 text-indigo-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                <i data-lucide="bot" class="w-4 h-4"></i>
            </div>
            <div class="bg-slate-950/80 border border-slate-800 rounded-2xl p-4 max-w-[88%] text-slate-200 space-y-2">
                <p class="font-bold text-white text-sm">Hello! I am your Ras El Hekma Project Controls AI Assistant.</p>
                <p class="text-slate-300 leading-relaxed">
                    You can ask me questions in English or Arabic. I analyze live Oracle Aconex data across all 20 packages, including RFIs, SCRs, Workflows, and Ball in Court records.
                </p>
                <div class="pt-2 border-t border-slate-800/80 grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
                    <div class="bg-slate-900 p-2 rounded-lg border border-slate-800">
                        <span class="font-semibold text-sky-400">English query example:</span>
                        <div class="text-slate-400 italic mt-0.5">"Show me all overdue RFIs in DP03-West"</div>
                    </div>
                    <div class="bg-slate-900 p-2 rounded-lg border border-slate-800">
                        <span class="font-semibold text-emerald-400">Arabic query example:</span>
                        <div class="text-slate-400 italic mt-0.5">"Show me all RFIs in project DP03-West since 2026-06-01"</div>
                    </div>
                </div>
            </div>
        </div>
    `;
    if (window.lucide) lucide.createIcons();
    showToast('Chat history cleared', 'info');
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);
    // Code blocks ```code```
    html = html.replace(/```([\s\S]*?)```/g, '<pre class="bg-slate-900 border border-slate-800 rounded-lg p-2.5 my-2 overflow-x-auto text-[11px] font-mono text-sky-300"><code>$1</code></pre>');
    // Inline code `code`
    html = html.replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-sky-300 font-mono text-[11px]">$1</code>');
    // Bold **text**
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="text-white font-bold">$1</strong>');
    // Headings
    html = html.replace(/^### (.*$)/gim, '<h4 class="text-xs font-bold text-sky-400 mt-3 mb-1 uppercase tracking-wider">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 class="text-sm font-black text-white mt-3.5 mb-1.5 pb-1 border-b border-slate-800">$1</h3>');
    html = html.replace(/^# (.*$)/gim, '<h2 class="text-base font-black text-white mt-4 mb-2 pb-1 border-b border-slate-800">$1</h2>');
    // Bullet points
    html = html.replace(/^\s*[-*]\s+(.*$)/gim, '<li class="ml-4 list-disc text-slate-300 my-0.5">$1</li>');
    // Numbered lists
    html = html.replace(/^\s*(\d+)\.\s+(.*$)/gim, '<li class="ml-4 list-decimal text-slate-300 my-0.5"><span class="font-bold text-slate-200">$1.</span> $2</li>');
    // Line breaks
    html = html.replace(/\n\n/g, '<div class="h-2"></div>');
    html = html.replace(/\n/g, '<br/>');
    return html;
}

async function sendAiChatMessage(userMessage) {
    if (!userMessage || isAiThinking) return;
    if (!aiCopilotOpen) toggleAiCopilot(true);
    const container = document.getElementById('ai-chat-messages');
    const input = document.getElementById('ai-chat-input');
    const sendBtn = document.getElementById('ai-send-btn');
    if (!container) {
        console.error("AI chat messages container #ai-chat-messages not found");
        return;
    }

    if (input) input.value = '';
    isAiThinking = true;
    if (sendBtn) sendBtn.disabled = true;

    // Detect if input contains Arabic characters
    const isArabic = /[\u0600-\u06FF]/.test(userMessage);

    // Append User Message
    const userMsgHtml = `
        <div class="flex items-start justify-end gap-3">
            <div class="bg-gradient-to-r from-sky-600 to-indigo-600 text-white rounded-2xl rounded-tr-sm p-3.5 max-w-[85%] shadow-md shadow-sky-600/10 text-xs font-medium leading-relaxed ${isArabic ? 'text-right' : 'text-left'}" ${isArabic ? 'dir="rtl"' : ''}>
                ${escapeHtml(userMessage)}
            </div>
            <div class="w-7 h-7 rounded-lg bg-sky-500/20 border border-sky-500/40 text-sky-300 flex items-center justify-center flex-shrink-0 mt-0.5">
                <i data-lucide="user" class="w-4 h-4"></i>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', userMsgHtml);

    // Append Thinking Indicator
    const thinkingId = `ai-thinking-${Date.now()}`;
    const thinkingHtml = `
        <div id="${thinkingId}" class="flex items-start gap-3">
            <div class="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/40 text-indigo-400 flex items-center justify-center flex-shrink-0 mt-0.5 animate-pulse">
                <i data-lucide="bot" class="w-4 h-4"></i>
            </div>
            <div class="bg-slate-950/80 border border-slate-800 rounded-2xl p-3 max-w-[85%] text-slate-400 flex items-center gap-2 text-xs">
                <div class="w-2 h-2 rounded-full bg-sky-400 animate-ping"></div>
                <span>Analyzing Oracle Aconex database & DuckDB tables...</span>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', thinkingHtml);
    container.scrollTop = container.scrollHeight;
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch('/api/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: userMessage,
                history: aiChatHistory
            })
        });

        // Remove thinking indicator
        const thinkingEl = document.getElementById(thinkingId);
        if (thinkingEl) thinkingEl.remove();

        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: Failed to get answer from AI service`);
        }

        const data = await res.json();
        const replyText = data.text || data.reply || (data.status === 'success' ? 'Completed query.' : 'No data found.');
        const replyLang = data.language || (isArabic ? 'ar' : 'en');
        const isReplyArabic = replyLang === 'ar' || /[\u0600-\u06FF]/.test(replyText);

        // Save history
        aiChatHistory.push({ role: 'user', content: userMessage });
        aiChatHistory.push({ role: 'assistant', content: replyText });

        // Build Response HTML
        aiTableCounter++;
        const currentTableId = `ai-table-${aiTableCounter}`;
        let responseInnerHtml = `
            <div class="text-xs leading-relaxed text-slate-200 ${isReplyArabic ? 'text-right' : 'text-left'}" ${isReplyArabic ? 'dir="rtl"' : ''}>
                ${formatMarkdown(replyText)}
            </div>
        `;

        // Render KPI metrics cards if available
        if (data.kpis && Object.keys(data.kpis).length > 0) {
            const k = data.kpis;
            const kpiEntries = Object.entries(k);
            let kpiCardsHtml = '';
            kpiEntries.forEach(([label, val]) => {
                const isOverdueLabel = label.toLowerCase().includes('overdue');
                const valStr = String(val);
                const colorClass = isOverdueLabel && val > 0 ? 'text-rose-400 font-bold' : (isOverdueLabel ? 'text-emerald-400' : 'text-sky-300');
                kpiCardsHtml += `
                    <div class="bg-slate-900/90 rounded-lg p-2 border border-slate-800 text-center">
                        <div class="text-[10px] text-slate-400 uppercase font-semibold truncate" title="${escapeHtml(label)}">${escapeHtml(label)}</div>
                        <div class="text-sm font-black ${colorClass} font-mono mt-0.5 truncate" title="${escapeHtml(valStr)}">${escapeHtml(valStr)}</div>
                    </div>
                `;
            });

            responseInnerHtml += `
                <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-3 mt-3 border-t border-slate-800/80">
                    ${kpiCardsHtml}
                </div>
            `;
        }

        // Render Interactive Table if available
        if (data.table_rows && data.table_rows.length > 0) {
            const rows = data.table_rows.slice(0, 50); // display up to 50 rows in inline chat
            let tableRowsHtml = '';
            rows.forEach(r => {
                let ref, pkg, subject, date, lateStr, url, isOverdue;
                if (Array.isArray(r)) {
                    ref = r[0] || '-';
                    pkg = r[1] || '-';
                    subject = r[2] || '-';
                    date = r[5] || r[6] || '-';
                    lateStr = r[7] !== undefined ? String(r[7]) : '0d';
                    url = r[8] || '#';
                    isOverdue = lateStr.includes('+') || parseInt(lateStr) > 0;
                } else {
                    ref = r.ref || r.id || r.mail_no || '-';
                    pkg = r.project_id || r.package || '-';
                    subject = r.subject || r.title || '-';
                    date = r.date || r.sent_date || '-';
                    lateStr = r.days_late ? `+${r.days_late}d` : '0d';
                    url = r.aconex_url || '#';
                    isOverdue = r.overdue || (r.days_late && r.days_late > 0);
                }

                const statusBadge = isOverdue
                    ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">${lateStr} Late</span>`
                    : `<span class="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Active</span>`;

                tableRowsHtml += `
                    <tr class="hover:bg-slate-800/50 transition border-b border-slate-800/60">
                        <td class="p-2 font-mono font-bold">
                            <a href="${url}" target="_blank" class="text-sky-400 hover:underline flex items-center gap-1">
                                <span>${escapeHtml(ref)}</span>
                                <i data-lucide="external-link" class="w-3 h-3 text-slate-500"></i>
                            </a>
                        </td>
                        <td class="p-2 font-mono text-slate-300 text-[11px]">${escapeHtml(pkg)}</td>
                        <td class="p-2 text-slate-200 truncate max-w-[200px]" title="${escapeHtml(subject)}">${escapeHtml(subject)}</td>
                        <td class="p-2 text-slate-400 whitespace-nowrap text-[11px] font-mono">${escapeHtml(date)}</td>
                        <td class="p-2 text-center whitespace-nowrap">${statusBadge}</td>
                    </tr>
                `;
            });

            responseInnerHtml += `
                <div class="mt-3 pt-3 border-t border-slate-800 space-y-2">
                    <div class="flex items-center justify-between">
                        <div class="text-[11px] font-bold text-slate-300 flex items-center gap-1.5">
                            <i data-lucide="table" class="w-3.5 h-3.5 text-sky-400"></i>
                            <span>Query Results Preview (${rows.length} of ${data.table_rows.length} records)</span>
                        </div>
                        <button onclick="exportAiTableToCsv('${currentTableId}', 'Aconex_AI_Query_${Date.now()}.csv')" class="px-2.5 py-1 rounded-lg bg-emerald-600/20 hover:bg-emerald-600 text-emerald-300 hover:text-white border border-emerald-500/30 text-[11px] font-bold flex items-center gap-1 transition">
                            <i data-lucide="download" class="w-3 h-3"></i>
                            <span>Export CSV</span>
                        </button>
                    </div>

                    <div class="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/90 max-h-64 custom-scrollbar">
                        <table class="w-full text-left text-xs" id="${currentTableId}">
                            <thead class="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800 sticky top-0 z-10">
                                <tr>
                                    <th class="p-2">Reference</th>
                                    <th class="p-2">Package</th>
                                    <th class="p-2">Subject / Title</th>
                                    <th class="p-2">Date</th>
                                    <th class="p-2 text-center">Status / SLA</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-slate-800/40">
                                ${tableRowsHtml}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }

        // Render suggested follow-up chips if available
        const suggestionsList = data.suggested_queries || data.suggestions || [];
        if (suggestionsList && suggestionsList.length > 0) {
            let pillsHtml = '';
            suggestionsList.forEach(sug => {
                pillsHtml += `
                    <button onclick="submitAiPrompt('${escapeHtml(sug)}')" class="px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 text-[11px] transition text-left cursor-pointer">
                        ${escapeHtml(sug)}
                    </button>
                `;
            });
            responseInnerHtml += `
                <div class="pt-3 mt-3 border-t border-slate-800/80">
                    <div class="text-[10px] uppercase font-bold text-slate-500 mb-1.5">Suggested Next Questions:</div>
                    <div class="flex flex-wrap gap-1.5">${pillsHtml}</div>
                </div>
            `;
        }

        const assistantBubbleHtml = `
            <div class="flex items-start gap-3">
                <div class="w-7 h-7 rounded-lg bg-indigo-600/30 border border-indigo-500/40 text-indigo-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <i data-lucide="bot" class="w-4 h-4"></i>
                </div>
                <div class="bg-slate-950/80 border border-slate-800 rounded-2xl p-4 max-w-[92%] shadow-xl space-y-2">
                    ${responseInnerHtml}
                </div>
            </div>
        `;

        container.insertAdjacentHTML('beforeend', assistantBubbleHtml);

    } catch (err) {
        const thinkingEl = document.getElementById(thinkingId);
        if (thinkingEl) thinkingEl.remove();

        const errorHtml = `
            <div class="flex items-start gap-3">
                <div class="w-7 h-7 rounded-lg bg-rose-600/30 border border-rose-500/40 text-rose-400 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <i data-lucide="alert-circle" class="w-4 h-4"></i>
                </div>
                <div class="bg-rose-500/10 border border-rose-500/30 text-rose-300 rounded-2xl p-3.5 max-w-[85%] text-xs">
                    <strong class="font-bold">Error analyzing request:</strong> ${escapeHtml(err.message)}
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', errorHtml);
    } finally {
        isAiThinking = false;
        if (sendBtn) sendBtn.disabled = false;
        container.scrollTop = container.scrollHeight;
        if (window.lucide) lucide.createIcons();
    }
}

function exportAiTableToCsv(tableId, filename = 'aconex_ai_query_results.csv') {
    const table = document.getElementById(tableId);
    if (!table) return;
    let csv = [];
    const rows = table.querySelectorAll('tr');
    rows.forEach(row => {
        const cols = row.querySelectorAll('th, td');
        const rowData = [];
        cols.forEach(col => {
            let text = col.innerText.replace(/"/g, '""').trim();
            rowData.push(`"${text}"`);
        });
        csv.push(rowData.join(','));
    });
    const csvContent = '\uFEFF' + csv.join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('Exported AI query results to CSV', 'success');
}

// Explicit Global Window Bindings for AI Copilot
window.toggleAiCopilot = toggleAiCopilot;
window.submitAiPrompt = submitAiPrompt;
window.handleAiChatSubmit = handleAiChatSubmit;
window.handleAiInputKeyDown = handleAiInputKeyDown;
window.clearAiChatHistory = clearAiChatHistory;
window.sendAiChatMessage = sendAiChatMessage;
window.exportAiTableToCsv = exportAiTableToCsv;

// =========================================================================
// THEME SWITCHER (LIGHT MODE / DARK MODE)
// =========================================================================
function initAppTheme() {
    const saved = localStorage.getItem('reh_app_theme') || 'dark';
    setAppTheme(saved);
}

function setAppTheme(theme) {
    const html = document.documentElement;
    const isLight = theme === 'light';
    if (isLight) {
        html.classList.remove('dark');
        html.classList.add('light');
    } else {
        html.classList.remove('light');
        html.classList.add('dark');
    }
    localStorage.setItem('reh_app_theme', theme);

    // When dark, button shows Sun icon + "Light Mode" (action: switch to light)
    // When light, button shows Moon icon + "Dark Mode" (action: switch to dark)
    document.querySelectorAll('.theme-icon-sun').forEach(el => el.classList.toggle('hidden', isLight));
    document.querySelectorAll('.theme-icon-moon').forEach(el => el.classList.toggle('hidden', !isLight));
    document.querySelectorAll('.theme-toggle-label').forEach(el => el.innerText = isLight ? 'Dark Mode' : 'Light Mode');

    if (window.lucide) lucide.createIcons();
}

function toggleAppTheme() {
    const current = document.documentElement.classList.contains('light') ? 'light' : 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    setAppTheme(next);
    showToast(`Switched to ${next.toUpperCase()} Mode`, 'info');
}

window.toggleAppTheme = toggleAppTheme;
window.setAppTheme = setAppTheme;
window.initAppTheme = initAppTheme;

// Initialize theme on script evaluation
initAppTheme();

// =========================================================================
// 8. OVERDUE SUB-TABS (SSC BACKLOG vs CONTRACTOR RFIs)
// =========================================================================
function switchOverdueSubTab(subtab) {
    const btnSsc = document.getElementById('btn-subtab-ssc-overdue');
    const btnRfi = document.getElementById('btn-subtab-contractor-rfis');
    const contentSsc = document.getElementById('subtab-content-ssc');
    const contentRfi = document.getElementById('subtab-content-contractor-rfis');

    if (subtab === 'ssc') {
        if (contentSsc) contentSsc.classList.remove('hidden');
        if (contentRfi) contentRfi.classList.add('hidden');

        if (btnSsc) {
            btnSsc.className = 'px-5 py-2.5 rounded-xl text-xs font-black transition flex items-center gap-2 bg-gradient-to-r from-rose-600 to-amber-600 text-white shadow-lg shadow-rose-600/30 cursor-pointer';
        }
        if (btnRfi) {
            btnRfi.className = 'px-5 py-2.5 rounded-xl text-xs font-black transition flex items-center gap-2 bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800 border border-slate-800 cursor-pointer';
        }
    } else if (subtab === 'rfis') {
        if (contentSsc) contentSsc.classList.add('hidden');
        if (contentRfi) contentRfi.classList.remove('hidden');

        if (btnRfi) {
            btnRfi.className = 'px-5 py-2.5 rounded-xl text-xs font-black transition flex items-center gap-2 bg-gradient-to-r from-sky-600 to-indigo-600 text-white shadow-lg shadow-sky-600/30 cursor-pointer';
        }
        if (btnSsc) {
            btnSsc.className = 'px-5 py-2.5 rounded-xl text-xs font-black transition flex items-center gap-2 bg-slate-900 text-slate-400 hover:text-white hover:bg-slate-800 border border-slate-800 cursor-pointer';
        }

        loadContractorRfis(1);
    }
    if (window.lucide) lucide.createIcons();
}
window.switchOverdueSubTab = switchOverdueSubTab;

// Universal Date Range Presets across All Registers
function applyUniversalDatePreset(preset, tabKey) {
    const today = new Date();
    let toDateStr = today.toISOString().split('T')[0];
    let fromDateStr = ''; // Default full history

    if (preset === 'all') {
        fromDateStr = '';
        toDateStr = '';
    } else if (preset === 'baseline') {
        fromDateStr = '2026-03-01';
        toDateStr = today.toISOString().split('T')[0];
    } else if (preset === '1m') {
        const d = new Date(today);
        d.setMonth(d.getMonth() - 1);
        fromDateStr = d.toISOString().split('T')[0];
    } else if (preset === '2m') {
        const d = new Date(today);
        d.setMonth(d.getMonth() - 2);
        fromDateStr = d.toISOString().split('T')[0];
    } else if (preset === '3m') {
        const d = new Date(today);
        d.setMonth(d.getMonth() - 3);
        fromDateStr = d.toISOString().split('T')[0];
    } else if (preset === '6m') {
        const d = new Date(today);
        d.setMonth(d.getMonth() - 6);
        fromDateStr = d.toISOString().split('T')[0];
    } else if (preset === 'custom') {
        return;
    }

    if (tabKey === 'ctrl-ssc') {
        const f = document.getElementById('ctrl-ssc-from-date');
        const t = document.getElementById('ctrl-ssc-to-date');
        if (f) f.value = fromDateStr;
        if (t) t.value = toDateStr;
        onCtrlSscDateRangeChanged();
    } else if (tabKey === 'rfi-contractor') {
        const f = document.getElementById('rfi-contractor-from-date');
        const t = document.getElementById('rfi-contractor-to-date');
        if (f) f.value = fromDateStr;
        if (t) t.value = toDateStr;
        loadContractorRfis(1);
    }
}
window.applyUniversalDatePreset = applyUniversalDatePreset;

async function onCtrlSscDateRangeChanged() {
    await initControlsTab(true);
    if (ctrlSelectedProjectId) {
        selectCtrlProject(ctrlSelectedProjectId);
    }
}
window.onCtrlSscDateRangeChanged = onCtrlSscDateRangeChanged;

// =========================================================================
// 9. CONTRACTOR RFIs LOGIC & EMAIL REMINDER CONTROLLER
// =========================================================================
let crfiCurrentPage = 1;
let crfiLimit = 50;
let crfiTotal = 0;
let crfiDebounceTimer = null;
let crfiFilterOptionsLoaded = false;

function debounceContractorRfiSearch() {
    clearTimeout(crfiDebounceTimer);
    crfiDebounceTimer = setTimeout(() => {
        loadContractorRfis(1);
    }, 300);
}
window.debounceContractorRfiSearch = debounceContractorRfiSearch;

async function loadContractorRfis(page = 1) {
    crfiCurrentPage = page;
    const project = document.getElementById('crfi-filter-project')?.value || 'all';
    const company = document.getElementById('crfi-filter-company')?.value || 'all';
    const status = document.getElementById('crfi-filter-status')?.value || 'overdue';
    const search = document.getElementById('crfi-filter-search')?.value || '';
    const fromDate = document.getElementById('rfi-contractor-from-date')?.value || '';
    const toDate = document.getElementById('rfi-contractor-to-date')?.value || '';
    const limit = document.getElementById('crfi-limit-select')?.value || 50;
    crfiLimit = parseInt(limit, 10);

    const tbody = document.getElementById('crfi-table-tbody');
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="py-12 text-center text-slate-400">
                    <div class="inline-block animate-spin w-6 h-6 border-2 border-sky-500 border-t-transparent rounded-full mb-2"></div>
                    <p class="text-xs">Loading Contractor RFIs from DuckDB...</p>
                </td>
            </tr>
        `;
    }

    try {
        const params = new URLSearchParams({
            page: String(page),
            limit: String(limit),
            project: project,
            company: company,
            status: status,
            from_date: fromDate,
            to_date: toDate,
            search: search
        });

        const res = await fetch(`/api/controls/contractor_rfis?${params.toString()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load contractor RFIs`);
        const json = await res.json();

        // Update KPIs
        const kpis = json.kpis || {};
        const kTotal = document.getElementById('kpi-crfi-total');
        const kOverdue = document.getElementById('kpi-crfi-overdue');
        const kOntime = document.getElementById('kpi-crfi-ontime');
        const kMaxDelay = document.getElementById('kpi-crfi-maxdelay');
        if (kTotal) kTotal.innerText = (kpis.total_rfis || 0).toLocaleString();
        if (kOverdue) kOverdue.innerText = (kpis.overdue_rfis ?? kpis.overdue_count ?? 0).toLocaleString();
        if (kOntime) kOntime.innerText = (kpis.on_time_rfis ?? kpis.ontime_count ?? 0).toLocaleString();
        if (kMaxDelay) kMaxDelay.innerText = `+${kpis.max_delay_days || 0}d`;

        // Update Subtab count badge
        const rfiBadge = document.getElementById('badge-subtab-rfi-count');
        if (rfiBadge) {
            rfiBadge.innerText = `${(kpis.overdue_rfis ?? kpis.overdue_count ?? json.total_count ?? 0).toLocaleString()} Overdue RFIs`;
        }

        // Dynamically update responsible answering companies based on selected project
        const availableProjects = json.available_projects || json.filter_options?.projects || [];
        const availableCompanies = json.available_companies || json.filter_options?.companies || [];
        if (!crfiFilterOptionsLoaded && availableProjects.length > 0) {
            populateContractorRfiFilters({ projects: availableProjects });
            crfiFilterOptionsLoaded = true;
        }
        // Always refresh company dropdown for current project selection
        if (availableCompanies && availableCompanies.length > 0) {
            updateContractorRfiCompanyDropdown(availableCompanies);
        }

        crfiTotal = json.total_count ?? json.total ?? 0;
        const totalPages = json.total_pages || Math.ceil(crfiTotal / crfiLimit) || 1;

        // Render table
        renderContractorRfisTable(json.rfis || json.data || []);

        // Update pagination
        const countLabel = document.getElementById('crfi-table-count-label');
        if (countLabel) {
            const start = crfiTotal === 0 ? 0 : (page - 1) * crfiLimit + 1;
            const end = Math.min(page * crfiLimit, crfiTotal);
            countLabel.innerText = `Showing ${start}-${end} of ${crfiTotal.toLocaleString()} contractor RFIs`;
        }

        const pageInd = document.getElementById('crfi-page-indicator');
        const pageIndTop = document.getElementById('crfi-page-indicator-top');
        const pageStr = `Page ${page} of ${totalPages}`;
        if (pageInd) pageInd.innerText = pageStr;
        if (pageIndTop) pageIndTop.innerText = pageStr;

        const prevBtn = document.getElementById('crfi-prev-btn');
        const prevBtnTop = document.getElementById('crfi-prev-btn-top');
        const nextBtn = document.getElementById('crfi-next-btn');
        const nextBtnTop = document.getElementById('crfi-next-btn-top');
        const isPrevDisabled = page <= 1;
        const isNextDisabled = page >= totalPages;

        if (prevBtn) prevBtn.disabled = isPrevDisabled;
        if (prevBtnTop) prevBtnTop.disabled = isPrevDisabled;
        if (nextBtn) nextBtn.disabled = isNextDisabled;
        if (nextBtnTop) nextBtnTop.disabled = isNextDisabled;

    } catch (err) {
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="py-12 text-center text-rose-400">
                        <i data-lucide="alert-triangle" class="w-6 h-6 mx-auto mb-1"></i>
                        <p class="text-xs font-bold">Error loading contractor RFIs: ${escapeHtml(err.message)}</p>
                    </td>
                </tr>
            `;
        }
    }
    if (window.lucide) lucide.createIcons();
}
window.loadContractorRfis = loadContractorRfis;

function populateContractorRfiFilters(opts) {
    const projSelect = document.getElementById('crfi-filter-project');
    const compSelect = document.getElementById('crfi-filter-company');

    if (projSelect && opts.projects) {
        const cur = projSelect.value;
        let html = '<option value="all">All Project Packages</option>';
        opts.projects.forEach(p => {
            html += `<option value="${escapeHtml(p)}" ${p === cur ? 'selected' : ''}>${escapeHtml(p)}</option>`;
        });
        projSelect.innerHTML = html;
    }

    if (compSelect && opts.companies) {
        const cur = compSelect.value;
        let html = '<option value="all">All Responsible Companies</option>';
        opts.companies.forEach(c => {
            html += `<option value="${escapeHtml(c)}" ${c === cur ? 'selected' : ''}>${escapeHtml(c)}</option>`;
        });
        compSelect.innerHTML = html;
    }
}

function renderContractorRfisTable(items) {
    const tbody = document.getElementById('crfi-table-tbody');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="py-16 text-center text-slate-500">
                    <i data-lucide="inbox" class="w-8 h-8 mx-auto mb-2 text-slate-600"></i>
                    <p class="text-sm font-semibold text-slate-400">No Contractor RFIs match the active filter criteria.</p>
                </td>
            </tr>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    let rowsHtml = '';
    items.forEach(r => {
        const mailNo = r.mail_no || r.mail_number || '-';
        const pkg = r.project_package || r.project_id || '-';
        const fromOrg = r.from_org || r.from_organization || '-';
        const toOrg = r.to_org || r.to_organization || '-';
        const daysLate = r.days_late ?? r.delay_days ?? 0;
        const isLate = r.is_overdue || daysLate > 0;
        const delayBadge = isLate
            ? `<span class="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">+${daysLate}d Late</span>`
            : `<span class="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">On Time</span>`;

        const isScr = (r.mail_type && r.mail_type.includes('Clarification')) || (r.mail_no && r.mail_no.includes('SCR')) || (r.subject && r.subject.includes('SCR'));
        const typeBadge = isScr 
            ? `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 mr-1.5">SCR</span>`
            : `<span class="px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30 mr-1.5">RFI</span>`;

        rowsHtml += `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="p-3">
                    <div class="flex items-center gap-1">
                        ${typeBadge}
                        <a href="${escapeHtml(r.aconex_url || '#')}" target="_blank" class="font-mono text-sky-400 hover:text-sky-300 hover:underline font-bold flex items-center gap-1">
                            <span>${escapeHtml(mailNo)}</span>
                            <i data-lucide="external-link" class="w-3 h-3 text-slate-500"></i>
                        </a>
                    </div>
                </td>
                <td class="p-3 font-semibold text-slate-300">
                    <span class="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 font-mono text-[11px]">${escapeHtml(pkg)}</span>
                </td>
                <td class="p-3 text-slate-200">
                    <div class="line-clamp-2 leading-relaxed" title="${escapeHtml(r.subject || '')}">
                        ${escapeHtml(r.subject || '-')}
                    </div>
                </td>
                <td class="p-3 text-slate-400 truncate" title="${escapeHtml(fromOrg)}">
                    ${escapeHtml(fromOrg)}
                </td>
                <td class="p-3 font-medium text-sky-300 truncate" title="${escapeHtml(toOrg)}">
                    <span class="px-2 py-0.5 rounded bg-sky-950/40 border border-sky-800/50 text-[11px]">${escapeHtml(toOrg)}</span>
                </td>
                <td class="p-3 font-mono text-slate-400 text-[11px]">${escapeHtml(String(r.sent_date || '').slice(0, 10))}</td>
                <td class="p-3 font-mono text-slate-400 text-[11px]">${escapeHtml(String(r.due_date || '').slice(0, 10))}</td>
                <td class="p-3 text-center">${delayBadge}</td>
            </tr>
        `;
    });

    tbody.innerHTML = rowsHtml;
    if (window.lucide) lucide.createIcons();
}

function prevContractorRfiPage() {
    if (crfiCurrentPage > 1) {
        loadContractorRfis(crfiCurrentPage - 1);
    }
}
window.prevContractorRfiPage = prevContractorRfiPage;

function nextContractorRfiPage() {
    const totalPages = Math.ceil(crfiTotal / crfiLimit) || 1;
    if (crfiCurrentPage < totalPages) {
        loadContractorRfis(crfiCurrentPage + 1);
    }
}
window.nextContractorRfiPage = nextContractorRfiPage;

let currentRfiEmailHtml = '';
let currentRfiEmailPlain = '';

function switchRfiModalTab(mode) {
    const tabHtml = document.getElementById('modal-rfi-tab-html');
    const tabPlain = document.getElementById('modal-rfi-tab-plain');
    const containerHtml = document.getElementById('modal-rfi-preview-html-container');
    const containerPlain = document.getElementById('modal-rfi-preview-plain-container');

    if (mode === 'html') {
        if (tabHtml) {
            tabHtml.className = 'px-3 py-1.5 rounded-lg bg-sky-600 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer';
        }
        if (tabPlain) {
            tabPlain.className = 'px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 font-semibold text-xs flex items-center gap-1.5 transition cursor-pointer';
        }
        if (containerHtml) containerHtml.classList.remove('hidden');
        if (containerPlain) containerPlain.classList.add('hidden');
    } else {
        if (tabPlain) {
            tabPlain.className = 'px-3 py-1.5 rounded-lg bg-sky-600 text-white font-bold text-xs flex items-center gap-1.5 transition cursor-pointer';
        }
        if (tabHtml) {
            tabHtml.className = 'px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700 font-semibold text-xs flex items-center gap-1.5 transition cursor-pointer';
        }
        if (containerHtml) containerHtml.classList.add('hidden');
        if (containerPlain) containerPlain.classList.remove('hidden');
    }
}
window.switchRfiModalTab = switchRfiModalTab;

async function copyRfiEmailHtml() {
    const previewEl = document.getElementById('modal-rfi-email-preview-html');
    const htmlContent = currentRfiEmailHtml || (previewEl ? previewEl.innerHTML : '');
    const plainContent = document.getElementById('modal-rfi-email-body')?.value || currentRfiEmailPlain || '';

    if (!htmlContent) {
        showToast('No formatted email preview available to copy.', 'error');
        return;
    }

    try {
        const blobHtml = new Blob([htmlContent], { type: 'text/html' });
        const blobText = new Blob([plainContent || htmlContent.replace(/<[^>]+>/g, ' ')], { type: 'text/plain' });
        const item = new ClipboardItem({ 'text/html': blobHtml, 'text/plain': blobText });
        await navigator.clipboard.write([item]);
        showToast('Formatted HTML Table copied! Paste directly into Outlook or Gmail.', 'success');
    } catch (e) {
        console.warn('ClipboardItem write failed, falling back to plain writeText:', e);
        try {
            await navigator.clipboard.writeText(htmlContent);
            showToast('HTML code copied to clipboard.', 'info');
        } catch (err2) {
            showToast(`Copy failed: ${err2.message}`, 'error');
        }
    }
}
window.copyRfiEmailHtml = copyRfiEmailHtml;

async function openContractorRfiEmailComposer() {
    const project = document.getElementById('crfi-filter-project')?.value || 'all';
    const company = document.getElementById('crfi-filter-company')?.value || 'all';
    const status = document.getElementById('crfi-filter-status')?.value || 'overdue';
    const fromDate = document.getElementById('rfi-contractor-from-date')?.value || '';
    const toDate = document.getElementById('rfi-contractor-to-date')?.value || '';

    const modal = document.getElementById('modal-rfi-remind-email');
    if (!modal) return;

    modal.classList.remove('hidden');

    const toInput = document.getElementById('modal-rfi-email-to');
    const ccInput = document.getElementById('modal-rfi-email-cc');
    const subjInput = document.getElementById('modal-rfi-email-subject');
    const bodyArea = document.getElementById('modal-rfi-email-body');
    const previewEl = document.getElementById('modal-rfi-email-preview-html');
    const mailtoBtn = document.getElementById('modal-rfi-email-mailto-btn');

    if (bodyArea) bodyArea.value = 'Generating official contractual reminder draft from DuckDB live data...';
    if (previewEl) previewEl.innerHTML = '<div class="p-8 text-center text-slate-400"><div class="inline-block animate-spin w-6 h-6 border-2 border-sky-500 border-t-transparent rounded-full mb-2"></div><p class="font-semibold text-xs">Generating Executive Colored HTML Email...</p></div>';

    switchRfiModalTab('html');

    try {
        const params = new URLSearchParams({
            project: project,
            company: company,
            status: status,
            from_date: fromDate,
            to_date: toDate
        });
        const res = await fetch(`/api/controls/contractor_rfis/remind_email?${params.toString()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to generate reminder draft`);
        const json = await res.json();

        const toStr = Array.isArray(json.to_emails) ? json.to_emails.join(', ') : (json.to_emails || '');
        const ccStr = Array.isArray(json.cc_emails) ? json.cc_emails.join(', ') : (json.cc_emails || '');
        if (toInput) toInput.value = toStr;
        if (ccInput) ccInput.value = ccStr;
        if (subjInput) subjInput.value = json.subject || 'CONTRACTUAL NOTICE: Contractor RFIs Pending Determination';
        if (bodyArea) bodyArea.value = json.body || '';

        currentRfiEmailHtml = json.body_html || '';
        currentRfiEmailPlain = json.body || '';

        if (previewEl) {
            if (json.body_html) {
                previewEl.innerHTML = json.body_html;
            } else {
                previewEl.innerHTML = `<div class="p-6 text-slate-800 text-xs font-mono whitespace-pre-wrap">${escapeHtml(json.body || '')}</div>`;
            }
        }

        if (mailtoBtn) {
            mailtoBtn.href = json.mailto_url || json.mailto_link || '#';
        }

        const titleEl = document.getElementById('modal-rfi-email-title');
        const subtitleEl = document.getElementById('modal-rfi-email-subtitle');
        if (titleEl) {
            titleEl.innerText = `RFI Remind Notice: ${json.company || 'Consultant'} (${json.project || 'All Packages'})`;
        }
        if (subtitleEl) {
            subtitleEl.innerText = `${json.overdue_count ?? 0} overdue items exceeding SLA • Max delay +${json.max_delay_days ?? 0} days`;
        }
    } catch (err) {
        if (bodyArea) bodyArea.value = `Error generating reminder: ${err.message}`;
        if (previewEl) previewEl.innerHTML = `<div class="p-6 text-rose-500 text-xs font-bold">Error loading HTML preview: ${escapeHtml(err.message)}</div>`;
    }
    if (window.lucide) lucide.createIcons();
}
window.openContractorRfiEmailComposer = openContractorRfiEmailComposer;

function closeContractorRfiEmailModal() {
    const modal = document.getElementById('modal-rfi-remind-email');
    if (modal) modal.classList.add('hidden');
}
window.closeContractorRfiEmailModal = closeContractorRfiEmailModal;

function copyRfiEmailBody() {
    const bodyArea = document.getElementById('modal-rfi-email-body');
    const textToCopy = bodyArea ? bodyArea.value : currentRfiEmailPlain;
    if (!textToCopy) return;
    navigator.clipboard.writeText(textToCopy).then(() => {
        showToast('Plain text notice body copied to clipboard!', 'success');
    }).catch(err => {
        showToast(`Failed to copy: ${err.message}`, 'error');
    });
}
window.copyRfiEmailBody = copyRfiEmailBody;

function exportContractorRfisExcel() {
    const project = document.getElementById('crfi-filter-project')?.value || 'all';
    const company = document.getElementById('crfi-filter-company')?.value || 'all';
    const status = document.getElementById('crfi-filter-status')?.value || 'all';
    const search = document.getElementById('crfi-filter-search')?.value || '';
    const fromDate = document.getElementById('rfi-contractor-from-date')?.value || '';
    const toDate = document.getElementById('rfi-contractor-to-date')?.value || '';

    const params = new URLSearchParams({
        project: project,
        company: company,
        status: status,
        from_date: fromDate,
        to_date: toDate,
        search: search
    });

    window.location.href = `/api/controls/contractor_rfis/export_excel?${params.toString()}`;
}
window.exportContractorRfisExcel = exportContractorRfisExcel;

// =========================================================================
// 10. SETTINGS & RECIPIENT MATRICES CONTROLLER
// =========================================================================
let currentDispatchSettings = null;

async function loadDispatchSettings() {
    try {
        const token = (typeof window.getAdminToken === 'function') ? window.getAdminToken() : '';
        const headers = {};
        if (token) headers['X-Admin-Key'] = token;
        const res = await fetch('/api/settings/dispatch', { headers });
        if (res.status === 403) {
            console.warn("Settings access restricted to Administrator.");
            if (typeof window.updateAdminUIState === 'function') window.updateAdminUIState();
            return;
        }
        if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load settings`);
        const json = await res.json();
        currentDispatchSettings = json;

        renderSscMatrixTable(json.ssc_remind_emails || json.ssc_emails || {});
        renderRfiMatrixTable(json.rfi_remind_emails || json.rfi_emails || []);

        // Populate Gemini fields
        const geminiConf = json.gemini_config || {};
        const keyInput = document.getElementById('setting-gemini-key');
        const modelSelect = document.getElementById('setting-gemini-model');
        if (keyInput && geminiConf.api_key) {
            keyInput.value = geminiConf.api_key;
        }
        if (modelSelect && geminiConf.model) {
            modelSelect.value = geminiConf.model;
        }
    } catch (err) {
        showToast(`Error loading dispatch settings: ${err.message}`, 'error');
    }
    if (window.lucide) lucide.createIcons();
}
window.loadDispatchSettings = loadDispatchSettings;

function switchSettingsSubTab(subtab) {
    if (typeof window.isAdminUnlocked === 'function' && !window.isAdminUnlocked()) {
        if (typeof window.promptAdminUnlock === 'function') {
            window.promptAdminUnlock(() => switchSettingsSubTab(subtab));
            return;
        }
    }
    const btnSsc = document.getElementById('btn-setting-tab-ssc');
    const btnRfi = document.getElementById('btn-setting-tab-rfi');
    const btnGemini = document.getElementById('btn-setting-tab-gemini');

    const subSsc = document.getElementById('settings-subtab-ssc');
    const subRfi = document.getElementById('settings-subtab-rfi');
    const subGemini = document.getElementById('settings-subtab-gemini');

    const activeBtnClass = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-indigo-600 text-white shadow-md shadow-indigo-600/20 cursor-pointer';
    const inactiveBtnClass = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-slate-900 text-slate-400 hover:text-white border border-slate-800 cursor-pointer';

    if (btnSsc) btnSsc.className = subtab === 'ssc' ? activeBtnClass : inactiveBtnClass;
    if (btnRfi) btnRfi.className = subtab === 'rfi' ? activeBtnClass : inactiveBtnClass;
    if (btnGemini) btnGemini.className = subtab === 'gemini' ? activeBtnClass : inactiveBtnClass;

    if (subSsc) subSsc.classList.toggle('hidden', subtab !== 'ssc');
    if (subRfi) subRfi.classList.toggle('hidden', subtab !== 'rfi');
    if (subGemini) subGemini.classList.toggle('hidden', subtab !== 'gemini');

    const btnSync = document.getElementById('btn-setting-tab-sync');
    const subSync = document.getElementById('settings-subtab-sync');
    if (btnSync) btnSync.className = subtab === 'sync' ? activeBtnClass : inactiveBtnClass;
    if (subSync) subSync.classList.toggle('hidden', subtab !== 'sync');
    if (subtab === 'sync') loadSyncStatus();

    if (window.lucide) lucide.createIcons();
}
window.switchSettingsSubTab = switchSettingsSubTab;

function renderSscMatrixTable(sscData) {
    const tbody = document.getElementById('ssc-matrix-tbody');
    if (!tbody) return;

    let items = [];
    if (Array.isArray(sscData)) {
        items = sscData;
    } else if (sscData && typeof sscData === 'object') {
        items = Object.entries(sscData).map(([pkg, info]) => ({
            project: pkg,
            project_title: info.project_name || pkg,
            to_emails: Array.isArray(info.to) ? info.to.join(', ') : (info.to || ''),
            cc_emails: Array.isArray(info.cc) ? info.cc.join(', ') : (info.cc || '')
        }));
    }

    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="p-6 text-center text-slate-500">No SSC email configurations found.</td></tr>';
        return;
    }

    let rowsHtml = '';
    items.forEach(item => {
        const pkgSafe = escapeHtml(item.project);
        const toStr = Array.isArray(item.to) ? item.to.join(', ') : (item.to_emails || item.to || '');
        const ccStr = Array.isArray(item.cc) ? item.cc.join(', ') : (item.cc_emails || item.cc || '');
        rowsHtml += `
            <tr class="hover:bg-slate-900/50 transition">
                <td class="p-3 font-bold text-white">
                    <span class="px-2 py-1 rounded bg-slate-900 border border-slate-700 font-mono text-xs text-sky-400">${pkgSafe}</span>
                    <div class="text-[11px] text-slate-400 font-normal mt-0.5 truncate">${escapeHtml(item.project_title || '')}</div>
                </td>
                <td class="p-3">
                    <input type="text" id="ssc-to-${pkgSafe}" value="${escapeHtml(toStr)}" placeholder="dc1@shaker-ecg.com, dc2@shaker-ecg.com" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500">
                </td>
                <td class="p-3">
                    <input type="text" id="ssc-cc-${pkgSafe}" value="${escapeHtml(ccStr)}" placeholder="re@shaker-ecg.com, pm@hillintl.com, dean.english@hillintl.com" class="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500">
                </td>
                <td class="p-3 text-center">
                    <button onclick="saveSscEmailRow('${pkgSafe}')" class="px-3 py-1.5 rounded-lg bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/40 text-xs font-semibold transition cursor-pointer">
                        Save
                    </button>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = rowsHtml;
}

async function saveSscEmailRow(pkg) {
    if (typeof window.isAdminUnlocked === 'function' && !window.isAdminUnlocked()) {
        if (typeof window.promptAdminUnlock === 'function') {
            window.promptAdminUnlock(() => saveSscEmailRow(pkg));
            return;
        }
    }
    const toInput = document.getElementById(`ssc-to-${pkg}`);
    const ccInput = document.getElementById(`ssc-cc-${pkg}`);
    if (!toInput || !ccInput) return;

    try {
        const toList = toInput.value.split(',').map(s => s.trim()).filter(s => s.length > 0);
        const ccList = ccInput.value.split(',').map(s => s.trim()).filter(s => s.length > 0);
        const token = (typeof window.getAdminToken === 'function') ? window.getAdminToken() : '';
        const res = await fetch('/api/settings/ssc_emails', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Admin-Key': token
            },
            body: JSON.stringify({
                project: pkg,
                to: toList,
                cc: ccList
            })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        showToast(`Saved SSC contacts for ${pkg}`, 'success');
    } catch (err) {
        showToast(`Failed to save contacts for ${pkg}: ${err.message}`, 'error');
    }
}
window.saveSscEmailRow = saveSscEmailRow;

async function saveAllSscEmails() {
    if (typeof window.isAdminUnlocked === 'function' && !window.isAdminUnlocked()) {
        if (typeof window.promptAdminUnlock === 'function') {
            window.promptAdminUnlock(() => saveAllSscEmails());
            return;
        }
    }
    if (!currentDispatchSettings) return;
    const sscObj = currentDispatchSettings.ssc_remind_emails || currentDispatchSettings.ssc_emails || {};
    const pkgs = Array.isArray(sscObj) ? sscObj.map(x => x.project) : Object.keys(sscObj);
    let savedCount = 0;
    const token = (typeof window.getAdminToken === 'function') ? window.getAdminToken() : '';
    for (const pkg of pkgs) {
        const toInput = document.getElementById(`ssc-to-${pkg}`);
        const ccInput = document.getElementById(`ssc-cc-${pkg}`);
        if (toInput && ccInput) {
            try {
                const toList = toInput.value.split(',').map(s => s.trim()).filter(s => s.length > 0);
                const ccList = ccInput.value.split(',').map(s => s.trim()).filter(s => s.length > 0);
                await fetch('/api/settings/ssc_emails', {
                    method: 'POST',
                    headers: { 
                        'Content-Type': 'application/json',
                        'X-Admin-Key': token
                    },
                    body: JSON.stringify({
                        project: pkg,
                        to: toList,
                        cc: ccList
                    })
                });
                savedCount++;
            } catch (err) {
                console.error(`Failed to save ${pkg}:`, err);
            }
        }
    }
    showToast(`Successfully saved ${savedCount} SSC email matrices`, 'success');
}
window.saveAllSscEmails = saveAllSscEmails;

function renderRfiMatrixTable(rfiData) {
    const tbody = document.getElementById('rfi-matrix-tbody');
    if (!tbody) return;

    if (!rfiData || rfiData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-slate-500">No RFI company routing rules configured yet.</td></tr>';
        return;
    }

    let rowsHtml = '';
    rfiData.forEach(item => {
        const ruleId = escapeHtml(item.id || `${item.project}-${item.company}`);
        const toStr = Array.isArray(item.to) ? item.to.join(', ') : (item.to_emails || item.to || '-');
        const ccStr = Array.isArray(item.cc) ? item.cc.join(', ') : (item.cc_emails || item.cc || '-');
        rowsHtml += `
            <tr class="hover:bg-slate-900/50 transition">
                <td class="p-3 font-bold text-white">
                    <span class="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 font-mono text-[11px] text-sky-400">${escapeHtml(item.project || 'All')}</span>
                </td>
                <td class="p-3 font-semibold text-slate-200 truncate">
                    ${escapeHtml(item.company || '')}
                </td>
                <td class="p-3 text-slate-300 font-mono text-[11px] truncate" title="${escapeHtml(toStr)}">
                    ${escapeHtml(toStr)}
                </td>
                <td class="p-3 text-slate-400 font-mono text-[11px] truncate" title="${escapeHtml(ccStr)}">
                    ${escapeHtml(ccStr)}
                </td>
                <td class="p-3 text-center">
                    <div class="flex items-center justify-center gap-1.5">
                        <button onclick="openAddRfiRoutingModal('${ruleId}')" class="p-1 rounded hover:bg-slate-800 text-sky-400 hover:text-sky-300 transition cursor-pointer" title="Edit Rule">
                            <i data-lucide="edit-3" class="w-3.5 h-3.5"></i>
                        </button>
                        <button onclick="deleteRfiEmailRow('${ruleId}')" class="p-1 rounded hover:bg-slate-800 text-rose-400 hover:text-rose-300 transition cursor-pointer" title="Delete Rule">
                            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = rowsHtml;
    if (window.lucide) lucide.createIcons();
}

function openAddRfiRoutingModal(ruleId = null) {
    if (typeof window.isAdminUnlocked === 'function' && !window.isAdminUnlocked()) {
        if (typeof window.promptAdminUnlock === 'function') {
            window.promptAdminUnlock(() => openAddRfiRoutingModal(ruleId));
            return;
        }
    }
    const modal = document.getElementById('modal-edit-rfi-routing');
    if (!modal) return;

    const idInput = document.getElementById('form-rfi-rule-id');
    const projSelect = document.getElementById('form-rfi-project');
    const compInput = document.getElementById('form-rfi-company');
    const toInput = document.getElementById('form-rfi-to');
    const ccInput = document.getElementById('form-rfi-cc');
    const titleEl = document.getElementById('modal-rfi-routing-title');

    const rfiList = currentDispatchSettings?.rfi_remind_emails || currentDispatchSettings?.rfi_emails || [];
    if (ruleId && rfiList.length > 0) {
        const item = rfiList.find(r => (r.id || `${r.project}-${r.company}`) === ruleId);
        if (item) {
            const toStr = Array.isArray(item.to) ? item.to.join(', ') : (item.to_emails || item.to || '');
            const ccStr = Array.isArray(item.cc) ? item.cc.join(', ') : (item.cc_emails || item.cc || '');
            if (idInput) idInput.value = item.id || ruleId;
            if (projSelect) projSelect.value = item.project || 'All Packages';
            if (compInput) compInput.value = item.company || '';
            if (toInput) toInput.value = toStr;
            if (ccInput) ccInput.value = ccStr;
            if (titleEl) titleEl.innerText = 'Edit Company RFI Routing Rule';
        }
    } else {
        if (idInput) idInput.value = '';
        if (projSelect) projSelect.value = 'All Packages';
        if (compInput) compInput.value = '';
        if (toInput) toInput.value = '';
        if (ccInput) ccInput.value = '';
        if (titleEl) titleEl.innerText = 'Add Company RFI Routing Rule';
    }

    modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
}
window.openAddRfiRoutingModal = openAddRfiRoutingModal;

function closeEditRfiRoutingModal() {
    const modal = document.getElementById('modal-edit-rfi-routing');
    if (modal) modal.classList.add('hidden');
}
window.closeEditRfiRoutingModal = closeEditRfiRoutingModal;

async function handleSaveRfiRoutingModal(e) {
    if (e) e.preventDefault();
    const idInput = document.getElementById('form-rfi-rule-id');
    const projSelect = document.getElementById('form-rfi-project');
    const compInput = document.getElementById('form-rfi-company');
    const toInput = document.getElementById('form-rfi-to');
    const ccInput = document.getElementById('form-rfi-cc');

    const project = projSelect?.value || 'All Packages';
    const company = compInput?.value?.trim() || '';
    const toEmails = toInput?.value?.trim() || '';
    const ccEmails = ccInput?.value?.trim() || '';
    const ruleId = idInput?.value || `${project}-${company}`.replace(/[\s\W]+/g, '_');

    if (!company) {
        alert('Please specify the responsible company name.');
        return;
    }

    const toList = toEmails.split(',').map(s => s.trim()).filter(s => s.length > 0);
    const ccList = ccEmails.split(',').map(s => s.trim()).filter(s => s.length > 0);

    try {
        const token = (typeof window.getAdminToken === 'function') ? window.getAdminToken() : '';
        const res = await fetch('/api/settings/rfi_emails', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Admin-Key': token
            },
            body: JSON.stringify({
                id: ruleId,
                project: project,
                company: company,
                to: toList,
                cc: ccList
            })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        closeEditRfiRoutingModal();
        showToast('Saved RFI company routing rule', 'success');
        loadDispatchSettings();
    } catch (err) {
        showToast(`Failed to save rule: ${err.message}`, 'error');
    }
}
window.handleSaveRfiRoutingModal = handleSaveRfiRoutingModal;

async function deleteRfiEmailRow(ruleId) {
    if (typeof window.isAdminUnlocked === 'function' && !window.isAdminUnlocked()) {
        if (typeof window.promptAdminUnlock === 'function') {
            window.promptAdminUnlock(() => deleteRfiEmailRow(ruleId));
            return;
        }
    }
    if (!confirm(`Are you sure you want to remove routing for this entry?`)) return;
    try {
        const token = (typeof window.getAdminToken === 'function') ? window.getAdminToken() : '';
        const res = await fetch(`/api/settings/rfi_emails/${encodeURIComponent(ruleId)}`, {
            method: 'DELETE',
            headers: { 'X-Admin-Key': token }
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        showToast('Deleted RFI routing entry', 'info');
        loadDispatchSettings();
    } catch (err) {
        showToast(`Failed to delete: ${err.message}`, 'error');
    }
}
window.deleteRfiEmailRow = deleteRfiEmailRow;

function toggleGeminiKeyVisibility() {
    const input = document.getElementById('setting-gemini-key');
    if (!input) return;
    input.type = input.type === 'password' ? 'text' : 'password';
}
window.toggleGeminiKeyVisibility = toggleGeminiKeyVisibility;

async function saveGeminiSettings() {
    if (typeof window.isAdminUnlocked === 'function' && !window.isAdminUnlocked()) {
        if (typeof window.promptAdminUnlock === 'function') {
            window.promptAdminUnlock(() => saveGeminiSettings());
            return;
        }
    }
    const keyInput = document.getElementById('setting-gemini-key');
    const modelSelect = document.getElementById('setting-gemini-model');

    const key = keyInput?.value?.trim() || '';
    const model = modelSelect?.value || 'gemini-3-flash-preview';

    try {
        const token = (typeof window.getAdminToken === 'function') ? window.getAdminToken() : '';
        const res = await fetch('/api/settings/gemini_config', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Admin-Key': token
            },
            body: JSON.stringify({ api_key: key, model: model })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        showToast('Gemini AI engine configuration saved successfully!', 'success');
    } catch (err) {
        showToast(`Failed to save Gemini settings: ${err.message}`, 'error');
    }
}
window.saveGeminiSettings = saveGeminiSettings;

async function testGeminiConnection() {
    const keyInput = document.getElementById('setting-gemini-key');
    const modelSelect = document.getElementById('setting-gemini-model');
    const key = keyInput?.value?.trim() || '';
    const model = modelSelect?.value || 'gemini-3-flash-preview';

    const box = document.getElementById('gemini-test-status-box');

    if (!key) {
        showToast('Please enter your Gemini API Key first.', 'warning');
        if (box) {
            box.className = 'p-3.5 rounded-xl text-xs font-semibold bg-amber-950/40 border border-amber-800 text-amber-300 flex items-center gap-2';
            box.innerHTML = `
                <i data-lucide="alert-triangle" class="w-4 h-4 text-amber-400 flex-shrink-0"></i>
                <span>Please enter your Gemini API Key in the box above before testing.</span>
            `;
            box.classList.remove('hidden');
            if (window.lucide) lucide.createIcons();
        }
        return;
    }

    if (box) {
        box.className = 'p-3.5 rounded-xl text-xs font-semibold bg-purple-950/40 border border-purple-800 text-purple-300 flex items-center gap-2';
        box.innerHTML = `
            <div class="inline-block animate-spin w-4 h-4 border-2 border-purple-400 border-t-transparent rounded-full"></div>
            <span>Sending test prompt to Google Gemini API (${escapeHtml(model)})...</span>
        `;
        box.classList.remove('hidden');
    }

    try {
        const token = (typeof window.getAdminToken === 'function') ? window.getAdminToken() : '';
        const res = await fetch('/api/settings/gemini_test', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-Admin-Key': token
            },
            body: JSON.stringify({ api_key: key, model: model })
        });
        const json = await res.json();
        if (json.status === 'success') {
            if (modelSelect && json.model && modelSelect.value !== json.model) {
                modelSelect.value = json.model;
            }
            if (box) {
                box.className = 'p-3.5 rounded-xl text-xs font-semibold bg-emerald-950/40 border border-emerald-800 text-emerald-300 flex items-center gap-2';
                box.innerHTML = `
                    <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400 flex-shrink-0"></i>
                    <span>Connected successfully to <strong>${escapeHtml(json.model || 'Gemini')}</strong> (${json.latency_ms || 0}ms latency)! Configuration auto-saved.</span>
                `;
            }
            showToast(`Gemini Connected (${json.model})!`, 'success');
        } else {
            if (box) {
                box.className = 'p-3.5 rounded-xl text-xs font-semibold bg-rose-950/40 border border-rose-800 text-rose-300 flex items-center gap-2';
                box.innerHTML = `
                    <i data-lucide="alert-circle" class="w-4 h-4 text-rose-400 flex-shrink-0"></i>
                    <span>Connection failed: ${escapeHtml(json.message || 'Unknown error')}</span>
                `;
            }
            showToast('Gemini Connection Failed', 'error');
        }
    } catch (err) {
        if (box) {
            box.className = 'p-3.5 rounded-xl text-xs font-semibold bg-rose-950/40 border border-rose-800 text-rose-300 flex items-center gap-2';
            box.innerHTML = `
                <i data-lucide="alert-circle" class="w-4 h-4 text-rose-400 flex-shrink-0"></i>
                <span>Test Error: ${escapeHtml(err.message)}</span>
            `;
        }
        showToast(`Test Error: ${err.message}`, 'error');
    }
    if (window.lucide) lucide.createIcons();
}
window.testGeminiConnection = testGeminiConnection;

// =============================================================================
// 20. SPECIALIZED DISCIPLINE PORTALS (HSE, QA/QC, SITE OPS, TECHNICAL OFFICE)
// =============================================================================

function renderDisciplinePagination(containerId, currentPage, limit, total, loadFnName) {
    const container = document.getElementById(containerId);
    const containerTop = document.getElementById(containerId + '-top');
    if (!container && !containerTop) return;

    if (total === 0) {
        const noRec = `<span class="text-slate-500 text-xs">No records found</span>`;
        if (container) container.innerHTML = noRec;
        if (containerTop) containerTop.innerHTML = noRec;
        return;
    }
    const totalPages = Math.ceil(total / limit) || 1;
    const start = (currentPage - 1) * limit + 1;
    const end = Math.min(total, currentPage * limit);

    const buildHtml = () => `
        <div class="text-xs text-slate-400">
            Showing <span class="font-bold text-slate-200">${start.toLocaleString()}-${end.toLocaleString()}</span> of <span class="font-bold text-slate-200">${total.toLocaleString()}</span> items
        </div>
        <div class="flex items-center gap-2">
            <button onclick="${loadFnName}(${currentPage - 1})" ${currentPage <= 1 ? 'disabled class="px-3 py-1.5 rounded-lg bg-slate-950 text-slate-600 border border-slate-800 text-xs font-semibold cursor-not-allowed"' : 'class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition cursor-pointer"'}>
                Previous
            </button>
            <span class="px-2 text-xs font-mono text-slate-400">Page <strong class="text-white">${currentPage}</strong> of ${totalPages}</span>
            <button onclick="${loadFnName}(${currentPage + 1})" ${currentPage >= totalPages ? 'disabled class="px-3 py-1.5 rounded-lg bg-slate-950 text-slate-600 border border-slate-800 text-xs font-semibold cursor-not-allowed"' : 'class="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition cursor-pointer"'}>
                Next
            </button>
        </div>
    `;

    if (container) container.innerHTML = buildHtml();
    if (containerTop) containerTop.innerHTML = buildHtml();
}

// -----------------------------------------------------------------------------
// 20.1 HSE & SAFETY HUB
// -----------------------------------------------------------------------------
let safetyCurrentPage = 1;
let safetyViewMode = 'grid';
let safetyDebounceTimer = null;
let safetyFilterLoaded = false;

function setSafetyViewMode(mode) {
    safetyViewMode = mode;
    const btnGrid = document.getElementById('btn-safety-view-grid');
    const btnTable = document.getElementById('btn-safety-view-table');
    const gridContainer = document.getElementById('safety-grid-container');
    const tableContainer = document.getElementById('safety-table-container');

    if (mode === 'grid') {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (gridContainer) gridContainer.classList.remove('hidden');
        if (tableContainer) tableContainer.classList.add('hidden');
    } else {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (gridContainer) gridContainer.classList.add('hidden');
        if (tableContainer) tableContainer.classList.remove('hidden');
    }
}
window.setSafetyViewMode = setSafetyViewMode;

function debounceSafetySearch() {
    clearTimeout(safetyDebounceTimer);
    safetyDebounceTimer = setTimeout(() => loadDisciplineSafety(1), 300);
}
window.debounceSafetySearch = debounceSafetySearch;

async function setSafetyCategoryFilter(cat) {
    const elCat = document.getElementById('safety-filter-category');
    if (elCat) elCat.value = cat;
    const elType = document.getElementById('safety-filter-type');
    if (elType) elType.value = 'all';
    loadDisciplineSafety(1);
}
window.setSafetyCategoryFilter = setSafetyCategoryFilter;

function loadDisciplineSafety(page = 1) {
    safetyCurrentPage = page;
    const grid = document.getElementById('safety-grid-container');
    const tbody = document.getElementById('safety-table-tbody');

    if (grid && safetyViewMode === 'grid') {
        grid.innerHTML = `<div class="col-span-full py-16 text-center text-slate-400 flex items-center justify-center gap-2"><i data-lucide="loader" class="w-5 h-5 animate-spin text-emerald-400"></i><span>Loading HSE, Near Miss &amp; Governance records...</span></div>`;
    }
    if (tbody && safetyViewMode === 'table') {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-400"><div class="flex items-center justify-center gap-2"><i data-lucide="loader" class="w-4 h-4 animate-spin text-emerald-400"></i><span>Loading HSE &amp; MOM records...</span></div></td></tr>`;
    }
    if (window.lucide) lucide.createIcons();

    if (page === 1) {
        fetch('/api/disciplines/safety/stats')
            .then(r => r.json())
            .then(stats => {
                const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = (val || 0).toLocaleString(); };
                setEl('stat-safety-observations', stats.total_observations);
                setEl('stat-safety-remedial', stats.remedial_actions);
                setEl('stat-safety-closed', stats.closed_observations);
                setEl('stat-safety-ncrs', stats.hse_ncrs);
                setEl('stat-safety-near-miss', stats.total_near_miss_incidents || ((stats.near_misses || 0) + (stats.incidents || 0)));
                setEl('stat-safety-mom', stats.meeting_minutes);
            })
            .catch(err => console.error('Failed to load safety stats:', err));
    }

    const pkg = document.getElementById('safety-filter-project')?.value || 'all';
    const category = document.getElementById('safety-filter-category')?.value || 'all';
    const type = document.getElementById('safety-filter-type')?.value || 'all';
    const status = document.getElementById('safety-filter-status')?.value || 'all';
    const search = document.getElementById('safety-search-input')?.value || '';

    const params = new URLSearchParams({ page: safetyCurrentPage, limit: 30 });
    if (pkg !== 'all') params.append('project', pkg);
    if (category !== 'all') params.append('category', category);
    if (type !== 'all') params.append('item_type', type);
    if (status !== 'all') params.append('status', status);
    if (search.trim()) params.append('search', search.trim());

    fetch(`/api/disciplines/safety/items?${params.toString()}`)
        .then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
        })
        .then(data => {
            if (!safetyFilterLoaded) {
                const selPkg = document.getElementById('safety-filter-project');
                if (selPkg && data.projects) {
                    data.projects.forEach(p => {
                        const opt = document.createElement('option');
                        opt.value = p;
                        opt.innerText = p;
                        selPkg.appendChild(opt);
                    });
                }
                safetyFilterLoaded = true;
            }

            // Always update type dropdown to match current filtered scope
            const selType = document.getElementById('safety-filter-type');
            if (selType && data.types) {
                const currentVal = selType.value;
                selType.innerHTML = '<option value="all">All Item Types</option>';
                data.types.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t;
                    opt.innerText = t;
                    if (t === currentVal) opt.selected = true;
                    selType.appendChild(opt);
                });
            }

            renderSafetyData(data.items || []);
            renderDisciplinePagination('safety-pagination', data.page, data.limit, data.total, 'loadDisciplineSafety');
        })
        .catch(err => {
            console.error('Error loading safety items:', err);
            if (grid) grid.innerHTML = `<div class="col-span-full py-8 text-center text-rose-400">Failed to load HSE data: ${escapeHtml(err.message)}</div>`;
            if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-rose-400">Error: ${escapeHtml(err.message)}</td></tr>`;
        });
}
window.loadDisciplineSafety = loadDisciplineSafety;

function renderSafetyData(items) {
    const grid = document.getElementById('safety-grid-container');
    const tbody = document.getElementById('safety-table-tbody');

    if (!items || items.length === 0) {
        if (grid) grid.innerHTML = `<div class="col-span-full py-12 text-center text-slate-500 font-medium">No HSE, Near Miss, or MOM records match current filters.</div>`;
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-500">No records found</td></tr>`;
        return;
    }

    let cardsHtml = '';
    let tableHtml = '';

    items.forEach(item => {
        let statusBadge = '';
        if (item.is_overdue) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-500/10 text-rose-400 border border-rose-500/30">OVERDUE</span>`;
        } else if ((item.status || '').toLowerCase().includes('close') || (item.status || '').toLowerCase().includes('accept')) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">${escapeHtml(item.status)}</span>`;
        } else {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-500/10 text-amber-400 border border-amber-500/30">${escapeHtml(item.status || 'Active')}</span>`;
        }

        const tLower = (item.mail_type || '').toLowerCase();
        let typeColor = 'text-amber-400';
        let typeIcon = 'shield';
        let typeBadge = '';

        if (tLower.includes('near miss')) {
            typeColor = 'text-rose-400';
            typeIcon = 'alert-octagon';
            typeBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-black bg-rose-500/20 text-rose-300 border border-rose-500/40">Near Miss</span>`;
        } else if (tLower.includes('incident') || tLower.includes('stop work') || tLower.includes('accident')) {
            typeColor = 'text-red-400';
            typeIcon = 'alert-triangle';
            typeBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-black bg-red-600/20 text-red-300 border border-red-500/40">Incident</span>`;
        } else if (tLower.includes('meeting')) {
            typeColor = 'text-indigo-400';
            typeIcon = 'users';
            typeBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-black bg-indigo-500/20 text-indigo-300 border border-indigo-500/40">MOM</span>`;
        } else if (tLower.includes('remedial')) {
            typeColor = 'text-emerald-400';
            typeIcon = 'clock';
        } else if (tLower.includes('closure')) {
            typeColor = 'text-sky-400';
            typeIcon = 'check-circle-2';
        }

        const sourceBadge = item.source_type === 'Document'
            ? `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-950 text-indigo-300 border border-indigo-500/30">MOM Doc</span>`
            : `<span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-800 text-slate-300 border border-slate-700">Mail</span>`;

        cardsHtml += `
            <div class="bg-slate-900 rounded-2xl border border-slate-800 hover:border-emerald-500/40 p-5 flex flex-col justify-between transition-all duration-200 hover:shadow-xl hover:shadow-emerald-500/5 group">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-3">
                        <span class="text-xs font-mono font-bold text-emerald-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                            ${escapeHtml(item.mail_no)}
                        </span>
                        <div class="flex items-center gap-1.5">
                            ${sourceBadge}
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                                ${escapeHtml(item.project)}
                            </span>
                            ${statusBadge}
                        </div>
                    </div>

                    <div class="text-[11px] font-bold ${typeColor} mb-1 flex items-center gap-1.5">
                        <i data-lucide="${typeIcon}" class="w-3.5 h-3.5 flex-shrink-0"></i>
                        <span>${escapeHtml(item.mail_type)}</span>
                        ${typeBadge}
                    </div>

                    <h4 class="text-sm font-bold text-white group-hover:text-emerald-300 transition mb-3 leading-snug line-clamp-2">
                        ${escapeHtml(item.subject || 'No subject')}
                    </h4>

                    <div class="space-y-1.5 text-xs text-slate-400 border-t border-slate-800/80 pt-3">
                        <div class="flex items-center justify-between">
                            <span class="text-slate-500">From / Origin:</span>
                            <span class="font-medium text-slate-300 truncate max-w-[160px]" title="${escapeHtml(item.from_org)}">${escapeHtml(item.from_org)}</span>
                        </div>
                        <div class="flex items-center justify-between">
                            <span class="text-slate-500">To / Target:</span>
                            <span class="font-medium text-slate-300 truncate max-w-[160px]" title="${escapeHtml(item.to_org)}">${escapeHtml(item.to_org)}</span>
                        </div>
                        <div class="flex items-center justify-between">
                            <span class="text-slate-500">Date:</span>
                            <span class="font-mono text-slate-300">${escapeHtml(item.sent_date)}</span>
                        </div>
                    </div>
                </div>

                <div class="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-end">
                    ${item.aconex_url ? `
                        <a href="${item.aconex_url}" target="_blank" class="text-xs font-bold text-emerald-400 hover:text-emerald-300 flex items-center gap-1 transition">
                            <span>Open in Aconex</span>
                            <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
                        </a>
                    ` : '<span class="text-[11px] text-slate-600 font-mono">Archive Record</span>'}
                </div>
            </div>
        `;

        tableHtml += `
            <tr class="hover:bg-slate-800/50 transition border-b border-slate-800/60">
                <td class="px-4 py-3 text-xs font-mono font-bold text-emerald-400">
                    <div class="flex items-center gap-1.5">
                        ${item.aconex_url ? `<a href="${item.aconex_url}" target="_blank" class="hover:underline flex items-center gap-1">${escapeHtml(item.mail_no)}<i data-lucide="external-link" class="w-3 h-3 text-slate-500"></i></a>` : escapeHtml(item.mail_no)}
                    </div>
                </td>
                <td class="px-4 py-3 text-xs font-medium ${typeColor}">
                    <div class="flex items-center gap-1.5">
                        <i data-lucide="${typeIcon}" class="w-3.5 h-3.5"></i>
                        <span>${escapeHtml(item.mail_type)}</span>
                        ${typeBadge}
                    </div>
                </td>
                <td class="px-4 py-3 text-xs text-white max-w-md truncate" title="${escapeHtml(item.subject)}">
                    ${escapeHtml(item.subject)}
                </td>
                <td class="px-4 py-3 text-xs text-slate-300">
                    <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                        ${escapeHtml(item.project)}
                    </span>
                </td>
                <td class="px-4 py-3 text-xs text-slate-300 truncate max-w-[140px]" title="${escapeHtml(item.from_org)}">
                    ${escapeHtml(item.from_org)}
                </td>
                <td class="px-4 py-3 text-xs text-slate-300 truncate max-w-[140px]" title="${escapeHtml(item.to_org)}">
                    ${escapeHtml(item.to_org)}
                </td>
                <td class="px-4 py-3 text-xs font-mono text-slate-400 text-center">
                    ${escapeHtml(item.sent_date)}
                </td>
                <td class="px-4 py-3 text-center">
                    ${statusBadge}
                </td>
            </tr>
        `;
    });

    if (grid) grid.innerHTML = cardsHtml;
    if (tbody) tbody.innerHTML = tableHtml;
    if (window.lucide) lucide.createIcons();
}

function exportSafetyExcel() {
    const pkg = document.getElementById('safety-filter-project')?.value || 'all';
    const category = document.getElementById('safety-filter-category')?.value || 'all';
    const type = document.getElementById('safety-filter-type')?.value || 'all';
    const status = document.getElementById('safety-filter-status')?.value || 'all';
    const search = document.getElementById('safety-search-input')?.value || '';

    const params = new URLSearchParams();
    if (pkg !== 'all') params.append('project', pkg);
    if (category !== 'all') params.append('category', category);
    if (type !== 'all') params.append('item_type', type);
    if (status !== 'all') params.append('status', status);
    if (search.trim()) params.append('search', search.trim());

    window.location.href = `/api/disciplines/safety/export?${params.toString()}`;
}
window.exportSafetyExcel = exportSafetyExcel;

// 20.2 QA/QC & INSPECTIONS HUB
// -----------------------------------------------------------------------------
let qaqcCurrentPage = 1;
let qaqcViewMode = 'grid';
let qaqcDebounceTimer = null;
let qaqcFilterLoaded = false;

function setQaqcViewMode(mode) {
    qaqcViewMode = mode;
    const btnGrid = document.getElementById('btn-qaqc-view-grid');
    const btnTable = document.getElementById('btn-qaqc-view-table');
    const gridContainer = document.getElementById('qaqc-grid-container');
    const tableContainer = document.getElementById('qaqc-table-container');

    if (mode === 'grid') {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (gridContainer) gridContainer.classList.remove('hidden');
        if (tableContainer) tableContainer.classList.add('hidden');
    } else {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (gridContainer) gridContainer.classList.add('hidden');
        if (tableContainer) tableContainer.classList.remove('hidden');
    }
}
window.setQaqcViewMode = setQaqcViewMode;

function debounceQaqcSearch() {
    clearTimeout(qaqcDebounceTimer);
    qaqcDebounceTimer = setTimeout(() => loadDisciplineQaqc(1), 300);
}
window.debounceQaqcSearch = debounceQaqcSearch;

async function loadDisciplineQaqc(page = 1) {
    qaqcCurrentPage = page;
    const grid = document.getElementById('qaqc-grid-container');
    const tbody = document.getElementById('qaqc-table-tbody');

    if (grid && qaqcViewMode === 'grid') {
        grid.innerHTML = `<div class="col-span-full py-16 text-center text-slate-400 flex items-center justify-center gap-2"><i data-lucide="loader" class="w-5 h-5 animate-spin text-cyan-400"></i><span>Loading QA/QC &amp; Inspection records...</span></div>`;
    }
    if (tbody && qaqcViewMode === 'table') {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-400"><div class="flex items-center justify-center gap-2"><i data-lucide="loader" class="w-4 h-4 animate-spin text-cyan-400"></i><span>Loading inspections...</span></div></td></tr>`;
    }
    if (window.lucide) lucide.createIcons();

    if (page === 1) {
        fetch('/api/disciplines/qaqc/stats')
            .then(r => r.json())
            .then(stats => {
                const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = (val || 0).toLocaleString(); };
                setEl('stat-qaqc-wir', stats.total_wir);
                setEl('stat-qaqc-mir', stats.total_mir);
                setEl('stat-qaqc-ncrs', stats.total_ncrs);
                setEl('stat-qaqc-tests', (stats.total_tests || 0) + (stats.total_audits || 0));
            })
            .catch(err => console.error('Failed to load QA/QC stats:', err));
    }

    const pkg = document.getElementById('qaqc-filter-project')?.value || 'all';
    const type = document.getElementById('qaqc-filter-type')?.value || 'all';
    const status = document.getElementById('qaqc-filter-status')?.value || 'all';
    const search = document.getElementById('qaqc-search-input')?.value || '';

    const params = new URLSearchParams({ page: qaqcCurrentPage, limit: 30 });
    if (pkg !== 'all') params.append('project', pkg);
    if (type !== 'all') params.append('doc_type', type);
    if (status !== 'all') params.append('review_status', status);
    if (search.trim()) params.append('search', search.trim());

    try {
        const res = await fetch(`/api/disciplines/qaqc/items?${params.toString()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!qaqcFilterLoaded) {
            const selPkg = document.getElementById('qaqc-filter-project');
            if (selPkg && data.projects) {
                data.projects.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p;
                    opt.innerText = p;
                    selPkg.appendChild(opt);
                });
            }
            qaqcFilterLoaded = true;
        }

        renderQaqcData(data.items || []);
        renderDisciplinePagination('qaqc-pagination', data.page, data.limit, data.total, 'loadDisciplineQaqc');
    } catch (err) {
        console.error('Error loading QA/QC items:', err);
        if (grid) grid.innerHTML = `<div class="col-span-full py-8 text-center text-rose-400">Failed to load QA/QC data: ${escapeHtml(err.message)}</div>`;
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-rose-400">Error: ${escapeHtml(err.message)}</td></tr>`;
    }
}
window.loadDisciplineQaqc = loadDisciplineQaqc;

function renderQaqcData(items) {
    const grid = document.getElementById('qaqc-grid-container');
    const tbody = document.getElementById('qaqc-table-tbody');

    if (!items || items.length === 0) {
        if (grid) grid.innerHTML = `<div class="col-span-full py-12 text-center text-slate-500 font-medium">No QA/QC inspection records match current filters.</div>`;
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-500">No records found</td></tr>`;
        return;
    }

    let cardsHtml = '';
    let tableHtml = '';

    items.forEach(item => {
        let statusBadge = '';
        const st = (item.review_status || '').toLowerCase();
        if (st.includes('approved') && !st.includes('noted')) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">Approved</span>`;
        } else if (st.includes('noted') || st.includes('comment')) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">Approved as Noted</span>`;
        } else if (st.includes('reject')) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-500/10 text-rose-400 border border-rose-500/30">Rejected</span>`;
        } else {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-500/10 text-amber-400 border border-amber-500/30">${escapeHtml(item.review_status || 'Pending')}</span>`;
        }

        const typeColor = item.doc_type === 'Work Inspection Request' ? 'text-cyan-400' : (item.doc_type === 'Material Inspection Request' ? 'text-emerald-400' : 'text-purple-400');

        cardsHtml += `
            <div class="bg-slate-900 rounded-2xl border border-slate-800 hover:border-cyan-500/40 p-5 flex flex-col justify-between transition-all duration-200 hover:shadow-xl hover:shadow-cyan-500/5 group">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-3">
                        <span class="text-xs font-mono font-bold text-cyan-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800 truncate max-w-[200px]">
                            ${escapeHtml(item.document_no)}
                        </span>
                        <div class="flex items-center gap-1.5 flex-shrink-0">
                            <span class="text-[10px] font-mono text-slate-400">Rev ${escapeHtml(item.revision)}</span>
                            ${statusBadge}
                        </div>
                    </div>

                    <div class="text-[11px] font-bold ${typeColor} mb-1 flex items-center gap-1.5">
                        <i data-lucide="clipboard-check" class="w-3.5 h-3.5 flex-shrink-0"></i>
                        <span>${escapeHtml(item.doc_type)}</span>
                    </div>

                    <h4 class="text-sm font-bold text-white group-hover:text-cyan-300 transition mb-3 leading-snug line-clamp-2">
                        ${escapeHtml(item.title || 'Untitled Inspection')}
                    </h4>

                    <div class="space-y-1.5 p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 mb-3 text-xs">
                        <div class="flex items-center justify-between text-slate-400">
                            <span class="text-[11px]">Package:</span>
                            <span class="text-slate-200 font-semibold font-mono">${escapeHtml(item.project)}</span>
                        </div>
                        <div class="flex items-center justify-between text-slate-400">
                            <span class="text-[11px]">Created By:</span>
                            <span class="text-slate-300 font-medium truncate max-w-[180px]">${escapeHtml(item.created_by)}</span>
                        </div>
                    </div>
                </div>

                <div class="flex items-center justify-between pt-3 border-t border-slate-800/80 text-xs">
                    <div class="flex items-center gap-1.5 text-slate-400">
                        <i data-lucide="calendar" class="w-3.5 h-3.5 text-slate-500"></i>
                        <span class="font-mono text-[11px]">${item.date_modified}</span>
                    </div>
                    ${item.aconex_url ? `
                        <a href="${item.aconex_url}" target="_blank" class="px-3 py-1 rounded-lg bg-cyan-600/10 hover:bg-cyan-600 text-cyan-400 hover:text-white border border-cyan-500/20 text-[11px] font-bold flex items-center gap-1.5 transition">
                            <span>Open Aconex</span>
                            <i data-lucide="external-link" class="w-3 h-3"></i>
                        </a>
                    ` : `
                        <span class="text-[11px] text-slate-500">Aconex Document</span>
                    `}
                </div>
            </div>
        `;

        tableHtml += `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="p-3.5 whitespace-nowrap">
                    ${item.aconex_url ? `
                        <a href="${item.aconex_url}" target="_blank" class="font-mono font-bold text-cyan-400 hover:underline inline-flex items-center gap-1">
                            <span>${escapeHtml(item.document_no)}</span>
                            <i data-lucide="external-link" class="w-3 h-3 text-slate-500"></i>
                        </a>
                    ` : `<span class="font-mono font-bold text-cyan-400">${escapeHtml(item.document_no)}</span>`}
                </td>
                <td class="p-3.5 whitespace-nowrap font-medium text-slate-300">
                    <span class="px-2 py-0.5 rounded text-[11px] bg-slate-950 border border-slate-800 ${typeColor}">${escapeHtml(item.doc_type)}</span>
                </td>
                <td class="p-3.5 max-w-md">
                    <span class="font-medium text-white hover:text-cyan-300 transition line-clamp-1">${escapeHtml(item.title || '-')}</span>
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <span class="px-2 py-0.5 rounded text-[11px] bg-slate-950 text-slate-300 border border-slate-800 font-mono">${escapeHtml(item.project)}</span>
                </td>
                <td class="p-3.5 text-center whitespace-nowrap">${statusBadge}</td>
                <td class="p-3.5 text-center font-mono whitespace-nowrap text-slate-400">${escapeHtml(item.revision)}</td>
                <td class="p-3.5 whitespace-nowrap text-slate-300 truncate max-w-[150px]">${escapeHtml(item.created_by)}</td>
                <td class="p-3.5 text-center font-mono whitespace-nowrap text-slate-400">${item.date_modified}</td>
            </tr>
        `;
    });

    if (grid) grid.innerHTML = cardsHtml;
    if (tbody) tbody.innerHTML = tableHtml;
    if (window.lucide) lucide.createIcons();
}

function exportQaqcExcel() {
    const pkg = document.getElementById('qaqc-filter-project')?.value || 'all';
    const type = document.getElementById('qaqc-filter-type')?.value || 'all';
    const status = document.getElementById('qaqc-filter-status')?.value || 'all';
    const search = document.getElementById('qaqc-search-input')?.value || '';

    const params = new URLSearchParams();
    if (pkg !== 'all') params.append('project', pkg);
    if (type !== 'all') params.append('doc_type', type);
    if (status !== 'all') params.append('review_status', status);
    if (search.trim()) params.append('search', search.trim());

    window.location.href = `/api/disciplines/qaqc/export?${params.toString()}`;
}
window.exportQaqcExcel = exportQaqcExcel;

// -----------------------------------------------------------------------------
// 20.3 SITE OPERATIONS & SUPERVISION HUB
// -----------------------------------------------------------------------------
let siteCurrentPage = 1;
let siteViewMode = 'grid';
let siteDebounceTimer = null;
let siteFilterLoaded = false;

function setSiteViewMode(mode) {
    siteViewMode = mode;
    const btnGrid = document.getElementById('btn-site-view-grid');
    const btnTable = document.getElementById('btn-site-view-table');
    const gridContainer = document.getElementById('site-grid-container');
    const tableContainer = document.getElementById('site-table-container');

    if (mode === 'grid') {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (gridContainer) gridContainer.classList.remove('hidden');
        if (tableContainer) tableContainer.classList.add('hidden');
    } else {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (gridContainer) gridContainer.classList.add('hidden');
        if (tableContainer) tableContainer.classList.remove('hidden');
    }
}
window.setSiteViewMode = setSiteViewMode;

function debounceSiteSearch() {
    clearTimeout(siteDebounceTimer);
    siteDebounceTimer = setTimeout(() => loadDisciplineSite(1), 300);
}
window.debounceSiteSearch = debounceSiteSearch;

async function loadDisciplineSite(page = 1) {
    siteCurrentPage = page;
    const grid = document.getElementById('site-grid-container');
    const tbody = document.getElementById('site-table-tbody');

    if (grid && siteViewMode === 'grid') {
        grid.innerHTML = `<div class="col-span-full py-16 text-center text-slate-400 flex items-center justify-center gap-2"><i data-lucide="loader" class="w-5 h-5 animate-spin text-amber-400"></i><span>Loading Site Operations records...</span></div>`;
    }
    if (tbody && siteViewMode === 'table') {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-400"><div class="flex items-center justify-center gap-2"><i data-lucide="loader" class="w-4 h-4 animate-spin text-amber-400"></i><span>Loading site operations...</span></div></td></tr>`;
    }
    if (window.lucide) lucide.createIcons();

    if (page === 1) {
        fetch('/api/disciplines/site_ops/stats')
            .then(r => r.json())
            .then(stats => {
                const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = (val || 0).toLocaleString(); };
                setEl('stat-site-scr', stats.total_scr);
                setEl('stat-site-si', stats.total_si);
                setEl('stat-site-daily', (stats.daily_reports || 0) + (stats.weekly_reports || 0));
                setEl('stat-site-access', stats.total_access);
            })
            .catch(err => console.error('Failed to load site ops stats:', err));
    }

    const pkg = document.getElementById('site-filter-project')?.value || 'all';
    const type = document.getElementById('site-filter-type')?.value || 'all';
    const overdue = document.getElementById('site-filter-overdue')?.checked || false;
    const search = document.getElementById('site-search-input')?.value || '';

    const params = new URLSearchParams({ page: siteCurrentPage, limit: 30 });
    if (pkg !== 'all') params.append('project', pkg);
    if (type !== 'all') params.append('item_type', type);
    if (overdue) params.append('overdue_only', 'true');
    if (search.trim()) params.append('search', search.trim());

    try {
        const res = await fetch(`/api/disciplines/site_ops/items?${params.toString()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!siteFilterLoaded) {
            const selPkg = document.getElementById('site-filter-project');
            if (selPkg && data.projects) {
                data.projects.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p;
                    opt.innerText = p;
                    selPkg.appendChild(opt);
                });
            }
            siteFilterLoaded = true;
        }

        renderSiteOpsData(data.items || []);
        renderDisciplinePagination('site-pagination', data.page, data.limit, data.total, 'loadDisciplineSite');
    } catch (err) {
        console.error('Error loading site ops items:', err);
        if (grid) grid.innerHTML = `<div class="col-span-full py-8 text-center text-rose-400">Failed to load Site Operations data: ${escapeHtml(err.message)}</div>`;
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-rose-400">Error: ${escapeHtml(err.message)}</td></tr>`;
    }
}
window.loadDisciplineSite = loadDisciplineSite;

function renderSiteOpsData(items) {
    const grid = document.getElementById('site-grid-container');
    const tbody = document.getElementById('site-table-tbody');

    if (!items || items.length === 0) {
        if (grid) grid.innerHTML = `<div class="col-span-full py-12 text-center text-slate-500 font-medium">No Site Operations records match current filters.</div>`;
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-500">No records found</td></tr>`;
        return;
    }

    let cardsHtml = '';
    let tableHtml = '';

    items.forEach(item => {
        let statusBadge = '';
        if (item.is_overdue) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-500/10 text-rose-400 border border-rose-500/30">OVERDUE</span>`;
        } else {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-500/10 text-amber-400 border border-amber-500/30">${escapeHtml(item.status || 'Active')}</span>`;
        }

        const typeColor = (item.mail_type || '').includes('Clarification') ? 'text-amber-400' : ((item.mail_type || '').includes('Instruction') ? 'text-sky-400' : 'text-purple-400');

        cardsHtml += `
            <div class="bg-slate-900 rounded-2xl border border-slate-800 hover:border-amber-500/40 p-5 flex flex-col justify-between transition-all duration-200 hover:shadow-xl hover:shadow-amber-500/5 group">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-3">
                        <span class="text-xs font-mono font-bold text-amber-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                            ${escapeHtml(item.mail_no)}
                        </span>
                        <div class="flex items-center gap-1.5">
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                                ${escapeHtml(item.project)}
                            </span>
                            ${statusBadge}
                        </div>
                    </div>

                    <div class="text-[11px] font-bold ${typeColor} mb-1 flex items-center gap-1.5">
                        <i data-lucide="hard-hat" class="w-3.5 h-3.5 flex-shrink-0"></i>
                        <span>${escapeHtml(item.mail_type)}</span>
                    </div>

                    <h4 class="text-sm font-bold text-white group-hover:text-amber-300 transition mb-3 leading-snug line-clamp-2">
                        ${escapeHtml(item.subject || 'No subject')}
                    </h4>

                    <div class="space-y-1.5 p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 mb-3 text-xs">
                        <div class="flex items-center justify-between text-slate-400">
                            <span class="text-[11px]">From Org:</span>
                            <span class="text-slate-200 font-medium truncate max-w-[180px]">${escapeHtml(item.from_org)}</span>
                        </div>
                        <div class="flex items-center justify-between text-slate-400">
                            <span class="text-[11px]">To Org:</span>
                            <span class="text-slate-200 font-medium truncate max-w-[180px]">${escapeHtml(item.to_org)}</span>
                        </div>
                    </div>
                </div>

                <div class="flex items-center justify-between pt-3 border-t border-slate-800/80 text-xs">
                    <div class="flex items-center gap-1.5 text-slate-400">
                        <i data-lucide="calendar" class="w-3.5 h-3.5 text-slate-500"></i>
                        <span class="font-mono text-[11px]">${item.sent_date}</span>
                    </div>
                    ${item.aconex_url ? `
                        <a href="${item.aconex_url}" target="_blank" class="px-3 py-1 rounded-lg bg-amber-600/10 hover:bg-amber-600 text-amber-400 hover:text-white border border-amber-500/20 text-[11px] font-bold flex items-center gap-1.5 transition">
                            <span>Open Aconex</span>
                            <i data-lucide="external-link" class="w-3 h-3"></i>
                        </a>
                    ` : `
                        <span class="text-[11px] text-slate-500">Aconex Indexed</span>
                    `}
                </div>
            </div>
        `;

        tableHtml += `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="p-3.5 whitespace-nowrap">
                    ${item.aconex_url ? `
                        <a href="${item.aconex_url}" target="_blank" class="font-mono font-bold text-amber-400 hover:underline inline-flex items-center gap-1">
                            <span>${escapeHtml(item.mail_no)}</span>
                            <i data-lucide="external-link" class="w-3 h-3 text-slate-500"></i>
                        </a>
                    ` : `<span class="font-mono font-bold text-amber-400">${escapeHtml(item.mail_no)}</span>`}
                </td>
                <td class="p-3.5 whitespace-nowrap font-medium text-slate-300">
                    <span class="px-2 py-0.5 rounded text-[11px] bg-slate-950 border border-slate-800 ${typeColor}">${escapeHtml(item.mail_type)}</span>
                </td>
                <td class="p-3.5 max-w-md">
                    <span class="font-medium text-white hover:text-amber-300 transition line-clamp-1">${escapeHtml(item.subject || '-')}</span>
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <span class="px-2 py-0.5 rounded text-[11px] bg-slate-950 text-slate-300 border border-slate-800 font-mono">${escapeHtml(item.project)}</span>
                </td>
                <td class="p-3.5 whitespace-nowrap text-slate-300 truncate max-w-[150px]">${escapeHtml(item.from_org)}</td>
                <td class="p-3.5 whitespace-nowrap text-slate-300 truncate max-w-[150px]">${escapeHtml(item.to_org)}</td>
                <td class="p-3.5 text-center font-mono whitespace-nowrap text-slate-400">${item.sent_date}</td>
                <td class="p-3.5 text-center whitespace-nowrap">${statusBadge}</td>
            </tr>
        `;
    });

    if (grid) grid.innerHTML = cardsHtml;
    if (tbody) tbody.innerHTML = tableHtml;
    if (window.lucide) lucide.createIcons();
}

function exportSiteOpsExcel() {
    const pkg = document.getElementById('site-filter-project')?.value || 'all';
    const type = document.getElementById('site-filter-type')?.value || 'all';
    const overdue = document.getElementById('site-filter-overdue')?.checked || false;
    const search = document.getElementById('site-search-input')?.value || '';

    const params = new URLSearchParams();
    if (pkg !== 'all') params.append('project', pkg);
    if (type !== 'all') params.append('item_type', type);
    if (overdue) params.append('overdue_only', 'true');
    if (search.trim()) params.append('search', search.trim());

    window.location.href = `/api/disciplines/site_ops/export?${params.toString()}`;
}
window.exportSiteOpsExcel = exportSiteOpsExcel;

// -----------------------------------------------------------------------------
// 20.4 TECHNICAL OFFICE & SUBMITTALS HUB
// -----------------------------------------------------------------------------
let techCurrentPage = 1;
let techViewMode = 'grid';
let techDebounceTimer = null;
let techFilterLoaded = false;

function setTechViewMode(mode) {
    techViewMode = mode;
    const btnGrid = document.getElementById('btn-tech-view-grid');
    const btnTable = document.getElementById('btn-tech-view-table');
    const gridContainer = document.getElementById('tech-grid-container');
    const tableContainer = document.getElementById('tech-table-container');

    if (mode === 'grid') {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (gridContainer) gridContainer.classList.remove('hidden');
        if (tableContainer) tableContainer.classList.add('hidden');
    } else {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (gridContainer) gridContainer.classList.add('hidden');
        if (tableContainer) tableContainer.classList.remove('hidden');
    }
}
window.setTechViewMode = setTechViewMode;

function debounceTechSearch() {
    clearTimeout(techDebounceTimer);
    techDebounceTimer = setTimeout(() => loadDisciplineTech(1), 300);
}
window.debounceTechSearch = debounceTechSearch;

async function loadDisciplineTech(page = 1) {
    techCurrentPage = page;
    const grid = document.getElementById('tech-grid-container');
    const tbody = document.getElementById('tech-table-tbody');

    if (grid && techViewMode === 'grid') {
        grid.innerHTML = `<div class="col-span-full py-16 text-center text-slate-400 flex items-center justify-center gap-2"><i data-lucide="loader" class="w-5 h-5 animate-spin text-indigo-400"></i><span>Loading Technical Office submittals...</span></div>`;
    }
    if (tbody && techViewMode === 'table') {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-400"><div class="flex items-center justify-center gap-2"><i data-lucide="loader" class="w-4 h-4 animate-spin text-indigo-400"></i><span>Loading submittals...</span></div></td></tr>`;
    }
    if (window.lucide) lucide.createIcons();

    if (page === 1) {
        fetch('/api/disciplines/technical_office/stats')
            .then(r => r.json())
            .then(stats => {
                const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = (val || 0).toLocaleString(); };
                setEl('stat-tech-drawings', stats.total_shop_drawings);
                setEl('stat-tech-materials', stats.total_materials);
                setEl('stat-tech-crs', stats.total_crs);
                setEl('stat-tech-calc', stats.total_calculations);
            })
            .catch(err => console.error('Failed to load tech office stats:', err));
    }

    const pkg = document.getElementById('tech-filter-project')?.value || 'all';
    const disc = document.getElementById('tech-filter-discipline')?.value || 'all';
    const type = document.getElementById('tech-filter-type')?.value || 'all';
    const search = document.getElementById('tech-search-input')?.value || '';

    const params = new URLSearchParams({ page: techCurrentPage, limit: 30 });
    if (pkg !== 'all') params.append('project', pkg);
    if (disc !== 'all') params.append('discipline', disc);
    if (type !== 'all') params.append('doc_type', type);
    if (search.trim()) params.append('search', search.trim());

    try {
        const res = await fetch(`/api/disciplines/technical_office/items?${params.toString()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (!techFilterLoaded) {
            const selPkg = document.getElementById('tech-filter-project');
            if (selPkg && data.projects) {
                data.projects.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p;
                    opt.innerText = p;
                    selPkg.appendChild(opt);
                });
            }
            const selDisc = document.getElementById('tech-filter-discipline');
            if (selDisc && data.disciplines) {
                data.disciplines.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d;
                    opt.innerText = d;
                    selDisc.appendChild(opt);
                });
            }
            techFilterLoaded = true;
        }

        renderTechData(data.items || []);
        renderDisciplinePagination('tech-pagination', data.page, data.limit, data.total, 'loadDisciplineTech');
    } catch (err) {
        console.error('Error loading Tech Office items:', err);
        if (grid) grid.innerHTML = `<div class="col-span-full py-8 text-center text-rose-400">Failed to load Tech Office data: ${escapeHtml(err.message)}</div>`;
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-rose-400">Error: ${escapeHtml(err.message)}</td></tr>`;
    }
}
window.loadDisciplineTech = loadDisciplineTech;

function renderTechData(items) {
    const grid = document.getElementById('tech-grid-container');
    const tbody = document.getElementById('tech-table-tbody');

    if (!items || items.length === 0) {
        if (grid) grid.innerHTML = `<div class="col-span-full py-12 text-center text-slate-500 font-medium">No Technical Office submittals match current filters.</div>`;
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-500">No records found</td></tr>`;
        return;
    }

    let cardsHtml = '';
    let tableHtml = '';

    items.forEach(item => {
        let statusBadge = '';
        const st = (item.review_status || '').toLowerCase();
        if (st.includes('approved') && !st.includes('noted')) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">Approved</span>`;
        } else if (st.includes('noted') || st.includes('comment')) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">Approved w/ Notes</span>`;
        } else if (st.includes('reject') || st.includes('revise')) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-500/10 text-rose-400 border border-rose-500/30">Revise/Reject</span>`;
        } else {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">${escapeHtml(item.review_status || 'Under Review')}</span>`;
        }

        cardsHtml += `
            <div class="bg-slate-900 rounded-2xl border border-slate-800 hover:border-indigo-500/40 p-5 flex flex-col justify-between transition-all duration-200 hover:shadow-xl hover:shadow-indigo-500/5 group">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-3">
                        <span class="text-xs font-mono font-bold text-indigo-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800 truncate max-w-[200px]">
                            ${escapeHtml(item.document_no)}
                        </span>
                        <div class="flex items-center gap-1.5 flex-shrink-0">
                            <span class="text-[10px] font-mono text-slate-400">Rev ${escapeHtml(item.revision)}</span>
                            ${statusBadge}
                        </div>
                    </div>

                    <div class="flex items-center gap-2 mb-1">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-950/60 text-indigo-300 border border-indigo-800/80">
                            ${escapeHtml(item.discipline || 'General')}
                        </span>
                        <span class="text-[11px] font-semibold text-slate-400">${escapeHtml(item.doc_type)}</span>
                    </div>

                    <h4 class="text-sm font-bold text-white group-hover:text-indigo-300 transition mb-3 leading-snug line-clamp-2">
                        ${escapeHtml(item.title || 'Untitled Submittal')}
                    </h4>

                    <div class="p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 mb-3 text-xs">
                        <div class="flex items-center justify-between text-slate-400">
                            <span class="text-[11px]">Package:</span>
                            <span class="text-slate-200 font-semibold font-mono">${escapeHtml(item.project)}</span>
                        </div>
                    </div>
                </div>

                <div class="flex items-center justify-between pt-3 border-t border-slate-800/80 text-xs">
                    <div class="flex items-center gap-1.5 text-slate-400">
                        <i data-lucide="calendar" class="w-3.5 h-3.5 text-slate-500"></i>
                        <span class="font-mono text-[11px]">${item.date_modified}</span>
                    </div>
                    ${item.aconex_url ? `
                        <a href="${item.aconex_url}" target="_blank" class="px-3 py-1 rounded-lg bg-indigo-600/10 hover:bg-indigo-600 text-indigo-400 hover:text-white border border-indigo-500/20 text-[11px] font-bold flex items-center gap-1.5 transition">
                            <span>Open Aconex</span>
                            <i data-lucide="external-link" class="w-3 h-3"></i>
                        </a>
                    ` : `
                        <span class="text-[11px] text-slate-500">Aconex Submittal</span>
                    `}
                </div>
            </div>
        `;

        tableHtml += `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="p-3.5 whitespace-nowrap">
                    ${item.aconex_url ? `
                        <a href="${item.aconex_url}" target="_blank" class="font-mono font-bold text-indigo-400 hover:underline inline-flex items-center gap-1">
                            <span>${escapeHtml(item.document_no)}</span>
                            <i data-lucide="external-link" class="w-3 h-3 text-slate-500"></i>
                        </a>
                    ` : `<span class="font-mono font-bold text-indigo-400">${escapeHtml(item.document_no)}</span>`}
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <span class="px-2 py-0.5 rounded text-[11px] font-bold bg-indigo-950/60 text-indigo-300 border border-indigo-800/80">${escapeHtml(item.discipline || '-')}</span>
                </td>
                <td class="p-3.5 whitespace-nowrap text-slate-300 font-medium">${escapeHtml(item.doc_type)}</td>
                <td class="p-3.5 max-w-md">
                    <span class="font-medium text-white hover:text-indigo-300 transition line-clamp-1">${escapeHtml(item.title || '-')}</span>
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <span class="px-2 py-0.5 rounded text-[11px] bg-slate-950 text-slate-300 border border-slate-800 font-mono">${escapeHtml(item.project)}</span>
                </td>
                <td class="p-3.5 text-center whitespace-nowrap">${statusBadge}</td>
                <td class="p-3.5 text-center font-mono whitespace-nowrap text-slate-400">${escapeHtml(item.revision)}</td>
                <td class="p-3.5 text-center font-mono whitespace-nowrap text-slate-400">${item.date_modified}</td>
            </tr>
        `;
    });

    if (grid) grid.innerHTML = cardsHtml;
    if (tbody) tbody.innerHTML = tableHtml;
    if (window.lucide) lucide.createIcons();
}

function exportTechOfficeExcel() {
    const pkg = document.getElementById('tech-filter-project')?.value || 'all';
    const disc = document.getElementById('tech-filter-discipline')?.value || 'all';
    const type = document.getElementById('tech-filter-type')?.value || 'all';
    const search = document.getElementById('tech-search-input')?.value || '';

    const params = new URLSearchParams();
    if (pkg !== 'all') params.append('project', pkg);
    if (disc !== 'all') params.append('discipline', disc);
    if (type !== 'all') params.append('doc_type', type);
    if (search.trim()) params.append('search', search.trim());

    window.location.href = `/api/disciplines/technical_office/export?${params.toString()}`;
}
window.exportTechOfficeExcel = exportTechOfficeExcel;

// -----------------------------------------------------------------------------
// 20.5 CONTRACTUAL CORRESPONDENCE HUB
// -----------------------------------------------------------------------------
let contractualCurrentPage = 1;
let contractualViewMode = 'grid';
let contractualDebounceTimer = null;
let contractualFilterLoaded = false;

function setContractualViewMode(mode) {
    contractualViewMode = mode;
    const btnGrid = document.getElementById('btn-contractual-view-grid');
    const btnTable = document.getElementById('btn-contractual-view-table');
    const gridContainer = document.getElementById('contractual-grid-container');
    const tableContainer = document.getElementById('contractual-table-container');

    if (mode === 'grid') {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (gridContainer) gridContainer.classList.remove('hidden');
        if (tableContainer) tableContainer.classList.add('hidden');
    } else {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (gridContainer) gridContainer.classList.add('hidden');
        if (tableContainer) tableContainer.classList.remove('hidden');
    }
}
window.setContractualViewMode = setContractualViewMode;

function debounceContractualSearch() {
    clearTimeout(contractualDebounceTimer);
    contractualDebounceTimer = setTimeout(() => loadDisciplineContractual(1), 300);
}
window.debounceContractualSearch = debounceContractualSearch;

async function setContractualCategoryFilter(cat) {
    const elCat = document.getElementById('contractual-filter-category');
    if (elCat) elCat.value = cat;
    const elType = document.getElementById('contractual-filter-type');
    if (elType) elType.value = 'all';
    loadDisciplineContractual(1);
}
window.setContractualCategoryFilter = setContractualCategoryFilter;

function loadDisciplineContractual(page = 1) {
    contractualCurrentPage = page;
    const grid = document.getElementById('contractual-grid-container');
    const tbody = document.getElementById('contractual-table-tbody');

    if (grid && contractualViewMode === 'grid') {
        grid.innerHTML = `<div class="col-span-full py-16 text-center text-slate-400 flex items-center justify-center gap-2"><i data-lucide="loader" class="w-5 h-5 animate-spin text-blue-400"></i><span>Loading Contractual Correspondence...</span></div>`;
    }
    if (tbody && contractualViewMode === 'table') {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-400"><div class="flex items-center justify-center gap-2"><i data-lucide="loader" class="w-4 h-4 animate-spin text-blue-400"></i><span>Loading correspondence records...</span></div></td></tr>`;
    }
    if (window.lucide) lucide.createIcons();

    if (page === 1) {
        fetch('/api/disciplines/contractual/stats')
            .then(r => r.json())
            .then(stats => {
                const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = (val || 0).toLocaleString(); };
                setEl('stat-contractual-total', stats.total_correspondence);
                setEl('stat-contractual-letters', stats.letters);
                setEl('stat-contractual-general', stats.general_correspondence);
                setEl('stat-contractual-instructions', stats.instructions);
                setEl('stat-contractual-pending', stats.pending_action);
                setEl('stat-contractual-overdue', stats.overdue);
                const badge = document.getElementById('badge-contractual-total-count');
                if (badge && stats.total_correspondence) badge.innerText = `${(stats.total_correspondence / 1000).toFixed(1)}k Items`;
            })
            .catch(err => console.error('Failed to load contractual stats:', err));
    }

    const pkg = document.getElementById('contractual-filter-project')?.value || 'all';
    const category = document.getElementById('contractual-filter-category')?.value || 'all';
    const type = document.getElementById('contractual-filter-type')?.value || 'all';
    const status = document.getElementById('contractual-filter-status')?.value || 'all';
    const search = document.getElementById('contractual-search-input')?.value || '';

    const params = new URLSearchParams({ page: contractualCurrentPage, limit: 30 });
    if (pkg !== 'all') params.append('project', pkg);
    if (category !== 'all') params.append('category', category);
    if (type !== 'all') params.append('item_type', type);
    if (status !== 'all') params.append('status', status);
    if (search.trim()) params.append('search', search.trim());

    fetch(`/api/disciplines/contractual/items?${params.toString()}`)
        .then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
        })
        .then(data => {
            if (!contractualFilterLoaded) {
                const selPkg = document.getElementById('contractual-filter-project');
                if (selPkg && data.projects) {
                    data.projects.forEach(p => {
                        const opt = document.createElement('option');
                        opt.value = p;
                        opt.innerText = p;
                        selPkg.appendChild(opt);
                    });
                }
                contractualFilterLoaded = true;
            }

            const selType = document.getElementById('contractual-filter-type');
            if (selType && data.types) {
                const currentVal = selType.value;
                selType.innerHTML = '<option value="all">All Types</option>';
                data.types.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t;
                    opt.innerText = t;
                    if (t === currentVal) opt.selected = true;
                    selType.appendChild(opt);
                });
            }

            renderContractualData(data.items || []);
            renderDisciplinePagination('contractual-pagination', data.page, data.limit, data.total, 'loadDisciplineContractual');
        })
        .catch(err => {
            console.error('Error loading contractual items:', err);
            if (grid) grid.innerHTML = `<div class="col-span-full py-8 text-center text-rose-400">Failed to load Contractual data: ${escapeHtml(err.message)}</div>`;
            if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-rose-400">Error: ${escapeHtml(err.message)}</td></tr>`;
        });
}
window.loadDisciplineContractual = loadDisciplineContractual;

function renderContractualData(items) {
    const grid = document.getElementById('contractual-grid-container');
    const tbody = document.getElementById('contractual-table-tbody');

    if (!items || items.length === 0) {
        if (grid) grid.innerHTML = `<div class="col-span-full py-12 text-center text-slate-500 font-medium">No Contractual Correspondence matches current filters.</div>`;
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-500">No records found</td></tr>`;
        return;
    }

    let cardsHtml = '';
    let tableHtml = '';

    items.forEach(item => {
        let statusBadge = '';
        if (item.is_overdue) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-500/10 text-rose-400 border border-rose-500/30">OVERDUE</span>`;
        } else if ((item.status || '').toLowerCase().includes('close') || (item.status || '').toLowerCase().includes('accept') || (item.status || '').toLowerCase().includes('registered')) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-blue-500/10 text-blue-400 border border-blue-500/30">${escapeHtml(item.status)}</span>`;
        } else {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-amber-500/10 text-amber-400 border border-amber-500/30">${escapeHtml(item.status || 'Active')}</span>`;
        }

        const tLower = (item.item_type || '').toLowerCase();
        let typeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">${escapeHtml(item.item_type)}</span>`;
        if (tLower.includes('formal letter') || tLower === 'letter') {
            typeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30">Formal Letter</span>`;
        } else if (tLower.includes('instruction') || tLower.includes('warning')) {
            typeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">Instruction / Notice</span>`;
        } else if (tLower.includes('general correspondence')) {
            typeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">General Corr</span>`;
        }

        cardsHtml += `
            <div class="bg-slate-900 rounded-2xl border border-slate-800 hover:border-blue-500/40 p-5 flex flex-col justify-between transition-all duration-200 hover:shadow-xl hover:shadow-blue-500/5 group">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-3">
                        <span class="text-xs font-mono font-bold text-blue-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800 truncate max-w-[200px]">
                            ${escapeHtml(item.item_no)}
                        </span>
                        <div class="flex items-center gap-1.5 flex-shrink-0">
                            <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800">${escapeHtml(item.source_type || 'Mail')}</span>
                            ${statusBadge}
                        </div>
                    </div>

                    <div class="flex items-center gap-2 mb-2">
                        ${typeBadge}
                    </div>

                    <h4 class="text-sm font-bold text-white group-hover:text-blue-300 transition mb-3 leading-snug line-clamp-2">
                        ${escapeHtml(item.title || 'Untitled Correspondence')}
                    </h4>

                    <div class="space-y-1.5 p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 mb-3 text-xs">
                        <div class="flex items-center justify-between text-slate-400">
                            <span class="text-[11px]">Package:</span>
                            <span class="text-slate-200 font-semibold font-mono truncate max-w-[180px]">${escapeHtml(item.project || 'General')}</span>
                        </div>
                        <div class="flex items-center justify-between text-slate-400">
                            <span class="text-[11px]">From / To:</span>
                            <span class="text-slate-300 font-medium truncate max-w-[180px]">${escapeHtml(item.from_org || '-')} &rarr; ${escapeHtml(item.to_org || '-')}</span>
                        </div>
                    </div>
                </div>

                <div class="flex items-center justify-between pt-3 border-t border-slate-800/80 text-xs">
                    <div class="flex items-center gap-1.5 text-slate-400">
                        <i data-lucide="calendar" class="w-3.5 h-3.5 text-slate-500"></i>
                        <span class="font-mono text-[11px]">${item.item_date || '-'}</span>
                    </div>
                    ${item.aconex_url ? `
                        <a href="${item.aconex_url}" target="_blank" class="px-3 py-1 rounded-lg bg-blue-600/10 hover:bg-blue-600 text-blue-400 hover:text-white border border-blue-500/20 text-[11px] font-bold flex items-center gap-1.5 transition">
                            <span>Open in Aconex</span>
                            <i data-lucide="external-link" class="w-3 h-3"></i>
                        </a>
                    ` : `
                        <span class="text-[11px] text-slate-500 font-mono">Aconex Item</span>
                    `}
                </div>
            </div>
        `;

        tableHtml += `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="p-3.5 whitespace-nowrap">
                    ${item.aconex_url ? `
                        <a href="${item.aconex_url}" target="_blank" class="font-mono font-bold text-blue-400 hover:underline inline-flex items-center gap-1">
                            <span>${escapeHtml(item.item_no)}</span>
                            <i data-lucide="external-link" class="w-3 h-3 text-slate-500"></i>
                        </a>
                    ` : `<span class="font-mono font-bold text-blue-400">${escapeHtml(item.item_no)}</span>`}
                </td>
                <td class="p-3.5 whitespace-nowrap">${typeBadge}</td>
                <td class="p-3.5 max-w-xs">
                    <span class="font-medium text-white hover:text-blue-300 transition line-clamp-1">${escapeHtml(item.title || '-')}</span>
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <span class="px-2 py-0.5 rounded text-[11px] bg-slate-950 text-slate-300 border border-slate-800 font-mono">${escapeHtml(item.project || '-')}</span>
                </td>
                <td class="p-3.5 text-slate-300 text-xs whitespace-nowrap truncate max-w-[130px]">${escapeHtml(item.from_org || '-')}</td>
                <td class="p-3.5 text-slate-300 text-xs whitespace-nowrap truncate max-w-[130px]">${escapeHtml(item.to_org || '-')}</td>
                <td class="p-3.5 text-center font-mono whitespace-nowrap text-slate-400 text-xs">${item.item_date || '-'}</td>
                <td class="p-3.5 text-center whitespace-nowrap">${statusBadge}</td>
            </tr>
        `;
    });

    if (grid) grid.innerHTML = cardsHtml;
    if (tbody) tbody.innerHTML = tableHtml;
    if (window.lucide) lucide.createIcons();
}

function exportContractualExcel() {
    const pkg = document.getElementById('contractual-filter-project')?.value || 'all';
    const category = document.getElementById('contractual-filter-category')?.value || 'all';
    const type = document.getElementById('contractual-filter-type')?.value || 'all';
    const status = document.getElementById('contractual-filter-status')?.value || 'all';
    const search = document.getElementById('contractual-search-input')?.value || '';

    const params = new URLSearchParams();
    if (pkg !== 'all') params.append('project', pkg);
    if (category !== 'all') params.append('category', category);
    if (type !== 'all') params.append('item_type', type);
    if (status !== 'all') params.append('status', status);
    if (search.trim()) params.append('search', search.trim());

    window.location.href = `/api/disciplines/contractual/export?${params.toString()}`;
}
window.exportContractualExcel = exportContractualExcel;


// -----------------------------------------------------------------------------
// 20.6 COMMERCIAL & CONTROLS HUB
// -----------------------------------------------------------------------------
let commercialCurrentPage = 1;
let commercialViewMode = 'grid';
let commercialDebounceTimer = null;
let commercialFilterLoaded = false;

function setCommercialViewMode(mode) {
    commercialViewMode = mode;
    const btnGrid = document.getElementById('btn-commercial-view-grid');
    const btnTable = document.getElementById('btn-commercial-view-table');
    const gridContainer = document.getElementById('commercial-grid-container');
    const tableContainer = document.getElementById('commercial-table-container');

    if (mode === 'grid') {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (gridContainer) gridContainer.classList.remove('hidden');
        if (tableContainer) tableContainer.classList.add('hidden');
    } else {
        if (btnGrid) btnGrid.className = 'px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5 cursor-pointer';
        if (btnTable) btnTable.className = 'px-2.5 py-1 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-slate-800 text-white shadow-sm cursor-pointer';
        if (gridContainer) gridContainer.classList.add('hidden');
        if (tableContainer) tableContainer.classList.remove('hidden');
    }
}
window.setCommercialViewMode = setCommercialViewMode;

function debounceCommercialSearch() {
    clearTimeout(commercialDebounceTimer);
    commercialDebounceTimer = setTimeout(() => loadDisciplineCommercial(1), 300);
}
window.debounceCommercialSearch = debounceCommercialSearch;

async function setCommercialCategoryFilter(cat) {
    const elCat = document.getElementById('commercial-filter-category');
    if (elCat) elCat.value = cat;
    const elType = document.getElementById('commercial-filter-type');
    if (elType) elType.value = 'all';
    loadDisciplineCommercial(1);
}
window.setCommercialCategoryFilter = setCommercialCategoryFilter;

function loadDisciplineCommercial(page = 1) {
    commercialCurrentPage = page;
    const grid = document.getElementById('commercial-grid-container');
    const tbody = document.getElementById('commercial-table-tbody');

    if (grid && commercialViewMode === 'grid') {
        grid.innerHTML = `<div class="col-span-full py-16 text-center text-slate-400 flex items-center justify-center gap-2"><i data-lucide="loader" class="w-5 h-5 animate-spin text-emerald-400"></i><span>Loading Commercial &amp; Controls records...</span></div>`;
    }
    if (tbody && commercialViewMode === 'table') {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-400"><div class="flex items-center justify-center gap-2"><i data-lucide="loader" class="w-4 h-4 animate-spin text-emerald-400"></i><span>Loading commercial instruments...</span></div></td></tr>`;
    }
    if (window.lucide) lucide.createIcons();

    if (page === 1) {
        fetch('/api/disciplines/commercial/stats')
            .then(r => r.json())
            .then(stats => {
                const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = (val || 0).toLocaleString(); };
                setEl('stat-commercial-total', stats.total_commercial);
                setEl('stat-commercial-boqs', stats.boqs);
                setEl('stat-commercial-payments', stats.payment_apps_invoices);
                setEl('stat-commercial-variations', stats.variation_orders_claims);
                setEl('stat-commercial-proposals', stats.proposals_tenders);
                setEl('stat-commercial-bonds', stats.bonds_contracts_costs);
                const badge = document.getElementById('badge-commercial-total-count');
                if (badge && stats.total_commercial) badge.innerText = `${(stats.total_commercial / 1000).toFixed(1)}k Items`;
            })
            .catch(err => console.error('Failed to load commercial stats:', err));
    }

    const pkg = document.getElementById('commercial-filter-project')?.value || 'all';
    const category = document.getElementById('commercial-filter-category')?.value || 'all';
    const type = document.getElementById('commercial-filter-type')?.value || 'all';
    const status = document.getElementById('commercial-filter-status')?.value || 'all';
    const search = document.getElementById('commercial-search-input')?.value || '';

    const params = new URLSearchParams({ page: commercialCurrentPage, limit: 30 });
    if (pkg !== 'all') params.append('project', pkg);
    if (category !== 'all') params.append('category', category);
    if (type !== 'all') params.append('item_type', type);
    if (status !== 'all') params.append('status', status);
    if (search.trim()) params.append('search', search.trim());

    fetch(`/api/disciplines/commercial/items?${params.toString()}`)
        .then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.json();
        })
        .then(data => {
            if (!commercialFilterLoaded) {
                const selPkg = document.getElementById('commercial-filter-project');
                if (selPkg && data.projects) {
                    data.projects.forEach(p => {
                        const opt = document.createElement('option');
                        opt.value = p;
                        opt.innerText = p;
                        selPkg.appendChild(opt);
                    });
                }
                commercialFilterLoaded = true;
            }

            const selType = document.getElementById('commercial-filter-type');
            if (selType && data.types) {
                const currentVal = selType.value;
                selType.innerHTML = '<option value="all">All Types</option>';
                data.types.forEach(t => {
                    const opt = document.createElement('option');
                    opt.value = t;
                    opt.innerText = t;
                    if (t === currentVal) opt.selected = true;
                    selType.appendChild(opt);
                });
            }

            renderCommercialData(data.items || []);
            renderDisciplinePagination('commercial-pagination', data.page, data.limit, data.total, 'loadDisciplineCommercial');
        })
        .catch(err => {
            console.error('Error loading commercial items:', err);
            if (grid) grid.innerHTML = `<div class="col-span-full py-8 text-center text-rose-400">Failed to load Commercial data: ${escapeHtml(err.message)}</div>`;
            if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-6 text-rose-400">Error: ${escapeHtml(err.message)}</td></tr>`;
        });
}
window.loadDisciplineCommercial = loadDisciplineCommercial;

function renderCommercialData(items) {
    const grid = document.getElementById('commercial-grid-container');
    const tbody = document.getElementById('commercial-table-tbody');

    if (!items || items.length === 0) {
        if (grid) grid.innerHTML = `<div class="col-span-full py-12 text-center text-slate-500 font-medium">No Commercial &amp; Controls records match current filters.</div>`;
        if (tbody) tbody.innerHTML = `<tr><td colspan="8" class="text-center py-10 text-slate-500">No records found</td></tr>`;
        return;
    }

    let cardsHtml = '';
    let tableHtml = '';

    items.forEach(item => {
        let statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">${escapeHtml(item.status || 'Active')}</span>`;

        const tLower = (item.item_type || '').toLowerCase();
        let typeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">${escapeHtml(item.item_type)}</span>`;
        if (tLower.includes('bill of quantities') || tLower.includes('boq')) {
            typeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-teal-500/20 text-teal-300 border border-teal-500/30">BOQ</span>`;
        } else if (tLower.includes('invoice') || tLower.includes('payment')) {
            typeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Payment / Invoice</span>`;
        } else if (tLower.includes('variation') || tLower.includes('claim')) {
            typeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">VO / Claim</span>`;
        } else if (tLower.includes('proposal') || tLower.includes('tender')) {
            typeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/20 text-sky-300 border border-sky-500/30">Proposal / Tender</span>`;
        } else if (tLower.includes('insurance') || tLower.includes('bond') || tLower.includes('cost')) {
            typeBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">Bond / Cost</span>`;
        }

        cardsHtml += `
            <div class="bg-slate-900 rounded-2xl border border-slate-800 hover:border-emerald-500/40 p-5 flex flex-col justify-between transition-all duration-200 hover:shadow-xl hover:shadow-emerald-500/5 group">
                <div>
                    <div class="flex items-center justify-between gap-2 mb-3">
                        <span class="text-xs font-mono font-bold text-emerald-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800 truncate max-w-[200px]">
                            ${escapeHtml(item.item_no)}
                        </span>
                        <div class="flex items-center gap-1.5 flex-shrink-0">
                            <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-950 text-slate-400 border border-slate-800">${escapeHtml(item.source_type || 'Document')}</span>
                            ${statusBadge}
                        </div>
                    </div>

                    <div class="flex items-center gap-2 mb-2">
                        ${typeBadge}
                    </div>

                    <h4 class="text-sm font-bold text-white group-hover:text-emerald-300 transition mb-3 leading-snug line-clamp-2">
                        ${escapeHtml(item.title || 'Untitled Commercial Item')}
                    </h4>

                    <div class="space-y-1.5 p-3 rounded-xl bg-slate-950/70 border border-slate-800/80 mb-3 text-xs">
                        <div class="flex items-center justify-between text-slate-400">
                            <span class="text-[11px]">Package:</span>
                            <span class="text-slate-200 font-semibold font-mono truncate max-w-[180px]">${escapeHtml(item.project || 'General')}</span>
                        </div>
                        <div class="flex items-center justify-between text-slate-400">
                            <span class="text-[11px]">Discipline / Author:</span>
                            <span class="text-slate-300 font-medium truncate max-w-[180px]">${escapeHtml(item.from_org || '-')}</span>
                        </div>
                    </div>
                </div>

                <div class="flex items-center justify-between pt-3 border-t border-slate-800/80 text-xs">
                    <div class="flex items-center gap-1.5 text-slate-400">
                        <i data-lucide="calendar" class="w-3.5 h-3.5 text-slate-500"></i>
                        <span class="font-mono text-[11px]">${item.item_date || '-'}</span>
                    </div>
                    ${item.aconex_url ? `
                        <a href="${item.aconex_url}" target="_blank" class="px-3 py-1 rounded-lg bg-emerald-600/10 hover:bg-emerald-600 text-emerald-400 hover:text-white border border-emerald-500/20 text-[11px] font-bold flex items-center gap-1.5 transition">
                            <span>Open in Aconex</span>
                            <i data-lucide="external-link" class="w-3 h-3"></i>
                        </a>
                    ` : `
                        <span class="text-[11px] text-slate-500 font-mono">Aconex Document</span>
                    `}
                </div>
            </div>
        `;

        tableHtml += `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="p-3.5 whitespace-nowrap">
                    ${item.aconex_url ? `
                        <a href="${item.aconex_url}" target="_blank" class="font-mono font-bold text-emerald-400 hover:underline inline-flex items-center gap-1">
                            <span>${escapeHtml(item.item_no)}</span>
                            <i data-lucide="external-link" class="w-3 h-3 text-slate-500"></i>
                        </a>
                    ` : `<span class="font-mono font-bold text-emerald-400">${escapeHtml(item.item_no)}</span>`}
                </td>
                <td class="p-3.5 whitespace-nowrap">${typeBadge}</td>
                <td class="p-3.5 max-w-xs">
                    <span class="font-medium text-white hover:text-emerald-300 transition line-clamp-1">${escapeHtml(item.title || '-')}</span>
                </td>
                <td class="p-3.5 whitespace-nowrap">
                    <span class="px-2 py-0.5 rounded text-[11px] bg-slate-950 text-slate-300 border border-slate-800 font-mono">${escapeHtml(item.project || '-')}</span>
                </td>
                <td class="p-3.5 text-slate-300 text-xs whitespace-nowrap truncate max-w-[130px]">${escapeHtml(item.from_org || '-')}</td>
                <td class="p-3.5 text-center font-mono whitespace-nowrap text-slate-400 text-xs">${escapeHtml(item.to_org || '01')}</td>
                <td class="p-3.5 text-center font-mono whitespace-nowrap text-slate-400 text-xs">${item.item_date || '-'}</td>
                <td class="p-3.5 text-center whitespace-nowrap">${statusBadge}</td>
            </tr>
        `;
    });

    if (grid) grid.innerHTML = cardsHtml;
    if (tbody) tbody.innerHTML = tableHtml;
    if (window.lucide) lucide.createIcons();
}

function exportCommercialExcel() {
    const pkg = document.getElementById('commercial-filter-project')?.value || 'all';
    const category = document.getElementById('commercial-filter-category')?.value || 'all';
    const type = document.getElementById('commercial-filter-type')?.value || 'all';
    const status = document.getElementById('commercial-filter-status')?.value || 'all';
    const search = document.getElementById('commercial-search-input')?.value || '';

    const params = new URLSearchParams();
    if (pkg !== 'all') params.append('project', pkg);
    if (category !== 'all') params.append('category', category);
    if (type !== 'all') params.append('item_type', type);
    if (status !== 'all') params.append('status', status);
    if (search.trim()) params.append('search', search.trim());

    window.location.href = `/api/disciplines/commercial/export?${params.toString()}`;
}
window.exportCommercialExcel = exportCommercialExcel;


// Attach clean DOMContentLoaded listener
document.addEventListener('DOMContentLoaded', () => {
    initAppTheme();
});




// =============================================================================

// ACONEX AUTONOMOUS PIPELINE & TASK SCHEDULER CONTROLS
let syncPollTimer = null;

// =========================================================================
// ACONEX PIPELINE SYNC DELEGATES (Unified with Main Controller)
// =========================================================================
function loadSyncStatus() {
    if (typeof window.loadSyncStatus === 'function') {
        window.loadSyncStatus();
    }
}
window.loadSyncStatus = loadSyncStatus;




// =============================================================================
// TAB 2: DAILY DELIVERABLES & ACTIVITY FEED (TODAY & YESTERDAY)
// =============================================================================
let feedCurrentTimeframe = 'today_yesterday';
let feedFromDate = '';
let feedToDate = '';
let feedDiscipline = 'all';
let feedStatus = 'all';
let feedCurrentSource = 'all';
let feedCurrentType = 'all';
let feedCurrentProject = 'all';
let feedCurrentSearch = '';
let feedCurrentPage = 1;
let feedLimit = 50;
let feedSummaryData = null;
let feedSearchTimeout = null;

function changeFeedTimeframe(tf) {
    feedCurrentTimeframe = tf;
    feedFromDate = '';
    feedToDate = '';
    
    // Clear custom date input fields
    const fIn = document.getElementById('feed-from-date');
    const tIn = document.getElementById('feed-to-date');
    if (fIn) fIn.value = '';
    if (tIn) tIn.value = '';

    // Update active highlight across preset buttons
    ['today', '7d', '14d', '30d', '60d', 'all'].forEach(k => {
        const btn = document.getElementById(`feed-timeframe-btn-${k}`);
        if (btn) {
            if ((k === 'today' && tf === 'today_yesterday') || (k === tf)) {
                btn.className = 'px-2.5 py-1.5 rounded-lg bg-amber-600 text-white shadow-sm transition cursor-pointer font-bold';
            } else {
                btn.className = 'px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer';
            }
        }
    });

    feedSummaryData = null;
    loadDailyFeed(1);
}
window.changeFeedTimeframe = changeFeedTimeframe;

function applyCustomFeedDateRange() {
    const fIn = document.getElementById('feed-from-date');
    const tIn = document.getElementById('feed-to-date');
    feedFromDate = (fIn?.value || '').trim();
    feedToDate = (tIn?.value || '').trim();

    if (!feedFromDate && !feedToDate) {
        changeFeedTimeframe('today_yesterday');
        return;
    }

    feedCurrentTimeframe = 'custom';
    // Remove active highlight from all preset buttons
    ['today', '7d', '14d', '30d', '60d', 'all'].forEach(k => {
        const btn = document.getElementById(`feed-timeframe-btn-${k}`);
        if (btn) {
            btn.className = 'px-2.5 py-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition cursor-pointer';
        }
    });

    feedSummaryData = null;
    loadDailyFeed(1);
}
window.applyCustomFeedDateRange = applyCustomFeedDateRange;

function filterFeedByDiscipline(disc) {
    feedDiscipline = disc || 'all';
    loadDailyFeed(1);
}
window.filterFeedByDiscipline = filterFeedByDiscipline;

function filterFeedByStatus(st) {
    feedStatus = st || 'all';
    loadDailyFeed(1);
}
window.filterFeedByStatus = filterFeedByStatus;

async function loadDailyFeed(page = 1) {
    feedCurrentPage = page;
    const tbody = document.getElementById('feed-table-tbody');
    if (tbody) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-12 text-slate-400"><div class="flex items-center justify-center gap-2"><i data-lucide="loader" class="w-5 h-5 animate-spin text-amber-400"></i><span>Loading ${feedCurrentTimeframe === 'today_yesterday' ? 'Today & Yesterday' : (feedCurrentTimeframe === '7d' ? 'Last 7 Days' : 'Last 30 Days')} deliverables...</span></div></td></tr>`;
        if (window.lucide) lucide.createIcons();
    }

    // Always fetch summary on page 1 or if not yet loaded
    if (page === 1 || !feedSummaryData) {
        try {
            const sumParams = new URLSearchParams({ timeframe: feedCurrentTimeframe });
            if (feedFromDate) sumParams.append('from_date', feedFromDate);
            if (feedToDate) sumParams.append('to_date', feedToDate);
            const sumRes = await fetch(`/api/feed/summary?${sumParams.toString()}`);
            if (sumRes.ok) {
                feedSummaryData = await sumRes.json();
                renderFeedSummary(feedSummaryData);
            }
        } catch (e) {
            console.error('Failed to load feed summary:', e);
        }
    }

    // Fetch paginated items
    const params = new URLSearchParams({
        timeframe: feedCurrentTimeframe,
        source: feedCurrentSource,
        item_type: feedCurrentType,
        project: feedCurrentProject,
        page: feedCurrentPage,
        limit: feedLimit
    });
    if (feedFromDate) params.append('from_date', feedFromDate);
    if (feedToDate) params.append('to_date', feedToDate);
    if (feedDiscipline && feedDiscipline !== 'all') params.append('discipline', feedDiscipline);
    if (feedStatus && feedStatus !== 'all') params.append('status', feedStatus);
    if (feedCurrentSearch.trim()) {
        params.append('search', feedCurrentSearch.trim());
    }

    try {
        const itemsRes = await fetch(`/api/feed/items?${params.toString()}`);
        if (!itemsRes.ok) throw new Error(`HTTP ${itemsRes.status}`);
        const data = await itemsRes.json();
        renderFeedTable(data.items || []);
        renderFeedPagination(data.page, data.limit, data.total);
    } catch (err) {
        console.error('Error loading feed items:', err);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center py-10 text-rose-400 font-semibold">Failed to load deliverables: ${escapeHtml(err.message)}</td></tr>`;
        }
    }
}
window.loadDailyFeed = loadDailyFeed;

function renderFeedSummary(summary) {
    if (!summary) return;

    // 1. Update Tab 2 Sidebar Badge
    const sideBadge = document.getElementById('badge-daily-feed-count');
    if (sideBadge) {
        sideBadge.innerText = `${(summary.total_items || 0).toLocaleString()} New`;
    }

    // 2. Update KPI / Source Legend Counts
    const sc = summary.source_counts || {};
    const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = (val || 0).toLocaleString(); };
    setEl('stat-feed-mail-count', sc.mail || 0);
    setEl('stat-feed-doc-count', sc.doc || 0);
    setEl('stat-feed-wf-count', sc.workflow || 0);
    setEl('stat-feed-process-count', sc.process || 0);

    // Highlight active source legend card if filtered
    ['mail', 'doc', 'workflow', 'process'].forEach(s => {
        const card = document.getElementById(`feed-legend-card-${s}`);
        if (card) {
            if (feedCurrentSource === s) {
                card.classList.add('ring-2', 'ring-amber-500', 'bg-slate-900');
            } else {
                card.classList.remove('ring-2', 'ring-amber-500', 'bg-slate-900');
            }
        }
    });

    // 3. Render Active File Types Chips
    renderFeedChips(summary.active_types || [], summary.total_items || 0);

    // 4. Populate Project Filter Dropdown
    const selProj = document.getElementById('feed-filter-project');
    if (selProj) {
        const currentVal = feedCurrentProject;
        selProj.innerHTML = `<option value="all">All Packages (${(summary.total_items || 0).toLocaleString()} Deliverables)</option>`;
        (summary.active_packages || []).forEach(pkg => {
            const opt = document.createElement('option');
            opt.value = pkg.project_id;
            opt.innerText = `${pkg.project_id} (${(pkg.count || 0).toLocaleString()})`;
            if (pkg.project_id === currentVal) opt.selected = true;
            selProj.appendChild(opt);
        });
    }
}

function renderFeedChips(types, totalAll) {
    const container = document.getElementById('feed-type-chips-container');
    if (!container) return;

    if (!types || types.length === 0) {
        container.innerHTML = `<span class="text-xs text-slate-500 italic py-2">No deliverables recorded for this timeframe.</span>`;
        return;
    }

    let html = '';
    const isAllSelected = (feedCurrentType === 'all');
    html += `
        <button onclick="filterFeedByType('all')" class="px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer ${isAllSelected ? 'bg-amber-600 text-white shadow-md shadow-amber-600/30 ring-1 ring-amber-400' : 'bg-slate-950 text-slate-300 hover:bg-slate-800 border border-slate-700/80'}">
            <span>All Types</span>
            <span class="px-1.5 py-0.2 rounded-full text-[10px] ${isAllSelected ? 'bg-amber-800/80 text-amber-100' : 'bg-slate-800 text-slate-400'} font-mono">${(totalAll || 0).toLocaleString()}</span>
        </button>
    `;

    types.forEach(t => {
        const isSelected = (feedCurrentType === t.type);
        let colorClasses = '';
        if (t.source === 'mail') {
            colorClasses = isSelected 
                ? 'bg-sky-600 text-white shadow-md shadow-sky-600/30 ring-1 ring-sky-300' 
                : 'bg-slate-950 text-sky-300 border border-sky-500/30 hover:bg-sky-950/50 hover:border-sky-400';
        } else if (t.source === 'doc') {
            colorClasses = isSelected 
                ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/30 ring-1 ring-emerald-300' 
                : 'bg-slate-950 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-950/50 hover:border-emerald-400';
        } else if (t.source === 'workflow') {
            colorClasses = isSelected 
                ? 'bg-purple-600 text-white shadow-md shadow-purple-600/30 ring-1 ring-purple-300' 
                : 'bg-slate-950 text-purple-300 border border-purple-500/30 hover:bg-purple-950/50 hover:border-purple-400';
        } else {
            colorClasses = isSelected 
                ? 'bg-amber-600 text-white shadow-md shadow-amber-600/30 ring-1 ring-amber-300' 
                : 'bg-slate-950 text-amber-300 border border-amber-500/30 hover:bg-amber-950/50 hover:border-amber-400';
        }

        html += `
            <button onclick="filterFeedByType('${escapeHtml(t.type)}')" class="px-2.5 py-1.2 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer ${colorClasses}">
                <span>${escapeHtml(t.label)}</span>
                <span class="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-900/80 font-mono font-bold">${(t.count || 0).toLocaleString()}</span>
            </button>
        `;
    });

    container.innerHTML = html;
}

function renderFeedTable(items) {
    const tbody = document.getElementById('feed-table-tbody');
    if (!tbody) return;

    if (!items || items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-12 text-slate-500 font-medium">No deliverables found matching the current filters.</td></tr>`;
        return;
    }

    let html = '';
    items.forEach(it => {
        // Exact Upload / Registered Date with Calendar Icon & relative tag badge
        const exactDate = it.item_date ? String(it.item_date).substring(0, 10) : '-';
        let relBadge = '';
        if (it.relative_tag === 'Today') {
            relBadge = `<span class="inline-flex items-center gap-1 px-1.5 py-0.2 rounded-full text-[9px] font-black bg-amber-500/20 text-amber-300 border border-amber-500/40"><span class="w-1 h-1 rounded-full bg-amber-400 animate-pulse"></span>Today</span>`;
        } else if (it.relative_tag === 'Yesterday') {
            relBadge = `<span class="inline-flex items-center gap-1 px-1.5 py-0.2 rounded-full text-[9px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">Yesterday</span>`;
        }
        
        const dateCellHtml = `
            <div class="flex items-center gap-2">
                <i data-lucide="calendar" class="w-3.5 h-3.5 text-amber-400/80 flex-shrink-0"></i>
                <span class="font-mono font-bold text-slate-100 text-xs">${escapeHtml(exactDate)}</span>
                ${relBadge}
            </div>
        `;

        // Source badge
        let srcBadge = '';
        if (it.source === 'mail') {
            srcBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/30">Mail (Mail)</span>`;
        } else if (it.source === 'doc') {
            srcBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">Doc (Doc)</span>`;
        } else if (it.source === 'workflow') {
            srcBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/30">WF (Workflow)</span>`;
        } else {
            srcBadge = `<span class="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30">BIC (Process)</span>`;
        }

        // Status badge
        let statusBadge = '';
        const st = (it.status || '').toLowerCase();
        if (st.includes('current') || st.includes('completed') || st.includes('registered') || st.includes('sent')) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">${escapeHtml(it.status || 'Active')}</span>`;
        } else if (st.includes('overdue') || st.includes('late')) {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-black bg-rose-500/20 text-rose-300 border border-rose-500/40">Overdue</span>`;
        } else {
            statusBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">${escapeHtml(it.status || 'Active')}</span>`;
        }

        const fullTypeLabel = `${it.item_type} ${it.source_label || ''}`;

        // Ensure feedUrl uses robust resolvers and avoids broken trackingid query
        let feedUrl = String(it.aconex_url || '');
        if (!feedUrl || feedUrl === '#') {
            if (it.source === 'mail') {
                feedUrl = `/api/aconex/mail?mail_no=${encodeURIComponent(it.item_id)}`;
            } else {
                feedUrl = `/api/aconex/doc?doc_no=${encodeURIComponent(it.item_id)}`;
            }
        }

        html += `
            <tr class="hover:bg-slate-800/40 transition group">
                <td class="py-3 px-4 whitespace-nowrap">${dateCellHtml}</td>
                <td class="py-3 px-3 whitespace-nowrap">${srcBadge}</td>
                <td class="py-3 px-4 font-semibold text-slate-200">${escapeHtml(fullTypeLabel)}</td>
                <td class="py-3 px-4 font-mono font-bold text-amber-400 whitespace-nowrap">
                    <a href="${escapeHtml(feedUrl || '#')}" target="_blank" class="hover:underline flex items-center gap-1" title="Open in Aconex">
                        <span>${escapeHtml(it.item_id)}</span>
                        <i data-lucide="external-link" class="w-3 h-3 opacity-0 group-hover:opacity-100 transition"></i>
                    </a>
                </td>
                <td class="py-3 px-4 text-white font-medium max-w-[360px] truncate" title="${escapeHtml(it.title || '')}">
                    ${escapeHtml(it.title || '-')}
                </td>
                <td class="py-3 px-4 whitespace-nowrap">
                    <span class="px-2 py-0.5 rounded-md text-[11px] font-mono font-semibold bg-slate-950 text-slate-300 border border-slate-800">
                        ${escapeHtml(it.project_id || 'General')}
                    </span>
                </td>
                <td class="py-3 px-4 text-slate-300 text-[11px]">
                    <div class="font-semibold text-white truncate max-w-[180px]">${escapeHtml(it.organization || '-')}</div>
                    ${it.author ? `<div class="text-[10px] text-slate-400 truncate max-w-[180px]">${escapeHtml(it.author)}</div>` : ''}
                </td>
                <td class="py-3 px-3 whitespace-nowrap">${statusBadge}</td>
                <td class="py-3 px-4 text-right whitespace-nowrap">
                    <a href="${escapeHtml(feedUrl || '#')}" target="_blank" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 text-[11px] font-semibold inline-flex items-center gap-1 transition">
                        <span>View</span>
                        <i data-lucide="external-link" class="w-3 h-3"></i>
                    </a>
                </td>
            </tr>
        `;
    });

    tbody.innerHTML = html;
    if (window.AntigravityTableEngine) {
        AntigravityTableEngine.initTable('feed-table');
        AntigravityTableEngine.applyColumnVisibility('feed-table');
    }
    if (window.lucide) lucide.createIcons();
}

function renderFeedPagination(page, limit, total) {
    const rangeEl = document.getElementById('feed-showing-range');
    const indicatorEl = document.getElementById('feed-page-indicator');
    const btnPrev = document.getElementById('feed-btn-prev');
    const btnNext = document.getElementById('feed-btn-next');

    const rangeElTop = document.getElementById('feed-showing-range-top');
    const indicatorElTop = document.getElementById('feed-page-indicator-top');
    const btnPrevTop = document.getElementById('feed-btn-prev-top');
    const btnNextTop = document.getElementById('feed-btn-next-top');

    const totalPages = Math.ceil(total / limit) || 1;
    const start = total === 0 ? 0 : (page - 1) * limit + 1;
    const end = Math.min(page * limit, total);
    const rangeText = `Showing ${start}-${end} of ${(total || 0).toLocaleString()} deliverables`;
    const pageText = `Page ${page} of ${totalPages}`;

    if (rangeEl) rangeEl.innerText = rangeText;
    if (rangeElTop) rangeElTop.innerText = rangeText;

    if (indicatorEl) indicatorEl.innerText = pageText;
    if (indicatorElTop) indicatorElTop.innerText = pageText;

    const isPrevDisabled = (page <= 1);
    const isNextDisabled = (page >= totalPages);

    if (btnPrev) btnPrev.disabled = isPrevDisabled;
    if (btnPrevTop) btnPrevTop.disabled = isPrevDisabled;

    if (btnNext) btnNext.disabled = isNextDisabled;
    if (btnNextTop) btnNextTop.disabled = isNextDisabled;
}

function changeFeedPage(delta) {
    const newPage = feedCurrentPage + delta;
    if (newPage >= 1) {
        loadDailyFeed(newPage);
    }
}
window.changeFeedPage = changeFeedPage;

function changeFeedLimit(newLimit) {
    feedLimit = parseInt(newLimit, 10) || 50;
    loadDailyFeed(1);
}
window.changeFeedLimit = changeFeedLimit;

function changeFeedTimeframe(timeframe) {
    if (feedCurrentTimeframe === timeframe) return;
    feedCurrentTimeframe = timeframe;

    const btnToday = document.getElementById('feed-timeframe-btn-today');
    const btn7d = document.getElementById('feed-timeframe-btn-7d');
    const btn30d = document.getElementById('feed-timeframe-btn-30d');

    const activeCls = ['bg-amber-600', 'text-white', 'shadow-sm'];
    const inactiveCls = ['text-slate-400', 'hover:text-white', 'hover:bg-slate-800'];

    [btnToday, btn7d, btn30d].forEach(b => {
        if (b) {
            b.classList.remove(...activeCls);
            b.classList.add(...inactiveCls);
        }
    });

    if (timeframe === 'today_yesterday' && btnToday) {
        btnToday.classList.remove(...inactiveCls);
        btnToday.classList.add(...activeCls);
    } else if (timeframe === '7d' && btn7d) {
        btn7d.classList.remove(...inactiveCls);
        btn7d.classList.add(...activeCls);
    } else if (timeframe === '30d' && btn30d) {
        btn30d.classList.remove(...inactiveCls);
        btn30d.classList.add(...activeCls);
    }

    feedCurrentType = 'all';
    feedSummaryData = null; // force reload summary
    loadDailyFeed(1);
}
window.changeFeedTimeframe = changeFeedTimeframe;

function filterFeedBySource(source) {
    if (feedCurrentSource === source) {
        feedCurrentSource = 'all';
    } else {
        feedCurrentSource = source;
    }
    const sel = document.getElementById('feed-filter-source');
    if (sel) sel.value = feedCurrentSource;
    loadDailyFeed(1);
}
window.filterFeedBySource = filterFeedBySource;

function filterFeedBySourceDropdown(source) {
    feedCurrentSource = source;
    loadDailyFeed(1);
}
window.filterFeedBySourceDropdown = filterFeedBySourceDropdown;

function filterFeedByType(typeName) {
    feedCurrentType = typeName;
    loadDailyFeed(1);
}
window.filterFeedByType = filterFeedByType;

function clearFeedTypeFilter() {
    feedCurrentType = 'all';
    loadDailyFeed(1);
}
window.clearFeedTypeFilter = clearFeedTypeFilter;

function filterFeedByProject(project) {
    feedCurrentProject = project;
    loadDailyFeed(1);
}
window.filterFeedByProject = filterFeedByProject;

function debounceFeedSearch() {
    clearTimeout(feedSearchTimeout);
    feedSearchTimeout = setTimeout(() => {
        const inp = document.getElementById('feed-search-input');
        feedCurrentSearch = inp ? inp.value : '';
        loadDailyFeed(1);
    }, 300);
}
window.debounceFeedSearch = debounceFeedSearch;

function resetAllFeedFilters() {
    feedCurrentSource = 'all';
    feedCurrentType = 'all';
    feedCurrentProject = 'all';
    feedCurrentSearch = '';

    const selProj = document.getElementById('feed-filter-project');
    const selSrc = document.getElementById('feed-filter-source');
    const inpSearch = document.getElementById('feed-search-input');

    if (selProj) selProj.value = 'all';
    if (selSrc) selSrc.value = 'all';
    if (inpSearch) inpSearch.value = '';

    loadDailyFeed(1);
}
window.resetAllFeedFilters = resetAllFeedFilters;

function exportDailyFeedExcel() {
    const params = new URLSearchParams({
        timeframe: feedCurrentTimeframe,
        source: feedCurrentSource,
        item_type: feedCurrentType,
        project: feedCurrentProject
    });
    if (feedCurrentSearch.trim()) {
        params.append('search', feedCurrentSearch.trim());
    }
    window.location.href = `/api/feed/export?${params.toString()}`;
}
window.exportDailyFeedExcel = exportDailyFeedExcel;



// ============================================================================
// CUSTOM FOLDER LOG SYNCHRONIZATION & DIRECTIONAL LETTERS LOG EXPORT
// ============================================================================

function exportLettersLogDirection(direction) {
    const projectId = currentProjectContext || 'DP02';
    const searchEl = document.getElementById('proj-letters-search');
    const typeEl = document.getElementById('proj-letters-type');
    const statusEl = document.getElementById('proj-letters-status');

    const params = new URLSearchParams({
        category: 'letters',
        direction: direction || 'all'
    });
    if (searchEl && searchEl.value.trim()) params.append('search', searchEl.value.trim());
    if (typeEl && typeEl.value) params.append('mail_type', typeEl.value);
    if (statusEl && statusEl.value) params.append('status', statusEl.value);

    const url = `/api/projects/${encodeURIComponent(projectId)}/export_filtered?${params.toString()}`;
    window.location.href = url;
}
window.exportLettersLogDirection = exportLettersLogDirection;

function openLogFolderSyncModal(mode = 'all') {
    const modal = document.getElementById('modal-log-folder-sync');
    if (!modal) return;
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    const inputEl = document.getElementById('input-custom-sync-folder');
    if (inputEl && !inputEl.value.trim()) {
        inputEl.value = mode === 'letters'
            ? 'C:\\Users\\bimst\\Downloads\\ACONEX\\Logs\\OneDrive_2_10-12-2026'
            : 'C:\\Users\\bimst\\Downloads\\ACONEX\\Logs';
    }
    const statusBox = document.getElementById('custom-sync-status-box');
    if (statusBox) {
        statusBox.classList.add('hidden');
        statusBox.innerHTML = '';
    }
    if (window.lucide) window.lucide.createIcons();
}
window.openLogFolderSyncModal = openLogFolderSyncModal;

function openUploadRfiModal() {
    openLogFolderSyncModal('rfis');
}
window.openUploadRfiModal = openUploadRfiModal;

function closeLogFolderSyncModal() {
    const modal = document.getElementById('modal-log-folder-sync');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}
window.closeLogFolderSyncModal = closeLogFolderSyncModal;

function renderSyncStatusBox(html, isError = false) {
    const statusBox = document.getElementById('custom-sync-status-box');
    if (!statusBox) return;
    statusBox.classList.remove('hidden');
    statusBox.className = `p-3.5 rounded-xl border text-xs font-mono space-y-1.5 max-h-60 overflow-y-auto ${
        isError
            ? 'bg-rose-950/60 border-rose-500/40 text-rose-200'
            : 'bg-slate-950/90 border-emerald-500/40 text-slate-200'
    }`;
    statusBox.innerHTML = html;
}

async function executeCustomFolderSync(syncType = 'all') {
    const inputEl = document.getElementById('input-custom-sync-folder');
    const folderPath = inputEl && inputEl.value.trim()
        ? inputEl.value.trim()
        : 'C:\\Users\\bimst\\Downloads\\ACONEX\\Logs';

    renderSyncStatusBox(`<div class="flex items-center gap-2 text-sky-400 font-bold"><span class="animate-spin inline-block w-3.5 h-3.5 border-2 border-sky-400 border-t-transparent rounded-full"></span> Synchronizing Excel Logs in: ${folderPath} ...</div>`);

    try {
        let endpoint = '/api/logs/sync_all';
        if (syncType === 'rfis') endpoint = '/api/rfi_explore/sync_all';
        else if (syncType === 'letters') endpoint = '/api/letters_explore/sync_all';

        const res = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_path: folderPath })
        });
        const data = await res.json();
        if (!res.ok || data.error) {
            renderSyncStatusBox(`<div class="text-rose-400 font-bold">Error: ${data.error || 'Failed to synchronize folder'}</div>`, true);
            return;
        }

        let lines = [];
        lines.push(`<div class="text-emerald-400 font-bold text-sm mb-1">✔ Synchronization Completed Successfully!</div>`);
        lines.push(`<div class="text-slate-400">Target Folder: <span class="text-sky-300">${data.folder || folderPath}</span></div>`);

        const rfiSyncObj = data.rfi_sync || (syncType === 'rfis' ? data : null);
        const letSyncObj = data.letters_sync || (syncType === 'letters' ? data : null);
        const rfiDetails = rfiSyncObj ? (rfiSyncObj.files || rfiSyncObj.details || []) : [];
        const letDetails = letSyncObj ? (letSyncObj.files || letSyncObj.details || []) : [];

        if (rfiDetails.length > 0) {
            lines.push(`<div class="mt-2 font-bold text-emerald-300 border-b border-slate-800 pb-1">RFI Logs Synced (${rfiDetails.length} files):</div>`);
            rfiDetails.forEach(d => {
                const fname = d.filename || d.file || 'Log';
                const pkg = d.package || d.project_id || '';
                const added = d.appended_new ?? d.added ?? 0;
                const updated = d.updated_existing ?? d.updated ?? 0;
                if (d.status === 'success') {
                    lines.push(`<div class="text-slate-300">• <b>${fname}</b> ${pkg ? '(' + pkg + ')' : ''}: <span class="text-emerald-400">+${added} new</span>, <span class="text-sky-400">${updated} updated</span></div>`);
                } else {
                    lines.push(`<div class="text-amber-400">• <b>${fname}</b>: ${d.message || d.reason || d.status}</div>`);
                }
            });
        }

        if (letDetails.length > 0) {
            lines.push(`<div class="mt-2 font-bold text-indigo-300 border-b border-slate-800 pb-1">Letters Logs Synced (${letDetails.length} files):</div>`);
            letDetails.forEach(d => {
                const fname = d.filename || d.file || 'Letters Log';
                const dirLabel = d.is_incoming === true ? 'From Contractor' : (d.is_incoming === false ? 'To Contractor' : (d.direction || 'All'));
                const added = d.appended_new_total ?? d.added ?? 0;
                const updated = d.updated_existing_total ?? d.updated ?? 0;
                const links = d.hyperlinks_added_total ?? 0;
                if (d.status === 'success') {
                    lines.push(`<div class="text-slate-300">• <b>${fname}</b> [${dirLabel}]: <span class="text-emerald-400">+${added} new</span>, <span class="text-sky-400">${updated} responses updated</span>, <span class="text-indigo-300">${links} hyperlinks active</span></div>`);
                } else {
                    lines.push(`<div class="text-amber-400">• <b>${fname}</b>: ${d.message || d.reason || d.status}</div>`);
                }
            });
        }

        if (rfiDetails.length === 0 && letDetails.length === 0) {
            lines.push(`<div class="text-amber-300 mt-1">No matching Excel (.xlsx) files found in the specified folder. You can click "Generate & Sync Both Logs in Folder" below to create fresh From/To Contractor logs directly in that folder.</div>`);
        }

        renderSyncStatusBox(lines.join(''));
    } catch (err) {
        renderSyncStatusBox(`<div class="text-rose-400 font-bold">Network/Server Error: ${err.message}</div>`, true);
    }
}
window.executeCustomFolderSync = executeCustomFolderSync;

async function executeGenerateDirectionLettersInFolder() {
    const inputEl = document.getElementById('input-custom-sync-folder');
    const folderPath = inputEl && inputEl.value.trim()
        ? inputEl.value.trim()
        : 'C:\\Users\\bimst\\Downloads\\ACONEX\\Logs';
    const projectId = currentProjectContext || null;

    renderSyncStatusBox(`<div class="flex items-center gap-2 text-indigo-400 font-bold"><span class="animate-spin inline-block w-3.5 h-3.5 border-2 border-indigo-400 border-t-transparent rounded-full"></span> Generating & Syncing Directional Letters Logs (From Contractor & To Contractor) in: ${folderPath} ...</div>`);

    try {
        const res = await fetch('/api/logs/generate_direction_letters', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_path: folderPath, project_id: projectId })
        });
        const data = await res.json();
        if (!res.ok || data.error) {
            renderSyncStatusBox(`<div class="text-rose-400 font-bold">Error: ${data.error || 'Failed to generate directional logs'}</div>`, true);
            return;
        }

        let lines = [];
        const genFiles = data.generated_files || data.details || [];
        lines.push(`<div class="text-emerald-400 font-bold text-sm mb-1">✔ Directional Letters Logs Created & Synchronized (${genFiles.length} directional logs + ${data.existing_logs_synced || 0} workbook logs)!</div>`);
        lines.push(`<div class="text-slate-400">Saved & Synced in Folder: <span class="text-sky-300">${data.folder_path || data.folder || folderPath}</span></div>`);
        genFiles.forEach(d => {
            const fname = d.filename || d.file;
            const isFrom = (d.direction || '').toLowerCase().includes('from') || d.direction === 'inbound';
            lines.push(`<div class="text-slate-300 mt-1">• <b>${fname}</b> [${isFrom ? 'From Contractor (Inbound)' : 'To Contractor (Outbound)'}]: <span class="text-emerald-400">Saved & Synced in-place</span></div>`);
        });
        renderSyncStatusBox(lines.join(''));
    } catch (err) {
        renderSyncStatusBox(`<div class="text-rose-400 font-bold">Error: ${err.message}</div>`, true);
    }
}
window.executeGenerateDirectionLettersInFolder = executeGenerateDirectionLettersInFolder;

async function uploadAndSyncSingleExcelLog() {
    const fileInput = document.getElementById('input-single-excel-sync');
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        renderSyncStatusBox(`<div class="text-amber-400 font-bold">Please choose an Excel (.xlsx) file first.</div>`, true);
        return;
    }
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    renderSyncStatusBox(`<div class="flex items-center gap-2 text-amber-400 font-bold"><span class="animate-spin inline-block w-3.5 h-3.5 border-2 border-amber-400 border-t-transparent rounded-full"></span> Uploading & Synchronizing ${file.name} ...</div>`);

    try {
        const res = await fetch('/api/rfi_explore/upload_sync', {
            method: 'POST',
            body: formData
        });
        if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            renderSyncStatusBox(`<div class="text-rose-400 font-bold">Upload Sync Failed: ${errData.error || res.statusText}</div>`, true);
            return;
        }
        const blob = await res.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `Synced_${file.name}`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(downloadUrl);

        renderSyncStatusBox(`<div class="text-emerald-400 font-bold">✔ File "${file.name}" synchronized with latest Aconex database records and downloaded as "Synced_${file.name}"!</div>`);
    } catch (err) {
        renderSyncStatusBox(`<div class="text-rose-400 font-bold">Error: ${err.message}</div>`, true);
    }
}
window.uploadAndSyncSingleExcelLog = uploadAndSyncSingleExcelLog;


// =============================================================================
// USER DATA REFRESH & OUT-OF-DATE REPORT CONTROLS
// =============================================================================
async function openRefreshRequestModal(prefillPackage = '') {
    const modal = document.getElementById('modal-refresh-request');
    if (!modal) return;

    // Reset views
    document.getElementById('rr-form-container')?.classList.remove('hidden');
    const resultCont = document.getElementById('rr-result-container');
    if (resultCont) {
        resultCont.classList.add('hidden');
        resultCont.innerHTML = '';
    }

    // Populate packages dropdown (Fetch from API if not yet in memory)
    const pkgSelect = document.getElementById('rr-package');
    if (pkgSelect) {
        let projs = (typeof allProjects !== 'undefined' && allProjects && allProjects.length > 0) ? allProjects : (window.allProjects || []);
        if (!projs || projs.length === 0) {
            try {
                const res = await fetch('/api/projects');
                if (res.ok) {
                    const data = await res.json();
                    projs = data.data || [];
                    allProjects = projs;
                    window.allProjects = projs;
                }
            } catch (err) {
                console.error('Could not fetch projects for dropdown:', err);
            }
        }

                const fallbackPackages = [
            { project_id: 'DP01', project_title: 'DP01 - Area 1 Basement & Superstructure' },
            { project_id: 'DP02', project_title: 'DP02 - Area 2 Basement & Superstructure' },
            { project_id: 'DP03-East', project_title: 'DP03 East - Buildings & Infrastructure' },
            { project_id: 'DP03-West', project_title: 'DP03 West - Buildings & Infrastructure' },
            { project_id: 'DP04', project_title: 'DP04 Buildings & Infrastructure' },
            { project_id: 'DP05', project_title: 'DP05 Buildings & Infrastructure' },
            { project_id: 'DP06', project_title: 'DP06 Buildings & Infrastructure' },
            { project_id: 'DP07', project_title: 'DP07 Buildings & Infrastructure' },
            { project_id: 'DP08 - South Golf', project_title: 'DP08 - South Golf' },
            { project_id: 'Grand Canal', project_title: 'Grand Canal Infrastructure' },
            { project_id: 'West Canal', project_title: 'West Canal Infrastructure' },
            { project_id: 'Infra', project_title: 'Primary Infrastructure & Utility (Package A East)' },
            { project_id: 'MMS', project_title: 'MMS / Substation 220kV' },
            { project_id: 'RO Plant', project_title: 'Sea Water RO Desalination Plant' },
            { project_id: 'STP', project_title: 'Sewage Treatment Plant' },
            { project_id: 'Airport', project_title: 'Ras El Hekma Airport Early Works' },
            { project_id: 'Ring Road', project_title: 'Ring Road Infrastructure' },
            { project_id: 'General Grading', project_title: 'Bulk Earthworks & Grading' },
            { project_id: 'Aedas Design Packages', project_title: 'Aedas Design Packages' }
        ];

        const listToRender = (projs && projs.length > 0) ? projs : fallbackPackages;
        let optionsHtml = '<option value="General Platform / All Packages">General Platform / All Packages</option>';
        listToRender.forEach(p => {
            const pid = p.project_id || '';
            const title = p.project_title || p.project_name || pid;
            const isSel = (prefillPackage && (prefillPackage === pid || prefillPackage === title)) ? 'selected' : '';
            optionsHtml += `<option value="${escapeHtml(pid)}" ${isSel}>[${escapeHtml(pid)}] ${escapeHtml(title)}</option>`;
        });
        pkgSelect.innerHTML = optionsHtml;
    }

    // Pre-fill user info from localStorage
    const savedName = localStorage.getItem('rr_requester_name') || '';
    const savedEmail = localStorage.getItem('rr_requester_email') || '';
    const nameInput = document.getElementById('rr-name');
    const emailInput = document.getElementById('rr-email');
    if (nameInput && savedName) nameInput.value = savedName;
    if (emailInput && savedEmail) emailInput.value = savedEmail;

    // Fetch live business hours status
    try {
        const res = await fetch('/api/refresh-requests/business-hours');
        if (res.ok) {
            const bh = await res.json();
            const badge = document.getElementById('rr-bh-badge');
            const timeEl = document.getElementById('rr-bh-time');
            const slaEl = document.getElementById('rr-bh-sla');
            if (badge) {
                if (bh.is_in_hours) {
                    badge.className = 'px-2.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5';
                    badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>Within Business Hours';
                } else {
                    badge.className = 'px-2.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1.5';
                    badge.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>After-Hours / Weekend';
                }
            }
            if (timeEl) timeEl.innerText = bh.cairo_time_str || '';
            if (slaEl) slaEl.innerText = bh.sla_text || '';
        }
    } catch (e) {
        console.warn('Could not fetch business hours:', e);
    }

    modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
}
window.openRefreshRequestModal = openRefreshRequestModal;

function closeRefreshRequestModal() {
    const modal = document.getElementById('modal-refresh-request');
    if (modal) modal.classList.add('hidden');
}
window.closeRefreshRequestModal = closeRefreshRequestModal;

async function submitRefreshRequest(e) {
    e.preventDefault();
    const btn = document.getElementById('rr-submit-btn');
    const originalText = btn ? btn.innerHTML : '';
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Validating & Submitting...</span>';
        if (window.lucide) lucide.createIcons();
    }

    const payload = {
        requester_name: document.getElementById('rr-name')?.value.trim() || '',
        requester_email: document.getElementById('rr-email')?.value.trim() || '',
        package_id: document.getElementById('rr-package')?.value || 'General',
        category: document.getElementById('rr-category')?.value || 'General',
        reference_no: document.getElementById('rr-ref')?.value.trim() || '',
        user_notes: document.getElementById('rr-notes')?.value.trim() || ''
    };

    // Save requester identity for convenience
    if (payload.requester_name) localStorage.setItem('rr_requester_name', payload.requester_name);
    if (payload.requester_email) localStorage.setItem('rr_requester_email', payload.requester_email);

    try {
        const res = await fetch('/api/refresh-requests/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Submission failed');
        }

        const data = await res.json();
        const ticket = data.ticket || {};
        const findings = ticket.validation_findings || {};

        // Switch to result container
        document.getElementById('rr-form-container')?.classList.add('hidden');
        const resultCont = document.getElementById('rr-result-container');
        if (resultCont) {
            resultCont.classList.remove('hidden');

            const isHours = ticket.is_in_hours;
            const badgeClass = isHours ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' : 'bg-amber-500/15 text-amber-300 border-amber-500/30';
            const badgeText = isHours ? 'Processed Live (Within Business Hours)' : 'Queued for Next Business Day 08:00 AM';

            let refDetailsHtml = '';
            if (findings.ref_item_found && findings.ref_item_details) {
                const d = findings.ref_item_details;
                refDetailsHtml = `
                    <div class="p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 space-y-1">
                        <div class="text-[10px] font-bold uppercase tracking-wider text-sky-400">Record Found in Aconex Analytical Warehouse:</div>
                        <div><strong>Identifier:</strong> <span class="font-mono text-white">${escapeHtml(d.mail_number || d.doc_number || '')}</span></div>
                        <div><strong>Subject/Title:</strong> ${escapeHtml(d.subject || d.title || '')}</div>
                        <div><strong>Date:</strong> ${escapeHtml(d.mail_date || d.date_modified || '')} | <strong>Status:</strong> ${escapeHtml(d.status || 'N/A')}</div>
                    </div>
                `;
            }

            resultCont.innerHTML = `
                <div class="text-center space-y-2 pb-2">
                    <div class="w-12 h-12 rounded-2xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/10">
                        <i data-lucide="check-circle-2" class="w-6 h-6"></i>
                    </div>
                    <h3 class="text-base font-extrabold text-white">Refresh Request Logged & Validated</h3>
                    <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono font-bold bg-slate-950 border border-slate-800 text-sky-400">
                        <span>Ticket ID:</span>
                        <span class="text-white">${escapeHtml(ticket.ticket_id || '')}</span>
                    </div>
                </div>

                <div class="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2 text-xs">
                    <div class="flex items-center justify-between">
                        <span class="text-slate-400">Queue & SLA Status:</span>
                        <span class="px-2 py-0.5 rounded text-[11px] font-bold border ${badgeClass}">${badgeText}</span>
                    </div>
                    <div class="flex items-center justify-between">
                        <span class="text-slate-400">Analytical Database Cutoff:</span>
                        <span class="font-mono text-emerald-400 font-bold">${escapeHtml(findings.current_db_cutoff || 'Current')}</span>
                    </div>
                    <div class="flex items-center justify-between">
                        <span class="text-slate-400">Assigned Reviewer:</span>
                        <span class="text-sky-300 font-semibold">Mohamed Meneaem (Hill International)</span>
                    </div>
                </div>

                <!-- Automated Technical Validation Assessment -->
                <div class="p-4 rounded-xl bg-sky-950/30 border border-sky-500/30 space-y-2 text-xs">
                    <div class="flex items-center gap-1.5 font-bold text-sky-300">
                        <i data-lucide="cpu" class="w-4 h-4 text-sky-400"></i>
                        <span>Automated Engine Assessment: ${escapeHtml(findings.verdict_title || 'Validated')}</span>
                    </div>
                    <p class="text-slate-300 leading-relaxed">${escapeHtml(findings.recommended_action || '')}</p>
                    ${refDetailsHtml}
                </div>

                <div class="p-3 rounded-xl bg-slate-950/90 border border-slate-800/80 text-[11px] text-slate-400 flex items-start gap-2">
                    <i data-lucide="mail-check" class="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5"></i>
                    <div>
                        An executive notification containing your request, current warehouse state, and automated assessment has been dispatched to 
                        <strong class="text-slate-200">MohamedMeneaem@hillintl.com</strong>.
                    </div>
                </div>

                <div class="pt-2 flex items-center justify-end gap-3">
                    <button type="button" onclick="closeRefreshRequestModal()" class="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold transition">
                        Done & Close
                    </button>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
        }

    } catch (err) {
        alert('Error submitting request: ' + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
            if (window.lucide) lucide.createIcons();
        }
    }
}
window.submitRefreshRequest = submitRefreshRequest;
