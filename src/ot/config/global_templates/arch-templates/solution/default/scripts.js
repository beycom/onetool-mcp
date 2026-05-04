// Solution Export Scripts

const panzoomInstances = {};

function initDiagramPanZoom() {
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
}

function zoomIn(btn) {
    const panel = btn.closest('.diagram-panel');
    if (!panel) return;
    const container = panel.querySelector('.diagram-container');
    if (!container) return;
    const pz = panzoomInstances[container.dataset.panzoomId];
    if (pz) pz.zoomIn();
}

function zoomOut(btn) {
    const panel = btn.closest('.diagram-panel');
    if (!panel) return;
    const container = panel.querySelector('.diagram-container');
    if (!container) return;
    const pz = panzoomInstances[container.dataset.panzoomId];
    if (pz) pz.zoomOut();
}

function resetZoom(btn) {
    const panel = btn.closest('.diagram-panel');
    if (!panel) return;
    const container = panel.querySelector('.diagram-container');
    if (!container) return;
    const pz = panzoomInstances[container.dataset.panzoomId];
    if (pz) pz.reset();
}

function printDiagram(btn) {
    const panel = btn.closest('.diagram-panel');
    if (!panel) return;
    const container = panel.querySelector('.diagram-container');
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
    const title = activeTab ? activeTab.getAttribute('aria-label') + ' Diagram' : 'Diagram';

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
    gridInstances[containerId] = { api: gridApi, data: data, columns: columns };

    return gridApi;
}

function downloadTableXLSX(containerId, filename) {
    const grid = gridInstances[containerId];
    if (!grid) return;

    const rowData = [];
    grid.api.forEachNode(node => rowData.push(node.data));

    const ws = XLSX.utils.json_to_sheet(rowData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Data');
    XLSX.writeFile(wb, filename);
}
