const CONFIG = {
    apiKey: "", // Handled by server.py proxy
    baseUrl: "/api/proxy"
};

const elements = {
    dropZone: document.getElementById('drop-zone'),
    fileInput: document.getElementById('file-input'),
    statusContainer: document.getElementById('status-container'),
    chatHistory: document.getElementById('chat-history'),
    queryInput: document.getElementById('query-input'),
    sendQuery: document.getElementById('send-query'),
    settingsToggle: document.getElementById('settings-toggle'),
    settingsPanel: document.getElementById('settings-panel'),
    apiKeyInput: document.getElementById('api-key-input'),
    geminiKeyInput: document.getElementById('gemini-key-input'),
    databaseUrlInput: document.getElementById('database-url-input'),
    saveSettings: document.getElementById('save-settings'),
};

// --- Settings Logic ---
elements.settingsToggle.addEventListener('click', () => {
    elements.settingsPanel.classList.toggle('hidden');
});

elements.saveSettings.addEventListener('click', () => {
    // Save all keys to sessionStorage
    const keys = [
        { id: 'TENSORLAKE_API_KEY', el: elements.apiKeyInput },
        { id: 'GEMINI_API_KEY', el: elements.geminiKeyInput },
        { id: 'DATABASE_URL', el: elements.databaseUrlInput }
    ];

    keys.forEach(({ id, el }) => {
        const val = el.value.trim();
        if (val) {
            sessionStorage.setItem(id, val);
        } else {
            sessionStorage.removeItem(id);
        }
    });

    elements.saveSettings.innerText = 'Saved!';
    setTimeout(() => elements.saveSettings.innerText = 'Save All', 2000);
});

// Load saved keys
['TENSORLAKE_API_KEY', 'GEMINI_API_KEY', 'DATABASE_URL'].forEach(id => {
    const saved = sessionStorage.getItem(id);
    if (saved) {
        const inputMap = {
            'TENSORLAKE_API_KEY': elements.apiKeyInput,
            'GEMINI_API_KEY': elements.geminiKeyInput,
            'DATABASE_URL': elements.databaseUrlInput
        };
        if (inputMap[id]) inputMap[id].value = saved;
    }
});

function getHeaders() {
    const headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    };
    const tensorlakeKey = sessionStorage.getItem('TENSORLAKE_API_KEY');
    const geminiKey = sessionStorage.getItem('GEMINI_API_KEY');
    const databaseUrl = sessionStorage.getItem('DATABASE_URL');

    if (tensorlakeKey) headers['X-TensorLake-API-Key'] = tensorlakeKey;
    if (geminiKey) headers['X-Gemini-API-Key'] = geminiKey;
    if (databaseUrl) headers['X-Database-URL'] = databaseUrl;

    return headers;
}

// Initialize Marked options
if (typeof marked !== 'undefined') {
    marked.setOptions({
        gfm: true,
        breaks: true,
        headerIds: false,
        mangle: false
    });
}

// --- Ingestion Logic ---

elements.dropZone.addEventListener('click', () => elements.fileInput.click());

elements.dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    elements.dropZone.classList.add('drag-over');
});

elements.dropZone.addEventListener('dragleave', () => elements.dropZone.classList.remove('drag-over'));

elements.dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    elements.dropZone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    handleFiles(files);
});

elements.fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

async function handleFiles(files) {
    for (const file of files) {
        if (file.type !== 'application/pdf') {
            addStatusMsg(file.name, 'Only PDF allowed', 'error');
            continue;
        }
        processFile(file);
    }
}

async function processFile(file) {
    const statusId = addStatusMsg(file.name, 'Pending...', 'pending');

    try {
        const b64 = await fileToBase64(file);
        const b64Data = b64.split(',')[1];

        // Match IngestionRequest Pydantic model exactly
        const payload = {
            file_b64: b64Data,
            content_type: file.type,
            filename: file.name
        };

        const requestId = await runRemoteApp('expense_ingestion_app', payload);
        updateStatusMsg(statusId, 'Extracting transactions...', 'pending');

        const result = await pollRequest('expense_ingestion_app', requestId);
        updateStatusMsg(statusId, `Success: Added ${result} records`, 'success');
        addChatMessage('agent', `Finished processing <b>${file.name}</b>. Added ${result} transactions to your database.`);

        // Refresh insights after new data is ingested
        loadInsights(true);

    } catch (error) {
        console.error(error);
        updateStatusMsg(statusId, 'Error: ' + error.message, 'error');
    }
}

// --- Query Logic ---

elements.sendQuery.addEventListener('click', () => sendQuery());
elements.queryInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendQuery();
});

