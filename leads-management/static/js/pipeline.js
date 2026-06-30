// Advanced Pipeline Management for Training Center CRM
class PipelineManager {
    constructor() {
        this.leads = [];
        this.stages = ['New', 'Contacted', 'Interested', 'Quoted', 'Converted', 'Lost'];
        this.stageColors = {
            'New': '#3498db',
            'Contacted': '#f39c12', 
            'Interested': '#e67e22',
            'Quoted': '#9b59b6',
            'Converted': '#27ae60',
            'Lost': '#e74c3c'
        };
        this.draggedElement = null;
        this.touchStartY = 0;
        this.touchStartX = 0;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.loadPipelineData();
        this.renderPipeline();
        this.setupAutoRefresh();
    }
    
    setupEventListeners() {
        // Desktop drag and drop
        document.addEventListener('dragstart', this.handleDragStart.bind(this));
        document.addEventListener('dragend', this.handleDragEnd.bind(this));
        document.addEventListener('dragover', this.handleDragOver.bind(this));
        document.addEventListener('drop', this.handleDrop.bind(this));
        document.addEventListener('dragenter', this.handleDragEnter.bind(this));
        document.addEventListener('dragleave', this.handleDragLeave.bind(this));
        
        // Mobile touch events
        document.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
        document.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
        document.addEventListener('touchend', this.handleTouchEnd.bind(this));
        
        // Keyboard navigation
        document.addEventListener('keydown', this.handleKeyNavigation.bind(this));
        
        // Window resize for responsive layout
        window.addEventListener('resize', this.handleResize.bind(this));
        
        // Pipeline view toggle
        document.querySelectorAll('[data-pipeline-view]').forEach(btn => {
            btn.addEventListener('click', this.changeView.bind(this));
        });
    }
    
    loadPipelineData() {
        // Load pipeline data from server or local storage
        const savedData = localStorage.getItem('pipelineData');
        if (savedData) {
            this.leads = JSON.parse(savedData);
        } else {
            this.fetchPipelineData();
        }
    }
    
    async fetchPipelineData() {
        try {
            const response = await fetch('/api/pipeline/data');
            if (response.ok) {
                const data = await response.json();
                this.leads = data.leads || [];
                this.updateLocalStorage();
            }
        } catch (error) {
            console.error('Error fetching pipeline data:', error);
            this.showNotification('Error loading pipeline data', 'error');
        }
    }
    
    renderPipeline() {
        this.stages.forEach(stage => {
            this.renderStageColumn(stage);
        });
        this.updatePipelineStats();
        this.setupColumnAnimations();
    }
    
    renderStageColumn(stage) {
        const column = document.querySelector(`[data-stage="${stage}"]`);
        if (!column) return;
        
        const leadsContainer = column.querySelector('.pipeline-leads') || column;
        const stageLeads = this.leads.filter(lead => lead.status === stage);
        
        // Clear existing leads
        leadsContainer.innerHTML = '';
        
        if (stageLeads.length === 0) {
            this.renderEmptyState(leadsContainer, stage);
            return;
        }
        
        stageLeads.forEach(lead => {
            const leadCard = this.createLeadCard(lead);
            leadsContainer.appendChild(leadCard);
        });
        
        // Update stage header counts
        this.updateStageHeader(stage, stageLeads);
    }
    
