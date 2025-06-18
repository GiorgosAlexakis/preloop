// Global variables
let currentUser = null;
let trackers = [];
let apiKeys = [];
let apiUsage = null;
let activeKeyId = null;
let activeTrackerId = null;
let activeLLMModelId = null;
let llm_models_url = '/api/v1/llm-models';
let llmModels = [];

// Data store for duplicates tab with sorting capability
let projectDuplicatesDataStore = {
    duplicates: [],
    projectId: null,
    modelIdUsed: null,
    thresholdUsed: null,
    llmRequestsPending: 0
};

// Helper to initialize tooltips
function initializeTooltips(selector = '[data-bs-toggle="tooltip"]') {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll(selector));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        // Ensure existing tooltips are disposed before creating new ones if necessary
        // For simplicity, Bootstrap 5 handles this reasonably well, but for older versions or complex scenarios, manual disposal might be needed.
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Initialize dashboard
function initializeDashboard() {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    fetchUserProfile();
    setupEventListeners();
    loadDashboardData();
    loadLastActiveTab(); // Restore last active tab
}

// Call initializeDashboard when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function () {
    initializeDashboard();
});

// Check if user is authenticated
function checkAuthStatus() {
    const token = localStorage.getItem('accessToken');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    fetchUserProfile();
}

// Set up event listeners
function setupEventListeners() {

    // Let Bootstrap handle tab switching, and hook into its event system
    // to update the page title. This avoids conflicts with the default tab behavior.
    const tabToggles = document.querySelectorAll('[data-bs-toggle="tab"]');
    tabToggles.forEach(tabToggle => {
        tabToggle.addEventListener('shown.bs.tab', event => {
            document.getElementById('currentPageTitle').textContent = event.target.textContent.trim();
            // Store the active tab and timestamp
            const activeTabData = {
                tabId: event.target.id,
                timestamp: Date.now()
            };
            localStorage.setItem('activeDashboardTab', JSON.stringify(activeTabData));
        });
    });

    // Custom date range toggle
    document.getElementById('dateRangeSelector').addEventListener('change', function() {
        if (this.value === 'custom') {
            document.querySelectorAll('.custom-date-range').forEach(el => el.classList.remove('d-none'));
        } else {
            document.querySelectorAll('.custom-date-range').forEach(el => el.classList.add('d-none'));
        }
    });

    // API key expiry toggle
    document.getElementById('keyExpiry').addEventListener('change', function() {
        if (this.value === 'custom') {
            document.querySelector('.custom-expiry-date').classList.remove('d-none');
        } else {
            document.querySelector('.custom-expiry-date').classList.add('d-none');
        }
    });

    // Tracker type toggle for Jira config and URL auto-population
    document.getElementById('trackerType').addEventListener('change', function() {
        const trackerUrlInput = document.getElementById('trackerUrl');
        const urlHelpText = document.getElementById('urlHelp');
        const tokenHelpLink = document.getElementById('tokenHelpLink');
        const jiraConfigSection = document.getElementById('jiraConfigSection');
        const jiraUsernameInput = document.getElementById('jiraUsername');

        // Handle Jira specific fields
        if (this.value === 'jira') {
            jiraConfigSection.classList.remove('d-none');
            jiraUsernameInput.setAttribute('required', 'required');
        } else {
            jiraConfigSection.classList.add('d-none');
            jiraUsernameInput.removeAttribute('required');
        }

        // Auto-populate URL and update help text
        switch(this.value) {
            case 'github':
                trackerUrlInput.value = 'https://api.github.com';
                urlHelpText.textContent = 'Default GitHub API URL. Edit for GitHub Enterprise.';
                tokenHelpLink.href = 'https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token';
                trackerUrlInput.readOnly = false; // Always allow editing
                break;
            case 'gitlab':
                trackerUrlInput.value = 'https://gitlab.com'; // Base URL, API path handled by backend/client
                urlHelpText.textContent = 'Default GitLab URL (gitlab.com). Edit for self-hosted instances.';
                tokenHelpLink.href = 'https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html';
                trackerUrlInput.readOnly = false; // Always allow editing
                break;
            case 'jira':
                // trackerUrlInput.value = ''; // Clear or leave as is for manual input
                urlHelpText.textContent = 'Your Jira instance URL, e.g., https://yourcompany.atlassian.net';
                tokenHelpLink.href = 'https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/';
                trackerUrlInput.readOnly = false; // Always allow editing
                break;
            default:
                // trackerUrlInput.value = ''; // Clear or leave as is
                urlHelpText.textContent = 'The base URL of your tracker instance.';
                tokenHelpLink.href = '#';
                trackerUrlInput.readOnly = false; // Always allow editing
        }
    });

    // Create API key
    document.getElementById('createKeyBtn').addEventListener('click', function() {
        createApiKey();
    });

    // Copy API key
    document.getElementById('copyKeyBtn').addEventListener('click', function() {
        const keyValue = document.getElementById('newKeyValue').textContent;
        navigator.clipboard.writeText(keyValue)
            .then(() => {
                this.innerHTML = '<i class="bi bi-check"></i> Copied!';
                setTimeout(() => {
                    this.innerHTML = '<i class="bi bi-clipboard"></i> Copy to Clipboard';
                }, 2000);
            })
            .catch(err => {
                console.error('Could not copy text: ', err);
            });
    });

    // Confirm delete API key
    document.getElementById('confirmDeleteKeyBtn').addEventListener('click', function() {
        if (activeKeyId) {
            deleteApiKey(activeKeyId);
        }
    });

    // Confirm delete tracker
    document.getElementById('confirmDeleteTrackerBtn').addEventListener('click', function() {
        if (activeTrackerId) {
            deleteTracker(activeTrackerId);
        }
    });

    // Update profile form
    document.getElementById('updateProfileForm').addEventListener('submit', function(e) {
        e.preventDefault();
        updateProfile();
    });

    // Change password form
    document.getElementById('changePasswordForm').addEventListener('submit', function(e) {
        e.preventDefault();
        changePassword();
    });

    // Password confirmation validation
    document.getElementById('confirmNewPassword').addEventListener('input', function() {
        const newPassword = document.getElementById('newPassword').value;
        if (this.value !== newPassword) {
            this.setCustomValidity('Passwords do not match');
        } else {
            this.setCustomValidity('');
        }
    });

    // Update API usage when date range changes
    document.getElementById('dateRangeSelector').addEventListener('change', fetchApiUsage);
    document.getElementById('startDate').addEventListener('change', fetchApiUsage);
    document.getElementById('endDate').addEventListener('change', fetchApiUsage);
}

