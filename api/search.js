import { GoogleGenAI } from '@google/genai';

// Initialize Gemini
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

// In-memory cache for extracted subjects
let syllabusCache = null;

// PDF text cache (extracted once)
let pdfTextCache = null;

export default async function handler(req, res) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    const { query, searchSubject } = req.body;

    if (!query && !searchSubject) {
        return res.status(400).json({ error: 'Query or searchSubject required' });
    }

    try {
        // If searching for a specific subject, extract from PDF
        if (searchSubject) {
            const subject = await extractSubjectFromPDF(searchSubject);
            return res.status(200).json({ subject });
        }

        // Regular chat - check if we have syllabus context
        const syllabusContext = await getSyllabusContext();

        // Call Gemini with syllabus context
        const response = await ai.models.generateContent({
            model: 'gemini-2.0-flash',
            contents: `You are a helpful SRM University syllabus assistant.

AVAILABLE SYLLABUS DATA:
${JSON.stringify(syllabusContext, null, 2)}

If the student asks about a subject NOT in the data above, tell them you can search for it.

Student Question: ${query}

Provide a helpful response:`
        });

        return res.status(200).json({
            response: response.text,
            foundInCache: true
        });

    } catch (error) {
        console.error('API error:', error);
        return res.status(500).json({ error: error.message });
    }
}

async function getSyllabusContext() {
    // Load from file if not cached
    if (!syllabusCache) {
        try {
            const fs = await import('fs/promises');
            const data = await fs.readFile('./data/syllabus.json', 'utf-8');
            syllabusCache = JSON.parse(data);
        } catch (e) {
            syllabusCache = { subjects: [] };
        }
    }
    return syllabusCache;
}

async function extractSubjectFromPDF(subjectName) {
    // This would search the PDF and extract subject details using Gemini
    // For now, return a placeholder
    const prompt = `Search for the subject "${subjectName}" in the SRM CSE syllabus and extract:
    - code (course code like 21CSE253T)
    - name (full course name)
    - units (array with number, title, and topics)
    
    Return as JSON.`;

    try {
        const response = await ai.models.generateContent({
            model: 'gemini-2.0-flash',
            contents: prompt
        });

        let content = response.text.trim();
        if (content.startsWith('```json')) content = content.slice(7);
        if (content.startsWith('```')) content = content.slice(3);
        if (content.endsWith('```')) content = content.slice(0, -3);

        return JSON.parse(content);
    } catch (e) {
        return null;
    }
}