async function sendQuery() {
    const query = elements.queryInput.value.trim();
    if (!query) return;

    elements.queryInput.value = '';
    addChatMessage('user', query);
    const agentMsgId = addChatMessage('agent', '<span class="loading">Thinking...</span>');

    try {
        // Function takes a single string argument, so payload is just the string
        const requestId = await runRemoteApp('expense_query_app', query);
        const result = await pollRequest('expense_query_app', requestId);
        updateChatMessage(agentMsgId, result);

    } catch (error) {
        console.error(error);
        updateChatMessage(agentMsgId, 'Sorry, I encountered an error: ' + error.message);
    }
}

// --- Helper Functions ---

async function runRemoteApp(appName, payload) {
    const response = await fetch(`${CONFIG.baseUrl}/applications/${appName}`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const err = await response.json();
        throw new Error(err.message || 'API Error');
    }

    const data = await response.json();
    return data.request_id;
}

async function pollRequest(appName, requestId) {
    while (true) {
        // Using the SDK pattern for status check
        const response = await fetch(`${CONFIG.baseUrl}/applications/${appName}/requests/${requestId}`, {
            headers: getHeaders()
        });

        if (!response.ok) throw new Error('Polling status failed');

        const data = await response.json();
        // The data returned is RequestMetadata
        // outcome is 'success', a failure dict, or null if not finished
        if (data.outcome === 'success') {
            // Fetch the actual output value
            const outputResp = await fetch(`${CONFIG.baseUrl}/applications/${appName}/requests/${requestId}/output`, {
                headers: getHeaders()
            });
            if (!outputResp.ok) throw new Error('Fetching output failed');
            const outputData = await outputResp.json();
            return outputData;
        } else if (data.request_error || (data.outcome && typeof data.outcome === 'object')) {
            throw new Error(data.request_error ? data.request_error.message : 'Computation failed');
        }

        await new Promise(r => setTimeout(r, 2000));
    }
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => resolve(reader.result);
        reader.onerror = error => reject(error);
    });
}

function addStatusMsg(filename, message, type) {
    const id = 'status-' + Math.random().toString(36).substr(2, 9);
    const div = document.createElement('div');
    div.id = id;
    div.className = `status-item ${type}`;
    div.innerHTML = `<span class="filename">${filename}</span> <span class="status-text">${message}</span>`;
    elements.statusContainer.prepend(div);
    return id;
}

function updateStatusMsg(id, message, type) {
    const div = document.getElementById(id);
    if (div) {
        div.className = `status-item ${type}`;
        div.querySelector('.status-text').innerText = message;
    }
}

function addChatMessage(role, text) {
    const id = 'msg-' + Math.random().toString(36).substr(2, 9);
    const div = document.createElement('div');
    div.id = id;
    div.className = `message ${role}`;

    if (role === 'agent' && typeof marked !== 'undefined') {
        // Add a newline to help marked recognize tables even if they start at the first char
        div.innerHTML = marked.parse('\n' + text);
        if (text.includes('|') && text.includes('-')) {
            div.classList.add('wide-message');
        }
    } else {
        div.innerHTML = text;
    }

    elements.chatHistory.appendChild(div);
    elements.chatHistory.scrollTop = elements.chatHistory.scrollHeight;
    return id;
}

function updateChatMessage(id, text) {
    const div = document.getElementById(id);
    if (div) {
        if (div.classList.contains('agent') && typeof marked !== 'undefined') {
            div.innerHTML = marked.parse('\n' + text);
            if (text.includes('|') && text.includes('-')) {
                div.classList.add('wide-message');
            }
        } else {
            div.innerHTML = text;
        }
        elements.chatHistory.scrollTop = elements.chatHistory.scrollHeight;
    }
}

// --- Insights Logic ---
const insightsElements = {
    panel: document.getElementById('insights-panel'),
    loading: document.getElementById('insights-loading'),
    content: document.getElementById('insights-content'),
    categorySummary: document.getElementById('category-summary'),
    subscriptions: document.getElementById('subscriptions'),
    trends: document.getElementById('trends'),
    refreshBtn: document.getElementById('refresh-insights')
};

async function loadInsights(forceRefresh = false) {
    if (!insightsElements.panel) return;

    // Show loading state
    insightsElements.loading.classList.remove('hidden');
    insightsElements.content.style.opacity = '0.5';

    try {
        const requestId = await runRemoteApp('insights_app', forceRefresh);
        const insights = await pollRequest('insights_app', requestId);
        renderInsights(insights);
    } catch (error) {
        console.error('Failed to load insights:', error);
        // Keep existing content, just hide loading
    } finally {
        insightsElements.loading.classList.add('hidden');
        insightsElements.content.style.opacity = '1';
    }
}

