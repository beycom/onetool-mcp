// Solution Export Scripts

const panzoomInstances = {};

function initDiagramPanZoom() {
    // Panzoom loads from a CDN; when the bundle is opened offline the
    // diagrams stay readable, just without zoom/pan.
    if (typeof Panzoom === 'undefined') return;

    const containers = document.querySelectorAll('.diagram-container');

    containers.forEach((container, i) => {
        const svg = container.querySelector('svg');
        if (!svg) return;

        const instance = Panzoom(svg, {
            maxScale: 10,
            minScale: 0.1,
            contain: 'outside',
            cursor: 'grab'
        });

        const id = 'pz-' + i;
        container.dataset.panzoomId = id;
        panzoomInstances[id] = instance;

        container.addEventListener('wheel', function(e) {
            e.preventDefault();
            instance.zoomWithWheel(e);
        }, { passive: false });
    });

    initDiagramLinkGuard(containers);
}

// D2 nodes render as SVG <a> links (see D4 in openspec/changes/arch-render-nav).
// Panzoom drags end with a mouseup/click on whatever is under the pointer, which
// would otherwise trigger navigation on every drag that happens to end over a
// linked node. Track pointerdown position per container and, in the click
// capture phase, cancel navigation only when the pointer moved more than the
// drag threshold before the click fired; clean (non-drag) clicks still navigate.
function initDiagramLinkGuard(containers) {
    const DRAG_THRESHOLD_PX = 5;

    containers.forEach((container) => {
        let pointerDownX = 0;
        let pointerDownY = 0;

        container.addEventListener('pointerdown', function(e) {
            pointerDownX = e.clientX;
            pointerDownY = e.clientY;
        }, true);

        container.addEventListener('click', function(e) {
            const link = e.target.closest && e.target.closest('a');
            if (!link) return;

            const dx = e.clientX - pointerDownX;
            const dy = e.clientY - pointerDownY;
            const moved = Math.sqrt(dx * dx + dy * dy);
            if (moved > DRAG_THRESHOLD_PX) {
                e.preventDefault();
                e.stopPropagation();
            }
        }, true);
    });
}

// Resolve the .diagram-container that belongs to the toolbar button's panel.
function getDiagramContainer(btn) {
    const panel = btn.closest('.diagram-panel');
    return panel ? panel.querySelector('.diagram-container') : null;
}

// Resolve the Panzoom instance for the toolbar button's diagram, if any.
function getPanzoom(btn) {
    const container = getDiagramContainer(btn);
    return container ? panzoomInstances[container.dataset.panzoomId] : null;
}

function zoomIn(btn) {
    const pz = getPanzoom(btn);
    if (pz) pz.zoomIn();
}

function zoomOut(btn) {
    const pz = getPanzoom(btn);
    if (pz) pz.zoomOut();
}

