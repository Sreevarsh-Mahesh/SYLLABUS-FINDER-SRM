// LLM Configuration
const LLM_CONFIG = {
    // Use our secure serverless API (API key is stored server-side)
    apiUrl: '/api/chat',

    // Model to use (free tier) - Google Gemma 3n E4B
    model: 'google/gemma-3n-e4b-it:free',

    // For local development, you can set a key in localStorage
    // For production (Vercel), the key is in environment variables
    localApiKey: localStorage.getItem('OPENROUTER_API_KEY') || ''
};

// System prompt for the LLM
const SYSTEM_PROMPT = `You are an intelligent, friendly SRM University syllabus assistant for the CINTEL (Computer Intelligence and Data Science) department.

IMPORTANT BEHAVIORS:
1. BE CONVERSATIONAL - If the user's request is unclear or incomplete, ask clarifying questions
2. BE SMART - Understand context and intent even from vague queries
3. BE HELPFUL - Always provide value, even if you need more info

EXAMPLE INTERACTIONS:
- User: "I need to prepare for a test" → Ask: "Which subject would you like to prepare for? I can help with AgentOps, Machine Learning, Deep Learning, NLP, or Computer Vision."
- User: "unit 1 and 2" → If you know the subject from context, show those units. If not, ask which subject.
- User: "what is backpropagation" → Search the syllabus and explain where it's covered and what it means.

YOUR CAPABILITIES:
1. Find and display subject syllabi
2. Explain any topic from the syllabus
3. Create study plans for exams (CT1=Units 1-2, CT2=Units 3-4, Semester=All Units)
4. Generate concise study notes
5. Answer questions about topics in the syllabus

RESPONSE FORMAT:
- Keep responses concise but complete
- Use bullet points and bold for clarity
- When showing syllabus content, organize by units
- Always be encouraging and supportive

You have access to the complete syllabus data in the context. Use it to give accurate, helpful responses.`;

// Conversation history for context
let conversationHistory = [];
const MAX_HISTORY = 10; // Keep last 10 messages for context

// Add message to history
function addToHistory(role, content) {
    conversationHistory.push({ role, content });
    if (conversationHistory.length > MAX_HISTORY) {
        conversationHistory.shift(); // Remove oldest
    }
}

// Call LLM with context
async function callLLM(userMessage, syllabusContext) {
    console.log('Calling LLM with query:', userMessage);

    // Add user message to history
    addToHistory('user', userMessage);

    // Build messages array with history
    const messages = [
        {
            role: 'system',
            content: SYSTEM_PROMPT + `\n\nAVAILABLE SYLLABUS DATA:\n${JSON.stringify(syllabusContext, null, 2)}`
        },
        ...conversationHistory
    ];

    try {
        // Use serverless API (key is on server) or direct if local key exists
        const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        const useDirectApi = isLocal && LLM_CONFIG.localApiKey;

        const apiUrl = useDirectApi ? 'https://openrouter.ai/api/v1/chat/completions' : LLM_CONFIG.apiUrl;
        const headers = {
            'Content-Type': 'application/json'
        };

        // Only add auth header for direct API calls (local dev)
        if (useDirectApi) {
            headers['Authorization'] = `Bearer ${LLM_CONFIG.localApiKey}`;
            headers['HTTP-Referer'] = window.location.href;
            headers['X-Title'] = 'SRM Syllabus Finder';
        }

        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                model: LLM_CONFIG.model,
                messages: messages
            })
        });

        console.log('LLM Response status:', response.status);

        if (!response.ok) {
            const errorText = await response.text();
            console.error('LLM API error:', response.status, errorText);

            // Check for rate limiting
            if (response.status === 429) {
                return "⚠️ Rate limit reached. Please wait a moment and try again.";
            }
            return null;
        }

        const data = await response.json();
        console.log('LLM Response data:', data);

        if (data.error) {
            console.error('LLM returned error:', data.error);
            return null;
        }

        const assistantMessage = data.choices?.[0]?.message?.content || null;

        // Add assistant response to history for context
        if (assistantMessage) {
            addToHistory('assistant', assistantMessage);
        }

        return assistantMessage;
    } catch (error) {
        console.error('LLM call failed:', error);
        return null;
    }
}

// Check if LLM is configured
function isLLMConfigured() {
    // In production (Vercel), always use serverless API
    // Locally, check if API key is in localStorage
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    return !isLocal || !!LLM_CONFIG.localApiKey;
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