function renderInsights(insights) {
    // Render category summary
    if (insights.category_summary && Object.keys(insights.category_summary).length > 0) {
        const categories = Object.entries(insights.category_summary)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 6);

        let html = '<ul>';
        for (const [category, amount] of categories) {
            html += `<li>
                <span class="category-name">${category}</span>
                <span class="category-amount">$${amount.toFixed(2)}</span>
            </li>`;
        }
        html += '</ul>';

        insightsElements.categorySummary.querySelector('.insight-body').innerHTML = html;
    }

    // Render subscriptions
    if (insights.subscriptions && insights.subscriptions.length > 0) {
        let html = '';
        for (const sub of insights.subscriptions.slice(0, 5)) {
            html += `<div class="subscription-item">
                <div class="subscription-name">${sub.description || 'Unknown'}</div>
                <div class="subscription-cost">$${sub.amount?.toFixed(2) || '0.00'}/month • ${sub.occurrences || 0} occurrences</div>
            </div>`;
        }
        insightsElements.subscriptions.querySelector('.insight-body').innerHTML = html || 'No subscriptions detected.';
    }

    // Setup Chart
    if (insights.trends) {
        initChart(insights.trends);
    }
}

// Chart instance
let trendsChart = null;
let currentTrendData = null;

function initChart(trendData) {
    currentTrendData = trendData;
    const ctx = document.getElementById('trendsChart').getContext('2d');

    // Default to monthly
    const sortedData = (trendData.monthly || []).sort((a, b) => a.month.localeCompare(b.month));
    const labels = sortedData.map(d => formatLabel(d.month, 'monthly'));
    const data = sortedData.map(d => d.amount);

    if (trendsChart) {
        trendsChart.destroy();
    }

    trendsChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Spending',
                data: data,
                backgroundColor: 'rgba(0, 102, 204, 0.2)',
                borderColor: 'rgba(0, 102, 204, 1)',
                borderWidth: 1,
                borderRadius: 4,
                barThickness: 'flex'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return '$' + context.raw.toFixed(2);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { display: false },
                    ticks: {
                        callback: function (value) {
                            return '$' + value;
                        },
                        font: { size: 10 }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { font: { size: 10 } }
                }
            }
        }
    });

    // Setup toggles
    document.querySelectorAll('.toggle-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.toggle-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            updateChart(e.target.dataset.period);
        });
    });
}

function updateChart(period) {
    if (!trendsChart || !currentTrendData) return;

    let rawData = [];
    let labels = [];
    let chartType = 'bar';

    if (period === 'monthly') {
        rawData = (currentTrendData.monthly || []).sort((a, b) => a.month.localeCompare(b.month));
        labels = rawData.map(d => formatLabel(d.month, 'monthly'));
    } else if (period === 'weekly') {
        rawData = (currentTrendData.weekly || []).sort((a, b) => a.week.localeCompare(b.week));
        labels = rawData.map(d => formatLabel(d.week, 'weekly'));
    } else if (period === 'daily') {
        rawData = (currentTrendData.daily || []).sort((a, b) => a.date.localeCompare(b.date));
        labels = rawData.map(d => formatLabel(d.date, 'daily'));
        chartType = 'line'; // Use line for daily
    }

    trendsChart.config.type = chartType;
    trendsChart.data.labels = labels;
    trendsChart.data.datasets[0].data = rawData.map(d => d.amount);

    if (chartType === 'line') {
        trendsChart.data.datasets[0].borderWidth = 2;
        trendsChart.data.datasets[0].pointRadius = 2;
        trendsChart.data.datasets[0].fill = true;
    } else {
        trendsChart.data.datasets[0].borderWidth = 1;
        trendsChart.data.datasets[0].pointRadius = 0;
        trendsChart.data.datasets[0].fill = false;
    }

    trendsChart.update();
}

function formatLabel(val, type) {
    if (!val) return '';
    const date = new Date(val);
    if (type === 'monthly') { // YYYY-MM
        const [y, m] = val.split('-');
        return `${new Date(y, m - 1).toLocaleString('default', { month: 'short' })}`;
    } else if (type === 'weekly') { // YYYY-WW
        return val.split('-')[1]; // Just show week number
    } else { // YYYY-MM-DD
        const [y, m, d] = val.split('-');
        return `${m}/${d}`;
    }
}

// Refresh button click handler
if (insightsElements.refreshBtn) {
    insightsElements.refreshBtn.addEventListener('click', () => loadInsights(true));
}

// Load insights on page load (delayed to not block initial render)
setTimeout(() => loadInsights(false), 1000);