    createLeadCard(lead) {
        const card = document.createElement('div');
        card.className = 'lead-card pipeline-card';
        card.setAttribute('data-lead-id', lead.id);
        card.setAttribute('draggable', 'true');
        card.setAttribute('tabindex', '0');
        card.setAttribute('role', 'button');
        card.setAttribute('aria-label', `Lead: ${lead.name}, Status: ${lead.status}`);
        
        const daysSinceContact = this.calculateDaysSinceLastContact(lead.last_contact_date);
        const urgencyClass = this.getUrgencyClass(daysSinceContact, lead.status);
        
        card.innerHTML = `
            <div class="card-header d-flex justify-content-between align-items-start">
                <div class="lead-info">
                    <h6 class="lead-name mb-1">${this.escapeHtml(lead.name)}</h6>
                    <div class="lead-meta">
                        <small class="text-muted">
                            <i class="fas fa-phone me-1"></i>${this.escapeHtml(lead.phone)}
                        </small>
                    </div>
                </div>
                <div class="lead-actions">
                    <div class="dropdown">
                        <button class="btn btn-sm btn-link text-muted" data-bs-toggle="dropdown" aria-label="Lead actions">
                            <i class="fas fa-ellipsis-v"></i>
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><a class="dropdown-item" href="#" onclick="viewLeadDetails(${lead.id})">
                                <i class="fas fa-eye me-2"></i>View Details
                            </a></li>
                            <li><a class="dropdown-item" href="#" onclick="editLead(${lead.id})">
                                <i class="fas fa-edit me-2"></i>Edit Lead
                            </a></li>
                            <li><a class="dropdown-item" href="#" onclick="scheduleMeeting(${lead.id})">
                                <i class="fas fa-calendar me-2"></i>Schedule Meeting
                            </a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item text-danger" href="#" onclick="deleteLead(${lead.id})">
                                <i class="fas fa-trash me-2"></i>Delete Lead
                            </a></li>
                        </ul>
                    </div>
                </div>
            </div>
            
            <div class="card-body">
                ${lead.course_name ? `
                <div class="course-info mb-2">
                    <span class="badge bg-info">${this.escapeHtml(lead.course_name)}</span>
                </div>
                ` : ''}
                
                ${lead.quoted_amount && lead.quoted_amount > 0 ? `
                <div class="quote-amount mb-2">
                    <span class="fw-bold text-success">
                        <i class="fas fa-dollar-sign me-1"></i>$${this.formatCurrency(lead.quoted_amount)}
                    </span>
                </div>
                ` : ''}
                
                ${lead.next_followup_date ? `
                <div class="followup-info mb-2 ${urgencyClass}">
                    <small>
                        <i class="fas fa-clock me-1"></i>
                        Follow-up: ${this.formatDate(lead.next_followup_date)}
                    </small>
                </div>
                ` : ''}
                
                ${lead.lead_source ? `
                <div class="lead-source mb-2">
                    <small class="text-muted">
                        <i class="fas fa-source me-1"></i>
                        Source: ${this.escapeHtml(lead.lead_source)}
                    </small>
                </div>
                ` : ''}
            </div>
            
            <div class="card-footer">
                <div class="quick-actions d-flex gap-1">
                    <button class="btn btn-sm btn-outline-primary flex-fill" 
                            onclick="makeCall('${lead.phone}')" 
                            title="Call ${lead.name}"
                            aria-label="Call ${lead.name}">
                        <i class="fas fa-phone"></i>
                    </button>
                    ${lead.whatsapp ? `
                    <button class="btn btn-sm btn-outline-success flex-fill" 
                            onclick="openWhatsApp('${lead.whatsapp}')" 
                            title="WhatsApp ${lead.name}"
                            aria-label="WhatsApp ${lead.name}">
                        <i class="fab fa-whatsapp"></i>
                    </button>
                    ` : ''}
                    ${lead.email ? `
                    <button class="btn btn-sm btn-outline-info flex-fill" 
                            onclick="sendEmail('${lead.email}')" 
                            title="Email ${lead.name}"
                            aria-label="Email ${lead.name}">
                        <i class="fas fa-envelope"></i>
                    </button>
                    ` : ''}
                </div>
            </div>
            
            <div class="progress-indicator" style="background-color: ${this.stageColors[lead.status]}"></div>
        `;
        
        // Add priority styling
        if (lead.priority === 'high') {
            card.classList.add('high-priority');
        } else if (lead.priority === 'urgent') {
            card.classList.add('urgent-priority');
        }
        
        // Add overdue styling if needed
        if (urgencyClass.includes('overdue')) {
            card.classList.add('overdue');
        }
        
        return card;
    }
    
