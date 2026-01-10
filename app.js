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
};

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
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        },
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
            headers: {
                'Accept': 'application/json'
            }
        });

        if (!response.ok) throw new Error('Polling status failed');

        const data = await response.json();
        // The data returned is RequestMetadata
        // outcome is 'success', a failure dict, or null if not finished
        if (data.outcome === 'success') {
            // Fetch the actual output value
            const outputResp = await fetch(`${CONFIG.baseUrl}/applications/${appName}/requests/${requestId}/output`, {
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
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
    div.innerHTML = text;
    elements.chatHistory.appendChild(div);
    elements.chatHistory.scrollTop = elements.chatHistory.scrollHeight;
    return id;
}

function updateChatMessage(id, text) {
    const div = document.getElementById(id);
    if (div) {
        div.innerHTML = text;
        elements.chatHistory.scrollTop = elements.chatHistory.scrollHeight;
    }
}
