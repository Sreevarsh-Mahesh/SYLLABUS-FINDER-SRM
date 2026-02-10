// =====================================================
// SRM Study Buddy - Animated Mascot Controller
// A cute owl mascot with glass shine, cursor tracking,
// and expressive animations (thinking, eureka, happy)
// =====================================================

// Mascot State Management
const MascotStates = {
    IDLE: 'idle',
    THINKING: 'thinking',
    EUREKA: 'eureka',
    HAPPY: 'happy'
};

let currentMascotState = MascotStates.IDLE;
let blinkInterval = null;
let thinkingInterval = null;

// Create the mascot SVG and inject into the page
function initMascot() {
    const mascotContainer = document.getElementById('mascot-container');
    if (!mascotContainer) return;

    mascotContainer.innerHTML = createMascotSVG();

    // Start idle animations
    startIdleAnimations();

    // Setup cursor tracking
    document.addEventListener('mousemove', handleMouseMove);

    // Touch support for mobile
    document.addEventListener('touchmove', handleTouchMove);
}

// Generate the owl mascot SVG
function createMascotSVG() {
    return `
    <div class="mascot-wrapper">
        <!-- Lightbulb (hidden by default) -->
        <div class="lightbulb-container" id="lightbulb">
            <svg class="lightbulb-svg" viewBox="0 0 40 50" width="40" height="50">
                <defs>
                    <linearGradient id="bulbGlow" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#fef3c7"/>
                        <stop offset="100%" style="stop-color:#fbbf24"/>
                    </linearGradient>
                </defs>
                <!-- Bulb -->
                <ellipse cx="20" cy="18" rx="14" ry="16" fill="url(#bulbGlow)" class="bulb-glow"/>
                <!-- Filament -->
                <path d="M15 18 Q17 12 20 18 Q23 24 25 18" stroke="#f59e0b" stroke-width="2" fill="none"/>
                <!-- Base -->
                <rect x="14" y="32" width="12" height="4" rx="1" fill="#9ca3af"/>
                <rect x="15" y="36" width="10" height="3" rx="1" fill="#6b7280"/>
                <rect x="16" y="39" width="8" height="3" rx="1" fill="#4b5563"/>
                <!-- Rays -->
                <g class="light-rays">
                    <line x1="20" y1="0" x2="20" y2="-5" stroke="#fbbf24" stroke-width="2" stroke-linecap="round"/>
                    <line x1="6" y1="10" x2="2" y2="6" stroke="#fbbf24" stroke-width="2" stroke-linecap="round"/>
                    <line x1="34" y1="10" x2="38" y2="6" stroke="#fbbf24" stroke-width="2" stroke-linecap="round"/>
                    <line x1="0" y1="22" x2="-4" y2="22" stroke="#fbbf24" stroke-width="2" stroke-linecap="round"/>
                    <line x1="40" y1="22" x2="44" y2="22" stroke="#fbbf24" stroke-width="2" stroke-linecap="round"/>
                </g>
            </svg>
        </div>

        <!-- Question marks (for thinking) -->
        <div class="thinking-bubbles" id="thinkingBubbles">
            <span class="bubble">?</span>
            <span class="bubble">?</span>
            <span class="bubble">?</span>
        </div>

        <!-- Sparkles (for happy state) -->
        <div class="sparkles" id="sparkles">
            <span class="sparkle">✨</span>
            <span class="sparkle">✨</span>
            <span class="sparkle">✨</span>
            <span class="sparkle">✨</span>
        </div>

        <!-- Main Mascot SVG -->
        <svg class="mascot-svg" id="mascot" viewBox="0 0 120 140" width="100" height="116">
            <defs>
                <!-- Glass Shine Gradient -->
                <linearGradient id="glassShine" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:rgba(255,255,255,0)"/>
                    <stop offset="40%" style="stop-color:rgba(255,255,255,0.6)"/>
                    <stop offset="60%" style="stop-color:rgba(255,255,255,0.6)"/>
                    <stop offset="100%" style="stop-color:rgba(255,255,255,0)"/>
                </linearGradient>
                
                <!-- Body Gradient -->
                <linearGradient id="bodyGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#818cf8"/>
                    <stop offset="100%" style="stop-color:#6366f1"/>
                </linearGradient>
                
                <!-- Shadow -->
                <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                    <feDropShadow dx="0" dy="4" stdDeviation="4" flood-color="rgba(0,0,0,0.2)"/>
                </filter>
            </defs>
            
            <!-- Ears/Tufts -->
            <path d="M25 35 L15 10 L35 25 Z" fill="#818cf8" class="ear-left"/>
            <path d="M95 35 L105 10 L85 25 Z" fill="#818cf8" class="ear-right"/>
            
            <!-- Body -->
            <ellipse cx="60" cy="85" rx="45" ry="50" fill="url(#bodyGradient)" filter="url(#shadow)" class="body"/>
            
            <!-- Belly -->
            <ellipse cx="60" cy="95" rx="30" ry="35" fill="#c7d2fe" class="belly"/>
            
            <!-- Face/Head -->
            <ellipse cx="60" cy="55" rx="40" ry="35" fill="url(#bodyGradient)" class="head"/>
            
            <!-- Glasses Frame -->
            <g class="glasses">
                <!-- Left Lens Frame -->
                <ellipse cx="40" cy="55" rx="18" ry="16" fill="none" stroke="#312e81" stroke-width="4"/>
                <!-- Right Lens Frame -->
                <ellipse cx="80" cy="55" rx="18" ry="16" fill="none" stroke="#312e81" stroke-width="4"/>
                <!-- Bridge -->
                <path d="M58 55 Q60 50 62 55" stroke="#312e81" stroke-width="3" fill="none"/>
                <!-- Temple Arms -->
                <line x1="22" y1="52" x2="10" y2="48" stroke="#312e81" stroke-width="3" stroke-linecap="round"/>
                <line x1="98" y1="52" x2="110" y2="48" stroke="#312e81" stroke-width="3" stroke-linecap="round"/>
            </g>
            
            <!-- Left Eye -->
            <g class="eye-group left-eye" id="leftEye">
                <ellipse cx="40" cy="55" rx="14" ry="12" fill="white" class="eye-white"/>
                <g class="pupil-group" id="leftPupil">
                    <circle cx="40" cy="55" r="6" fill="#1e1b4b" class="pupil"/>
                    <circle cx="42" cy="53" r="2" fill="white" class="eye-highlight"/>
                </g>
            </g>
            
            <!-- Right Eye -->
            <g class="eye-group right-eye" id="rightEye">
                <ellipse cx="80" cy="55" rx="14" ry="12" fill="white" class="eye-white"/>
                <g class="pupil-group" id="rightPupil">
                    <circle cx="80" cy="55" r="6" fill="#1e1b4b" class="pupil"/>
                    <circle cx="82" cy="53" r="2" fill="white" class="eye-highlight"/>
                </g>
            </g>
            
            <!-- Eyelids (for blinking) -->
            <ellipse cx="40" cy="55" rx="15" ry="0" fill="#818cf8" class="eyelid" id="leftEyelid"/>
            <ellipse cx="80" cy="55" rx="15" ry="0" fill="#818cf8" class="eyelid" id="rightEyelid"/>
            
            <!-- Glass Shine Effect (Animated) -->
            <ellipse cx="35" cy="50" rx="6" ry="4" fill="url(#glassShine)" class="glass-shine left-shine"/>
            <ellipse cx="75" cy="50" rx="6" ry="4" fill="url(#glassShine)" class="glass-shine right-shine"/>
            
            <!-- Beak/Mouth -->
            <path d="M55 72 L60 80 L65 72" fill="#f59e0b" stroke="#d97706" stroke-width="1" class="beak"/>
            
            <!-- Blush -->
            <ellipse cx="25" cy="65" rx="8" ry="4" fill="#fca5a5" opacity="0.6" class="blush left-blush"/>
            <ellipse cx="95" cy="65" rx="8" ry="4" fill="#fca5a5" opacity="0.6" class="blush right-blush"/>
            
            <!-- Wings -->
            <ellipse cx="18" cy="90" rx="12" ry="25" fill="#818cf8" class="wing left-wing"/>
            <ellipse cx="102" cy="90" rx="12" ry="25" fill="#818cf8" class="wing right-wing"/>
            
            <!-- Feet -->
            <ellipse cx="45" cy="132" rx="12" ry="6" fill="#f59e0b" class="foot left-foot"/>
            <ellipse cx="75" cy="132" rx="12" ry="6" fill="#f59e0b" class="foot right-foot"/>
        </svg>
        
        <!-- Status Text -->
        <div class="mascot-status" id="mascotStatus">Ready to help!</div>
    </div>
    `;
}

