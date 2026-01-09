// App State
let isLoading = false;

// DOM Elements
const messagesContainer = document.getElementById('messages');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

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

    // Show typing indicator
    showTyping();

    // Process with slight delay for natural feel
    setTimeout(() => {
        processQuery(message);
    }, 500);
}

// Add message to chat
function addMessage(content, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = type === 'bot' ? '🤖' : '👤';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (typeof content === 'string') {
        contentDiv.innerHTML = content;
    } else {
        contentDiv.appendChild(content);
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
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
        <div class="message-avatar">🤖</div>
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
}

// Process user query
function processQuery(query) {
    const q = query.toLowerCase();
    let response;

    // Check for list all subjects
    if (q.includes('list') && (q.includes('subject') || q.includes('all'))) {
        response = createSubjectsList();
    }
    // Check for specific unit query
    else if (q.includes('unit')) {
        const unitMatch = q.match(/unit\s*(\d+)/i);
        const unitNum = unitMatch ? parseInt(unitMatch[1]) : null;

        // Try to find subject name in query
        const subject = findSubjectInQuery(q);

        if (subject && unitNum) {
            const result = findSubjectUnit(subject.name, unitNum);
            if (result && result.unit) {
                response = createUnitCard(result.subject, result.unit);
            } else {
                response = `<p>I couldn't find Unit ${unitNum} for <strong>${subject.name}</strong>. This subject has ${subject.units.length} units.</p>`;
            }
        } else if (subject) {
            response = createSyllabusCard(subject);
        } else {
            response = `<p>I couldn't identify the subject. Try asking about a specific subject like:</p>
                <div class="suggestions">
                    <button class="suggestion-btn" onclick="askQuestion('What is Unit 1 of AgentOps?')">Unit 1 of AgentOps</button>
                    <button class="suggestion-btn" onclick="askQuestion('Show me Deep Learning Unit 2')">Deep Learning Unit 2</button>
                </div>`;
        }
    }
    // Check for syllabus query
    else if (q.includes('syllabus') || q.includes('what is') || q.includes('show me') || q.includes('tell me about')) {
        const subject = findSubjectInQuery(q);
        if (subject) {
            response = createSyllabusCard(subject);
        } else {
            response = `<p>I couldn't find that subject. Here are the available subjects:</p>` + createSubjectsList();
        }
    }
    // Check for topic search
    else if (q.includes('topic') || q.includes('where') || q.includes('find')) {
        const topics = searchTopics(q.replace(/topic|where|find|is|the|in|which/gi, '').trim());
        if (topics.length > 0) {
            response = createTopicResults(topics);
        } else {
            response = `<p>I couldn't find that topic. Try searching for something else or view a subject's syllabus.</p>`;
        }
    }
    // Default: try to find a subject
    else {
        const subject = findSubjectInQuery(q);
        if (subject) {
            response = createSyllabusCard(subject);
        } else {
            response = `<p>I'm not sure what you're looking for. Here's what I can help you with:</p>
                <div class="suggestions">
                    <button class="suggestion-btn" onclick="askQuestion('List all subjects')">📋 All Subjects</button>
                    <button class="suggestion-btn" onclick="askQuestion('What is the syllabus for Machine Learning?')">🤖 ML Syllabus</button>
                    <button class="suggestion-btn" onclick="askQuestion('Show me Deep Learning Unit 4')">🧠 DL Unit 4</button>
                </div>`;
        }
    }

    hideTyping();

    if (typeof response === 'string') {
        addMessage(response, 'bot');
    } else {
        const container = document.createElement('div');
        container.appendChild(response);
        addMessage(container, 'bot');
    }
}

// Find subject in query
function findSubjectInQuery(query) {
    const q = query.toLowerCase();

    // Check each subject
    for (const subject of syllabusData.subjects) {
        if (q.includes(subject.name.toLowerCase()) ||
            q.includes(subject.code.toLowerCase()) ||
            q.includes(subject.fullName.toLowerCase())) {
            return subject;
        }
    }

    // Check for partial matches
    const keywords = {
        'agent': 'AgentOps',
        'agentops': 'AgentOps',
        'ml': 'Machine Learning',
        'machine': 'Machine Learning',
        'deep': 'Deep Learning',
        'dl': 'Deep Learning',
        'nlp': 'NLP',
        'natural': 'NLP',
        'language': 'NLP',
        'cv': 'Computer Vision',
        'vision': 'Computer Vision',
        'image': 'Computer Vision'
    };

    for (const [keyword, subjectName] of Object.entries(keywords)) {
        if (q.includes(keyword)) {
            return findSubject(subjectName);
        }
    }

    return null;
}

// Create syllabus card HTML
function createSyllabusCard(subject) {
    const card = document.createElement('div');
    card.innerHTML = `
        <p>Here's the complete syllabus for <strong>${subject.name}</strong>:</p>
        <div class="syllabus-card">
            <div class="syllabus-header">
                <h3>${subject.fullName}</h3>
                <span class="code">${subject.code}</span>
            </div>
            <div class="syllabus-meta">
                <span>📚 ${subject.credits} Credits</span>
                <span>📋 ${subject.type}</span>
                <span>📖 ${subject.units.length} Units</span>
            </div>
            <div class="syllabus-units">
                ${subject.units.map(unit => `
                    <div class="unit">
                        <div class="unit-title">Unit ${unit.number}: ${unit.title}</div>
                        <ul class="unit-topics">
                            ${unit.topics.map(topic => `<li>${topic}</li>`).join('')}
                        </ul>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
    return card;
}

// Create unit card HTML
function createUnitCard(subject, unit) {
    const card = document.createElement('div');
    card.innerHTML = `
        <p>Here's <strong>Unit ${unit.number}</strong> of <strong>${subject.name}</strong>:</p>
        <div class="syllabus-card">
            <div class="syllabus-header">
                <h3>${unit.title}</h3>
                <span class="code">${subject.code} - Unit ${unit.number}</span>
            </div>
            <div class="syllabus-units">
                <div class="unit">
                    <ul class="unit-topics">
                        ${unit.topics.map(topic => `<li>${topic}</li>`).join('')}
                    </ul>
                </div>
            </div>
        </div>
        <div class="suggestions" style="margin-top: 12px;">
            ${unit.number > 1 ? `<button class="suggestion-btn" onclick="askQuestion('Show me ${subject.name} Unit ${unit.number - 1}')">← Unit ${unit.number - 1}</button>` : ''}
            ${unit.number < subject.units.length ? `<button class="suggestion-btn" onclick="askQuestion('Show me ${subject.name} Unit ${unit.number + 1}')">Unit ${unit.number + 1} →</button>` : ''}
            <button class="suggestion-btn" onclick="askQuestion('What is the complete syllabus for ${subject.name}?')">Full Syllabus</button>
        </div>
    `;
    return card;
}

// Create subjects list HTML
function createSubjectsList() {
    const subjects = getAllSubjects();
    return `
        <p>Here are all available <strong>CINTEL</strong> subjects:</p>
        <div class="subjects-list">
            ${subjects.map(s => `
                <div class="subject-item" onclick="askQuestion('What is the syllabus for ${s.name}?')">
                    <div>
                        <div class="name">${s.fullName}</div>
                        <div class="code">${s.code} • ${s.credits} Credits • ${s.type}</div>
                    </div>
                    <span>→</span>
                </div>
            `).join('')}
        </div>
    `;
}

// Create topic results HTML
function createTopicResults(topics) {
    const grouped = topics.reduce((acc, t) => {
        const key = `${t.subjectCode}-${t.unit}`;
        if (!acc[key]) {
            acc[key] = {
                subject: t.subject,
                subjectCode: t.subjectCode,
                unit: t.unit,
                unitTitle: t.unitTitle,
                topics: []
            };
        }
        acc[key].topics.push(t.topic);
        return acc;
    }, {});

    const results = Object.values(grouped);

    return `
        <p>Found <strong>${topics.length}</strong> matching topic(s):</p>
        <div class="subjects-list">
            ${results.map(r => `
                <div class="subject-item" onclick="askQuestion('Show me ${r.subject} Unit ${r.unit}')">
                    <div>
                        <div class="name">${r.topics[0]}</div>
                        <div class="code">${r.subject} - Unit ${r.unit}: ${r.unitTitle}</div>
                    </div>
                    <span>→</span>
                </div>
            `).join('')}
        </div>
    `;
}

// Focus input on load
document.addEventListener('DOMContentLoaded', () => {
    userInput.focus();
});