// Fetch user profile
function fetchUserProfile() {
    fetch('/api/v1/auth/users/me', {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else if (response.status === 401) {
            // Try to refresh the token
            return refreshToken().then(() => fetchUserProfile());
        } else {
            throw new Error('Failed to fetch user profile');
        }
    })
    .then(data => {
        currentUser = data;

        // Update UI with user info
        document.getElementById('username').textContent = data.username;
        document.getElementById('email').textContent = data.email;
        document.getElementById('userUsername').value = data.username;
        document.getElementById('userEmail').value = data.email;
        document.getElementById('userFullName').value = data.full_name || '';

        const emailVerifiedStatus = document.getElementById('emailVerificationStatus');
        if (data.email_verified) {
            emailVerifiedStatus.textContent = 'Email verified';
            emailVerifiedStatus.classList.add('text-success');
        } else {
            emailVerifiedStatus.innerHTML = 'Email not verified. <a href="#" id="resendVerificationLink">Resend verification email</a>';
            emailVerifiedStatus.classList.add('text-danger');

            // Add event listener for resend link
            document.getElementById('resendVerificationLink').addEventListener('click', function(e) {
                e.preventDefault();
                resendVerificationEmail();
            });
        }

        // Load data for dashboard
        loadDashboardData();
    })
    .catch(error => {
        console.error('Error:', error);
        logout();
    });
}

// Refresh token
function refreshToken() {
    const refreshToken = localStorage.getItem('refreshToken');
    if (!refreshToken) {
        logout();
        return Promise.reject('No refresh token available');
    }

    return fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ refresh_token: refreshToken })
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Failed to refresh token');
        }
    })
    .then(data => {
        localStorage.setItem('accessToken', data.access_token);
        localStorage.setItem('refreshToken', data.refresh_token);
        localStorage.setItem('tokenExpires', Date.now() + (data.expires_in * 1000));
        return data;
    })
    .catch(error => {
        console.error('Error refreshing token:', error);
        logout();
        return Promise.reject(error);
    });
}

// Logout
function logout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('tokenExpires');
    window.location.href = '/login';
}

// Load all dashboard data
function loadDashboardData() {
    // Fetch trackers
    fetchTrackers();

    // Fetch API tokens
    fetchApiKeys();

    // Fetch API usage statistics
    fetchApiUsage();

    // Fetch projects for duplicates tab
    loadProjectsForDuplicatesTab();

    // Fetch LLM models
    loadLLMModels();
}

