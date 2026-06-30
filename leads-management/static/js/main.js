// Training Center CRM - Main JavaScript Functions

// Global variables
let currentUser = null;
let sidebarOpen = false;

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    initializeSidebar();
    initializeTooltips();
    initializeSearchFilters();
    initializePipeline();
    initializeModals();
    initializeCharts();
    initializeFileUploads();
});

// Sidebar functionality
function initializeSidebar() {
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    
    if (toggleBtn && sidebar && mainContent) {
        toggleBtn.addEventListener('click', function() {
            sidebarOpen = !sidebarOpen;
            if (sidebarOpen) {
                sidebar.classList.add('active');
                mainContent.classList.add('sidebar-open');
            } else {
                sidebar.classList.remove('active');
                mainContent.classList.remove('sidebar-open');
            }
        });
        
        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function(e) {
            if (window.innerWidth <= 768 && sidebarOpen && 
                !sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
                sidebar.classList.remove('active');
                mainContent.classList.remove('sidebar-open');
                sidebarOpen = false;
            }
        });
    }
}

// Initialize tooltips
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Search and filter functionality
function initializeSearchFilters() {
    const searchInput = document.getElementById('searchInput');
    const filterSelects = document.querySelectorAll('.filter-select');
    
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                performSearch(this.value);
            }, 300);
        });
    }
    
    filterSelects.forEach(select => {
        select.addEventListener('change', function() {
            applyFilters();
        });
    });
}

// Perform search functionality
function performSearch(query) {
    const tableRows = document.querySelectorAll('.data-table tbody tr');
    const lowercaseQuery = query.toLowerCase();
    
    tableRows.forEach(row => {
        const textContent = row.textContent.toLowerCase();
        if (textContent.includes(lowercaseQuery)) {
            row.style.display = '';
            row.classList.add('fade-in');
        } else {
            row.style.display = 'none';
            row.classList.remove('fade-in');
        }
    });
    
    updateSearchResults(query);
}

// Apply filters
function applyFilters() {
    const filters = {};
    document.querySelectorAll('.filter-select').forEach(select => {
        if (select.value) {
            filters[select.name] = select.value;
        }
    });
    
    const tableRows = document.querySelectorAll('.data-table tbody tr');
    tableRows.forEach(row => {
        let showRow = true;
        
        Object.keys(filters).forEach(filterKey => {
            const filterValue = filters[filterKey];
            const cellValue = row.querySelector(`[data-${filterKey}]`)?.textContent || '';
            
            if (filterValue && !cellValue.includes(filterValue)) {
                showRow = false;
            }
        });
        
        row.style.display = showRow ? '' : 'none';
    });
}

// Pipeline drag and drop functionality
function initializePipeline() {
    const pipelineColumns = document.querySelectorAll('.pipeline-column');
    const leadCards = document.querySelectorAll('.lead-card');
    
    leadCards.forEach(card => {
        card.draggable = true;
        card.addEventListener('dragstart', handleDragStart);
        card.addEventListener('dragend', handleDragEnd);
    });
    
    pipelineColumns.forEach(column => {
        column.addEventListener('dragover', handleDragOver);
        column.addEventListener('drop', handleDrop);
        column.addEventListener('dragenter', handleDragEnter);
        column.addEventListener('dragleave', handleDragLeave);
    });
}

function handleDragStart(e) {
    this.classList.add('dragging');
    e.dataTransfer.setData('text/plain', this.dataset.leadId);
    e.dataTransfer.setData('text/html', this.outerHTML);
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd(e) {
    this.classList.remove('dragging');
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
}

function handleDragEnter(e) {
    e.preventDefault();
    this.classList.add('drag-over');
}

function handleDragLeave(e) {
    this.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    this.classList.remove('drag-over');
    
    const leadId = e.dataTransfer.getData('text/plain');
    const newStatus = this.dataset.status;
    
    if (leadId && newStatus) {
        updateLeadStatus(leadId, newStatus);
    }
}

// Update lead status via AJAX
function updateLeadStatus(leadId, newStatus) {
    showLoading();
    
    fetch(`/api/leads/${leadId}/status`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({ status: newStatus })
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();
        if (data.success) {
            showNotification('Lead status updated successfully!', 'success');
            // Move the lead card to the new column
            moveLeadCard(leadId, newStatus);
            updatePipelineStats();
        } else {
            showNotification('Error updating lead status: ' + data.message, 'error');
        }
    })
    .catch(error => {
        hideLoading();
        showNotification('Error updating lead status: ' + error.message, 'error');
    });
}

