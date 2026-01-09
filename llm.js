// LLM Configuration
const LLM_CONFIG = {
    // OpenRouter API endpoint
    apiUrl: 'https://openrouter.ai/api/v1/chat/completions',

    // Free model options (no API key needed for some)
    model: 'google/gemma-2-9b-it:free', // Free tier

    // Your OpenRouter API key (get from https://openrouter.ai)
    // Leave empty to use the built-in smart search without LLM
    apiKey: '' // User should add their key here
};

// System prompt for the LLM
const SYSTEM_PROMPT = `You are a helpful SRM University syllabus assistant for the CINTEL (Computer Intelligence and Data Science) department.

Your role:
1. Help students find subject syllabi
2. Explain topics from the syllabus
3. Guide students on what to study for exams (CT1, CT2, Semester)
4. Generate concise study notes when asked

Guidelines:
- Be concise and helpful
- Use bullet points for clarity
- When showing syllabus, organize by units
- For exam prep, focus on key topics
- Be encouraging and supportive

You have access to the syllabus data that will be provided in the context.`;

// Call LLM with context
async function callLLM(userMessage, syllabusContext) {
    if (!LLM_CONFIG.apiKey) {
        return null; // Fall back to local search
    }

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
                messages: [
                    {
                        role: 'system',
                        content: SYSTEM_PROMPT
                    },
                    {
                        role: 'user',
                        content: `Context - Available Syllabus Data:
${JSON.stringify(syllabusContext, null, 2)}

Student Question: ${userMessage}

Please provide a helpful response based on the syllabus data.`
                    }
                ],
                max_tokens: 1000,
                temperature: 0.7
            })
        });

        if (!response.ok) {
            console.error('LLM API error:', response.status);
            return null;
        }

        const data = await response.json();
        return data.choices[0]?.message?.content || null;
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
