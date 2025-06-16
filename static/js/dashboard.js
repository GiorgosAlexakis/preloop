// Global variables
let currentUser = null;
let trackers = [];
let apiKeys = [];
let apiUsage = null;
let activeKeyId = null;
let activeTrackerId = null;
let llm_providers_url = '/api/v1/llm-providers';

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

    // Fetch LLM providers
    // TODO: When adding this, I get multiple TypeError: Load Failed and the page returns to login
    loadLLMProviders();
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
                // Try to refresh the token and retry
                await refreshToken(); // Wait for token refresh
                // Retry the request with the new token
                const retryResponse = await fetch(`/api/v1/projects/${projectId}/duplicates`, {
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
                    }
                });
                if (!retryResponse.ok) {
                    const errorData = await retryResponse.json().catch(() => ({ detail: 'Failed to fetch duplicates after token refresh.' }));
                    throw new Error(errorData.detail || `HTTP error! status: ${retryResponse.status}`);
                }
                const data = await retryResponse.json();
                renderDuplicates(data);
                return; // Exit after successful retry
            }
            const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch duplicates. Server returned an error.' }));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log(data)
        renderDuplicates(data);
    } catch (error) {
        console.error('Error fetching project duplicates:', error);
        resultArea.innerHTML = `<div class="alert alert-danger" role="alert">Error fetching duplicates: ${error.message}</div>`;
    }
}

