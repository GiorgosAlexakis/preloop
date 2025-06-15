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
            const defaultBadge = document.createElement('span');
            defaultBadge.classList.add('badge');
            if (provider.is_default) {
                defaultBadge.classList.add('bg-success');
                defaultBadge.textContent = 'Default';
            } else {
                defaultBadge.classList.add('bg-secondary', 'clickable');
                defaultBadge.textContent = 'Set Default';
                defaultBadge.title = 'Click to set as default provider';
                defaultBadge.addEventListener('click', () => setDefaultLLMProvider(provider.id));
            }
            defaultCell.appendChild(defaultBadge);

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

    async function loadLLMProviders() {
        showLoadingIndicator(llmProvidersTableBody, 4);
        const providers = await fetchLLMProviders();
        renderLLMProvidersTable(providers);
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

    // Load LLM providers when the settings tab is shown or if it's already active
    const settingsTabButton = document.getElementById('settings-tab-btn');
    if (settingsTabButton) {
        if (settingsTabButton.classList.contains('active')) {
            loadLLMProviders();
        }
        settingsTabButton.addEventListener('shown.bs.tab', function (event) {
            if (event.target.hash === '#settings-tab') {
                loadLLMProviders();
            }
        });
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
}

// Fetch trackers
function fetchTrackers() {
    fetch('/api/v1/trackers', {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else if (response.status === 401) {
            return refreshToken().then(() => fetchTrackers());
        } else {
            throw new Error('Failed to fetch trackers');
        }
    })
    .then(data => {
        trackers = data;
        renderTrackers();
        updateDashboardStats();
    })
    .catch(error => {
        console.error('Error fetching trackers:', error);
    });
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

// --- Tracker Wizard Logic ---
let currentStep = 1;
let isEditing = false;
let projectData = null; // To store fetched projects/orgs

function resetTrackerModal() {
    currentStep = 1;
    isEditing = false;
    projectData = null;
    document.getElementById('trackerForm').reset();
    document.getElementById('trackerId').value = '';
    document.getElementById('trackerModalLabel').textContent = 'Add New Tracker';
    document.getElementById('trackerStep1').classList.remove('d-none');
    document.getElementById('trackerStep2').classList.add('d-none');
    document.getElementById('trackerWizardPrevBtn').classList.add('d-none');
    document.getElementById('trackerWizardNextBtn').classList.remove('d-none');
    document.getElementById('trackerSubmitBtn').classList.add('d-none');
    document.getElementById('trackerWizardSteps').classList.add('d-none'); // Hide steps for now
    document.getElementById('projectSelectionTree').innerHTML = '<p class="text-muted">Enter credentials and click Next to load projects.</p>';
    document.getElementById('projectSelectionError').textContent = '';
    document.getElementById('testConnectionStatus').innerHTML = '';
    document.getElementById('trackerType').disabled = false; // Re-enable type selection
    document.getElementById('trackerUrl').disabled = false; // Re-enable URL
    document.getElementById('trackerToken').placeholder = ''; // Reset placeholder
    document.getElementById('trackerToken').required = true; // Reset required status
}

function showStep(step) {
    currentStep = step;
    document.querySelectorAll('#trackerForm [id^="trackerStep"]').forEach(el => el.classList.add('d-none'));
    document.getElementById(`trackerStep${step}`).classList.remove('d-none');

    // Update step indicator (optional)
    document.querySelectorAll('#trackerWizardSteps .nav-link').forEach(link => {
        link.classList.remove('active');
        if (parseInt(link.getAttribute('data-step')) === step) {
            link.classList.add('active');
        }
    });

    // Update buttons
    document.getElementById('trackerWizardPrevBtn').classList.toggle('d-none', step === 1);
    document.getElementById('trackerWizardNextBtn').classList.toggle('d-none', step === 2);
    document.getElementById('trackerSubmitBtn').classList.toggle('d-none', step !== 2);
}

// Event listener for modal opening (to reset)
const trackerModalElement = document.getElementById('addTrackerModal'); // Use the correct ID
trackerModalElement.addEventListener('show.bs.modal', () => {
    // Reset only if not editing (edit function will populate)
    if (!isEditing) {
        resetTrackerModal();
    }
});
trackerModalElement.addEventListener('hidden.bs.modal', () => {
        // Always fully reset when hidden, clearing edit state
    isEditing = false;
    resetTrackerModal();
});


// Event listener for Next button
document.getElementById('trackerWizardNextBtn').addEventListener('click', async () => {
    if (currentStep === 1) {
        // Validate Step 1 form before proceeding
        const form = document.getElementById('trackerForm');
        const step2Inputs = document.querySelectorAll('#trackerStep2 input, #trackerStep2 select');
        step2Inputs.forEach(input => input.disabled = true); // Disable step 2 for step 1 validation

        let isValid = form.checkValidity();
        if (!isValid) {
            form.reportValidity();
        }
        step2Inputs.forEach(input => input.disabled = false); // Re-enable step 2 inputs

        if (isValid) {
            if (isEditing) {
                // If editing, just move to step 2 without testing connection again
                // Project list rendering happens in openEditTrackerModal based on saved scope
                showStep(2);
            } else {
                // If adding, test connection and fetch projects
                await testAndListProjects();
            }
        }
    }
});

// Event listener for Previous button
document.getElementById('trackerWizardPrevBtn').addEventListener('click', () => {
    if (currentStep === 2) {
        showStep(1);
    }
});

// Event listener for Submit button
document.getElementById('trackerSubmitBtn').addEventListener('click', () => {
    saveTracker();
});

// Function to test connection and list projects
async function testAndListProjects() {
    const name = document.getElementById('trackerName').value; // Needed for context, though not sent
    const type = document.getElementById('trackerType').value;
    const url = document.getElementById('trackerUrl').value;
    const token = document.getElementById('trackerToken').value;
    const trackerIdForTest = document.getElementById('trackerId').value; // Get ID if editing
    let config = null;
    if (type === 'jira') {
        config = { username: document.getElementById('jiraUsername').value };
    }

    const nextButton = document.getElementById('trackerWizardNextBtn');
    const statusDiv = document.getElementById('testConnectionStatus');
    const projectTree = document.getElementById('projectSelectionTree');
    const projectError = document.getElementById('projectSelectionError');

    nextButton.disabled = true;
    nextButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Testing...';
    statusDiv.innerHTML = '<div class="text-info"><span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Testing connection...</div>';
    projectTree.innerHTML = '<p class="text-muted">Testing connection and fetching projects...</p>';
    projectError.textContent = '';

    // Construct payload: Use tracker_id if editing and token is blank, otherwise send credentials
    const payload = { tracker_type: type, url, connection_details: config }; // Corrected keys
    if (isEditing && trackerIdForTest && !token) {
            payload.tracker_id = trackerIdForTest; // Signal backend to use saved creds
    } else if (token) {
            payload.api_key = token; // Corrected key
    } else {
            // If adding and no token, it's an error (should be caught by validation, but double-check)
            statusDiv.innerHTML = `<div class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> Access token is required.</div>`;
            nextButton.disabled = false;
            nextButton.innerHTML = 'Next: Test & Select Projects';
            return;
    }


    try {
        const response = await fetch('/api/v1/trackers/test-and-list-projects', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (response.ok && data.success) {
            statusDiv.innerHTML = `<div class="text-success"><i class="bi bi-check-circle-fill"></i> ${data.message || 'Connection successful!'}</div>`;
            projectData = data.projects || []; // Store project data

            // If editing, use existing scope settings, otherwise default to true
            const existingTracker = isEditing ? trackers.find(t => t.id === trackerIdForTest) : null;
            const initialIncludeFuture = existingTracker ? existingTracker.include_future_projects : true;
            const initialSelected = existingTracker ? existingTracker.included_project_identifiers || [] : [];

            renderProjectSelectionTree(projectData, initialSelected, initialIncludeFuture);
            showStep(2); // Move to next step on success
        } else if (response.status === 401) {
            await refreshToken();
            await testAndListProjects(); // Retry after refresh
            return; // Prevent further execution in this try block
        } else {
            statusDiv.innerHTML = `<div class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> ${data.message || 'Connection failed.'}</div>`;
            projectTree.innerHTML = '<p class="text-danger">Could not fetch projects. Please check credentials and try again.</p>';
            projectError.textContent = data.message || 'Connection failed.';
        }
    } catch (error) {
            console.error('Error testing connection:', error);
            statusDiv.innerHTML = `<div class="text-danger"><i class="bi bi-exclamation-triangle-fill"></i> An error occurred while testing the connection.</div>`;
            projectTree.innerHTML = '<p class="text-danger">An error occurred. Please try again.</p>';
            projectError.textContent = 'An error occurred.';
    } finally {
        nextButton.disabled = false;
        nextButton.innerHTML = isEditing ? 'Next: Configure Project Scope' : 'Next: Test & Select Projects';
    }
}

// Function to render the project selection tree
function renderProjectSelectionTree(projects, selectedIdentifiers = [], includeFuture = true) {
    const treeContainer = document.getElementById('projectSelectionTree');
    const includeFutureCheckbox = document.getElementById('includeFutureProjects');
    const selectAllCheckbox = document.getElementById('selectAllProjects');
    includeFutureCheckbox.checked = includeFuture; // Set initial state

    if (!projects || projects.length === 0) {
        treeContainer.innerHTML = '<p class="text-muted">No projects or organizations found for this tracker.</p>';
        selectAllCheckbox.checked = false;
        selectAllCheckbox.disabled = true; // Disable select all if no projects
        addTreeEventListeners();
        return;
    } else {
            selectAllCheckbox.disabled = false; // Enable if projects exist
    }

    let treeHtml = '<ul class="list-unstyled">';
    let allInitiallyChecked = true; // Assume all are checked initially

    projects.forEach(org => {
        const orgId = `org-${org.id}`;
        const childrenListId = `children-${org.id}`;
        // Default to checked unless editing and specific identifiers were provided
        let isOrgChecked = true;
        let someChildrenSelected = false; // Track for indeterminate state

        // If editing (selectedIdentifiers has values), determine state based on that
        if (selectedIdentifiers.length > 0) {
                const orgProjects = org.children.map(p => p.identifier);
                const selectedOrgProjects = orgProjects.filter(id => selectedIdentifiers.includes(id));
                isOrgChecked = selectedOrgProjects.length === orgProjects.length && orgProjects.length > 0;
                someChildrenSelected = !isOrgChecked && selectedOrgProjects.length > 0;
                if (!isOrgChecked) allInitiallyChecked = false; // If any org isn't fully checked, not all are checked
        }


        treeHtml += `
            <li>
                <div class="d-flex align-items-center">
                        <i class="bi bi-chevron-right me-1 expand-icon" style="cursor: pointer;" data-target="#${childrenListId}"></i>
                    <div class="form-check flex-grow-1">
                        <input class="form-check-input org-checkbox" type="checkbox" value="${org.id}" id="${orgId}" data-org-id="${org.id}" ${isOrgChecked ? 'checked' : ''} ${someChildrenSelected ? 'data-indeterminate="true"' : ''}>
                        <label class="form-check-label fw-bold" for="${orgId}">
                            ${org.name} (Organization)
                        </label>
                    </div>
                </div>
                <ul class="list-unstyled ms-4 d-none" id="${childrenListId}">`; // Initially hidden

        org.children.forEach(proj => {
            const projId = `proj-${proj.identifier}`;
            // Default to checked unless editing and specific identifiers were provided
            let isProjChecked = true;
            if (selectedIdentifiers.length > 0) {
                isProjChecked = selectedIdentifiers.includes(proj.identifier);
                if (!isProjChecked) allInitiallyChecked = false; // If any project isn't checked, not all are checked
            }

            treeHtml += `
                <li>
                    <div class="form-check">
                        <input class="form-check-input project-checkbox" type="checkbox" value="${proj.identifier}" id="${projId}" data-org-id="${org.id}" ${isProjChecked ? 'checked' : ''}>
                        <label class="form-check-label" for="${projId}">
                            ${proj.name} (${proj.identifier})
                        </label>
                    </div>
                </li>`;
        });

        treeHtml += `</ul></li>`;
    });

    treeHtml += '</ul>';
    treeContainer.innerHTML = treeHtml;

    // Set initial indeterminate state after rendering
    document.querySelectorAll('.org-checkbox[data-indeterminate="true"]').forEach(cb => {
        cb.indeterminate = true;
    });

    // Set initial state for "Select All" checkbox
    selectAllCheckbox.checked = allInitiallyChecked;
    selectAllCheckbox.indeterminate = !allInitiallyChecked && Array.from(treeContainer.querySelectorAll('.project-checkbox')).some(cb => cb.checked);


    // Add event listeners after rendering
    addTreeEventListeners();
}

// Add event listeners for tree checkboxes, expand/collapse, and select all
function addTreeEventListeners() {
    // Remove previous listeners to avoid duplicates on re-render
    document.querySelectorAll('.org-checkbox').forEach(checkbox => {
        checkbox.removeEventListener('change', handleOrgCheckboxChange);
        checkbox.addEventListener('change', handleOrgCheckboxChange);
    });

    document.querySelectorAll('.project-checkbox').forEach(checkbox => {
        checkbox.removeEventListener('change', handleProjectCheckboxChange);
        checkbox.addEventListener('change', handleProjectCheckboxChange);
    });

    document.querySelectorAll('.expand-icon').forEach(icon => {
        icon.removeEventListener('click', handleExpandCollapse);
        icon.addEventListener('click', handleExpandCollapse);
    });

    const selectAllCheckbox = document.getElementById('selectAllProjects');
    selectAllCheckbox.removeEventListener('change', handleSelectAllChange);
    selectAllCheckbox.addEventListener('change', handleSelectAllChange);

    // No listener needed for includeFutureProjects regarding tree disabling
}

// REMOVED: toggleProjectSelectionAvailability function (Req 2)


// Handle expand/collapse icon clicks
function handleExpandCollapse(event) {
    const icon = event.target;
    const targetId = icon.getAttribute('data-target');
    const targetList = document.querySelector(targetId);

    if (targetList) {
        targetList.classList.toggle('d-none');
        icon.classList.toggle('bi-chevron-right');
        icon.classList.toggle('bi-chevron-down');
    }
}

// Handle organization checkbox changes
function handleOrgCheckboxChange(event) {
    const orgId = event.target.dataset.orgId;
    const isChecked = event.target.checked;
    // Find projects within the specific UL associated with this org
    const orgLi = event.target.closest('li');
    if (!orgLi) return;
    const projectList = orgLi.querySelector(`ul#children-${orgId}`);
    if (!projectList) return;

    projectList.querySelectorAll(`.project-checkbox[data-org-id="${orgId}"]`).forEach(projCheckbox => {
        projCheckbox.checked = isChecked;
    });
    // Reset indeterminate state when org checkbox is explicitly clicked
    event.target.indeterminate = false;
}

// Handle individual project checkbox changes
function handleProjectCheckboxChange(event) {
    const orgId = event.target.dataset.orgId;
    const orgCheckbox = document.getElementById(`org-${orgId}`);
    if (!orgCheckbox) return; // Safety check

    const orgLi = event.target.closest('li').closest('ul').closest('li'); // Find parent org LI
        if (!orgLi) return;
    const projectList = orgLi.querySelector(`ul#children-${orgId}`);
        if (!projectList) return;

    const projectCheckboxes = projectList.querySelectorAll(`.project-checkbox[data-org-id="${orgId}"]`);
    const allProjectsChecked = Array.from(projectCheckboxes).every(cb => cb.checked);
    const someProjectsChecked = Array.from(projectCheckboxes).some(cb => cb.checked);

    orgCheckbox.checked = allProjectsChecked;
    // Set indeterminate state visually if some but not all are checked
    orgCheckbox.indeterminate = !allProjectsChecked && someProjectsChecked;
}

// Handle Select All / Deselect All checkbox changes
function handleSelectAllChange(event) {
    const isChecked = event.target.checked;
    const treeContainer = document.getElementById('projectSelectionTree');
    treeContainer.querySelectorAll('.org-checkbox, .project-checkbox').forEach(checkbox => {
        checkbox.checked = isChecked;
        checkbox.indeterminate = false; // Clear indeterminate state
    });
}


// Save (Add or Update) a tracker
async function saveTracker() {
    const form = document.getElementById('trackerForm');
        // Temporarily disable step 1 validation if needed
    const step1Inputs = document.querySelectorAll('#trackerStep1 input:not([type=hidden]), #trackerStep1 select');
    // Check validity of the whole form
    if (!form.checkValidity()) {
        form.reportValidity();
        return; // Don't submit if basic validation fails
    }

    const trackerId = document.getElementById('trackerId').value;
    const name = document.getElementById('trackerName').value;
    const type = document.getElementById('trackerType').value; // Need type even for edit payload structure
    const url = document.getElementById('trackerUrl').value; // Need url even for edit payload structure
    const tokenInput = document.getElementById('trackerToken');
    const token = tokenInput.value; // Might be empty if editing and not changing

    let config = null;
    if (type === 'jira') {
        const usernameInput = document.getElementById('jiraUsername');
            if (!usernameInput.value && usernameInput.required) {
                alert('Jira username is required.');
                usernameInput.focus();
                return;
            }
        config = { username: usernameInput.value };
    }

    // --- Project Scope Data ---
    const includeFutureProjects = document.getElementById('includeFutureProjects').checked;
    let includedProjectIdentifiers = null; // Initialize as null
    let excludedProjectIdentifiers = null; // Initialize as null

    // Get all project identifiers currently rendered in the tree
    const allProjectCheckboxes = document.querySelectorAll('.project-checkbox');
    const allProjectIdentifiers = Array.from(allProjectCheckboxes).map(cb => cb.value);

    // Get checked project identifiers
    const checkedProjectCheckboxes = document.querySelectorAll('.project-checkbox:checked');
    const checkedProjectIdentifiers = Array.from(checkedProjectCheckboxes).map(cb => cb.value);

    if (includeFutureProjects) {
        // If including future, calculate EXCLUDED identifiers (all minus checked)
        excludedProjectIdentifiers = allProjectIdentifiers.filter(id => !checkedProjectIdentifiers.includes(id));
        // includedProjectIdentifiers remains null
    } else {
        // If NOT including future, use the INCLUDED (checked) identifiers
        includedProjectIdentifiers = checkedProjectIdentifiers;
        // excludedProjectIdentifiers remains null
    }
    // --- End Project Scope Data ---


    const basePayload = {
        name,
        include_future_projects: includeFutureProjects,
        included_project_identifiers: includedProjectIdentifiers, // Use calculated value
        excluded_project_identifiers: excludedProjectIdentifiers  // Use calculated value
    };

    // Add fields specific to add or edit
    let payload;
    let method;
    let endpoint;

    if (isEditing) {
        method = 'PUT';
        endpoint = `/api/v1/trackers/${trackerId}`;
        payload = { ...basePayload };
        // Only send token if a new one was provided
        if (token) {
            payload.token = token;
        }
        // Only send config if Jira and username was editable and potentially changed
        if (type === 'jira' && document.getElementById('jiraUsername').disabled === false) {
                payload.config = config;
            }
    } else {
        // Adding a new tracker
        method = 'POST';
        endpoint = '/api/v1/trackers';
        payload = {
            ...basePayload,
            type,
            url,
            config, // Will be null if not Jira
            token // Token is required for adding
        };
    }

    const submitButton = document.getElementById('trackerSubmitBtn');
    submitButton.disabled = true;
    submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...';


    try {
        const response = await fetch(endpoint, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
            },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const modal = bootstrap.Modal.getInstance(trackerModalElement);
            modal.hide(); // This should trigger the 'hidden.bs.modal' event to reset
            fetchTrackers(); // Refresh list
            console.log(`Tracker ${isEditing ? 'updated' : 'added'} successfully!`);
        } else if (response.status === 401) {
            await refreshToken();
            await saveTracker(); // Retry after refresh
            return; // Prevent further execution in this try block
        } else {
            const err = await response.json();
            throw new Error(err.detail || `Failed to ${isEditing ? 'update' : 'add'} tracker`);
        }
    } catch (error) {
            console.error(`Error ${isEditing ? 'updating' : 'adding'} tracker:`, error);
            throw error;
    } finally {
            submitButton.disabled = false;
            submitButton.innerHTML = isEditing ? 'Update Tracker' : 'Save Tracker';
    }
}

// --- Edit Tracker Logic ---
async function openEditTrackerModal(trackerId) {
    // Set editing flag *before* showing modal to prevent reset
    isEditing = true;
    activeTrackerId = trackerId; // Store the ID for saving

    // Fetch tracker details
    try {
        const response = await fetch(`/api/v1/trackers/${trackerId}`, {
            headers: { 'Authorization': `Bearer ${localStorage.getItem('accessToken')}` }
        });

            if (!response.ok) {
                if (response.status === 401) {
                    await refreshToken();
                    await openEditTrackerModal(trackerId); // Retry
                    return; // Stop execution here
                } else {
                    const errText = await response.text();
                    throw new Error(`Failed to fetch tracker details: ${response.status} ${errText}`);
                }
            }

        const tracker = await response.json();

        // REMOVED check for essential tracker data to bypass potential issue
        // console.log("Tracker data received:", tracker); // Optional: Add logging to see the data

        // --- Populate Step 1 ---
        document.getElementById('trackerId').value = tracker.id;
        document.getElementById('trackerName').value = tracker.name;
        document.getElementById('trackerType').value = tracker.tracker_type; // Use correct field name
        document.getElementById('trackerUrl').value = tracker.url;
        // Don't show existing token, prompt for new one if needed
        const tokenInput = document.getElementById('trackerToken');
        tokenInput.value = '';
        tokenInput.placeholder = 'Enter new token to update, leave blank to keep existing';
        tokenInput.required = false; // Not required for edit unless changing

        // Handle Jira config
        const jiraSection = document.getElementById('jiraConfigSection');
        const jiraUsernameInput = document.getElementById('jiraUsername');
        if (tracker.tracker_type === 'jira') { // Use correct field name
            jiraSection.classList.remove('d-none');
            jiraUsernameInput.value = tracker.connection_details?.username || ''; // Use connection_details from response
            // Jira username might be required depending on backend logic for updates
            // Let's assume it's required if the section is visible.
            jiraUsernameInput.required = true;
            jiraUsernameInput.disabled = false; // Assume username can be edited
        } else {
            jiraSection.classList.add('d-none');
            jiraUsernameInput.required = false;
        }

        // Disable type/URL editing
        document.getElementById('trackerType').disabled = true;
        document.getElementById('trackerUrl').disabled = true; // Keep URL disabled as it's not meant to change on edit
        document.getElementById('testConnectionStatus').innerHTML = ''; // Clear previous status


        // --- Render Project Scope (Step 2) based on fetched tracker data ---
        // NOTE: We are NOT calling testAndListProjects here for edit flow anymore
        // This means the project list might not be up-to-date and won't have names/structure
        // We can only render based on the saved identifiers. This is a limitation.
        const projectTree = document.getElementById('projectSelectionTree');
        const projectError = document.getElementById('projectSelectionError');
        projectError.textContent = ''; // Clear any previous error

        // Since we don't have the project list structure (orgs/children),
        // we cannot render the tree accurately for editing scope.
        // Display a message indicating this limitation.
        projectTree.innerHTML = `
            <div class="alert alert-warning small">
                <i class="bi bi-exclamation-triangle"></i>
                Project list cannot be displayed or modified during edit without re-entering credentials (functionality not yet implemented).
                Scope settings (Include Future Projects, specific selections) will be saved based on their current state.
            </div>
        `;
            // Populate the 'Include Future Projects' checkbox based on saved value
            document.getElementById('includeFutureProjects').checked = tracker.include_future_projects;
            // Disable the tree and select all as we can't interact with it meaningfully
            document.getElementById('projectSelectionTreeContainer').style.opacity = 0.7;
            document.getElementById('selectAllProjects').disabled = true;
            document.getElementById('selectAllProjects').checked = false; // Uncheck select all


        // --- Configure Modal for Editing ---
        document.getElementById('trackerModalLabel').textContent = `Edit Tracker: ${tracker.name}`;
        showStep(1); // Start at step 1 for editing basic info
        document.getElementById('trackerWizardNextBtn').textContent = 'Next: Configure Project Scope'; // Change button text
        document.getElementById('trackerSubmitBtn').textContent = 'Update Tracker'; // Change final button text

        // Show the modal *after* populating
        const modal = new bootstrap.Modal(trackerModalElement);
        modal.show();

    } catch (error) {
        console.error('Error opening edit tracker modal:', error);
        alert(`Could not load tracker details: ${error.message}`);
        isEditing = false; // Reset editing state on error
    }
}

// Add event listeners for edit and delete buttons (needs to be done after rendering trackers)
function addTrackerActionEventListeners() {

    // Edit buttons
    document.querySelectorAll('.edit-tracker-btn').forEach(btn => {
        const newBtn = btn.cloneNode(true); // Clone to remove listeners easily
        btn.parentNode.replaceChild(newBtn, btn);
        newBtn.addEventListener('click', handleEditClick);
    });

    // Delete buttons
    document.querySelectorAll('.delete-tracker-btn').forEach(btn => {
        const newBtn = btn.cloneNode(true); // Clone to remove listeners easily
        btn.parentNode.replaceChild(newBtn, btn);
        newBtn.addEventListener('click', handleDeleteClick);
    });
}

function handleEditClick(event) {
    const trackerId = event.currentTarget.getAttribute('data-tracker-id');
    openEditTrackerModal(trackerId);
}

function handleDeleteClick(event) {
    const trackerId = event.currentTarget.getAttribute('data-tracker-id'); // Get ID locally
    const trackerName = event.currentTarget.getAttribute('data-tracker-name');
    const confirmBtn = document.getElementById('confirmDeleteTrackerBtn');
    const deleteModalElement = document.getElementById('deleteTrackerModal');
    const deleteModal = bootstrap.Modal.getOrCreateInstance(deleteModalElement); // Use getOrCreateInstance

    document.getElementById('deleteTrackerName').textContent = trackerName;

    // Remove any old listener and add a new one specifically for this deletion
    const newConfirmBtn = confirmBtn.cloneNode(true); // Clone to remove old listeners
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);

    newConfirmBtn.addEventListener('click', () => {
        newConfirmBtn.disabled = true;
        newConfirmBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Deleting...';

        deleteTracker(trackerId) // Call delete with the specific ID
            .catch(error => {
                // Re-enable button on error
                console.error("Error during delete confirmation:", error);
                alert(`Failed to delete tracker: ${error.message}`);
                newConfirmBtn.disabled = false;
                newConfirmBtn.textContent = 'Delete Tracker';
            });
    }, { once: true });

    deleteModal.show();
}

// Modify fetchTrackers to call addTrackerActionEventListeners after rendering
function fetchTrackers() {
    // Clear existing listeners before fetching to avoid duplicates if fetch fails partially
        document.querySelectorAll('.edit-tracker-btn, .delete-tracker-btn').forEach(btn => {
            const newBtn = btn.cloneNode(true);
            btn.parentNode.replaceChild(newBtn, btn);
    });

    fetch('/api/v1/trackers', {
        headers: {
            'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else if (response.status === 401) {
            return refreshToken().then(() => fetchTrackers());
        } else {
            throw new Error('Failed to fetch trackers');
        }
    })
    .then(data => {
        trackers = data;
        renderTrackers(); // Renders the list (which contains the buttons)
        addTrackerActionEventListeners(); // Add listeners AFTER rendering
        updateDashboardStats();
    })
    .catch(error => {
        console.error('Error fetching trackers:', error);
    });
}

// Delete a tracker (Returns a promise)
async function deleteTracker(trackerId) {
    try {
        const response = await fetch(`/api/v1/trackers/${trackerId}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('accessToken')}`
            }
        });

        if (response.ok) {
            const modalElement = document.getElementById('deleteTrackerModal');
            const modal = bootstrap.Modal.getInstance(modalElement);
            if (modal) { // Check if modal instance exists
                    modal.hide();
                    const confirmBtn = document.getElementById('confirmDeleteTrackerBtn');
                    if (confirmBtn) {
                        confirmBtn.disabled = false;
                        confirmBtn.textContent = 'Delete Tracker';
                    }
            }
            fetchTrackers(); // Refresh list
            console.log(`Tracker deleted successfully!`);
        } else if (response.status === 401) {
            await refreshToken();
            await deleteTracker(trackerId);
        } else {
            const err = await response.json();
            throw new Error(err.detail || 'Failed to delete tracker');
        }
    } catch (error) {
            console.error('Error deleting tracker:', error);
            throw error;
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

// Placeholder for showing issue details - implement if needed
function showIssueDetails(issueId) {
    console.log("Show details for issue:", issueId);
    // Implement logic to show issue details, perhaps in a modal
    // For now, this function is called by clicking the issue keys.
    // We've added event.stopPropagation() to prevent the row click when a key is clicked.
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

const EXPIRATION_TIME_MS = 2 * 60 * 1000; // 2 minutes

// Restore last active tab from localStorage if not expired
function loadLastActiveTab() {
    const storedTabData = localStorage.getItem('activeDashboardTab');

    if (storedTabData) {
        try {
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
                localStorage.removeItem('activeDashboardTab');
                const defaultTabButton = document.getElementById('dashboard-tab-btn'); // Assuming this is your default
                if (defaultTabButton && defaultTabButton.classList.contains('active')) {
                    document.getElementById('currentPageTitle').textContent = defaultTabButton.textContent.trim();
                }
            }
        } catch (error) {
            localStorage.removeItem('activeDashboardTab'); // Clean up corrupted entry
        }
    } else {
        const defaultTabButton = document.getElementById('dashboard-tab-btn'); // Assuming this is your default
        if (defaultTabButton && defaultTabButton.classList.contains('active')) {
             document.getElementById('currentPageTitle').textContent = defaultTabButton.textContent.trim();
        }
    }
}