// Move lead card to new pipeline column
function moveLeadCard(leadId, newStatus) {
    const leadCard = document.querySelector(`[data-lead-id="${leadId}"]`);
    const targetColumn = document.querySelector(`[data-status="${newStatus}"] .pipeline-leads`);
    
    if (leadCard && targetColumn) {
        // Update the card's status badge
        const statusBadge = leadCard.querySelector('.status-badge');
        if (statusBadge) {
            statusBadge.className = `status-badge status-${newStatus.toLowerCase()}`;
            statusBadge.textContent = newStatus;
        }
        
        // Move the card with animation
        leadCard.style.opacity = '0';
        setTimeout(() => {
            targetColumn.appendChild(leadCard);
            leadCard.style.opacity = '1';
            leadCard.classList.add('fade-in');
        }, 200);
    }
}

// Initialize modals
function initializeModals() {
    const modalTriggers = document.querySelectorAll('[data-bs-toggle="modal"]');
    modalTriggers.forEach(trigger => {
        trigger.addEventListener('click', function() {
            const modalId = this.dataset.bsTarget;
            const modal = document.querySelector(modalId);
            if (modal) {
                // Reset form if it exists
                const form = modal.querySelector('form');
                if (form) {
                    form.reset();
                }
            }
        });
    });
    
    // Auto-populate WhatsApp from phone number
    const phoneInputs = document.querySelectorAll('input[name="phone"]');
    phoneInputs.forEach(input => {
        input.addEventListener('blur', function() {
            const whatsappInput = document.querySelector('input[name="whatsapp"]');
            if (whatsappInput && !whatsappInput.value) {
                whatsappInput.value = this.value;
            }
        });
    });
}

// Initialize charts
function initializeCharts() {
    // This will be handled by charts.js
    if (typeof initializeDashboardCharts === 'function') {
        initializeDashboardCharts();
    }
}

// File upload functionality
function initializeFileUploads() {
    const uploadAreas = document.querySelectorAll('.upload-area');
    
    uploadAreas.forEach(area => {
        const fileInput = area.querySelector('input[type="file"]');
        
        area.addEventListener('click', () => fileInput?.click());
        
        area.addEventListener('dragover', (e) => {
            e.preventDefault();
            area.classList.add('dragover');
        });
        
        area.addEventListener('dragleave', () => {
            area.classList.remove('dragover');
        });
        
        area.addEventListener('drop', (e) => {
            e.preventDefault();
            area.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0 && fileInput) {
                fileInput.files = files;
                handleFileUpload(fileInput);
            }
        });
        
        if (fileInput) {
            fileInput.addEventListener('change', () => handleFileUpload(fileInput));
        }
    });
}

// Handle file upload
function handleFileUpload(input) {
    const files = input.files;
    if (files.length === 0) return;
    
    const progressBar = document.getElementById('uploadProgress');
    const progressContainer = document.getElementById('uploadProgressContainer');
    
    if (progressContainer) {
        progressContainer.style.display = 'block';
    }
    
    // Simulate file upload progress
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress >= 100) {
            progress = 100;
            clearInterval(interval);
            setTimeout(() => {
                if (progressContainer) {
                    progressContainer.style.display = 'none';
                }
                showNotification('File uploaded successfully!', 'success');
            }, 500);
        }
        
        if (progressBar) {
            progressBar.style.width = progress + '%';
            progressBar.textContent = Math.round(progress) + '%';
        }
    }, 200);
}

// Utility functions
function showLoading() {
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'block';
    }
}