// Start idle state animations
function startIdleAnimations() {
    // Random blinking
    blinkInterval = setInterval(() => {
        if (currentMascotState === MascotStates.IDLE) {
            blink();
        }
    }, 3000 + Math.random() * 3000);
}

// Blink animation
function blink() {
    const leftEyelid = document.getElementById('leftEyelid');
    const rightEyelid = document.getElementById('rightEyelid');

    if (!leftEyelid || !rightEyelid) return;

    // Close eyes
    leftEyelid.setAttribute('ry', '13');
    rightEyelid.setAttribute('ry', '13');

    // Open eyes after short delay
    setTimeout(() => {
        leftEyelid.setAttribute('ry', '0');
        rightEyelid.setAttribute('ry', '0');
    }, 150);
}

// Handle mouse movement for eye tracking
function handleMouseMove(e) {
    if (currentMascotState === MascotStates.THINKING) return;

    const mascot = document.getElementById('mascot');
    if (!mascot) return;

    const rect = mascot.getBoundingClientRect();
    const mascotCenterX = rect.left + rect.width / 2;
    const mascotCenterY = rect.top + rect.height / 2;

    // Calculate angle to cursor
    const deltaX = e.clientX - mascotCenterX;
    const deltaY = e.clientY - mascotCenterY;

    // Limit eye movement range
    const maxMove = 4;
    const moveX = Math.max(-maxMove, Math.min(maxMove, deltaX / 50));
    const moveY = Math.max(-maxMove, Math.min(maxMove, deltaY / 50));

    // Move pupils
    movePupils(moveX, moveY);
}

