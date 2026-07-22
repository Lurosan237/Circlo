/**
 * Circlo Law Enforcement Portal
 * 
 * Requirements: 6.1, 6.2, 6.3, 6.4
 * - Secure web interface for case viewing
 * - Read-only case dashboard
 * - Case status updates and resolution tracking
 */

// Configuration
const API_BASE_URL = 'http://localhost:8000/api/v1/law-enforcement';

// State
let authToken = null;
let currentOfficer = null;

// DOM Elements
const loginSection = document.getElementById('login-section');
const dashboardSection = document.getElementById('dashboard-section');
const loginForm = document.getElementById('login-form');
const loginError = document.getElementById('login-error');
const logoutBtn = document.getElementById('logout-btn');
const officerInfo = document.getElementById('officer-info');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Check for existing session
    const savedToken = sessionStorage.getItem('le_token');
    const savedOfficer = sessionStorage.getItem('le_officer');
    
    if (savedToken && savedOfficer) {
        authToken = savedToken;
        currentOfficer = JSON.parse(savedOfficer);
        showDashboard();
    }
    
    // Setup event listeners
    setupEventListeners();
});

function setupEventListeners() {
    // Login form
    loginForm.addEventListener('submit', handleLogin);
    
    // Logout button
    logoutBtn.addEventListener('click', handleLogout);
    
    // Tab navigation
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
    
    // Access request form
    document.getElementById('access-request-form').addEventListener('submit', handleAccessRequest);
}

// ==================== Authentication ====================

async function handleLogin(e) {
    e.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    // Hash email before sending (in production, use proper crypto library)
    const emailHash = await hashString(email);
    
    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email_hash: emailHash,
                password: password,
            }),
        });
        
        const data = await response.json();
        
        if (data.success) {
            authToken = data.data.access_token;
            currentOfficer = data.data.officer;
            
            // Save to session storage
            sessionStorage.setItem('le_token', authToken);
            sessionStorage.setItem('le_officer', JSON.stringify(currentOfficer));
            
            showDashboard();
        } else {
            showLoginError(data.message || 'Authentication failed');
        }
    } catch (error) {
        console.error('Login error:', error);
        showLoginError('Unable to connect to server. Please try again.');
    }
}

function handleLogout() {
    authToken = null;
    currentOfficer = null;
    sessionStorage.removeItem('le_token');
    sessionStorage.removeItem('le_officer');
    
    loginSection.classList.remove('hidden');
    dashboardSection.classList.add('hidden');
    loginForm.reset();
}

function showLoginError(message) {
    loginError.textContent = message;
    loginError.classList.remove('hidden');
    setTimeout(() => loginError.classList.add('hidden'), 5000);
}

// ==================== Dashboard ====================

function showDashboard() {
    loginSection.classList.add('hidden');
    dashboardSection.classList.remove('hidden');
    
    // Update officer info
    officerInfo.textContent = `Officer ID: ${currentOfficer.id.substring(0, 8)}...`;
    
    // Load initial data
    loadEscalatedCases();
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.add('hidden');
    });
    document.getElementById(`${tabName}-tab`).classList.remove('hidden');
    
    // Load data for the tab
    switch (tabName) {
        case 'escalated':
            loadEscalatedCases();
            break;
        case 'my-cases':
            loadMyCases();
            break;
        case 'audit':
            loadAuditLog();
            break;
    }
}

// ==================== Cases ====================

async function loadEscalatedCases() {
    const container = document.getElementById('escalated-cases-list');
    container.innerHTML = '<div class="loading">Loading cases...</div>';
    
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/cases/escalated`);
        const data = await response.json();
        
        if (data.success && data.data) {
            renderCasesList(container, data.data, true);
        } else {
            container.innerHTML = '<div class="empty-state"><h3>No escalated cases</h3><p>There are no cases currently escalated to law enforcement level.</p></div>';
        }
    } catch (error) {
        console.error('Error loading escalated cases:', error);
        container.innerHTML = '<div class="error-message">Failed to load cases. Please try again.</div>';
    }
}

async function loadMyCases() {
    const container = document.getElementById('my-cases-list');
    container.innerHTML = '<div class="loading">Loading cases...</div>';
    
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/cases`);
        const data = await response.json();
        
        if (data.success && data.data && data.data.length > 0) {
            renderCasesList(container, data.data, false);
        } else {
            container.innerHTML = '<div class="empty-state"><h3>No cases</h3><p>You have not been granted access to any cases yet.</p></div>';
        }
    } catch (error) {
        console.error('Error loading my cases:', error);
        container.innerHTML = '<div class="error-message">Failed to load cases. Please try again.</div>';
    }
}

