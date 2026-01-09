// LLM Configuration for Study Buddy
const LLM_CONFIG = {
    // Backend API URL (HuggingFace Spaces)
    backendUrl: 'https://sreevarsh-srm-study-buddy.hf.space',
};

// Conversation history for context
let conversationHistory = [];
const MAX_HISTORY = 10;

// Add message to history
function addToHistory(role, content) {
    conversationHistory.push({ role, content });
    if (conversationHistory.length > MAX_HISTORY) {
        conversationHistory.shift();
    }
}

// Main LLM call function
async function callLLM(userMessage, syllabusContext) {
    console.log('Calling Study Buddy API:', userMessage);

    // Add user message to history
    addToHistory('user', userMessage);

    try {
        const response = await fetch(`${LLM_CONFIG.backendUrl}/api/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                query: userMessage,
                history: conversationHistory.slice(-5)
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const data = await response.json();
        const assistantMessage = data.response;

        // Add to history
        if (assistantMessage) {
            addToHistory('assistant', assistantMessage);
        }

        // Return with sources if available
        if (data.sources && data.sources.length > 0) {
            const sourceInfo = data.sources
                .map(s => `📚 ${s.department || s.file}`)
                .join(', ');

            return assistantMessage + `\n\n---\n*Source: ${sourceInfo}*`;
        }

        return assistantMessage;

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