// Render trackers
function renderTrackers() {
    const trackersList = document.getElementById('trackersList');
    const trackersListFull = document.getElementById('trackersListFull');

    if (trackers.length >= 1) {
        // Render summary list for dashboard
        let trackerItems = '';
        trackers.slice(0, 3).forEach(tracker => {
            let iconClass = '';
            let badgeClass = '';

            switch(tracker.type) {
                case 'github':
                    iconClass = 'github-color';
                    badgeClass = 'badge-github';
                    break;
                case 'gitlab':
                    iconClass = 'gitlab-color';
                    badgeClass = 'badge-gitlab';
                    break;
                case 'jira':
                    iconClass = 'jira-color';
                    badgeClass = 'badge-jira';
                    break;
                default:
                    // Fallback for undefined
                    iconClass = 'text-secondary';
                    badgeClass = 'badge-secondary';
            }

            trackerItems += `
                <div class="d-flex align-items-center p-3 border-bottom">
                    <i class="bi bi-${tracker.type === 'jira' ? 'kanban' : 'git'} fs-4 ${iconClass} me-3"></i>
                    <div>
                        <h6 class="mb-0">${tracker.name}</h6>
                        <span class="badge ${badgeClass}">${tracker.type || 'unknown'}</span>
                    </div>
                </div>
            `;
        });

        if (trackers.length > 3) {
            trackerItems += `
                <div class="text-center p-2">
                    <a href="#trackers-tab" class="btn btn-sm btn-link" data-bs-toggle="tab">
                        View all ${trackers.length} trackers
                    </a>
                </div>
            `;
        }

        trackersList.innerHTML = trackerItems;

        // Render full list for trackers tab
        let trackerCards = '<div class="row">';
        trackers.forEach(tracker => {
            let iconClass = '';
            let iconName = '';

            switch(tracker.type) {
                case 'github':
                    iconClass = 'github-color';
                    iconName = 'github';
                    break;
                case 'gitlab':
                    iconClass = 'gitlab-color';
                    iconName = 'gitlab';
                    break;
                case 'jira':
                    iconClass = 'jira-color';
                    iconName = 'kanban';
                    break;
                default:
                    // Fallback for undefined
                    iconClass = 'text-secondary';
                    iconName = 'gear';
            }

            trackerCards += `
                <div class="col-md-4 mb-4">
                    <div class="tracker-card p-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <div class="d-flex align-items-center">
                                <i class="bi bi-${iconName} fs-2 ${iconClass} me-2"></i>
                                <h5 class="mb-0">${tracker.name}</h5>
                            </div>
                            <span class="badge bg-${tracker.tracker_type === 'github' ? 'dark' : tracker.tracker_type === 'gitlab' ? 'danger' : 'primary'}">${tracker.tracker_type ? tracker.tracker_type.charAt(0).toUpperCase() + tracker.tracker_type.slice(1) : 'Unknown'}</span>
                        </div>
                        <p class="text-muted mb-3 small">${tracker.url}</p>
                        <div class="d-flex justify-content-between align-items-center">
                            <small class="text-muted">Created: ${tracker.created ? new Date(tracker.created).toLocaleDateString() : 'Unknown'}</small>
                            <div>
                                <button class="btn btn-sm btn-outline-secondary edit-tracker-btn me-1" data-tracker-id="${tracker.id}">
                                    <i class="bi bi-pencil"></i> Edit
                                </button>
                                <button class="btn btn-sm btn-outline-danger delete-tracker-btn" data-tracker-id="${tracker.id}" data-tracker-name="${tracker.name}">
                                    <i class="bi bi-trash"></i> Delete
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        trackerCards += '</div>';

        trackersListFull.innerHTML = trackerCards;
    }

    // Add event listeners to delete buttons
    document.querySelectorAll('.delete-tracker-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            activeTrackerId = this.getAttribute('data-tracker-id');
            const trackerName = this.getAttribute('data-tracker-name');
            document.getElementById('deleteTrackerName').textContent = trackerName;
            const deleteModal = new bootstrap.Modal(document.getElementById('deleteTrackerModal'));
            deleteModal.show();
        });
    });
}

// Fetch API keys
function fetchApiKeys() {
    fetch('/api/v1/auth/api-keys', {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else if (response.status === 401) {
            return refreshToken().then(() => fetchApiKeys());
        } else {
            throw new Error('Failed to fetch API keys');
        }
    })
    .then(data => {
        apiKeys = data;
        renderApiKeys();
    })
    .catch(error => {
        console.error('Error fetching API keys:', error);
    });
}

// Render API keys
function renderApiKeys() {
    const keysList = document.getElementById('apiKeysList');

    if (apiKeys.length === 0) {
        keysList.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-4">
                    <p class="text-muted mb-0">No API keys created yet</p>
                </td>
            </tr>
        `;
        return;
    }

    let keyRows = '';
    apiKeys.forEach(key => {
        const createdDate = new Date(key.created_at).toLocaleDateString();
        const lastUsed = key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never used';
        const expires = key.expires_at ? new Date(key.expires_at).toLocaleDateString() : 'Never';

        keyRows += `
            <tr>
                <td>${key.name}</td>
                <td>${createdDate}</td>
                <td>${lastUsed}</td>
                <td>${expires}</td>
                <td>
                    <button class="btn btn-sm btn-outline-danger delete-key-btn" data-key-id="${key.id}" data-key-name="${key.name}">
                        <i class="bi bi-trash"></i> Revoke
                    </button>
                </td>
            </tr>
        `;
    });

    keysList.innerHTML = keyRows;

    // Add event listeners to delete buttons
    document.querySelectorAll('.delete-key-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            activeKeyId = this.getAttribute('data-key-id');
            const keyName = this.getAttribute('data-key-name');
            document.getElementById('deleteKeyName').textContent = keyName;
            const deleteModal = new bootstrap.Modal(document.getElementById('deleteKeyModal'));
            deleteModal.show();
        });
    });
}

// Fetch API usage statistics
function fetchApiUsage() {
    // Get date range parameters
    let params = new URLSearchParams();
    const dateRange = document.getElementById('dateRangeSelector').value;

    if (dateRange === 'custom') {
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;

        if (startDate) {
            params.append('start_date', new Date(startDate).toISOString());
        }
        if (endDate) {
            params.append('end_date', new Date(endDate + 'T23:59:59').toISOString());
        }
    } else {
        // Calculate start date based on selected range
        const now = new Date();
        let startDate = new Date();

        switch(dateRange) {
            case '7days':
                startDate.setDate(now.getDate() - 7);
                break;
            case '30days':
                startDate.setDate(now.getDate() - 30);
                break;
            case '90days':
                startDate.setDate(now.getDate() - 90);
                break;
        }

        params.append('start_date', startDate.toISOString());
        params.append('end_date', now.toISOString());
    }

    fetch(`/api/v1/auth/api-usage?${params.toString()}`, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else if (response.status === 401) {
            return refreshToken().then(() => fetchApiUsage());
        } else {
            throw new Error('Failed to fetch API usage');
        }
    })
    .then(data => {
        apiUsage = data;
        renderApiUsageStats();
        updateDashboardStats();
    })
    .catch(error => {
        console.error('Error fetching API usage:', error);
    });
}

// Render API usage statistics
function renderApiUsageStats() {
    if (!apiUsage) return;

    // Render endpoints list
    const endpointsList = document.getElementById('endpointsList');
    const endpoints = Object.entries(apiUsage.requests_by_endpoint)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);

    if (endpoints.length === 0) {
        endpointsList.innerHTML = '<p class="text-muted text-center">No API usage data available</p>';
        return;
    }

    let endpointsHtml = '';
    endpoints.forEach(([endpoint, count]) => {
        // Simplify endpoint path
        const simplifiedEndpoint = endpoint.split('/').slice(-2).join('/');

        endpointsHtml += `
            <div class="d-flex justify-content-between mb-2">
                <small title="${endpoint}">${simplifiedEndpoint}</small>
                <span class="badge bg-primary">${count}</span>
            </div>
        `;
    });

    endpointsList.innerHTML = endpointsHtml;

    // Render usage chart
    renderUsageCharts();
}