function hideLoading() {
    const loadingIndicator = document.getElementById('loadingIndicator');
    if (loadingIndicator) {
        loadingIndicator.style.display = 'none';
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}-custom alert-dismissible fade show`;
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.getElementById('notificationContainer') || document.body;
    container.insertBefore(notification, container.firstChild);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 5000);
}

function getCSRFToken() {
    const token = document.querySelector('meta[name="csrf-token"]');
    return token ? token.getAttribute('content') : '';
}

function updateSearchResults(query) {
    const resultCount = document.querySelectorAll('.data-table tbody tr:not([style*="display: none"])').length;
    const resultContainer = document.getElementById('searchResults');
    
    if (resultContainer) {
        if (query) {
            resultContainer.textContent = `Found ${resultCount} results for "${query}"`;
            resultContainer.style.display = 'block';
        } else {
            resultContainer.style.display = 'none';
        }
    }
}

function updatePipelineStats() {
    fetch('/api/pipeline/data')
        .then(response => response.json())
        .then(data => {
            Object.keys(data).forEach(status => {
                const countElement = document.getElementById(`${status.toLowerCase()}-count`);
                const valueElement = document.getElementById(`${status.toLowerCase()}-value`);
                
                if (countElement) {
                    countElement.textContent = data[status].count;
                }
                if (valueElement) {
                    valueElement.textContent = `$${data[status].total_value.toLocaleString()}`;
                }
            });
        })
        .catch(error => console.error('Error updating pipeline stats:', error));
}

// Meeting calendar functionality
function initializeMeetingCalendar() {
    const calendarEl = document.getElementById('meetingCalendar');
    if (!calendarEl) return;
    
    // Simple calendar implementation
    const today = new Date();
    const currentMonth = today.getMonth();
    const currentYear = today.getFullYear();
    
    renderCalendar(currentYear, currentMonth);
}

function renderCalendar(year, month) {
    const calendarEl = document.getElementById('meetingCalendar');
    if (!calendarEl) return;
    
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const monthNames = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    
    let calendarHTML = `
        <div class="calendar-header">
            <h4>${monthNames[month]} ${year}</h4>
            <div class="calendar-nav">
                <button class="btn btn-sm btn-outline-primary" onclick="changeMonth(-1)">‹ Prev</button>
                <button class="btn btn-sm btn-outline-primary" onclick="changeMonth(1)">Next ›</button>
            </div>
        </div>
        <div class="calendar-grid">
            <div class="calendar-weekdays">
                <div>Sun</div><div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div>
            </div>
            <div class="calendar-days">
    `;
    
    // Empty cells for days before the first day of the month
    for (let i = 0; i < firstDay; i++) {
        calendarHTML += '<div class="calendar-day empty"></div>';
    }
    
    // Days of the month
    for (let day = 1; day <= daysInMonth; day++) {
        const isToday = (year === new Date().getFullYear() && 
                        month === new Date().getMonth() && 
                        day === new Date().getDate());
        
        calendarHTML += `
            <div class="calendar-day ${isToday ? 'today' : ''}" data-date="${year}-${month + 1}-${day}">
                <span class="day-number">${day}</span>
                <div class="day-meetings"></div>
            </div>
        `;
    }
    
    calendarHTML += '</div></div>';
    calendarEl.innerHTML = calendarHTML;
}

// Export functionality
function exportData(format, type) {
    showLoading();
    
    fetch(`/api/export/${type}?format=${format}`)
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `${type}_export.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            hideLoading();
            showNotification(`${type} data exported successfully!`, 'success');
        })
        .catch(error => {
            hideLoading();
            showNotification('Error exporting data: ' + error.message, 'error');
        });
}

// Form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
            field.classList.add('is-valid');
        }
    });
    
    // Email validation
    const emailFields = form.querySelectorAll('input[type="email"]');
    emailFields.forEach(field => {
        if (field.value && !isValidEmail(field.value)) {
            field.classList.add('is-invalid');
            isValid = false;
        }
    });
    
    // Phone validation
    const phoneFields = form.querySelectorAll('input[type="tel"], input[name*="phone"]');
    phoneFields.forEach(field => {
        if (field.value && !isValidPhone(field.value)) {
            field.classList.add('is-invalid');
            isValid = false;
        }
    });
    
    return isValid;
}

function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function isValidPhone(phone) {
    const phoneRegex = /^[\+]?[1-9][\d]{0,15}$/;
    return phoneRegex.test(phone.replace(/[\s\-\(\)]/g, ''));
}

// Auto-save functionality for forms
function initializeAutoSave() {
    const forms = document.querySelectorAll('.auto-save-form');
    
    forms.forEach(form => {
        const inputs = form.querySelectorAll('input, textarea, select');
        
        inputs.forEach(input => {
            input.addEventListener('change', () => {
                saveFormData(form.id, getFormData(form));
            });
        });
        
        // Load saved data on page load
        loadFormData(form.id, form);
    });
}

function saveFormData(formId, data) {
    localStorage.setItem(`form_${formId}`, JSON.stringify(data));
}

function loadFormData(formId, form) {
    const savedData = localStorage.getItem(`form_${formId}`);
    if (savedData) {
        const data = JSON.parse(savedData);
        Object.keys(data).forEach(key => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input) {
                input.value = data[key];
            }
        });
    }
}

function getFormData(form) {
    const formData = new FormData(form);
    const data = {};
    for (let [key, value] of formData.entries()) {
        data[key] = value;
    }
    return data;
}

function clearFormData(formId) {
    localStorage.removeItem(`form_${formId}`);
}

// Initialize auto-save on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeAutoSave();
});
