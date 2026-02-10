// =====================================================
// SRM Study Buddy - App Controller
// Clean Minimalist UI
// =====================================================

// App State
let isLoading = false;

// DOM Elements
const messagesContainer = document.getElementById('messages');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const headerStatus = document.getElementById('headerStatus');

// Update header status text
function setHeaderStatus(text, isThinking = false) {
    if (headerStatus) {
        headerStatus.textContent = text;
        headerStatus.classList.toggle('thinking', isThinking);
    }
}

// Start a new chat session
function startNewChat() {
    // Clear server-side memory
    if (window.clearChatSession) {
        window.clearChatSession();
    }

    // Clear chat UI
    messagesContainer.innerHTML = '';

    // Add fresh welcome message
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'message bot-message';
    welcomeDiv.innerHTML = `
        <div class="message-header">
            <div class="message-avatar">
                <svg viewBox="0 0 40 40" fill="none">
                    <circle cx="13" cy="20" r="6" stroke="white" stroke-width="2" fill="none"/>
                    <circle cx="27" cy="20" r="6" stroke="white" stroke-width="2" fill="none"/>
                    <path d="M21 20 H19" stroke="white" stroke-width="2" stroke-linecap="round"/>
                    <circle cx="13" cy="20" r="2" fill="white"/>
                    <circle cx="27" cy="20" r="2" fill="white"/>
                </svg>
            </div>
            <span class="bot-name">Study Buddy</span>
        </div>
        <div class="message-content">
            <p>🔄 <strong>New conversation started!</strong></p>
            <p>I've cleared our chat. What subject would you like to explore?</p>
            <div class="suggestions">
                <button class="suggestion-btn" onclick="askQuestion('Machine Learning syllabus')">Machine Learning</button>
                <button class="suggestion-btn" onclick="askQuestion('Deep Learning syllabus')">Deep Learning</button>
                <button class="suggestion-btn" onclick="askQuestion('List all subjects')">All Subjects</button>
            </div>
        </div>
    `;
    messagesContainer.appendChild(welcomeDiv);

    // Reset header status
    setHeaderStatus('Ready to help');

    // Focus input
    userInput.focus();

    // Show toast
    showToast('New chat started!');
}

// Toast notification
function showToast(message) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
}

// Handle Enter key
function handleKeyPress(event) {
    if (event.key === 'Enter' && !isLoading) {
        sendMessage();
    }
}

// Ask a question (from suggestion buttons)
function askQuestion(question) {
    userInput.value = question;
    sendMessage();
}

// Send user message
function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isLoading) return;

    // Add user message
    addMessage(message, 'user');
    userInput.value = '';

    // Update header status
    setHeaderStatus('Thinking...', true);

    // Show typing indicator
    showTyping();

    // Process with slight delay
    setTimeout(() => {
        processQuery(message);
    }, 300);
}

// Add message to chat
function addMessage(content, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    if (type === 'bot') {
        // Bot message with header
        messageDiv.innerHTML = `
            <div class="message-header">
                <div class="message-avatar">
                    <svg viewBox="0 0 40 40" fill="none">
                        <circle cx="13" cy="20" r="6" stroke="white" stroke-width="2" fill="none"/>
                        <circle cx="27" cy="20" r="6" stroke="white" stroke-width="2" fill="none"/>
                        <path d="M21 20 H19" stroke="white" stroke-width="2" stroke-linecap="round"/>
                        <circle cx="13" cy="20" r="2" fill="white"/>
                        <circle cx="27" cy="20" r="2" fill="white"/>
                    </svg>
                </div>
                <span class="bot-name">Study Buddy</span>
            </div>
            <div class="message-content">${content}</div>
        `;
    } else {
        // User message with avatar
        messageDiv.innerHTML = `
            <div class="message-content">${content}</div>
            <div class="message-avatar"></div>
        `;
    }

    messagesContainer.appendChild(messageDiv);

    // Scroll to bottom
    messagesContainer.parentElement.scrollTop = messagesContainer.parentElement.scrollHeight;
}

// Show typing indicator
function showTyping() {
    isLoading = true;
    sendBtn.disabled = true;

    const typingDiv = document.createElement('div');
    typingDiv.className = 'message bot-message';
    typingDiv.id = 'typing-indicator';

    typingDiv.innerHTML = `
        <div class="message-header">
            <div class="message-avatar">
                <svg viewBox="0 0 40 40" fill="none">
                    <circle cx="13" cy="20" r="6" stroke="white" stroke-width="2" fill="none"/>
                    <circle cx="27" cy="20" r="6" stroke="white" stroke-width="2" fill="none"/>
                    <path d="M21 20 H19" stroke="white" stroke-width="2" stroke-linecap="round"/>
                    <circle cx="13" cy="20" r="2" fill="white"/>
                    <circle cx="27" cy="20" r="2" fill="white"/>
                </svg>
            </div>
            <span class="bot-name">Study Buddy</span>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;

    messagesContainer.appendChild(typingDiv);
    messagesContainer.parentElement.scrollTop = messagesContainer.parentElement.scrollHeight;
}

// Hide typing indicator
function hideTyping() {
    isLoading = false;
    sendBtn.disabled = false;

    const typing = document.getElementById('typing-indicator');
    if (typing) typing.remove();

    // Reset header status
    setHeaderStatus('Ready to help');
}

// Process user query
async function processQuery(query) {
    let response;

    // Always use LLM backend
    if (isLLMConfigured()) {
        const context = typeof syllabusData !== 'undefined' ? syllabusData : {};
        response = await callLLM(query, context);

        if (response) {
            // Format response using marked.js
            const formatted = formatLLMResponse(response);
            hideTyping();
            addMessage(formatted || response, 'bot');
            return;
        }
    }

    // Fallback response
    hideTyping();
    addMessage("I'm having trouble connecting to the AI. Please try again in a moment.", 'bot');
}

// Check if LLM is configured
function isLLMConfigured() {
    return typeof callLLM === 'function';
}

// Format LLM response to HTML using marked.js
function formatLLMResponse(text) {
    if (!text) return null;

    try {
        return marked.parse(text);
    } catch (e) {
        console.error("Markdown parsing error:", e);
        return '<p>' + text.replace(/\n/g, '<br>') + '</p>';
    }
}
