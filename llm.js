// LLM Configuration
const LLM_CONFIG = {
    // OpenRouter API endpoint
    apiUrl: 'https://openrouter.ai/api/v1/chat/completions',

    // Free model - Using Meta Llama 3.1 8B (fast and reliable)
    model: 'meta-llama/llama-3.1-8b-instruct:free',

    // Your OpenRouter API key (get from https://openrouter.ai)
    // ⚠️ For security, you can also set this via: localStorage.setItem('OPENROUTER_API_KEY', 'your-key')
    apiKey: localStorage.getItem('OPENROUTER_API_KEY') || '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'
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
    if (!LLM_CONFIG.apiKey) {
        console.log('No API key configured');
        return null; // Fall back to local search
    }

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
        const response = await fetch(LLM_CONFIG.apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${LLM_CONFIG.apiKey}`,
                'HTTP-Referer': window.location.href,
                'X-Title': 'SRM Syllabus Finder'
            },
            body: JSON.stringify({
                model: LLM_CONFIG.model,
                messages: messages,
                max_tokens: 1000,
                temperature: 0.7
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
    return !!LLM_CONFIG.apiKey;
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