function resetZoom(btn) {
    const pz = getPanzoom(btn);
    if (pz) pz.reset();
}

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function printDiagram(btn) {
    const container = getDiagramContainer(btn);
    if (!container) return;
    const svg = container.querySelector('svg');
    if (!svg) return;

    const svgClone = svg.cloneNode(true);
    svgClone.style.transform = '';
    svgClone.style.width = '100%';
    svgClone.style.height = 'auto';

    const tabContent = btn.closest('.diagram-tab-content');
    const tabId = tabContent ? tabContent.id : '';
    const activeTab = document.querySelector(`input[data-tab-target="${tabId}"]`);
    // The aria-label carries workbook-supplied names; escape before writing
    // it into the popup markup.
    const title = escapeHtml(activeTab ? activeTab.getAttribute('aria-label') + ' Diagram' : 'Diagram');

    const printWindow = window.open('', '_blank', 'width=800,height=600');
    if (!printWindow) return;

    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>${title}</title>
            <style>
                @media print {
                    @page { margin: 0.5in; }
                }
                body {
                    margin: 0;
                    padding: 20px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                }
                h1 {
                    font-family: system-ui, sans-serif;
                    font-size: 18px;
                    margin-bottom: 20px;
                }
                svg {
                    max-width: 100%;
                    height: auto;
                }
            </style>
        </head>
        <body>
            <h1>${title}</h1>
            ${svgClone.outerHTML}
        </body>
        </html>
    `);
    printWindow.document.close();

    printWindow.onload = function() {
        printWindow.print();
        printWindow.onafterprint = function() {
            printWindow.close();
        };
    };
}

function initCollapse() {
    document.querySelectorAll('[data-collapse]').forEach(header => {
        header.addEventListener('click', function() {
            const targetId = this.dataset.collapse;
            const target = document.getElementById(targetId);
            const icon = this.querySelector('.collapse-icon');
            if (target) {
                const isCollapsed = target.dataset.collapsed === 'true';
                if (isCollapsed) {
                    target.style.display = '';
                    target.dataset.collapsed = 'false';
                    if (icon) icon.innerHTML = '&#9660;';
                } else {
                    target.style.display = 'none';
                    target.dataset.collapsed = 'true';
                    if (icon) icon.innerHTML = '&#9654;';
                }
            }
        });
    });
}

function initDiagramTabs() {
    const tabs = document.querySelectorAll("input[data-tab-group][data-tab-target]");
    const tabGroups = new Set();

    tabs.forEach(tab => {
        const groupName = tab.dataset.tabGroup;
        if (!groupName) return;
        tabGroups.add(groupName);

        tab.addEventListener("change", function() {
            if (!this.checked) return;
            const targetId = this.dataset.tabTarget;
            const contents = document.querySelectorAll(`.diagram-tab-content[data-tab-group="${groupName}"]`);
            contents.forEach(content => {
                content.style.display = "none";
            });
            const target = document.getElementById(targetId);
            if (target && target.dataset.tabGroup === groupName) {
                target.style.display = "";
            }
        });
    });

    tabGroups.forEach(groupName => {
        const contents = document.querySelectorAll(`.diagram-tab-content[data-tab-group="${groupName}"]`);
        contents.forEach(content => {
            content.style.display = "none";
        });

        const activeTab = document.querySelector(`input[data-tab-group="${groupName}"]:checked`) ||
            document.querySelector(`input[data-tab-group="${groupName}"]`);
        if (!activeTab) return;

        const target = document.getElementById(activeTab.dataset.tabTarget);
        if (target && target.dataset.tabGroup === groupName) {
            target.style.display = "";
        }
    });
}

const gridInstances = {};

function initAgGridTable(containerId, data, columns, options = {}) {
    // AG Grid loads from a CDN; when the bundle is opened offline the page
    // stays readable, just without interactive tables.
    if (typeof agGrid === 'undefined') return null;

    const container = document.getElementById(containerId);
    if (!container) return null;

    const columnDefs = columns.map(col => ({
        field: col.field,
        headerName: col.title,
        flex: col.flex || 1,
        minWidth: col.minWidth || 80,
        maxWidth: col.maxWidth || undefined,
        resizable: true,
        sortable: true,
        filter: true,
        wrapText: true,
        autoHeight: true,
        cellRenderer: col.formatter === 'html' ? (params) => params.value || '' : undefined,
        sort: col.sort || undefined,
    }));

    const defaultOptions = {
        columnDefs: columnDefs,
        rowData: data,
        defaultColDef: {
            minWidth: 80,
            resizable: true,
        },
        pagination: true,
        paginationPageSize: 20,
        paginationPageSizeSelector: [10, 20, 50, 100],
        domLayout: 'autoHeight',
        suppressHorizontalScroll: false,
    };

    const gridOptions = Object.assign({}, defaultOptions, options);

    const gridApi = agGrid.createGrid(container, gridOptions);
    gridInstances[containerId] = gridApi;

    return gridApi;
}

// Wires each `[data-quick-filter]` search input (index entity tables, D7) to
// its AG Grid instance's quickFilterText, filtering rows client-side as the
// user types.
function initTableQuickFilters() {
    document.querySelectorAll('[data-quick-filter]').forEach(function(input) {
        const containerId = input.dataset.quickFilter;
        input.addEventListener('input', function() {
            const gridApi = gridInstances[containerId];
            if (!gridApi) return;
            gridApi.setGridOption('quickFilterText', input.value);
        });
    });
}

function downloadTableXLSX(containerId, filename) {
    // SheetJS loads from a CDN; no-op when the bundle is opened offline.
    if (typeof XLSX === 'undefined') return;

    const gridApi = gridInstances[containerId];
    if (!gridApi) return;

    const rowData = [];
    gridApi.forEachNode(node => rowData.push(node.data));

    const ws = XLSX.utils.json_to_sheet(rowData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Data');
    XLSX.writeFile(wb, filename);
}