function renderDuplicates(data) {
    const resultArea = document.getElementById('duplicates-result-area');
    if (!data || !data.duplicates) {
        resultArea.innerHTML = '<p class="text-muted text-center">No duplicate data received.</p>';
        return;
    }

    const duplicates = data.duplicates;
    const projectId = data.project_id; // Assuming project_id is in the response for context if needed

    // Sort duplicates by similarity in descending order
    duplicates.sort((a, b) => b.similarity - a.similarity);

    if (duplicates.length === 0) {
        resultArea.innerHTML = '<p class="text-center">No duplicates found for this project.</p>';
        return;
    }

    let tableHtml = `
        <h5 class="mt-4 mb-3"Potential Duplicate Pairs</h5>
        <h6 class="text-muted">Threshold: ${(data.threshold_used * 100).toFixed(2)}%</h6>
        <table class="table table-hover table-sm small">
            <thead>
                <tr>
                    <th>Issue Keys</th>
                    <th>Issue Titles</th>
                    <th>Similarity</th>
                </tr>
            </thead>
            <tbody>
    `;

    duplicates.forEach((pair, index) => {
        console.log(`Rendering duplicate pair ${index}:`, JSON.stringify(pair, null, 2)); // Log the pair data
        const detailRowId = `details-row-${index}`;
        tableHtml += `
            <tr onclick="toggleDetails('${detailRowId}')" style="cursor: pointer;" title="Click to see details">
                <td>
                    <div><a href="${pair.issue1.url}" target="_blank" rel="noopener noreferrer"><strong>${pair.issue1.key}</strong> <i class="bi bi-box-arrow-up-right ms-1"></i></a></div>
                    <div><a href="${pair.issue2.url}" target="_blank" rel="noopener noreferrer"><strong>${pair.issue2.key}</strong> <i class="bi bi-box-arrow-up-right ms-1"></i></a></div>
                </td>
                <td>
                    <div>${pair.issue1.title}</div>
                    <div>${pair.issue2.title}</div>
                </td>
                <td>${(pair.similarity * 100).toFixed(2)}%</td>
            </tr>
            <tr id="${detailRowId}" class="duplicate-details-row" style="display: none;">
                <td colspan="3" class="p-3">
                    <div class="row">
                        <div class="col-md-6">
                            <h5>${pair.issue1.title}</h5>
                            <div><a href="${pair.issue1.url}" target="_blank" rel="noopener noreferrer"><strong>${pair.issue1.key}</strong> <i class="bi bi-box-arrow-up-right ms-1"></i></a></div>
                            <p><strong>Status:</strong> ${pair.issue1.status || 'N/A'}<br>
                               <strong>Priority:</strong> ${pair.issue1.priority || 'N/A'}</p>
                            <div class="description-text">${pair.issue1.description ? pair.issue1.description.replace(/\n/g, '<br>') : 'No description available.'}</div>
                        </div>
                        <div class="col-md-6">
                            <h5>${pair.issue2.title}</h5>
                            <div><a href="${pair.issue2.url}" target="_blank" rel="noopener noreferrer"><strong>${pair.issue2.key}</strong> <i class="bi bi-box-arrow-up-right ms-1"></i></a></div>
                            <p><strong>Status:</strong> ${pair.issue2.status || 'N/A'}<br>
                               <strong>Priority:</strong> ${pair.issue2.priority || 'N/A'}</p>
                            <div class="description-text">${pair.issue2.description ? pair.issue2.description.replace(/\n/g, '<br>') : 'No description available.'}</div>
                        </div>
                    </div>
                </td>
            </tr>
        `;
    });

    tableHtml += `
            </tbody>
        </table>
    `;

    resultArea.innerHTML = tableHtml;
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

// Add event listener for project selection dropdown
const projectSelectElement = document.getElementById('projectSelect');
if (projectSelectElement) {
    projectSelectElement.addEventListener('change', function() {
        const selectedProjectId = this.value;
        if (selectedProjectId) {
            fetchProjectDuplicates(selectedProjectId);
        } else {
            const resultArea = document.getElementById('duplicates-result-area');
            resultArea.innerHTML = '<p class="text-muted text-center">Please select a project.</p>';
        }
    });
}

// LLM Providers Section
const llmProviderModal = new bootstrap.Modal(document.getElementById('llmProviderModal'));
const llmProviderForm = document.getElementById('llmProviderForm');
const saveLLMProviderBtn = document.getElementById('saveLLMProviderBtn');
const llmProvidersTableBody = document.getElementById('llmProvidersTable');

async function fetchLLMProviders() {
    try {
        const response = await fetch(llm_providers_url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
            }
        });
        if (!response.ok) {
            if (response.status === 401) {
                console.error('Session expired. Please log in again.');
                // Potentially redirect to login: window.location.href = '/login';
                return [];
            }
            const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch LLM providers' }));
            console.error(`Error fetching LLM providers: ${errorData.detail}`);
            return [];
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching LLM providers:', error);
        console.error('An unexpected error occurred while fetching LLM providers.');
        return [];
    }
}

function renderLLMProvidersTable(providers) {
    llmProvidersTableBody.innerHTML = ''; // Clear existing rows
    if (!providers || providers.length === 0) {
        const row = llmProvidersTableBody.insertRow();
        const cell = row.insertCell(0);
        cell.colSpan = 4;
        cell.textContent = 'No LLM providers configured yet.';
        cell.classList.add('text-center', 'text-muted');
        return;
    }

    providers.forEach(provider => {
        const row = llmProvidersTableBody.insertRow();
        row.insertCell().textContent = provider.provider_name;

        const defaultCell = row.insertCell();
        if (provider.is_default) {
            const defaultBadge = document.createElement('span');
            defaultBadge.classList.add('badge', 'bg-success');
            defaultBadge.textContent = 'Default';
            defaultCell.appendChild(defaultBadge);
        } else {
            const setDefaultLink = document.createElement('a');
            setDefaultLink.href = '#';
            setDefaultLink.classList.add('badge', 'bg-secondary', 'text-decoration-none');
            setDefaultLink.textContent = 'Set Default';
            setDefaultLink.title = 'Click to set as default provider';
            setDefaultLink.addEventListener('click', (event) => {
                event.preventDefault(); // Prevent page from jumping to top
                setDefaultLLMProvider(provider.id);
            });
            defaultCell.appendChild(setDefaultLink);
        }

        row.insertCell().textContent = new Date(provider.created_at).toLocaleDateString();

        const actionsCell = row.insertCell();
        const deleteBtn = document.createElement('button');
        deleteBtn.classList.add('btn', 'btn-danger', 'btn-sm');
        deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';
        deleteBtn.title = 'Delete Provider';
        deleteBtn.addEventListener('click', () => confirmDeleteLLMProvider(provider.id, provider.provider_name));
        actionsCell.appendChild(deleteBtn);
    });
}