// Render usage charts
function renderUsageCharts() {
    if (!apiUsage) return;

    // Main dashboard chart
    const dashboardChartCtx = document.getElementById('apiUsageChart').getContext('2d');

    // Sort dates
    const sortedDates = Object.keys(apiUsage.requests_by_date).sort();
    const data = sortedDates.map(date => apiUsage.requests_by_date[date]);

    // Dashboard chart
    if (window.dashboardChart) {
        window.dashboardChart.destroy();
    }

    window.dashboardChart = new Chart(dashboardChartCtx, {
        type: 'line',
        data: {
            labels: sortedDates,
            datasets: [{
                label: 'API Requests',
                data: data,
                borderColor: '#4a86e8',
                backgroundColor: 'rgba(74, 134, 232, 0.1)',
                borderWidth: 2,
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });

    // Detailed usage chart
    const detailChartCtx = document.getElementById('apiUsageDetailChart').getContext('2d');

    if (window.detailChart) {
        window.detailChart.destroy();
    }

    window.detailChart = new Chart(detailChartCtx, {
        type: 'bar',
        data: {
            labels: sortedDates,
            datasets: [{
                label: 'API Requests',
                data: data,
                backgroundColor: '#4a86e8'
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'API Requests by Date'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            }
        }
    });

    // Issue actions chart
    const issueActionsCtx = document.getElementById('issueActionsChart').getContext('2d');

    if (window.issueActionsChart && typeof window.issueActionsChart.destroy === 'function') {
        window.issueActionsChart.destroy();
    }

    window.issueActionsChart = new Chart(issueActionsCtx, {
        type: 'doughnut',
        data: {
            labels: ['Created', 'Updated', 'Closed'],
            datasets: [{
                data: [
                    apiUsage.issues_created,
                    apiUsage.issues_updated,
                    apiUsage.issues_closed
                ],
                backgroundColor: [
                    '#4CAF50',
                    '#2196F3',
                    '#F44336'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// Update dashboard statistics
function updateDashboardStats() {
    document.getElementById('totalTrackers').textContent = trackers.length;

    if (apiUsage) {
        document.getElementById('totalRequests').textContent = apiUsage.total_requests;
        const totalIssues = apiUsage.issues_created + apiUsage.issues_updated + apiUsage.issues_closed;
        document.getElementById('totalIssues').textContent = totalIssues;
    }
}

// --- Duplicates Tab Logic ---
async function loadProjectsForDuplicatesTab() {
    const selectElement = document.getElementById('projectSelect');
    try {
        const response = await fetch('/api/v1/projects', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
            }
        });

        if (response.ok) {
            const projects = await response.json();
            selectElement.innerHTML = '<option selected disabled>Select a project...</option>'; // Clear loading text
            if (projects.length > 0) {
                projects.forEach(project => {
                    const option = document.createElement('option');
                    option.value = project.id;
                    option.textContent = project.name;
                    selectElement.appendChild(option);
                });
            } else {
                selectElement.innerHTML = '<option selected disabled>No projects found</option>';
            }
        } else if (response.status === 401) {
            await refreshToken();
            await loadProjectsForDuplicatesTab(); // Retry
        } else {
            selectElement.innerHTML = '<option selected disabled>Error loading projects</option>';
            console.error('Failed to load projects for duplicates tab');
        }
    } catch (error) {
        selectElement.innerHTML = '<option selected disabled>Error loading projects</option>';
        console.error('Error fetching projects:', error);
    }
}

// --- Fetch and Render Project Duplicates ---
async function fetchProjectDuplicates(projectId) {
    const resultArea = document.getElementById('duplicates-result-area');
    resultArea.innerHTML = '<p class="text-center"><i class="bi bi-hourglass-split"></i> Loading issues...</p>';

    if (!projectId) {
        resultArea.innerHTML = '<p class="text-muted text-center">Please select a project.</p>';
        return;
    }

    try {
        const response = await fetch(`/api/v1/projects/${projectId}/duplicates`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
            }
        });
        if (!response.ok) {
            if (response.status === 401) {
                await refreshToken();
                return fetchProjectDuplicates(projectId); // Retry
            }
            // Try to parse error response, default if parsing fails
            const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch duplicates after token refresh.' }));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        renderDuplicates(data);
    } catch (error) { // Catch network errors or other unexpected issues during fetch itself
        console.error('Error fetching project duplicates:', error);
        resultArea.innerHTML = `<div class="alert alert-danger" role="alert">Error fetching duplicates: ${error.message}</div>`;
    }
}

function renderDuplicates(data) {
    console.log("Rendering duplicates with data:", data);
    const resultArea = document.getElementById('duplicates-result-area'); // Ensure this ID matches your HTML
    if (!data || !data.duplicates || data.duplicates.length === 0) {
        resultArea.innerHTML = '<p>No potential duplicates found with the current settings.</p>';
        return;
    }

    // Initialize data store
    projectDuplicatesDataStore.duplicates = data.duplicates.map(pair => ({
        ...pair,
        llm_decision_status: 'loading', // Initial status
        llm_decision_details: null      // To store the full response from LLM check
    }));
    projectDuplicatesDataStore.projectId = data.project_id_used;
    projectDuplicatesDataStore.modelIdUsed = data.model_id_used;
    projectDuplicatesDataStore.thresholdUsed = data.threshold_used;
    projectDuplicatesDataStore.llmRequestsPending = data.duplicates.length;

    let tableHtml = `
        <p>Showing ${projectDuplicatesDataStore.duplicates.length} potential duplicate pairs.</p>
        <table class="table table-hover duplicates-table">
            <thead>
                <tr>
                    <th>Issue IDs</th>
                    <th>Titles</th>
                    <th>Similarity</th>
                    <th class="text-center">LLM Check</th>
                </tr>
            </thead>
            <tbody id="duplicatesTableBody">
    `; // Added id to tbody

    // Initial render (unsorted, with spinners)
    projectDuplicatesDataStore.duplicates.forEach((pairData) => {
        const issue1 = pairData.issue1;
        const issue2 = pairData.issue2;
        // Use actual issue IDs for unique and stable row/detail IDs
        const stableIdSuffix = `${issue1.id}-${issue2.id}`;
        const detailRowId = `details-row-${stableIdSuffix}`;
        const rowId = `duplicate-row-${stableIdSuffix}`;
        const llmCellId = `llm-check-${stableIdSuffix}`;

        tableHtml += `
            <tr id="${rowId}" onclick="toggleDetails('${detailRowId}')" style="cursor: pointer;" title="Click to see details">
                <td>
                    <div>${issue1.external_id || issue1.id.substring(0,8)}</div>
                    <div>${issue2.external_id || issue2.id.substring(0,8)}</div>
                </td>
                <td>
                    <div>${truncateText(issue1.title, 50)}</div>
                    <div>${truncateText(issue2.title, 50)}</div>
                </td>
                <td>${(pairData.similarity * 100).toFixed(2)}%</td>
                <td id="${llmCellId}" class="text-center align-middle">
                    <div class="spinner-border spinner-border-sm" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </td>
            </tr>
            <tr id="${detailRowId}" class="duplicate-details-row" style="display: none;">
                <td colspan="4">
                    <h6>Issue 1: ${truncateText(issue1.title, 100)} (${issue1.external_id || issue1.id})</h6>
                    <p><strong>Description:</strong><br>${issue1.description ? truncateText(issue1.description.replace(/\n/g, '<br>'), 300) : 'No description'}</p>
                    <h6>Issue 2: ${truncateText(issue2.title, 100)} (${issue2.external_id || issue2.id})</h6>
                    <p><strong>Description:</strong><br>${issue2.description ? truncateText(issue2.description.replace(/\n/g, '<br>'), 300) : 'No description'}</p>
                </td>
            </tr>
        `;
    });

    tableHtml += `
            </tbody>
        </table>
    `;
    resultArea.innerHTML = tableHtml;
    initializeTooltips(); // Initialize tooltips for title attributes on rows

    // Fetch LLM decisions for each pair
    projectDuplicatesDataStore.duplicates.forEach((pairData) => {
        const issue1Id = pairData.issue1.id;
        const issue2Id = pairData.issue2.id;
        const llmCellId = `llm-check-${issue1Id}-${issue2Id}`;
        const rowId = `duplicate-row-${issue1Id}-${issue2Id}`;
        // Pass the pairData object by reference so fetchLLMDuplicateDecision can update it
        fetchLLMDuplicateDecision(projectDuplicatesDataStore.projectId, issue1Id, issue2Id, llmCellId, rowId, pairData);
    });
}

async function fetchLLMDuplicateDecision(projectId, issue1Id, issue2Id, cellId, rowId, pairDataRef) {
    const cellElement = document.getElementById(cellId);
    const rowElement = document.getElementById(rowId);

    try {
        const response = await fetch(`/api/v1/issue-duplicates/check?issue1_id=${encodeURIComponent(issue1Id)}&issue2_id=${encodeURIComponent(issue2Id)}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('accessToken')}`,
                'Content-Type': 'application/json'
            },
        });

        let decisionResult;
        if (!response.ok) {
            if (response.status === 401) {
                await refreshToken();
                return fetchLLMDuplicateDecision(projectId, issue1Id, issue2Id, cellId, rowId, pairDataRef); // Retry
            }
            // Try to parse error response, default if parsing fails
            const errorData = await response.json().catch(() => ({ detail: 'LLM check failed with non-JSON response.' }));
            decisionResult = { decision: 'error', detail: errorData.detail || `HTTP error! status: ${response.status}` };
        } else {
            decisionResult = await response.json();
        }

        // Update the data store
        pairDataRef.llm_decision_details = decisionResult; // Store full details
        pairDataRef.llm_decision_status = decisionResult.decision; // Store just the decision string for sorting

        if (decisionResult.decision === 'error') {
             console.error(`LLM check error for ${issue1Id} & ${issue2Id}:`, decisionResult.detail);
        }

        // Update the specific cell immediately
        let iconHtml = '';
        let tooltipText = '';

        switch (pairDataRef.llm_decision_status) {
            case 'confirmed':
                iconHtml = '<i class="bi bi-check-circle-fill text-success llm-status-icon"></i>';
                tooltipText = `LLM Decision: Confirmed`;
                break;
            case 'rejected':
                iconHtml = '<i class="bi bi-x-circle-fill text-danger llm-status-icon"></i>';
                tooltipText = `LLM Decision: Rejected`;
                rowElement.classList.add('issue-rejected');
                break;
            case 'undecided':
                iconHtml = '<i class="bi bi-question-circle-fill text-warning llm-status-icon"></i>';
                tooltipText = `LLM Decision: Undecided`;
                break;
            case 'error':
                iconHtml = '<i class="bi bi-exclamation-triangle-fill text-danger llm-status-icon"></i>';
                tooltipText = `Error: ${pairDataRef.llm_decision_details.detail || 'Failed to get LLM decision.'}`;
                break;
            case 'loading': // Should ideally not be 'loading' when re-rendering after all calls
                iconHtml = '<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div>';
                tooltipText = 'LLM Check: Loading...';
                break;
            default:
                iconHtml = `<i class="bi bi-slash-circle text-muted llm-status-icon"></i>`;
                tooltipText = `Status: ${pairDataRef.llm_decision_status}`;
        }

        // Add more details to tooltip if available and not an error
        if (pairDataRef.llm_decision_details && pairDataRef.llm_decision_status !== 'error' && pairDataRef.llm_decision_status !== 'loading') {
             tooltipText += `\nChecked at: ${new Date(pairDataRef.llm_decision_details.decision_at || pairDataRef.llm_decision_details.created_at).toLocaleString()}`;
             tooltipText += `\nLLM: ${pairDataRef.llm_decision_details.llm_model_name}`;
        }

        if (cellElement) {
            cellElement.innerHTML = `<span data-bs-toggle="tooltip" data-bs-placement="top" title="${tooltipText.replace(/"/g, '&quot;')}">${iconHtml}</span>`;
            // Re-initialize tooltip for this specific new element
            if (cellElement.querySelector('[data-bs-toggle="tooltip"]')) {
                 new bootstrap.Tooltip(cellElement.querySelector('[data-bs-toggle="tooltip"]'));
            }
        } else {
            console.warn("Could not find cellElement to update: ", cellId);
        }

    } catch (error) { // Catch network errors or other unexpected issues during fetch itself
        console.error(`Critical error in fetchLLMDuplicateDecision for ${issue1Id} & ${issue2Id}:`, error);
        pairDataRef.llm_decision_status = 'error';
        pairDataRef.llm_decision_details = { detail: error.message || 'Network error or critical failure during fetch.' };
        if (cellElement) {
            const errorTooltipText = `Error: ${pairDataRef.llm_decision_details.detail}`;
            cellElement.innerHTML = `<span data-bs-toggle="tooltip" data-bs-placement="top" title="${errorTooltipText.replace(/"/g, '&quot;')}"><i class="bi bi-exclamation-triangle-fill text-danger llm-status-icon"></i></span>`;
            if (cellElement.querySelector('[data-bs-toggle="tooltip"]')) {
                 new bootstrap.Tooltip(cellElement.querySelector('[data-bs-toggle="tooltip"]'));
            }
        }
    } finally {
        projectDuplicatesDataStore.llmRequestsPending--;
        sortAndReRenderDuplicatesTable();
    }
}

function sortAndReRenderDuplicatesTable() {
    const decisionOrder = {
        'confirmed': 0,
        'undecided': 1,
        'rejected': 2,
        'error': 3,    // Errors after rejected
        'loading': 4   // Loading last (should ideally not be 'loading' if all requests are done)
    };

    projectDuplicatesDataStore.duplicates.sort((a, b) => {
        const statusA = decisionOrder[a.llm_decision_status] !== undefined ? decisionOrder[a.llm_decision_status] : 99; // Default for unknown statuses
        const statusB = decisionOrder[b.llm_decision_status] !== undefined ? decisionOrder[b.llm_decision_status] : 99;

        if (statusA !== statusB) {
            return statusA - statusB;
        }
        return b.similarity - a.similarity; // Secondary sort: by similarity descending
    });

    const tableBody = document.getElementById('duplicatesTableBody');
    if (!tableBody) {
        console.error('Could not find duplicatesTableBody to re-render.');
        return;
    }

    let newTableBodyHtml = '';
    projectDuplicatesDataStore.duplicates.forEach((pairData) => {
        const issue1 = pairData.issue1;
        const issue2 = pairData.issue2;
        const stableIdSuffix = `${issue1.id}-${issue2.id}`;
        const detailRowId = `details-row-${stableIdSuffix}`;
        const rowId = `duplicate-row-${stableIdSuffix}`;

        let iconHtml = '';
        let tooltipText = '';
        let rowClass = '';

        switch (pairData.llm_decision_status) {
            case 'confirmed':
                iconHtml = '<i class="bi bi-check-circle-fill text-success llm-status-icon"></i>';
                tooltipText = `LLM Decision: Confirmed`;
                break;
            case 'rejected':
                iconHtml = '<i class="bi bi-x-circle-fill text-danger llm-status-icon"></i>';
                tooltipText = `LLM Decision: Rejected`;
                rowClass = 'issue-rejected';
                break;
            case 'undecided':
                iconHtml = '<i class="bi bi-question-circle-fill text-warning llm-status-icon"></i>';
                tooltipText = `LLM Decision: Undecided`;
                break;
            case 'error':
                iconHtml = '<i class="bi bi-exclamation-triangle-fill text-danger llm-status-icon"></i>';
                tooltipText = `Error: ${pairData.llm_decision_details && pairData.llm_decision_details.detail ? pairData.llm_decision_details.detail : 'Failed to get LLM decision.'}`;
                break;
            case 'loading': // Should ideally not be 'loading' when re-rendering after all calls
                iconHtml = '<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div>';
                tooltipText = 'LLM Check: Loading...';
                break;
            default:
                iconHtml = `<i class="bi bi-slash-circle text-muted llm-status-icon"></i>`;
                tooltipText = `Status: ${pairData.llm_decision_status}`;
        }

        if (pairData.llm_decision_details && pairData.llm_decision_status !== 'error' && pairData.llm_decision_status !== 'loading') {
            tooltipText += `\nChecked at: ${new Date(pairData.llm_decision_details.decision_at || pairData.llm_decision_details.created_at).toLocaleString()}`;
            tooltipText += `\nLLM: ${pairData.llm_decision_details.llm_model_name}`;
        }

        newTableBodyHtml += `
            <tr id="${rowId}" class="${rowClass}" onclick="toggleDetails('${detailRowId}')" style="cursor: pointer;" title="Click to see details">
                <td>
                    <div>${issue1.external_id || issue1.id.substring(0,8)}</div>
                    <div>${issue2.external_id || issue2.id.substring(0,8)}</div>
                </td>
                <td>
                    <div>${truncateText(issue1.title, 50)}</div>
                    <div>${truncateText(issue2.title, 50)}</div>
                </td>
                <td>${(pairData.similarity * 100).toFixed(2)}%</td>
                <td class="text-center align-middle">
                    <span data-bs-toggle="tooltip" data-bs-placement="top" title="${tooltipText.replace(/"/g, '&quot;')}">${iconHtml}</span>
                </td>
            </tr>
            <tr id="${detailRowId}" class="duplicate-details-row" style="display: none;">
                <td colspan="4">
                    <h6>Issue 1: ${truncateText(issue1.title, 100)} (${issue1.external_id || issue1.id})</h6>
                    <p><strong>Description:</strong><br>${issue1.description ? truncateText(issue1.description.replace(/\n/g, '<br>'), 300) : 'No description'}</p>
                    <h6>Issue 2: ${truncateText(issue2.title, 100)} (${issue2.external_id || issue2.id})</h6>
                    <p><strong>Description:</strong><br>${issue2.description ? truncateText(issue2.description.replace(/\n/g, '<br>'), 300) : 'No description'}</p>
                </td>
            </tr>
        `;
    });

    tableBody.innerHTML = newTableBodyHtml;
    initializeTooltips('#duplicatesTableBody [data-bs-toggle="tooltip"]'); // Re-initialize tooltips for the new content
}

// Add event listener for project selection dropdown
const projectSelectElement = document.getElementById('projectSelect');
if (projectSelectElement) {
    projectSelectElement.addEventListener('change', function() {
        const selectedProjectId = this.value;
        if (selectedProjectId) {
            fetchProjectDuplicates(selectedProjectId);
        } else {
            const resultArea = document.getElementById('duplicatesResultArea');
            resultArea.innerHTML = '<p class="text-muted text-center">Please select a project.</p>';
        }
    });
}

function toggleDetails(detailsRowId) {
    console.log(`toggleDetails called for: ${detailsRowId}`); // Log when function is called
    const detailsRow = document.getElementById(detailsRowId);
    if (detailsRow) {
        console.log(`Details row found. Current display: ${detailsRow.style.display}`); // Log current state
        if (detailsRow.style.display === 'none' || detailsRow.style.display === '') {
            detailsRow.style.display = 'table-row'; // Show the row
            console.log(`Details row set to display: 'table-row'`);
        } else {
            detailsRow.style.display = 'none'; // Hide the row
            console.log(`Details row set to display: 'none'`);
        }
    } else {
        console.error(`Details row with ID ${detailsRowId} not found!`);
    }
}

// LLM Models Section
const llmModelModal = new bootstrap.Modal(document.getElementById('llmModelModal'));
const llmModelForm = document.getElementById('llmModelForm');
const saveLLMModelBtn = document.getElementById('saveLLMModelBtn');
const addLLMModelBtn = document.getElementById('addLLMModelBtn');
const deleteLLMModelModal = new bootstrap.Modal(document.getElementById('deleteLLMModelModal'));
const llmModelProviderSelect = document.getElementById('llmModelProvider');
const llmModelApiUrlInput = document.getElementById('llmModelApiUrl');

const providerUrls = {
    'openai': 'https://api.openai.com/v1',
    'anthropic': 'https://api.anthropic.com/v1',
    'google': 'https://generativelanguage.googleapis.com/v1beta'
};

if (llmModelProviderSelect) {
    llmModelProviderSelect.addEventListener('change', () => {
        const selectedProvider = llmModelProviderSelect.value;
        const apiUrl = providerUrls[selectedProvider] || '';
        if (llmModelApiUrlInput) {
            llmModelApiUrlInput.value = apiUrl;
            llmModelApiUrlInput.readOnly = selectedProvider !== 'custom';
            if (selectedProvider === 'custom') {
                llmModelApiUrlInput.placeholder = 'Enter custom API URL';
            }
        }
    });
}

function loadLLMModels() {
    fetch(llm_models_url, {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
    })
    .then(response => response.json())
    .then(data => {
        llmModels = data;
        renderLLMModelsTable(data);
    })
    .catch(error => console.error('Error fetching LLM models:', error));
}

function renderLLMModelsTable(models) {
    const tableBody = document.getElementById('llmModelsListBody');
    const noModelsAlert = document.getElementById('noLLMModelsAlert');

    if (models.length === 0) {
        tableBody.innerHTML = '';
        noModelsAlert.classList.remove('d-none');
        return;
    }

    noModelsAlert.classList.add('d-none');
    tableBody.innerHTML = models.map(model => `
        <tr>
            <td>${model.name}</td>
            <td><span class="badge bg-secondary">${model.provider_name}</span></td>
            <td><code>${model.model_name}</code></td>
            <td>
                <button
                    class="btn btn-sm ${model.is_default ? 'btn-success' : 'btn-outline-secondary'}"
                    onclick="setDefaultLLMModel('${model.id}')"
                    ${model.is_default ? 'disabled' : ''}>
                    ${model.is_default ? 'Default' : 'Set Default'}
                </button>
            </td>
            <td>
                <button class="btn btn-sm btn-outline-primary" onclick="editLLMModel('${model.id}')"><i class="bi bi-pencil"></i></button>
                <button class="btn btn-sm btn-outline-danger" onclick="confirmDeleteLLMModel('${model.id}', '${model.name}')"><i class="bi bi-trash"></i></button>
            </td>
        </tr>
    `).join('');
}

if (addLLMModelBtn) {
    addLLMModelBtn.addEventListener('click', () => {
        activeLLMModelId = null;
        document.getElementById('llmModelModalLabel').textContent = 'Add LLM Model';
        llmModelForm.reset();
        document.getElementById('llmModelApiKey').placeholder = 'Enter API Key';
    });
}

if (saveLLMModelBtn) {
    saveLLMModelBtn.addEventListener('click', async () => {
        const modelId = document.getElementById('llmModelId').value;
        const name = document.getElementById('llmModelName').value; // Friendly Name
        const providerName = document.getElementById('llmModelProvider').value; // Changed variable name and will use for correct payload key
        const modelIdentifier = document.getElementById('llmModelIdentifier').value; // Model Name/Identifier
        const apiUrl = document.getElementById('llmModelApiUrl').value;
        const apiKey = document.getElementById('llmModelApiKey').value;

        if (!name || !providerName || !modelIdentifier || !apiUrl) {
            alert('Please fill in all required fields: Friendly Name, Provider, Model Identifier, and API URL.');
            return;
        }

        const url = modelId ? `${llm_models_url}/${modelId}` : llm_models_url;
        const method = modelId ? 'PUT' : 'POST';

        let payload = {
            name: name,
            provider_name: providerName,
            model_name: modelIdentifier,
            api_url: apiUrl,
            is_default: false, // Default value, can be updated separately
            model_version: null, // Optional, can be added later
        };

        // Only include the API key if it's being set or changed
        if (apiKey) {
            payload.api_key = apiKey;
        }

        try {
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to save LLM model');
            }

            llmModelModal.hide();
            loadLLMModels();
        } catch (error) {
            console.error('Error saving LLM Model:', error);
            alert(`Error: ${error.message}`);
        }
    });
}

function editLLMModel(modelId) {
    const model = llmModels.find(m => m.id === modelId);
    if (!model) return;

    activeLLMModelId = modelId;
    document.getElementById('llmModelId').value = model.id;
    document.getElementById('llmModelModalLabel').textContent = 'Edit LLM Model';
    document.getElementById('llmModelName').value = model.name;
    document.getElementById('llmModelProvider').value = model.provider_name;
    document.getElementById('llmModelIdentifier').value = model.model_name;
    document.getElementById('llmModelApiUrl').value = model.api_url;
    document.getElementById('llmModelApiKey').value = '';
    document.getElementById('llmModelApiKey').placeholder = 'Leave blank to keep existing key';

    // Trigger change event to set readonly status of URL field correctly
    llmModelProviderSelect.dispatchEvent(new Event('change'));

    llmModelModal.show();
}

function confirmDeleteLLMModel(modelId, modelName) {
    activeLLMModelId = modelId;
    document.getElementById('llmModelNameToDelete').textContent = modelName;
    deleteLLMModelModal.show();
}

document.getElementById('confirmDeleteLLMModelBtn')?.addEventListener('click', () => {
    if (activeLLMModelId) {
        deleteLLMModel(activeLLMModelId);
    }
});

async function deleteLLMModel(modelId) {
    try {
        const response = await fetch(`${llm_models_url}/${modelId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
            }
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to delete LLM model');
        }

        deleteLLMModelModal.hide();
        loadLLMModels();
    } catch (error) {
        console.error('Error deleting LLM model:', error);
        alert(`Error: ${error.message}`);
    }
}

async function setDefaultLLMModel(modelId) {
    try {
        const response = await fetch(`${llm_models_url}/${modelId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
            },
            body: JSON.stringify({ is_default: true })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to set default LLM model');
        }

        loadLLMModels(); // Reload to reflect the change
    } catch (error) {
        console.error('Error setting default LLM model:', error);
        alert(`Error: ${error.message}`);
    }
}

// Utility function to show loading indicator (assuming you might have one)
function showLoadingIndicator(element, colspan) {
    const loadingRow = `
        <tr>
            <td colspan="${colspan}" class="text-center">
                <div class="spinner-border spinner-border-sm" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </td>
        </tr>
    `;
    element.innerHTML = loadingRow;
}

const EXPIRATION_TIME_MS = 2 * 60 * 1000; // 2 minutes

// Restore last active tab from localStorage if not expired
function loadLastActiveTab() {
    try {
        const storedTabData = localStorage.getItem('activeDashboardTab');
        const { tabId, timestamp } = JSON.parse(storedTabData);

        const timeSinceStored = Date.now() - timestamp;
        const isExpired = timeSinceStored >= EXPIRATION_TIME_MS;

        if (tabId && timestamp && !isExpired) {
            const tabButton = document.getElementById(tabId);

            if (tabButton) {
                if (!tabButton.classList.contains('active')) {
                    const tab = new bootstrap.Tab(tabButton);
                    tab.show(); // This should trigger 'shown.bs.tab' which also updates title
                } else {
                    document.getElementById('currentPageTitle').textContent = tabButton.textContent.trim();
                }
            } else {
                localStorage.removeItem('activeDashboardTab'); // Clean up invalid entry
            }
        } else {
            showDefaultTab();
        }
    } catch (error) {
        showDefaultTab();
    }
}

function showDefaultTab() {
    localStorage.removeItem('activeDashboardTab');
    const defaultTabButton = document.getElementById('dashboard-tab-btn'); // Assuming this is your default
    if (defaultTabButton && defaultTabButton.classList.contains('active')) {
        document.getElementById('currentPageTitle').textContent = defaultTabButton.textContent.trim();
    }
}

// Helper function for truncating text (if not already present)
function truncateText(text, maxLength) {
    if (!text) return '';
    if (text.length <= maxLength) {
        return text;
    }
    return text.substring(0, maxLength) + '...';
}