// Handle touch movement
function handleTouchMove(e) {
    if (e.touches.length > 0) {
        handleMouseMove({ clientX: e.touches[0].clientX, clientY: e.touches[0].clientY });
    }
}

// Move pupils to follow cursor
function movePupils(offsetX, offsetY) {
    const leftPupil = document.getElementById('leftPupil');
    const rightPupil = document.getElementById('rightPupil');

    if (leftPupil) {
        leftPupil.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
    }
    if (rightPupil) {
        rightPupil.style.transform = `translate(${offsetX}px, ${offsetY}px)`;
    }
}

// Set mascot state
function setMascotState(state) {
    const mascotWrapper = document.querySelector('.mascot-wrapper');
    const statusEl = document.getElementById('mascotStatus');
    const lightbulb = document.getElementById('lightbulb');
    const thinkingBubbles = document.getElementById('thinkingBubbles');
    const sparkles = document.getElementById('sparkles');

    if (!mascotWrapper) return;

    // Remove all state classes
    mascotWrapper.classList.remove('state-idle', 'state-thinking', 'state-eureka', 'state-happy');

    currentMascotState = state;

    switch (state) {
        case MascotStates.THINKING:
            mascotWrapper.classList.add('state-thinking');
            if (statusEl) statusEl.textContent = 'Thinking...';
            if (thinkingBubbles) thinkingBubbles.classList.add('active');
            if (lightbulb) lightbulb.classList.remove('active');
            if (sparkles) sparkles.classList.remove('active');
            startThinkingAnimation();
            break;

        case MascotStates.EUREKA:
            mascotWrapper.classList.add('state-eureka');
            if (statusEl) statusEl.textContent = 'Found it!';
            if (thinkingBubbles) thinkingBubbles.classList.remove('active');
            if (lightbulb) lightbulb.classList.add('active');
            if (sparkles) sparkles.classList.remove('active');
            stopThinkingAnimation();

            // Transition to happy after eureka animation
            setTimeout(() => {
                if (currentMascotState === MascotStates.EUREKA) {
                    setMascotState(MascotStates.HAPPY);
                }
            }, 1500);
            break;

        case MascotStates.HAPPY:
            mascotWrapper.classList.add('state-happy');
            if (statusEl) statusEl.textContent = 'Here you go!';
            if (thinkingBubbles) thinkingBubbles.classList.remove('active');
            if (lightbulb) lightbulb.classList.remove('active');
            if (sparkles) sparkles.classList.add('active');

            // Return to idle after happy animation
            setTimeout(() => {
                if (currentMascotState === MascotStates.HAPPY) {
                    setMascotState(MascotStates.IDLE);
                }
            }, 2000);
            break;

        case MascotStates.IDLE:
        default:
            mascotWrapper.classList.add('state-idle');
            if (statusEl) statusEl.textContent = 'Ready to help!';
            if (thinkingBubbles) thinkingBubbles.classList.remove('active');
            if (lightbulb) lightbulb.classList.remove('active');
            if (sparkles) sparkles.classList.remove('active');
            stopThinkingAnimation();
            break;
    }
}

// Thinking animation (spinning eyes)
function startThinkingAnimation() {
    const leftPupil = document.getElementById('leftPupil');
    const rightPupil = document.getElementById('rightPupil');

    if (leftPupil) leftPupil.classList.add('spinning');
    if (rightPupil) rightPupil.classList.add('spinning');
}

function stopThinkingAnimation() {
    const leftPupil = document.getElementById('leftPupil');
    const rightPupil = document.getElementById('rightPupil');

    if (leftPupil) leftPupil.classList.remove('spinning');
    if (rightPupil) rightPupil.classList.remove('spinning');

    // Reset pupil position
    movePupils(0, 0);
}

// Initialize mascot when DOM is ready
document.addEventListener('DOMContentLoaded', initMascot);

// Export for use in app.js
window.MascotStates = MascotStates;
window.setMascotState = setMascotState;