function loadLLMProviders() {
    showLoadingIndicator(llmProvidersTableBody, 4);
    fetchLLMProviders().then(providers => renderLLMProvidersTable(providers));
}

if (saveLLMProviderBtn) {
    saveLLMProviderBtn.addEventListener('click', async function () {
        const providerName = document.getElementById('llmProviderName').value;
        const apiKey = document.getElementById('llmProviderApiKey').value;
        const isDefault = document.getElementById('llmProviderIsDefault').checked;

        if (!providerName || !apiKey) {
            console.warn('Provider name and API key are required.');
            return;
        }

        const payload = {
            provider_name: providerName,
            credentials: { api_key: apiKey }, // Assuming all providers use 'api_key' for now
            is_default: isDefault
        };

        try {
            const response = await fetch(llm_providers_url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
                },
                body: JSON.stringify(payload)
            });

            if (response.status === 201) {
                console.log('LLM Provider added successfully!');
                llmProviderForm.reset();
                llmProviderModal.hide();
                loadLLMProviders(); // Refresh the table
            } else {
                const errorData = await response.json().catch(() => ({ detail: 'Failed to add LLM provider' }));
                console.error(`Error adding LLM provider: ${errorData.detail}`);
            }
        } catch (error) {
            console.error('Error adding LLM provider:', error);
            console.error('An unexpected error occurred while adding LLM provider.');
        }
    });
}

function confirmDeleteLLMProvider(providerId, providerName) {
    // Assuming you have a generic confirmation modal or use window.confirm
    if (confirm(`Are you sure you want to delete the LLM provider "${providerName}"?`)) {
        deleteLLMProvider(providerId);
    }
}

async function deleteLLMProvider(providerId) {
    try {
        const response = await fetch(`${llm_providers_url}/${providerId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
            }
        });

        if (response.status === 204) {
            console.log('LLM Provider deleted successfully.');
            loadLLMProviders(); // Refresh the table
        } else {
            const errorData = await response.json().catch(() => ({ detail: 'Failed to delete LLM provider' }));
            console.error(`Error deleting LLM provider: ${errorData.detail}`);
        }
    } catch (error) {
        console.error('Error deleting LLM provider:', error);
        console.error('An unexpected error occurred while deleting LLM provider.');
    }
}

async function setDefaultLLMProvider(providerId) {
    try {
        const response = await fetch(`${llm_providers_url}/${providerId}`,
        {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
            },
            body: JSON.stringify({ is_default: true })
        });

        if (response.ok) {
            console.log('LLM Provider set as default.');
            loadLLMProviders(); // Refresh the table to show the new default
        } else {
            const errorData = await response.json().catch(() => ({ detail: 'Failed to set default LLM provider' }));
            console.error(`Error setting default LLM provider: ${errorData.detail}`);
        }
    } catch (error) {
        console.error('Error setting default LLM provider:', error);
        console.error('An unexpected error occurred while setting default LLM provider.');
    }
}

// Utility function to show loading indicator (assuming you might have one)
function showLoadingIndicator(element, colspan) {
    if (element && typeof element.insertRow === 'function') {
        element.innerHTML = ''; // Clear existing content
        const row = element.insertRow();
        const cell = row.insertCell(0);
        cell.colSpan = colspan;
        cell.innerHTML = '<div class="d-flex justify-content-center"><div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    }
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
