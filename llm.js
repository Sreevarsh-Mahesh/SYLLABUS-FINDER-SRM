// LLM Configuration for Study Buddy with Redis Memory Support
const LLM_CONFIG = {
    // Backend API URL (HuggingFace Spaces)
    backendUrl: 'https://sreevarsh-srm-study-buddy.hf.space',
};

// Session management for persistent memory
const SESSION_STORAGE_KEY = 'srm_study_buddy_session';

// Get or create session ID
function getSessionId() {
    let sessionId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!sessionId) {
        sessionId = generateSessionId();
        localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    }
    return sessionId;
}

// Generate a unique session ID
function generateSessionId() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Clear session and start fresh
function clearSession() {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    conversationHistory = [];

    // Also clear on server
    const sessionId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (sessionId) {
        fetch(`${LLM_CONFIG.backendUrl}/api/session/clear`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        }).catch(e => console.log('Session clear error:', e));
    }

    // Generate new session
    const newSessionId = generateSessionId();
    localStorage.setItem(SESSION_STORAGE_KEY, newSessionId);

    return newSessionId;
}

// Local conversation history (backup/fallback)
let conversationHistory = [];
const MAX_HISTORY = 10;

// Add message to local history (fallback)
function addToHistory(role, content) {
    conversationHistory.push({ role, content });
    if (conversationHistory.length > MAX_HISTORY) {
        conversationHistory.shift();
    }
}

// Main LLM call function with session support
async function callLLM(userMessage, syllabusContext) {
    console.log('Calling Study Buddy API:', userMessage);

    // Get session ID for memory
    const sessionId = getSessionId();

    // Add user message to local history (fallback)
    addToHistory('user', userMessage);

    try {
        const response = await fetch(`${LLM_CONFIG.backendUrl}/api/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: userMessage,
                session_id: sessionId,  // Pass session ID for server-side memory
                history: conversationHistory.slice(-5)  // Fallback local history
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const data = await response.json();
        const assistantMessage = data.response;

        // Update session ID if server returned a different one
        if (data.session_id && data.session_id !== sessionId) {
            localStorage.setItem(SESSION_STORAGE_KEY, data.session_id);
        }

        // Add to local history (as backup)
        if (assistantMessage) {
            addToHistory('assistant', assistantMessage);
        }

        // Build response with sources
        let finalResponse = assistantMessage;

        if (data.sources && data.sources.length > 0) {
            const sourceInfo = data.sources
                .map(s => `📚 ${s.department || s.file}`)
                .join(', ');
            finalResponse += `\n\n---\n*Source: ${sourceInfo}*`;
        }

        return finalResponse;

    } catch (error) {
        console.error('API Error:', error);

        // Fallback to local syllabus data
        return generateLocalResponse(userMessage, syllabusContext);
    }
}

// Fallback function using local syllabus data
function generateLocalResponse(query, syllabusData) {
    const queryLower = query.toLowerCase();

    // Search for matching subject
    for (const subject of syllabusData.subjects || []) {
        if (subject.name.toLowerCase().includes(queryLower) ||
            queryLower.includes(subject.name.toLowerCase())) {

            let response = `**${subject.name}** (${subject.code})\n\n`;
            for (const unit of subject.units || []) {
                response += `**Unit ${unit.number}: ${unit.title}**\n`;
                response += unit.topics.map(t => `• ${t}`).join('\n') + '\n\n';
            }
            return response;
        }
    }

    // List available subjects
    const subjects = (syllabusData.subjects || []).map(s => s.name).join(', ');
    return `I couldn't connect to the AI backend. Here are the available subjects: ${subjects}\n\nTry asking about a specific subject like "Machine Learning" or "Deep Learning".`;
}

// Check if LLM/Backend is configured
function isLLMConfigured() {
    return true; // Always try
}

// Format LLM response to HTML
function formatLLMResponse(text) {
    if (!text) return null;

    // Parse markdown to HTML using marked.js
    try {
        return marked.parse(text);
    } catch (e) {
        console.error("Markdown parsing error:", e);
        // Fallback to basic text
        return '<p>' + text.replace(/\n/g, '<br>') + '</p>';
    }
}

// Get memory status from backend
async function getMemoryStatus() {
    try {
        const response = await fetch(`${LLM_CONFIG.backendUrl}/`);
        const data = await response.json();
        return {
            memoryEnabled: data.memory_enabled || false,
            redisConnected: data.redis_connected || false
        };
    } catch (e) {
        return { memoryEnabled: false, redisConnected: false };
    }
}

// Get conversation history from server
async function getServerHistory() {
    const sessionId = getSessionId();
    try {
        const response = await fetch(`${LLM_CONFIG.backendUrl}/api/session/${sessionId}/history`);
        const data = await response.json();
        return data.history || [];
    } catch (e) {
        console.error('Failed to get server history:', e);
        return [];
    }
}

// Export for use in app.js
window.clearChatSession = clearSession;
window.getMemoryStatus = getMemoryStatus;
window.getServerHistory = getServerHistory;