function renderCasesList(container, cases, showRequestAccess) {
    if (cases.length === 0) {
        container.innerHTML = '<div class="empty-state"><h3>No cases found</h3></div>';
        return;
    }
    
    container.innerHTML = cases.map(caseData => `
        <div class="case-card">
            <div class="case-card-header">
                <div>
                    <div class="case-id">Case ID: ${caseData.case_id.substring(0, 8)}...</div>
                    <div class="case-type">${formatCaseType(caseData.case_type)}</div>
                </div>
                <span class="case-status status-${caseData.status}">${caseData.status}</span>
            </div>
            <div class="case-info">
                <div class="info-item">
                    <span class="info-label">Escalation Level</span>
                    <span class="info-value">${getEscalationLabel(caseData.escalation_level)}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Created</span>
                    <span class="info-value">${formatDate(caseData.created_at)}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Verifications</span>
                    <span class="info-value">${caseData.verification_count}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Participants</span>
                    <span class="info-value">${caseData.active_participants_count}</span>
                </div>
            </div>
            <div class="case-actions">
                ${showRequestAccess ? `
                    <button class="btn btn-primary btn-small" onclick="openAccessModal('${caseData.case_id}')">
                        Request Access
                    </button>
                ` : `
                    <button class="btn btn-primary btn-small" onclick="viewCaseDetail('${caseData.case_id}')">
                        View Details
                    </button>
                `}
            </div>
        </div>
    `).join('');
}

async function viewCaseDetail(caseId) {
    const modal = document.getElementById('case-modal');
    const content = document.getElementById('case-detail-content');
    
    modal.classList.remove('hidden');
    content.innerHTML = '<div class="loading">Loading case details...</div>';
    
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/cases/${caseId}`);
        const data = await response.json();
        
        if (data.success && data.data) {
            renderCaseDetail(content, data.data);
        } else {
            content.innerHTML = `<div class="error-message">${data.message || 'Failed to load case details'}</div>`;
        }
    } catch (error) {
        console.error('Error loading case detail:', error);
        content.innerHTML = '<div class="error-message">Failed to load case details. Please try again.</div>';
    }
}

function renderCaseDetail(container, caseData) {
    container.innerHTML = `
        <div class="case-info">
            <div class="info-item">
                <span class="info-label">Case ID</span>
                <span class="info-value">${caseData.case_id}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Type</span>
                <span class="info-value">${formatCaseType(caseData.case_type)}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Status</span>
                <span class="case-status status-${caseData.status}">${caseData.status}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Escalation Level</span>
                <span class="info-value">${getEscalationLabel(caseData.escalation_level)}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Created</span>
                <span class="info-value">${formatDateTime(caseData.created_at)}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Verifications</span>
                <span class="info-value">${caseData.verification_count} / ${caseData.required_verifications}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Active Participants</span>
                <span class="info-value">${caseData.active_participants_count}</span>
            </div>
            ${caseData.general_area ? `
                <div class="info-item">
                    <span class="info-label">General Area</span>
                    <span class="info-value">${caseData.general_area}</span>
                </div>
            ` : ''}
        </div>
        
        ${caseData.timeline && caseData.timeline.length > 0 ? `
            <div class="timeline">
                <h3>Case Timeline</h3>
                ${caseData.timeline.map(event => `
                    <div class="timeline-item">
                        <span class="timeline-time">${formatDateTime(event.timestamp)}</span>
                        <div>
                            <div class="timeline-event">${formatEventType(event.event_type)}</div>
                            <div class="timeline-description">${event.description}</div>
                        </div>
                    </div>
                `).join('')}
            </div>
        ` : ''}
        
        <p class="notice" style="margin-top: 20px;">
            <strong>Privacy Notice:</strong> Personal information about the missing person and their contacts 
            is not displayed to protect privacy. Only essential case information is shown.
        </p>
    `;
}

function closeModal() {
    document.getElementById('case-modal').classList.add('hidden');
}

// ==================== Access Request ====================

function openAccessModal(caseId) {
    document.getElementById('access-case-id').value = caseId;
    document.getElementById('access-reason').value = '';
    document.getElementById('access-error').classList.add('hidden');
    document.getElementById('access-modal').classList.remove('hidden');
}

function closeAccessModal() {
    document.getElementById('access-modal').classList.add('hidden');
}

async function handleAccessRequest(e) {
    e.preventDefault();
    
    const caseId = document.getElementById('access-case-id').value;
    const reason = document.getElementById('access-reason').value;
    const errorDiv = document.getElementById('access-error');
    
    // Encrypt reason (in production, use proper encryption)
    const encryptedReason = btoa(reason);
    const iv = generateIV();
    
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/cases/access`, {
            method: 'POST',
            body: JSON.stringify({
                alert_id: caseId,
                access_reason_encrypted: encryptedReason,
                iv: iv,
            }),
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeAccessModal();
            alert(data.message || 'Access request submitted successfully');
            
            // Refresh the cases list
            loadEscalatedCases();
            loadMyCases();
        } else {
            errorDiv.textContent = data.message || 'Failed to submit access request';
            errorDiv.classList.remove('hidden');
        }
    } catch (error) {
        console.error('Error submitting access request:', error);
        errorDiv.textContent = 'Failed to submit request. Please try again.';
        errorDiv.classList.remove('hidden');
    }
}

