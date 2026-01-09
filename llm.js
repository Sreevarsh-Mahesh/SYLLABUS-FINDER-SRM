// LLM Configuration for Study Buddy
const LLM_CONFIG = {
    // Backend API URL (HuggingFace Spaces or local)
    backendUrl: 'https://your-space.hf.space', // Update after deployment

    // Fallback to local for development
    localBackend: 'http://localhost:7860',

    // For direct API calls (fallback)
    geminiKey: localStorage.getItem('GEMINI_API_KEY') || ''
};

// Conversation history for context
let conversationHistory = [];
const MAX_HISTORY = 10;

// Check if we're in development mode
function isLocalDev() {
    return window.location.protocol === 'file:' ||
        window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1';
}

// Get the API URL
function getApiUrl() {
    if (isLocalDev()) {
        return LLM_CONFIG.localBackend;
    }
    // In production, use the configured backend
    return LLM_CONFIG.backendUrl !== 'https://your-space.hf.space'
        ? LLM_CONFIG.backendUrl
        : LLM_CONFIG.localBackend;
}

// Add message to history
function addToHistory(role, content) {
    conversationHistory.push({ role, content });
    if (conversationHistory.length > MAX_HISTORY) {
        conversationHistory.shift();
    }
}

// Main LLM call function
async function callLLM(userMessage, syllabusContext) {
    console.log('Calling Study Buddy API with:', userMessage);

    // Add user message to history
    addToHistory('user', userMessage);

    const apiUrl = getApiUrl();

    try {
        // Try the RAG backend first
        const response = await fetch(`${apiUrl}/api/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: userMessage,
                history: conversationHistory.slice(-5)
            })
        });

        if (response.ok) {
            const data = await response.json();
            const assistantMessage = data.response;

            // Add to history
            if (assistantMessage) {
                addToHistory('assistant', assistantMessage);
            }

            // Return with sources if available
            if (data.sources && data.sources.length > 0) {
                const sourceInfo = data.sources
                    .filter(s => s.subject !== 'Unknown')
                    .map(s => `📚 ${s.subject} - ${s.unit}`)
                    .join('\n');

                return assistantMessage + (sourceInfo ? `\n\n---\n*Sources:*\n${sourceInfo}` : '');
            }

            return assistantMessage;
        }

        console.log('Backend unavailable, falling back to local...');
    } catch (error) {
        console.log('Backend error, using fallback:', error.message);
    }

    // Fallback: Use local syllabus data with Gemini directly
    return await fallbackLLMCall(userMessage, syllabusContext);
}

// Fallback function for direct Gemini calls
async function fallbackLLMCall(userMessage, syllabusContext) {
    const geminiKey = LLM_CONFIG.geminiKey || localStorage.getItem('GEMINI_API_KEY');

    if (!geminiKey) {
        return "⚠️ Backend unavailable and no API key configured. Please set up the backend or add a Gemini API key.";
    }

    const prompt = `You are a helpful SRM University study buddy.

SYLLABUS DATA:
${JSON.stringify(syllabusContext, null, 2)}

STUDENT QUESTION: ${userMessage}

Provide a helpful response:`;

    try {
        const response = await fetch(
            `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${geminiKey}`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contents: [{ parts: [{ text: prompt }] }]
                })
            }
        );

        if (response.ok) {
            const data = await response.json();
            return data.candidates?.[0]?.content?.parts?.[0]?.text || "I couldn't generate a response.";
        }
    } catch (error) {
        console.error('Fallback LLM error:', error);
    }

    return "Sorry, I'm having trouble connecting. Please try again.";
}

// Check if LLM/Backend is configured
function isLLMConfigured() {
    // Always return true - we'll handle errors gracefully
    return true;
}

// Format LLM response to HTML
function formatLLMResponse(text) {
    if (!text) return null;

    // Convert markdown-like formatting to HTML
    let html = text
        // Headers
        .replace(/^### (.+)$/gm, '<h4>$1</h4>')
        .replace(/^## (.+)$/gm, '<h3>$1</h3>')
        .replace(/^# (.+)$/gm, '<h2>$1</h2>')
        // Bold
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Code
        .replace(/`(.+?)`/g, '<code>$1</code>')
        // Line breaks
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    // Wrap in paragraph
    html = '<p>' + html + '</p>';

    // Convert bullet lists
    html = html.replace(/<p>- (.+?)(<br>|<\/p>)/g, '<li>$1</li>$2');
    html = html.replace(/(<li>.+<\/li>)+/g, '<ul>$&</ul>');

    return html;
}

// Semantic search function
async function searchSyllabus(query) {
    const apiUrl = getApiUrl();

    try {
        const response = await fetch(`${apiUrl}/api/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });

        if (response.ok) {
            return await response.json();
        }
    } catch (error) {
        console.error('Search error:', error);
    }

    return { results: [], count: 0 };
}

// Get available subjects
async function getIndexedSubjects() {
    const apiUrl = getApiUrl();

    try {
        const response = await fetch(`${apiUrl}/api/subjects`);
        if (response.ok) {
            return await response.json();
        }
    } catch (error) {
        console.error('Get subjects error:', error);
    }

    return { subjects: [], count: 0 };
}