    renderEmptyState(container, stage) {
        const emptyState = document.createElement('div');
        emptyState.className = 'empty-state text-center py-4';
        emptyState.innerHTML = `
            <div class="empty-icon mb-3">
                <i class="fas fa-inbox fa-2x text-muted"></i>
            </div>
            <p class="empty-text text-muted mb-0">No leads in ${stage.toLowerCase()}</p>
            ${stage === 'New' ? `
            <button class="btn btn-sm btn-outline-primary mt-2" onclick="openAddLeadModal()">
                <i class="fas fa-plus me-1"></i>Add Lead
            </button>
            ` : ''}
        `;
        container.appendChild(emptyState);
    }
    
    updateStageHeader(stage, leads) {
        const header = document.querySelector(`[data-stage="${stage}"] .pipeline-header`);
        if (!header) return;
        
        const countElement = header.querySelector('.stage-count');
        const valueElement = header.querySelector('.stage-value');
        
        const count = leads.length;
        const totalValue = leads.reduce((sum, lead) => sum + (lead.quoted_amount || 0), 0);
        
        if (countElement) {
            countElement.textContent = count;
            countElement.setAttribute('aria-label', `${count} leads in ${stage}`);
        }
        
        if (valueElement) {
            valueElement.textContent = `$${this.formatCurrency(totalValue)}`;
            valueElement.setAttribute('aria-label', `Total value: $${this.formatCurrency(totalValue)}`);
        }
        
        // Add visual indicators for stage health
        this.updateStageHealth(header, stage, leads);
    }
    
    updateStageHealth(header, stage, leads) {
        const healthIndicator = header.querySelector('.stage-health') || 
                              this.createStageHealthIndicator(header);
        
        let healthStatus = 'good';
        let healthMessage = '';
        
        if (stage === 'New' && leads.length > 10) {
            healthStatus = 'warning';
            healthMessage = 'High volume of new leads';
        } else if (stage === 'Contacted' && leads.some(lead => 
            this.calculateDaysSinceLastContact(lead.last_contact_date) > 7)) {
            healthStatus = 'danger';
            healthMessage = 'Some leads need follow-up';
        } else if (stage === 'Quoted' && leads.some(lead => 
            this.calculateDaysSinceLastContact(lead.last_contact_date) > 14)) {
            healthStatus = 'danger';
            healthMessage = 'Quotes are getting stale';
        }
        
        healthIndicator.className = `stage-health health-${healthStatus}`;
        healthIndicator.setAttribute('title', healthMessage);
        healthIndicator.setAttribute('aria-label', `Stage health: ${healthStatus}. ${healthMessage}`);
    }
    
    createStageHealthIndicator(header) {
        const indicator = document.createElement('div');
        indicator.className = 'stage-health';
        indicator.innerHTML = '<i class="fas fa-circle"></i>';
        header.appendChild(indicator);
        return indicator;
    }
    
    // Drag and Drop Event Handlers
    handleDragStart(e) {
        if (!e.target.classList.contains('lead-card')) return;
        
        this.draggedElement = e.target;
        e.target.classList.add('dragging');
        e.target.style.opacity = '0.5';
        
        // Set drag data
        e.dataTransfer.setData('text/plain', e.target.dataset.leadId);
        e.dataTransfer.effectAllowed = 'move';
        
        // Add visual feedback
        this.highlightDropZones();
        
        // Announce to screen readers
        this.announceToScreenReader(`Started dragging lead ${e.target.querySelector('.lead-name').textContent}`);
    }
    
    handleDragEnd(e) {
        if (!e.target.classList.contains('lead-card')) return;
        
        e.target.classList.remove('dragging');
        e.target.style.opacity = '';
        this.draggedElement = null;
        
        // Remove visual feedback
        this.removeDropZoneHighlights();
    }
    
    handleDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        
        const dropZone = e.target.closest('[data-stage]');
        if (dropZone) {
            dropZone.classList.add('drag-over');
        }
    }
    
    handleDragEnter(e) {
        e.preventDefault();
        const dropZone = e.target.closest('[data-stage]');
        if (dropZone) {
            dropZone.classList.add('drag-over');
        }
    }
    
    handleDragLeave(e) {
        const dropZone = e.target.closest('[data-stage]');
        if (dropZone && !dropZone.contains(e.relatedTarget)) {
            dropZone.classList.remove('drag-over');
        }
    }
    
    handleDrop(e) {
        e.preventDefault();
        
        const dropZone = e.target.closest('[data-stage]');
        if (!dropZone) return;
        
        dropZone.classList.remove('drag-over');
        
        const leadId = e.dataTransfer.getData('text/plain');
        const newStage = dropZone.dataset.stage;
        
        if (leadId && newStage) {
            this.moveLeadToStage(leadId, newStage);
        }
    }
    
    // Touch Event Handlers for Mobile
    handleTouchStart(e) {
        if (!e.target.closest('.lead-card')) return;
        
        const card = e.target.closest('.lead-card');
        this.touchStartY = e.touches[0].clientY;
        this.touchStartX = e.touches[0].clientX;
        
        // Add touch feedback
        card.classList.add('touch-active');
        
        // Haptic feedback if available
        if (navigator.vibrate) {
            navigator.vibrate(50);
        }
    }
    
    handleTouchMove(e) {
        if (!e.target.closest('.lead-card')) return;
        
        const card = e.target.closest('.lead-card');
        const touch = e.touches[0];
        const deltaY = touch.clientY - this.touchStartY;
        const deltaX = touch.clientX - this.touchStartX;
        
        // If significant movement, start drag mode
        if (Math.abs(deltaY) > 10 || Math.abs(deltaX) > 10) {
            e.preventDefault();
            card.style.transform = `translate(${deltaX}px, ${deltaY}px)`;
            card.classList.add('touch-dragging');
            
            // Show drop zones
            this.highlightDropZones();
        }
    }
    
    handleTouchEnd(e) {
        const card = e.target.closest('.lead-card');
        if (!card) return;
        
        card.classList.remove('touch-active', 'touch-dragging');
        card.style.transform = '';
        
        // Check if dropped on a stage
        const touch = e.changedTouches[0];
        const elementBelow = document.elementFromPoint(touch.clientX, touch.clientY);
        const dropZone = elementBelow?.closest('[data-stage]');
        
        if (dropZone && card.dataset.leadId) {
            const newStage = dropZone.dataset.stage;
            this.moveLeadToStage(card.dataset.leadId, newStage);
        }
        
        this.removeDropZoneHighlights();
    }
    
    // Keyboard Navigation
    handleKeyNavigation(e) {
        if (!document.activeElement.classList.contains('lead-card')) return;
        
        const card = document.activeElement;
        const leadId = card.dataset.leadId;
        const currentLead = this.leads.find(lead => lead.id == leadId);
        
        if (!currentLead) return;
        
        const currentStageIndex = this.stages.indexOf(currentLead.status);
        let newStageIndex = currentStageIndex;
        
        switch (e.key) {
            case 'ArrowLeft':
                e.preventDefault();
                newStageIndex = Math.max(0, currentStageIndex - 1);
                break;
            case 'ArrowRight':
                e.preventDefault();
                newStageIndex = Math.min(this.stages.length - 1, currentStageIndex + 1);
                break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                this.openLeadDetailsModal(leadId);
                return;
            case 'Delete':
            case 'Backspace':
                e.preventDefault();
                if (confirm('Are you sure you want to delete this lead?')) {
                    this.deleteLead(leadId);
                }
                return;
        }
        
        if (newStageIndex !== currentStageIndex) {
            const newStage = this.stages[newStageIndex];
            this.moveLeadToStage(leadId, newStage);
            
            // Maintain focus on the moved card
            setTimeout(() => {
                const movedCard = document.querySelector(`[data-lead-id="${leadId}"]`);
                if (movedCard) {
                    movedCard.focus();
                }
            }, 300);
        }
    }
    
    // Core Pipeline Operations
    async moveLeadToStage(leadId, newStage) {
        const lead = this.leads.find(l => l.id == leadId);
        if (!lead || lead.status === newStage) return;
        
        const oldStage = lead.status;
        
        // Optimistic update
        lead.status = newStage;
        lead.last_updated = new Date().toISOString();
        
        // Update UI immediately
        this.renderStageColumn(oldStage);
        this.renderStageColumn(newStage);
        this.updatePipelineStats();
        
        // Show loading state
        this.showStageLoadingState(newStage);
        
        try {
            // Send update to server
            const response = await fetch(`/api/leads/${leadId}/status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({ status: newStage })
            });
            
            if (!response.ok) {
                throw new Error('Failed to update lead status');
            }
            
            // Update local storage
            this.updateLocalStorage();
            
            // Show success notification
            this.showNotification(`Lead moved to ${newStage}`, 'success');
            
            // Log activity
            this.logActivity(`Lead ${lead.name} moved from ${oldStage} to ${newStage}`);
            
            // Trigger analytics
            this.trackPipelineMovement(leadId, oldStage, newStage);
            
        } catch (error) {
            // Revert optimistic update
            lead.status = oldStage;
            this.renderStageColumn(oldStage);
            this.renderStageColumn(newStage);
            
            console.error('Error updating lead status:', error);
            this.showNotification('Failed to update lead status', 'error');
        } finally {
            this.hideStageLoadingState(newStage);
        }
        
        // Announce to screen readers
        this.announceToScreenReader(`Lead ${lead.name} moved to ${newStage}`);
    }
    
    // Visual Feedback Methods
    highlightDropZones() {
        document.querySelectorAll('[data-stage]').forEach(zone => {
            zone.classList.add('drop-zone-active');
        });
    }
    
    removeDropZoneHighlights() {
        document.querySelectorAll('[data-stage]').forEach(zone => {
            zone.classList.remove('drop-zone-active', 'drag-over');
        });
    }
    
    showStageLoadingState(stage) {
        const header = document.querySelector(`[data-stage="${stage}"] .pipeline-header`);
        if (header) {
            const spinner = document.createElement('div');
            spinner.className = 'stage-spinner';
            spinner.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            header.appendChild(spinner);
        }
    }
    
    hideStageLoadingState(stage) {
        const spinner = document.querySelector(`[data-stage="${stage}"] .stage-spinner`);
        if (spinner) {
            spinner.remove();
        }
    }
    
    setupColumnAnimations() {
        // Animate cards entering stages
        document.querySelectorAll('.lead-card').forEach((card, index) => {
            card.style.animationDelay = `${index * 50}ms`;
            card.classList.add('fade-in-up');
        });
    }
    
    // Pipeline Statistics and Analytics
    updatePipelineStats() {
        const stats = this.calculatePipelineStats();
        this.updateStatsDisplay(stats);
        this.updateConversionRates();
        this.updateRevenueProjections();
    }
    
    calculatePipelineStats() {
        return {
            totalLeads: this.leads.length,
            totalValue: this.leads.reduce((sum, lead) => sum + (lead.quoted_amount || 0), 0),
            conversionRate: this.calculateConversionRate(),
            averageDealSize: this.calculateAverageDealSize(),
            stageDistribution: this.calculateStageDistribution(),
            velocityMetrics: this.calculateVelocityMetrics()
        };
    }
    
    calculateConversionRate() {
        const totalLeads = this.leads.length;
        const convertedLeads = this.leads.filter(lead => lead.status === 'Converted').length;
        return totalLeads > 0 ? (convertedLeads / totalLeads * 100).toFixed(1) : 0;
    }
    
    calculateAverageDealSize() {
        const dealsWithValue = this.leads.filter(lead => lead.quoted_amount > 0);
        if (dealsWithValue.length === 0) return 0;
        
        const totalValue = dealsWithValue.reduce((sum, lead) => sum + lead.quoted_amount, 0);
        return (totalValue / dealsWithValue.length).toFixed(0);
    }
    
    calculateStageDistribution() {
        const distribution = {};
        this.stages.forEach(stage => {
            distribution[stage] = this.leads.filter(lead => lead.status === stage).length;
        });
        return distribution;
    }
    
    calculateVelocityMetrics() {
        // Calculate average time spent in each stage
        const velocityData = {};
        this.stages.forEach(stage => {
            const stageLeads = this.leads.filter(lead => lead.status === stage);
            // This would require historical data to be meaningful
            velocityData[stage] = stageLeads.length > 0 ? 
                this.calculateAverageStageTime(stageLeads) : 0;
        });
        return velocityData;
    }
    
    calculateAverageStageTime(leads) {
        // Placeholder - would need historical stage transition data
        return Math.floor(Math.random() * 14) + 1; // Random 1-14 days for demo
    }
    
    updateStatsDisplay(stats) {
        // Update main dashboard stats
        this.updateElement('#total-leads', stats.totalLeads);
        this.updateElement('#total-value', `$${this.formatCurrency(stats.totalValue)}`);
        this.updateElement('#conversion-rate', `${stats.conversionRate}%`);
        this.updateElement('#average-deal', `$${this.formatCurrency(stats.averageDealSize)}`);
        
        // Update stage-specific stats
        Object.entries(stats.stageDistribution).forEach(([stage, count]) => {
            this.updateElement(`#${stage.toLowerCase()}-count`, count);
        });
    }
    
    updateConversionRates() {
        // Calculate and display conversion rates between stages
        const conversionChart = document.getElementById('conversion-chart');
        if (conversionChart) {
            this.renderConversionChart(conversionChart);
        }
    }
    
    updateRevenueProjections() {
        // Calculate projected revenue based on current pipeline
        const projectedRevenue = this.calculateProjectedRevenue();
        this.updateElement('#projected-revenue', `$${this.formatCurrency(projectedRevenue)}`);
    }
    
    calculateProjectedRevenue() {
        const stageWeights = {
            'New': 0.1,
            'Contacted': 0.2,
            'Interested': 0.4,
            'Quoted': 0.7,
            'Converted': 1.0,
            'Lost': 0
        };
        
        return this.leads.reduce((total, lead) => {
            const weight = stageWeights[lead.status] || 0;
            const value = lead.quoted_amount || 0;
            return total + (value * weight);
        }, 0);
    }
    
    // Utility Methods
    calculateDaysSinceLastContact(dateString) {
        if (!dateString) return Infinity;
        
        const lastContact = new Date(dateString);
        const today = new Date();
        const diffTime = today - lastContact;
        return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    }
    
    getUrgencyClass(daysSince, status) {
        if (status === 'Converted' || status === 'Lost') return '';
        
        if (daysSince > 14) return 'text-danger overdue';
        if (daysSince > 7) return 'text-warning urgent';
        return 'text-muted';
    }
    
    formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(amount || 0);
    }
    
    formatDate(dateString) {
        if (!dateString) return 'Not set';
        
        const date = new Date(dateString);
        const today = new Date();
        const diffDays = Math.ceil((date - today) / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Tomorrow';
        if (diffDays === -1) return 'Yesterday';
        if (diffDays < -1) return `${Math.abs(diffDays)} days ago`;
        if (diffDays > 1) return `In ${diffDays} days`;
        
        return date.toLocaleDateString();
    }
    
    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
    
    updateElement(selector, content) {
        const element = document.querySelector(selector);
        if (element) {
            element.textContent = content;
        }
    }
    
    updateLocalStorage() {
        try {
            localStorage.setItem('pipelineData', JSON.stringify(this.leads));
            localStorage.setItem('pipelineLastUpdate', new Date().toISOString());
        } catch (error) {
            console.error('Error saving to localStorage:', error);
        }
    }
    
    getCSRFToken() {
        const token = document.querySelector('meta[name="csrf-token"]');
        return token ? token.getAttribute('content') : '';
    }
    
    showNotification(message, type = 'info') {
        // Create toast notification
        const toast = document.createElement('div');
        toast.className = `toast-uiverse ${type}`;
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="fas fa-${this.getNotificationIcon(type)} me-2"></i>
                <span>${message}</span>
                <button type="button" class="btn-close ms-auto" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Show toast
        setTimeout(() => toast.classList.add('show'), 100);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }
    
    getNotificationIcon(type) {
        const icons = {
            success: 'check-circle',
            error: 'exclamation-triangle',
            warning: 'exclamation-circle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }
    
    announceToScreenReader(message) {
        const announcement = document.getElementById('sr-announcement') || 
                           this.createScreenReaderAnnouncement();
        announcement.textContent = message;
    }
    
    createScreenReaderAnnouncement() {
        const announcement = document.createElement('div');
        announcement.id = 'sr-announcement';
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.className = 'sr-only';
        document.body.appendChild(announcement);
        return announcement;
    }
    
    logActivity(activity) {
        const timestamp = new Date().toISOString();
        console.log(`[${timestamp}] Pipeline Activity: ${activity}`);
        
        // Could send to analytics service
        if (typeof gtag !== 'undefined') {
            gtag('event', 'pipeline_action', {
                event_category: 'Pipeline',
                event_label: activity,
                value: 1
            });
        }
    }
    
    trackPipelineMovement(leadId, fromStage, toStage) {
        // Track pipeline movements for analytics
        if (typeof gtag !== 'undefined') {
            gtag('event', 'pipeline_movement', {
                event_category: 'Pipeline',
                event_label: `${fromStage} → ${toStage}`,
                custom_parameters: {
                    lead_id: leadId,
                    from_stage: fromStage,
                    to_stage: toStage
                }
            });
        }
    }
    
    // View Management
    changeView(event) {
        const viewType = event.target.dataset.pipelineView;
        const currentView = document.querySelector('.pipeline-view.active');
        
        if (currentView) {
            currentView.classList.remove('active');
        }
        
        // Show selected view
        const newView = document.querySelector(`#${viewType}-view`);
        if (newView) {
            newView.classList.add('active');
        }
        
        // Update active button
        document.querySelectorAll('[data-pipeline-view]').forEach(btn => {
            btn.classList.remove('active');
        });
        event.target.classList.add('active');
        
        // Adjust layout for different views
        if (viewType === 'list') {
            this.renderListView();
        } else if (viewType === 'kanban') {
            this.renderKanbanView();
        }
    }
    
    renderListView() {
        const listContainer = document.getElementById('pipeline-list');
        if (!listContainer) return;
        
        const sortedLeads = this.leads.sort((a, b) => {
            const stageOrder = this.stages.indexOf(a.status) - this.stages.indexOf(b.status);
            if (stageOrder !== 0) return stageOrder;
            return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        });
        
        listContainer.innerHTML = sortedLeads.map(lead => this.createListViewRow(lead)).join('');
    }
    
    createListViewRow(lead) {
        return `
            <tr data-lead-id="${lead.id}" class="pipeline-row">
                <td>
                    <div class="d-flex align-items-center">
                        <div class="stage-indicator" style="background-color: ${this.stageColors[lead.status]}"></div>
                        <div class="ms-2">
                            <div class="fw-bold">${this.escapeHtml(lead.name)}</div>
                            <small class="text-muted">${this.escapeHtml(lead.phone)}</small>
                        </div>
                    </div>
                </td>
                <td>
                    <span class="status-badge status-${lead.status.toLowerCase()}">${lead.status}</span>
                </td>
                <td>${lead.course_name ? this.escapeHtml(lead.course_name) : '-'}</td>
                <td>${lead.quoted_amount ? '$' + this.formatCurrency(lead.quoted_amount) : '-'}</td>
                <td>${this.formatDate(lead.next_followup_date)}</td>
                <td>${lead.lead_source ? this.escapeHtml(lead.lead_source) : '-'}</td>
                <td>
                    <div class="action-buttons">
                        <button class="btn btn-sm btn-outline-primary" onclick="viewLeadDetails(${lead.id})">
                            <i class="fas fa-eye"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-warning" onclick="editLead(${lead.id})">
                            <i class="fas fa-edit"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }
    
    renderKanbanView() {
        // Re-render the kanban columns
        this.renderPipeline();
    }
    
    // Responsive Design
    handleResize() {
        const width = window.innerWidth;
        
        if (width < 768) {
            this.enableMobileLayout();
        } else {
            this.enableDesktopLayout();
        }
    }
    
    enableMobileLayout() {
        document.body.classList.add('mobile-pipeline');
        
        // Convert to vertical scrolling on mobile
        const pipelineContainer = document.querySelector('.pipeline-container');
        if (pipelineContainer) {
            pipelineContainer.classList.add('mobile-scroll');
        }
    }
    
    enableDesktopLayout() {
        document.body.classList.remove('mobile-pipeline');
        
        const pipelineContainer = document.querySelector('.pipeline-container');
        if (pipelineContainer) {
            pipelineContainer.classList.remove('mobile-scroll');
        }
    }
    
    // Auto-refresh functionality
    setupAutoRefresh() {
        // Refresh pipeline data every 30 seconds
        setInterval(() => {
            this.refreshPipelineData();
        }, 30000);
        
        // Set up visibility change listener to refresh when tab becomes visible
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.refreshPipelineData();
            }
        });
    }
    
    async refreshPipelineData() {
        try {
            const response = await fetch('/api/pipeline/data');
            if (response.ok) {
                const data = await response.json();
                
                // Check if data has changed
                const currentData = JSON.stringify(this.leads);
                const newData = JSON.stringify(data.leads || []);
                
                if (currentData !== newData) {
                    this.leads = data.leads || [];
                    this.renderPipeline();
                    this.updateLocalStorage();
                    
                    // Notify user of updates
                    this.showNotification('Pipeline updated', 'info');
                }
            }
        } catch (error) {
            console.error('Error refreshing pipeline data:', error);
        }
    }
    
    // Public API Methods
    addLead(leadData) {
        this.leads.push(leadData);
        this.renderStageColumn(leadData.status);
        this.updatePipelineStats();
        this.updateLocalStorage();
    }
    
    removeLead(leadId) {
        const leadIndex = this.leads.findIndex(lead => lead.id == leadId);
        if (leadIndex === -1) return;
        
        const lead = this.leads[leadIndex];
        this.leads.splice(leadIndex, 1);
        
        this.renderStageColumn(lead.status);
        this.updatePipelineStats();
        this.updateLocalStorage();
    }
    
    updateLead(leadId, updatedData) {
        const lead = this.leads.find(lead => lead.id == leadId);
        if (!lead) return;
        
        const oldStatus = lead.status;
        Object.assign(lead, updatedData);
        
        if (oldStatus !== lead.status) {
            this.renderStageColumn(oldStatus);
        }
        this.renderStageColumn(lead.status);
        this.updatePipelineStats();
        this.updateLocalStorage();
    }
    
    getLeadById(leadId) {
        return this.leads.find(lead => lead.id == leadId);
    }
    
    getLeadsByStatus(status) {
        return this.leads.filter(lead => lead.status === status);
    }
    
    exportPipelineData() {
        const dataStr = JSON.stringify(this.leads, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        
        const link = document.createElement('a');
        link.href = URL.createObjectURL(dataBlob);
        link.download = `pipeline-data-${new Date().toISOString().split('T')[0]}.json`;
        link.click();
    }
}

// Initialize Pipeline Manager when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.pipeline-container')) {
        window.pipelineManager = new PipelineManager();
    }
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PipelineManager;
}