// ==================== Audit Log ====================

async function loadAuditLog() {
    const container = document.getElementById('audit-log-list');
    container.innerHTML = '<div class="loading">Loading audit log...</div>';
    
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/audit`);
        const data = await response.json();
        
        if (data.success && data.data && data.data.length > 0) {
            renderAuditLog(container, data.data);
        } else {
            container.innerHTML = '<div class="empty-state"><h3>No audit entries</h3><p>Your access history will appear here.</p></div>';
        }
    } catch (error) {
        console.error('Error loading audit log:', error);
        container.innerHTML = '<div class="error-message">Failed to load audit log. Please try again.</div>';
    }
}

function renderAuditLog(container, logs) {
    container.innerHTML = logs.map(log => `
        <div class="audit-item">
            <div>
                <div class="audit-action">${formatAuditAction(log.action)}</div>
                <div class="audit-resource">${log.resource_type}${log.resource_id ? `: ${log.resource_id.substring(0, 8)}...` : ''}</div>
            </div>
            <div class="audit-time">${formatDateTime(log.created_at)}</div>
        </div>
    `).join('');
}

// ==================== Utility Functions ====================

async function fetchWithAuth(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`,
        ...options.headers,
    };
    
    const response = await fetch(url, {
        ...options,
        headers,
    });
    
    // Handle token expiry
    if (response.status === 401) {
        handleLogout();
        throw new Error('Session expired');
    }
    
    return response;
}

async function hashString(str) {
    // Simple hash for demo - in production use proper crypto
    const encoder = new TextEncoder();
    const data = encoder.encode(str);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

function generateIV() {
    const array = new Uint8Array(12);
    crypto.getRandomValues(array);
    return Array.from(array).map(b => b.toString(16).padStart(2, '0')).join('');
}

function formatCaseType(type) {
    const types = {
        'missing': 'Missing Person',
        'emergency': 'Emergency',
        'check_in': 'Check-In Request',
    };
    return types[type] || type;
}

function getEscalationLabel(level) {
    const labels = {
        1: 'Inner Circle',
        2: 'Community Circle',
        3: 'Professional Circle',
    };
    return labels[level] || `Level ${level}`;
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString();
}

function formatDateTime(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleString();
}

function formatEventType(eventType) {
    const types = {
        'alert_created': 'Case Created',
        'verification_added': 'Verification Added',
        'alert_verified': 'Case Verified',
        'alert_escalated': 'Case Escalated',
        'alert_force_escalated': 'Case Manually Escalated',
        'alert_resolved': 'Case Resolved',
    };
    return types[eventType] || eventType;
}

function formatAuditAction(action) {
    const actions = {
        'officer_login': 'Logged In',
        'officer_registered': 'Account Registered',
        'case_list_viewed': 'Viewed Case List',
        'case_detail_viewed': 'Viewed Case Details',
        'escalated_cases_viewed': 'Viewed Escalated Cases',
        'case_access_requested': 'Requested Case Access',
        'case_access_revoked': 'Access Revoked',
        'case_access_auto_revoked': 'Access Auto-Revoked',
        'case_notes_added': 'Added Case Notes',
    };
    return actions[action] || action;
}
