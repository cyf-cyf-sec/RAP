class FlowManager {
    constructor() {
        this.flowContainer = document.getElementById('analysis_flow');
        this.steps = {
            pr_crawler: document.getElementById('step_pr_list'),
            pr_filter: document.getElementById('step_pr_filter'),
            commit_crawler: document.getElementById('step_pr_details'),
            file_crawler: document.getElementById('step_code_files'),
            function_extractor: document.getElementById('step_function_extract'),
            code_generation: document.getElementById('step_code_generation'),
            deduplication: document.getElementById('step_deduplication')
        };
        
        this.currentStep = null;
        this.stepOrder = ['pr_crawler', 'pr_filter', 'commit_crawler', 'file_crawler', 'function_extractor', 'code_generation', 'deduplication'];
        
        // PR data cache
        this.prDataCache = null;
        
        // Step weight configuration
        this.stepWeights = {
            'pr_crawler': 1,
            'pr_filter': 1,
            'commit_crawler': 1,
            'file_analyzer': 1,
            'function_extractor': 1,
            'code_generation': 1,
            'deduplication': 1
        };
        
        // Total weight
        this.totalWeight = Object.values(this.stepWeights).reduce((sum, weight) => sum + weight, 0);
        
        // Task type to step name mapping
        this.taskTypeToStepMap = {
            'pr_crawl': 'pr_crawler',
            'pr_classification': 'pr_filter',
            'pr_details_crawl': 'commit_crawler',
            'file_analysis': 'file_crawler',
            'function_extraction': 'function_extractor',
            'code_generation': 'code_generation',
            'deduplication': 'deduplication'
        };
        
        // Initialize step visibility
        this.updateStepVisibility();
    }

    // Map backend task type to frontend step name
    mapTaskTypeToStepName(taskType) {
        return this.taskTypeToStepMap[taskType] || null;
    }

    // Show flow display area
    show() {
        if (this.flowContainer) {
            this.flowContainer.style.display = 'block';
        }
    }

    // Hide flow display area
    hide() {
        if (this.flowContainer) {
            this.flowContainer.style.display = 'none';
        }
    }

    // Reset all step states
    reset() {
        Object.values(this.steps).forEach(step => {
            if (step) {
                step.className = 'flow-step';
                step.style.display = 'block'; // Ensure all steps are displayed
                const statusElement = step.querySelector('.step-status');
                if (statusElement) {
                statusElement.textContent = 'Waiting to start';
            }
                
                // Hide all step progress info areas
                this.hideStepProgressInfo(step);
            }
        });
        
        this.updateProgress(0);
        this.currentStep = null;
    }

    // Start specified step
    startStep(stepName) {
        if (this.steps[stepName]) {
            // If there was a previous step, stop its timer and mark as completed
            if (this.currentStep && this.currentStep !== stepName) {
                this.stopStepTimer(this.currentStep);
                this.completeStep(this.currentStep);
            }
            
            this.steps[stepName].className = 'flow-step active';
            const statusElement = this.steps[stepName].querySelector('.step-status');
            if (statusElement) {
                statusElement.textContent = 'In progress...';
            }
            
            this.currentStep = stepName;
            
            // Reset current step timer start time
            const now = new Date();
            switch (stepName) {
                case 'pr_crawler':
                    this.prCrawlStartTime = now;
                    console.log('Step 1 started, reset timer:', now);
                    break;
                case 'pr_filter':
                    this.filterStartTime = now;
                    console.log('Step 2 started, reset timer:', now);
                    break;
                case 'commit_crawler':
                    this.detailsStartTime = now;
                    console.log('Step 3 started, reset timer:', now);
                    break;
                case 'file_crawler':
                    this.filesStartTime = now;
                    console.log('Step 4 started, reset timer:', now);
                    break;
                case 'function_extractor':
                    this.functionStartTime = now;
                    console.log('Step 5 started, reset timer:', now);
                    break;
                case 'code_generation':
                    this.codegenStartTime = now;
                    console.log('Step 5.5 started, reset timer:', now);
                    break;
                case 'deduplication':
                    this.dedupStartTime = now;
                    console.log('Step 6 started, reset timer:', now);
                    break;
            }
            
            // Show current step's progress info area
            this.showStepProgressInfo(this.steps[stepName]);
            
            console.log(`Starting step: ${stepName}`);
        }
    }

    // Complete specified step
    completeStep(stepName) {
        if (this.steps[stepName]) {
            this.steps[stepName].className = 'flow-step completed';
            const statusElement = this.steps[stepName].querySelector('.step-status');
            if (statusElement) {
                statusElement.textContent = 'Completed';
            }
            
            // Stop corresponding step timer
            this.stopStepTimer(stepName);
            
            this.updateProgress(this.calculateProgress());
        }
    }
    
    // Stop specified step timer
    stopStepTimer(stepName) {
        switch (stepName) {
            case 'pr_crawler':
                this.stopPRTimeUpdater();
                break;
            case 'pr_filter':
                this.stopFilterTimeUpdater();
                break;
            case 'commit_crawler':
                this.stopDetailsTimeUpdater();
                break;
        }
    }

    // Mark step as failed
    failStep(stepName, errorMessage = '') {
        if (this.steps[stepName]) {
            this.steps[stepName].className = 'flow-step failed';
            const statusElement = this.steps[stepName].querySelector('.step-status');
            if (statusElement) {
                statusElement.textContent = errorMessage || 'Failed';
            }
        }
    }

    // Update step status
    updateStepStatus(stepName, status, message = '') {
        if (this.steps[stepName]) {
            const statusElement = this.steps[stepName].querySelector('.step-status');
            if (statusElement) {
                statusElement.textContent = message || this.getStatusText(status);
            }
            
            switch (status) {
                case 'active':
                    this.steps[stepName].className = 'flow-step active';
                    this.currentStep = stepName;
                    break;
                case 'completed':
                    this.steps[stepName].className = 'flow-step completed';
                    break;
                case 'failed':
                    this.steps[stepName].className = 'flow-step failed';
                    break;
                default:
                    this.steps[stepName].className = 'flow-step';
            }
            
            this.updateProgress(this.calculateProgress());
        }
    }

    // Get status text
    getStatusText(status) {
        const statusMap = {
            'active': 'In progress...',
            'completed': 'Completed',
            'failed': 'Failed',
            'waiting': 'Waiting to start'
        };
        return statusMap[status] || 'Waiting to start';
    }

    // Calculate current progress
    calculateProgress() {
        let completedWeight = 0;
        
        this.stepOrder.forEach(stepName => {
            const step = this.steps[stepName];
            if (step && step.classList.contains('completed')) {
                completedWeight += this.stepWeights[stepName];
            } else if (step && step.classList.contains('active')) {
                // Current step is half completed
                completedWeight += this.stepWeights[stepName] * 0.5;
            }
        });
        
        return Math.round((completedWeight / this.totalWeight) * 100);
    }

    // Update progress bar
    updateProgress(percentage) {
        if (this.progressFill) {
            this.progressFill.style.width = `${percentage}%`;
        }
        
        if (this.progressText) {
            this.progressText.textContent = `${percentage}%`;
        }
    }

    // Simulate flow execution (for demo)
    async simulateFlow() {
        this.show();
        this.reset();
        
        const steps = this.stepOrder;
        
        for (let i = 0; i < steps.length; i++) {
            const stepName = steps[i];

            this.startStep(stepName);
            await this.delay(2000);
            this.completeStep(stepName);
            if (i < steps.length - 1) {
                await this.delay(500);
            }
        }
    }

    // Delay function
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // Handle backend progress update
    handleProgressUpdate(progressData) {
        if (!progressData) return;
        
        console.log('Received progress update:', progressData);
        
        // Update current step (using the current_task field from backend)
        if (progressData.current_task) {
            // Map backend task type to frontend step name
            const stepName = this.mapTaskTypeToStepName(progressData.current_task);
            if (stepName) {
                this.updateStepStatus(stepName, 'active', 'In progress...');
            }
        }
        
        // Update step detailed progress info (using the tasks field from backend)
        if (progressData.tasks) {
            Object.entries(progressData.tasks).forEach(([taskName, taskData]) => {
                this.updateStepProgress(taskName, taskData);
                
                // Update step status based on task status
                if (taskData.status === 'completed') {
                    this.updateStepStatus(taskName, 'completed', 'Completed');
                    
                    // If PR crawl completed, save data to cache
                    if (taskName === 'pr_crawler' && progressData.progress_data) {
                        this.cachePRData(progressData.progress_data);
                    }
                } else if (taskData.status === 'failed') {
                    this.updateStepStatus(taskName, 'failed', taskData.message || 'Failed');
                }
            });
        }
        
        // If no tasks field but has progress_data, update current step directly
        if (!progressData.tasks && progressData.progress_data) {
            const currentTask = progressData.current_task || 'pr_crawl';
            const stepName = this.mapTaskTypeToStepName(currentTask);
            
            if (stepName) {
                // Update step status
                this.updateStepStatus(stepName, progressData.status === 'completed' ? 'completed' : 'active', 
                                    progressData.status === 'completed' ? 'Completed' : 'In progress...');
                
                // Update step progress info
                this.updateStepProgress(stepName, progressData.progress_data);
                
                // If PR crawl completed, save data to cache
                if (stepName === 'pr_crawler' && progressData.status === 'completed') {
                    this.cachePRData(progressData.progress_data);
                }
            }
        }
        
        // Update step display status (don't show next step if previous step is not completed)
        this.updateStepVisibility();
    }

    // Update step detailed progress info
    updateStepProgress(stepName, stepData) {
        const stepElement = this.steps[stepName];
        if (!stepElement) return;
        
        // Update step progress info area visibility
        const progressInfo = stepElement.querySelector('.step-progress-info');
        if (progressInfo) {
            progressInfo.style.display = 'block';
        }
        
        // Update specific data based on step type
        switch (stepName) {
            case 'pr_crawler':
                this.updatePRListProgress(stepData);
                break;
            case 'pr_filter':
                this.updatePRFilterProgress(stepData);
                break;
            case 'commit_crawler':
                this.updatePRDetailsProgress(stepData);
                break;
            case 'file_crawler':
                this.updateCodeFilesProgress(stepData);
                break;
            case 'function_extractor':
                this.updateFunctionExtractProgress(stepData);
                break;
            case 'code_generation':
                this.updateCodeGenerationProgress(stepData);
                break;
            case 'deduplication':
                this.updateDeduplicationProgress(stepData);
                break;
        }
    }

    // Update PR list crawl progress (display count and time)
    updatePRListProgress(data) {
        const countElement = document.getElementById('pr_count');
        const timeElement = document.getElementById('pr_time');
        const statusElement = document.getElementById('pr_status');
        
        console.log('=== Step 1: PR List Crawl ===');
        console.log('Received progress data:', JSON.stringify(data, null, 2));
        
        // Update count display (only update the number part, not the fixed text)
        if (countElement) {
            switch (data.status) {
                case 'completed':
                    // Show total after completion
                    const total = data.total || data.pr_count || 0;
                    countElement.textContent = total;
                    break;
                case 'failed':
                    // Show crawled count on failure
                    const crawled = data.pr_count || 0;
                    countElement.textContent = crawled;
                    break;
                default:
                    // Show current count during progress
                    const current = data.current || data.pr_count || 0;
                    countElement.textContent = current;
            }
        }
        
        // Update time display (only update the number part)
        if (timeElement) {
            const elapsedTime = this.calculateElapsedTime(data);
            timeElement.textContent = elapsedTime;
        }
        
        // 如果有状态元素，显示状态信息
        if (statusElement) {
            switch (data.status) {
                case 'completed':
                    statusElement.textContent = '✓ Completed';
                    statusElement.className = 'status completed';
                    break;
                case 'failed':
                    statusElement.textContent = `✗ Failed: ${data.error || 'Unknown error'}`;
                    statusElement.className = 'status failed';
                    break;
                default:
                    statusElement.textContent = `In progress (Page ${data.current_page || 1})`;
                    statusElement.className = 'status running';
            }
        }
        
        // If still running, start independent time update timer
        if (data.status === 'running' && !this.prTimeInterval) {
            this.startPRTimeUpdater();
        } else if (data.status !== 'running' && this.prTimeInterval) {
            this.stopPRTimeUpdater();
        }
    }
    
    // Calculate elapsed time (seconds)
    calculateElapsedTime(data) {
        if (data.last_updated) {
            const startTime = this.prCrawlStartTime || new Date(data.last_updated);
            const currentTime = new Date();
            return Math.round((currentTime - startTime) / 1000);
        }
        return Math.round(data.elapsed_time || 0);
    }
    
    // Start PR crawl time update timer
    startPRTimeUpdater() {
        if (this.prTimeInterval) return;
        
        this.prTimeInterval = setInterval(() => {
            const timeElement = document.getElementById('pr_time');
            if (timeElement) {
                const elapsedTime = this.calculateElapsedTime({ last_updated: true });
                timeElement.textContent = elapsedTime;
            }
        }, 1000); // Update every second
    }
    
    // Stop PR crawl time update timer
    stopPRTimeUpdater() {
        if (this.prTimeInterval) {
            clearInterval(this.prTimeInterval);
            this.prTimeInterval = null;
        }
    }

    // Update PR filter progress (with progress bar)
    updatePRFilterProgress(data) {
        const countElement = document.getElementById('filter_count');
        const timeElement = document.getElementById('filter_time');
        const progressFill = document.getElementById('filter_progress');
        const progressText = document.getElementById('filter_progress_text');
        
        console.log('=== Step 2: PR Filter Classification ===');
        console.log('Received progress data:', JSON.stringify(data, null, 2));
        
        // Update processing count display
        if (countElement) {
            const processed = data.processed_count || data.current || 0;
            const total = data.total_count || data.total || 0;
            countElement.textContent = `${processed}/${total}`;
        }
        
        // Update time display
        if (timeElement) {
            const elapsedTime = this.calculateFilterElapsedTime(data);
            timeElement.textContent = elapsedTime;
        }
        
        // Update progress bar
        if (progressFill && progressText) {
            const processed = data.processed_count || data.current || 0;
            const total = data.total_count || data.total || 1;
            const percentage = total > 0 ? Math.round((processed / total) * 100) : 0;
            progressFill.style.width = percentage + '%';
            progressText.textContent = percentage + '%';
        }
        
        // If task completed, show file statistics
        if (data.status === 'completed') {
            const fileStatsElement = document.getElementById('files_stats');
            if (fileStatsElement) {
                const totalFiles = data.total_files || 0;
                const crawledFiles = data.crawled_files || 0;
                fileStatsElement.innerHTML = `
                    <div class="stats-row">
                        <span class="stats-label">Total files:</span>
                        <span class="stats-value">${totalFiles}</span>
                    </div>
                    <div class="stats-row">
                        <span class="stats-label">Crawled files:</span>
                        <span class="stats-value">${crawledFiles}</span>
                    </div>
                `;
            }
        }
        
        // If completed, show detailed statistics
        if (data.status === 'completed') {
            this.showFilterCompletionStats(data);
            // Cache output file path (supports both output_file and output_path field names)
            const outputPath = data.output_file || data.output_path || '';
            if (outputPath) {
                this.filterOutputFile = outputPath;
            }
            
            // Save filtered PR total for step 3 display
            const stats = data.statistics || {};
            this.filteredTotalPRs = stats.remaining_prs || data.processed_count || 0;
            console.log('Step 2 completed, saved filtered total:', this.filteredTotalPRs);
            
            // Trigger custom event to notify FormComponent to start next step
            const event = new CustomEvent('prFilterCompleted', {
                detail: {
                    outputFile: outputPath,
                    humanPrs: data.human_prs || 0,
                    agentPrs: data.agent_prs || 0,
                    statistics: data.statistics || {},
                    filteredTotal: this.filteredTotalPRs
                }
            });
            document.dispatchEvent(event);
        }
        
        // Start/stop time update timer
        if (data.status === 'running' && !this.filterTimeInterval) {
            this.startFilterTimeUpdater();
        } else if (data.status !== 'running' && this.filterTimeInterval) {
            this.stopFilterTimeUpdater();
        }
    }
    
    // Calculate filter elapsed time
    calculateFilterElapsedTime(data) {
        if (data.last_updated) {
            const startTime = this.filterStartTime || new Date(data.last_updated);
            const currentTime = new Date();
            return Math.round((currentTime - startTime) / 1000);
        }
        return Math.round(data.elapsed_time || 0);
    }
    
    // Start filter time update timer
    startFilterTimeUpdater() {
        if (this.filterTimeInterval) return;
        
        this.filterTimeInterval = setInterval(() => {
            const timeElement = document.getElementById('filter_time');
            if (timeElement) {
                const elapsedTime = this.calculateFilterElapsedTime({ last_updated: true });
                timeElement.textContent = elapsedTime;
            }
        }, 1000);
    }
    
    // Stop filter time update timer
    stopFilterTimeUpdater() {
        if (this.filterTimeInterval) {
            clearInterval(this.filterTimeInterval);
            this.filterTimeInterval = null;
        }
    }
    
    // Show filter completion statistics
    showFilterCompletionStats(data) {
        const statsElement = document.getElementById('filter_stats');
        if (!statsElement) {
            // Create statistics element
            const stepElement = this.steps['pr_filter'];
            if (stepElement) {
                const progressInfo = stepElement.querySelector('.step-progress-info');
                if (progressInfo) {
                    const statsDiv = document.createElement('div');
                    statsDiv.id = 'filter_stats';
                    statsDiv.className = 'filter-stats';
                    progressInfo.appendChild(statsDiv);
                }
            }
        }
        
        const statsDiv = document.getElementById('filter_stats');
        if (statsDiv) {
            const stats = data.statistics || {};
            const agentBreakdown = data.agent_breakdown || {};
            
            // Build Agent classification HTML
            let agentBreakdownHtml = '';
            if (Object.keys(agentBreakdown).length > 0) {
                const breakdownItems = Object.entries(agentBreakdown)
                    .filter(([agentName, count]) => agentName !== 'human' && count > 0)
                    .map(([agentName, count]) => `<div class="agent-item"><span class="agent-name">${agentName}:</span><span class="agent-count">${count}</span></div>`)
                    .join('');
                
                if (breakdownItems) {
                    agentBreakdownHtml = `
                        <div class="stats-column">
                            <div class="stats-column-title">Agent Classification</div>
                            <div class="agent-breakdown-list">
                                ${breakdownItems}
                            </div>
                        </div>
                    `;
                }
            }
            
            let statsHtml = `
                <div class="stats-grid">
                    <div class="stats-column">
                        <div class="stats-column-title">Total Statistics</div>
                        <div class="stats-item">
                            <span class="stats-label">Original total:</span>
                            <span class="stats-value">${stats.total_input_prs || 0}</span>
                        </div>
                        <div class="stats-item">
                            <span class="stats-label">Remaining after filter:</span>
                            <span class="stats-value highlight">${stats.remaining_prs || data.processed_count || 0}</span>
                        </div>
                    </div>
                    
                    <div class="stats-column">
                        <div class="stats-column-title">Filter Statistics</div>
                        <div class="stats-item">
                            <span class="stats-label">Time filter:</span>
                            <span class="stats-value negative">-${stats.filtered_time_prs || 0}</span>
                        </div>
                        <div class="stats-item">
                            <span class="stats-label">Merge filter:</span>
                            <span class="stats-value negative">-${stats.filtered_merged || 0}</span>
                        </div>
                    </div>
                    
                    <div class="stats-column">
                        <div class="stats-column-title">Classification Statistics</div>
                        <div class="stats-item">
                            <span class="stats-label">Human PRs:</span>
                            <span class="stats-value human">${data.human_prs || 0}</span>
                        </div>
                        <div class="stats-item">
                            <span class="stats-label">Agent PRs:</span>
                            <span class="stats-value agent">${data.agent_prs || 0}</span>
                        </div>
                    </div>
                    
                    ${agentBreakdownHtml}
                </div>
            `;
            
            statsDiv.innerHTML = statsHtml;
            statsDiv.style.display = 'block';
        }
    }

    // Update PR details crawl progress (with progress bar)
    updatePRDetailsProgress(data) {
        const countElement = document.getElementById('details_count');
        const timeElement = document.getElementById('details_time');
        const progressFill = document.getElementById('details_progress');
        const progressText = document.getElementById('details_progress_text');
        
        console.log('=== Step 3: PR Details Crawl ===');
        console.log('Received progress data:', JSON.stringify(data, null, 2));
        
        // Update processing count display
        if (countElement) {
            const processed = Math.max(0, data.processed_count || data.current || 0);
            // Use filtered total saved from step 2, or use backend returned value if not available
            const total = this.filteredTotalPRs || Math.max(1, data.total_count || data.total || 1);
            countElement.textContent = `${processed}/${total}`;
        }
        
        // Update time display
        if (timeElement) {
            const elapsedTime = this.calculateDetailsElapsedTime(data);
            timeElement.textContent = elapsedTime;
        }
        
        // Update progress bar
        if (progressFill && progressText) {
            const processed = Math.max(0, data.processed_count || data.current || 0);
            // Use filtered total saved from step 2
            const total = this.filteredTotalPRs || Math.max(1, data.total_count || data.total || 1);
            const percentage = total > 0 ? Math.round((processed / total) * 100) : 0;
            progressFill.style.width = percentage + '%';
            progressText.textContent = percentage + '%';
        }
        
        // If completed, cache output file path and trigger event
        if (data.status === 'completed') {
            if (data.output_file) {
                this.detailsOutputFile = data.output_file;
            }
            
            // Trigger custom event to notify FormComponent to start next step
            const event = new CustomEvent('prDetailsCompleted', {
                detail: {
                    outputFile: data.output_file || '',
                    totalPRs: this.filteredTotalPRs || data.total_count || 0
                }
            });
            document.dispatchEvent(event);
        }
        
        // Start/stop time update timer
        if (data.status === 'running' && !this.detailsTimeInterval) {
            console.log('Step 3: status is running, starting timer');
            this.startDetailsTimeUpdater();
        } else if (data.status !== 'running' && this.detailsTimeInterval) {
            console.log('Step 3: status is not running, stopping timer');
            this.stopDetailsTimeUpdater();
        } else {
            console.log('Step 3: timer status unchanged - status:', data.status, 'interval:', this.detailsTimeInterval);
        }
    }
    
    // Calculate details crawl elapsed time
    calculateDetailsElapsedTime(data) {
        if (data.last_updated) {
            const startTime = this.detailsStartTime || new Date(data.last_updated);
            const currentTime = new Date();
            const elapsed = Math.round((currentTime - startTime) / 1000);
            return elapsed;
        }
        return Math.round(data.elapsed_time || 0);
    }
    
    // Start details crawl time update timer
    startDetailsTimeUpdater() {
        if (this.detailsTimeInterval) return;
        
        this.detailsTimeInterval = setInterval(() => {
            const timeElement = document.getElementById('details_time');
            if (timeElement) {
                const elapsedTime = this.calculateDetailsElapsedTime({ last_updated: true });
                timeElement.textContent = elapsedTime;
            }
        }, 1000);
    }
    
    // Stop details crawl time update timer
    stopDetailsTimeUpdater() {
        if (this.detailsTimeInterval) {
            clearInterval(this.detailsTimeInterval);
            this.detailsTimeInterval = null;
        }
    }

    // Update code file fetch progress (with progress bar)
    updateCodeFilesProgress(data) {
        const countElement = document.getElementById('files_count');
        const timeElement = document.getElementById('files_time');
        const progressFill = document.getElementById('files_progress');
        const progressText = document.getElementById('files_progress_text');
        const statsElement = document.getElementById('files_stats');
        
        console.log('=== Step 4: Code File Crawl ===');
        console.log('Received progress data:', JSON.stringify(data, null, 2));
        
        const processed = data.processed_count || data.current || 0;
        const total = data.total_count || data.total || 0;
        const currentType = data.current_type || '';
        const codeFiles = data.code_files || 0;
        const downloadedFiles = data.downloaded_files || 0;
        const failedFiles = data.failed_files || 0;
        
        // Update processing count display
        if (countElement) {
            if (data.status === 'running' && currentType) {
                countElement.textContent = `${currentType}.jsonl: ${processed}/${total}`;
            } else if (data.status === 'completed') {
                countElement.textContent = `Download complete: ${downloadedFiles} successful, ${failedFiles} failed`;
            } else {
                countElement.textContent = `${processed}/${total}`;
            }
        }
        
        // Update time display
        if (timeElement) {
            const elapsedTime = this.calculateFilesElapsedTime(data);
            timeElement.textContent = elapsedTime;
        }
        
        // Update progress bar
        if (progressFill && progressText) {
            const percentage = total > 0 ? Math.round((processed / total) * 100) : 0;
            progressFill.style.width = percentage + '%';
            progressText.textContent = percentage + '%';
        }
        
        // Update detailed statistics
        if (statsElement) {
            if (data.status === 'running' && currentType) {
                statsElement.style.display = 'block';
                statsElement.innerHTML = `
                    <div class="stats-grid">
                        <div class="stats-item">
                            <span class="stats-label">Currently processing:</span>
                            <span class="stats-value">${currentType}.jsonl</span>
                        </div>
                        <div class="stats-item">
                            <span class="stats-label">Code files:</span>
                            <span class="stats-value">${codeFiles}</span>
                        </div>
                        <div class="stats-item">
                            <span class="stats-label">Downloaded:</span>
                            <span class="stats-value success">${downloadedFiles}</span>
                        </div>
                        <div class="stats-item">
                            <span class="stats-label">Failed:</span>
                            <span class="stats-value fail">${failedFiles}</span>
                        </div>
                    </div>
                `;
            } else if (data.status === 'completed') {
                statsElement.style.display = 'block';
                const fileResults = data.file_results || [];
                let resultsHtml = '';
                if (fileResults.length > 0) {
                    resultsHtml = '<div class="file-results">';
                    fileResults.forEach(fr => {
                        const r = fr.result || fr;
                        const typeName = fr.type || r.basename || 'unknown';
                        const success = r.success !== false;
                        const icon = success ? '✓' : '✗';
                        const cls = success ? 'success' : 'fail';
                        resultsHtml += `
                            <div class="file-result-item ${cls}">
                                <span class="result-icon">${icon}</span>
                                <span class="result-type">${typeName}.jsonl</span>
                                <span class="result-detail">${r.downloaded_files || 0} success / ${r.failed_files || 0} failed / ${r.code_files || 0} code files</span>
                            </div>
                        `;
                    });
                    resultsHtml += '</div>';
                }
                statsElement.innerHTML = `
                    <div class="stats-grid">
                        <div class="stats-item">
                            <span class="stats-label">Total changed files:</span>
                            <span class="stats-value">${data.total_files || 0}</span>
                        </div>
                        <div class="stats-item">
                            <span class="stats-label">Code files:</span>
                            <span class="stats-value">${data.code_files || 0}</span>
                        </div>
                        <div class="stats-item">
                            <span class="stats-label">Downloaded:</span>
                            <span class="stats-value success">${downloadedFiles}</span>
                        </div>
                        <div class="stats-item">
                            <span class="stats-label">Failed:</span>
                            <span class="stats-value fail">${failedFiles}</span>
                        </div>
                    </div>
                    ${resultsHtml}
                `;
            }
        }
        
        // If completed, cache output file path and trigger event
        if (data.status === 'completed') {
            if (data.output_file) {
                this.filesOutputFile = data.output_file;
            }
            
            // Trigger custom event to notify FormComponent to start next step
            const event = new CustomEvent('filesCrawlCompleted', {
                detail: {
                    outputFile: data.output_file || '',
                    totalFiles: data.total_files || 0,
                    codeFiles: data.code_files || 0,
                    downloadedFiles: downloadedFiles,
                    failedFiles: failedFiles
                }
            });
            document.dispatchEvent(event);
        }
        
        // Start/stop time update timer
        if (data.status === 'running' && !this.filesTimeInterval) {
            this.startFilesTimeUpdater();
        } else if (data.status !== 'running' && this.filesTimeInterval) {
            this.stopFilesTimeUpdater();
        }
    }

    // Calculate code file crawl elapsed time
    calculateFilesElapsedTime(data) {
        if (data.last_updated) {
            const startTime = this.filesStartTime || new Date(data.last_updated);
            const currentTime = new Date();
            return Math.round((currentTime - startTime) / 1000);
        }
        return Math.round(data.elapsed_time || 0);
    }
    
    // Start code file crawl time update timer
    startFilesTimeUpdater() {
        if (this.filesTimeInterval) return;
        
        this.filesTimeInterval = setInterval(() => {
            const timeElement = document.getElementById('files_time');
            if (timeElement) {
                const elapsedTime = this.calculateFilesElapsedTime({ last_updated: true });
                timeElement.textContent = elapsedTime;
            }
        }, 1000);
    }
    
    // Stop code file crawl time update timer
    stopFilesTimeUpdater() {
        if (this.filesTimeInterval) {
            clearInterval(this.filesTimeInterval);
            this.filesTimeInterval = null;
        }
    }
    
    // Update function extraction progress (with progress bar)
    updateFunctionExtractProgress(data) {
        const timeElement = document.getElementById('function_time');
        
        console.log('=== Step 5: Function Extraction ===');
        console.log('Received progress data:', JSON.stringify(data, null, 2));
        
        // Update changed code function count display
        const functionCountElement = document.getElementById('extracted_functions');
        if (functionCountElement) {
            const extracted = data.extracted_functions || 0;
            functionCountElement.textContent = extracted;
        }
        
        // Update time display
        if (timeElement) {
            const elapsedTime = this.calculateFunctionElapsedTime(data);
            timeElement.textContent = elapsedTime;
        }
        
        // If completed, show statistics
        if (data.status === 'completed') {
            const statsContainer = document.getElementById('function_stats');
            const statsContent = document.getElementById('function_stats_content');
            
            if (statsContainer && statsContent) {
                const agentStats = data.agent_stats || {};
                let html = '';
                
                if (Object.keys(agentStats).length > 0) {
                    html += '<div class="stats-grid">';
                    const sortedAgents = Object.entries(agentStats).sort((a, b) => b[1] - a[1]);
                    sortedAgents.forEach(([agentName, count]) => {
                        const agentClass = agentName === 'human' ? 'human' : 'agent';
                        html += `<div class="stats-item">
                            <span class="stats-label">${agentName}:</span>
                            <span class="stats-value ${agentClass}">${count}</span>
                        </div>`;
                    });
                    html += '</div>';
                }
                
                statsContent.innerHTML = html;
                statsContainer.style.display = 'block';
            }
        }
        
        // If completed, cache output file path and code count
        if (data.status === 'completed') {
            if (data.output_file) {
                this.functionOutputFile = data.output_file;
            }
            
            // Save extracted code total count
            if (data.total_functions || data.total_count) {
                this.totalFunctions = data.total_functions || data.total_count;
                console.log('Step 5 completed, saved code total:', this.totalFunctions);
            }
            
            // Trigger custom event to notify FormComponent to start next step
            const event = new CustomEvent('functionExtractCompleted', {
                detail: {
                    outputFile: data.output_file || '',
                    totalFunctions: this.totalFunctions || 0
                }
            });
            document.dispatchEvent(event);
        }
        
        // Start/stop time update timer
        if (data.status === 'running' && !this.functionTimeInterval) {
            this.startFunctionTimeUpdater();
        } else if (data.status !== 'running' && this.functionTimeInterval) {
            this.stopFunctionTimeUpdater();
        }
    }

    // Calculate function extraction elapsed time
    calculateFunctionElapsedTime(data) {
        // If there is a recorded start time, use it
        if (this.functionStartTime) {
            const currentTime = new Date();
            return Math.round((currentTime - this.functionStartTime) / 1000);
        }
        // Otherwise use the passed start time
        if (data.last_updated && typeof data.last_updated === 'string') {
            const startTime = new Date(data.last_updated);
            const currentTime = new Date();
            return Math.round((currentTime - startTime) / 1000);
        }
        return Math.round(data.elapsed_time || 0);
    }
    
    // Start function extraction time update timer
    startFunctionTimeUpdater() {
        if (this.functionTimeInterval) return;
        
        this.functionTimeInterval = setInterval(() => {
            const timeElement = document.getElementById('function_time');
            if (timeElement) {
                const elapsedTime = this.calculateFunctionElapsedTime({ last_updated: true });
                timeElement.textContent = elapsedTime;
            }
        }, 1000);
    }
    
    // Stop function extraction time update timer
    stopFunctionTimeUpdater() {
        if (this.functionTimeInterval) {
            clearInterval(this.functionTimeInterval);
            this.functionTimeInterval = null;
        }
    }
    
    updateCodeGenerationProgress(data) {
        const countElement = document.getElementById('codegen_count');
        const totalElement = document.getElementById('codegen_total');
        const timeElement = document.getElementById('codegen_time');
        const progressFill = document.getElementById('codegen_progress');
        const progressText = document.getElementById('codegen_progress_text');
        
        console.log('=== Step 5.5: AI Code Generation ===');
        console.log('Received progress data:', JSON.stringify(data, null, 2));
        
        const generated = data.generated_count || 0;
        const total = data.total_count || 0;
        
        if (countElement) {
            countElement.textContent = generated;
        }
        if (totalElement) {
            totalElement.textContent = total;
        }
        
        if (timeElement) {
            const elapsedTime = this.calculateCodegenElapsedTime(data);
            timeElement.textContent = elapsedTime;
        }
        
        if (progressFill && progressText) {
            const percentage = total > 0 ? Math.round((generated / total) * 100) : 0;
            progressFill.style.width = percentage + '%';
            progressText.textContent = percentage + '%';
        }
        
        if (data.status === 'completed') {
            const statsContainer = document.getElementById('codegen_stats');
            const statsContent = document.getElementById('codegen_stats_content');
            
            if (statsContainer && statsContent) {
                const agentStats = data.agent_stats || {};
                let html = '';
                
                if (Object.keys(agentStats).length > 0) {
                    html += '<div class="stats-grid">';
                    const sortedAgents = Object.entries(agentStats).sort((a, b) => b[1] - a[1]);
                    sortedAgents.forEach(([agentName, count]) => {
                        const agentClass = agentName === 'human' ? 'human' : 'agent';
                        html += `<div class="stats-item">
                            <span class="stats-label">${agentName}:</span>
                            <span class="stats-value ${agentClass}">${count}</span>
                        </div>`;
                    });
                    html += '</div>';
                }
                
                statsContent.innerHTML = html;
                statsContainer.style.display = 'block';
            }
            
            this.stopCodegenTimeUpdater();
        }
        
        if (data.status === 'running' && !this.codegenTimeInterval) {
            this.startCodegenTimeUpdater();
        } else if (data.status !== 'running' && this.codegenTimeInterval) {
            this.stopCodegenTimeUpdater();
        }
    }
    
    calculateCodegenElapsedTime(data) {
        if (this.codegenStartTime) {
            const currentTime = new Date();
            return Math.round((currentTime - this.codegenStartTime) / 1000);
        }
        if (data.last_updated && typeof data.last_updated === 'string') {
            const startTime = new Date(data.last_updated);
            const currentTime = new Date();
            return Math.round((currentTime - startTime) / 1000);
        }
        return Math.round(data.elapsed_time || 0);
    }
    
    startCodegenTimeUpdater() {
        if (this.codegenTimeInterval) return;
        
        this.codegenTimeInterval = setInterval(() => {
            const timeElement = document.getElementById('codegen_time');
            if (timeElement) {
                const elapsedTime = this.calculateCodegenElapsedTime({ last_updated: true });
                timeElement.textContent = elapsedTime;
            }
        }, 1000);
    }
    
    stopCodegenTimeUpdater() {
        if (this.codegenTimeInterval) {
            clearInterval(this.codegenTimeInterval);
            this.codegenTimeInterval = null;
        }
    }
    
    // Update code deduplication progress (with progress bar)
    updateDeduplicationProgress(data) {
        const remainingElement = document.getElementById('dedup_remaining');
        const originalElement = document.getElementById('dedup_original');
        const timeElement = document.getElementById('dedup_time');
        const spinnerElement = document.getElementById('dedup_spinner');
        
        console.log('=== Step 6: Code Deduplication ===');
        console.log('Received progress data:', JSON.stringify(data, null, 2));
        
        // Update time display
        if (timeElement) {
            const elapsedTime = this.calculateDedupElapsedTime(data);
            timeElement.textContent = elapsedTime;
        }
        
        // During runtime: show spinner
        if (data.status === 'running') {
            // Show spinner animation
            if (spinnerElement) {
                spinnerElement.style.display = 'flex';
                spinnerElement.style.alignItems = 'center';
            }
            
            // Start time update timer
            if (!this.dedupTimeInterval) {
                this.startDedupTimeUpdater();
            }
        }
        
        // On completion: show deduplicated code count / original code count
        if (data.status === 'completed') {
            if (spinnerElement) {
                spinnerElement.style.display = 'none';
            }
            
            const remainingCount = data.remaining_count || data.remaining_functions || 0;
            const originalCount = data.original_count || this.totalFunctions || 0;
            
            if (remainingElement) {
                remainingElement.textContent = remainingCount;
            }
            if (originalElement) {
                originalElement.textContent = originalCount;
            }
            
            if (data.output_file) {
                this.dedupOutputFile = data.output_file;
            }
            
            this.stopDedupTimeUpdater();
            
            const dedupStatsContainer = document.getElementById('dedup_stats');
            const dedupStatsContent = document.getElementById('dedup_stats_content');
            
            if (dedupStatsContainer && dedupStatsContent) {
                const agentStats = data.agent_stats || {};
                const dedupRates = agentStats.deduplication_rate || {};
                const originalStats = agentStats.original || {};
                const uniqueStats = agentStats.unique || {};
                
                let html = '';
                
                html += `<div class="stats-item">
                    <span class="stats-label">Overall Dedup Rate:</span>
                    <span class="stats-value highlight">${(data.deduplication_rate || 0).toFixed(1)}%</span>
                </div>`;
                
                if (Object.keys(originalStats).length > 0) {
                    html += '<div style="margin-top: 8px; font-weight: bold;">By Category:</div>';
                    html += '<div class="stats-grid">';
                    const sortedAgents = Object.entries(originalStats).sort((a, b) => b[1] - a[1]);
                    sortedAgents.forEach(([agentName, original]) => {
                        const unique = uniqueStats[agentName] || 0;
                        const rate = dedupRates[agentName] || 0;
                        const agentClass = agentName === 'human' ? 'human' : 'agent';
                        html += `<div class="stats-item" style="margin-bottom: 4px;">
                            <span class="stats-label">${agentName}:</span>
                            <span class="stats-value ${agentClass}">${unique}/${original} (${rate.toFixed(1)}%)</span>
                        </div>`;
                    });
                    html += '</div>';
                }
                
                dedupStatsContent.innerHTML = html;
                dedupStatsContainer.style.display = 'block';
            }
            
            this.showDownloadButton(data.output_file);
        }
    }
    
    // Show download button
    showDownloadButton(outputPath) {
        const stepElement = this.steps['deduplication'];
        if (!stepElement) return;
        
        // Check if download button already exists
        if (stepElement.querySelector('.download-btn')) {
            return;
        }
        
        const downloadBtn = document.createElement('button');
        downloadBtn.className = 'download-btn';
        downloadBtn.textContent = 'Download Dataset';
        downloadBtn.style.marginTop = '10px';
        downloadBtn.style.padding = '8px 16px';
        downloadBtn.style.background = '#27ae60';
        downloadBtn.style.color = 'white';
        downloadBtn.style.border = 'none';
        downloadBtn.style.borderRadius = '4px';
        downloadBtn.style.cursor = 'pointer';
        
        downloadBtn.addEventListener('click', async () => {
            try {
                downloadBtn.textContent = 'Downloading...';
                downloadBtn.disabled = true;
                
                const formComponent = window.formComponent;
                if (!formComponent || !formComponent.apiClient) {
                    alert('Unable to connect to server');
                    return;
                }
                
                const blob = await formComponent.apiClient.downloadDataset(outputPath);
                
                // Create download link
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                
                // Get filename (extract from path)
                const basename = outputPath.split(/[\\/]/).pop();
                a.download = `${basename}.zip`;
                
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                downloadBtn.textContent = 'Download Complete';
            } catch (error) {
                console.error('Download failed:', error);
                alert('Download failed: ' + error.message);
                downloadBtn.textContent = 'Download Dataset';
                downloadBtn.disabled = false;
            }
        });
        
        const progressInfo = stepElement.querySelector('.step-progress-info');
        if (progressInfo) {
            progressInfo.appendChild(downloadBtn);
        }
    }
    
    // Calculate code deduplication elapsed time
    calculateDedupElapsedTime(data) {
        if (data.last_updated) {
            const startTime = this.dedupStartTime || new Date(data.last_updated);
            const currentTime = new Date();
            return Math.round((currentTime - startTime) / 1000);
        }
        return Math.round(data.elapsed_time || 0);
    }
    
    // Start code deduplication time update timer
    startDedupTimeUpdater() {
        if (this.dedupTimeInterval) return;
        
        this.dedupTimeInterval = setInterval(() => {
            const timeElement = document.getElementById('dedup_time');
            if (timeElement) {
                const elapsedTime = this.calculateDedupElapsedTime({ last_updated: true });
                timeElement.textContent = elapsedTime;
            }
        }, 1000);
    }
    
    // Stop code deduplication time update timer
    stopDedupTimeUpdater() {
        if (this.dedupTimeInterval) {
            clearInterval(this.dedupTimeInterval);
            this.dedupTimeInterval = null;
        }
    }

    // Cache PR data and trigger next step
    cachePRData(progressData) {
        this.prDataCache = {
            prCount: progressData.pr_count || progressData.current || 0,
            prFilePath: progressData.output_file || progressData.pr_file_path || '',
            totalPRs: progressData.total_prs || progressData.total || 0,
            cachedAt: new Date().toISOString()
        };
        
        console.log('PR data cached:', this.prDataCache);
        
        // Trigger custom event to notify FormComponent to start next step
        if (this.prDataCache.prFilePath) {
            const event = new CustomEvent('prCrawlCompleted', {
                detail: this.prDataCache
            });
            document.dispatchEvent(event);
        }
    }

    // Get cached PR data
    getCachedPRData() {
        return this.prDataCache || null;
    }

    // Update step progress bar visibility (do not show next step's progress bar if previous step is not completed)
    updateStepVisibility() {
        const stepOrder = this.stepOrder;
        
        for (let i = 0; i < stepOrder.length; i++) {
            const stepName = stepOrder[i];
            const stepElement = this.steps[stepName];
            
            if (!stepElement) continue;
            
            // Step 1: show progress info only when active or completed
            if (i === 0) {
                // Show progress info when active or completed, hide when waiting
                if (stepElement.classList.contains('active') || stepElement.classList.contains('completed')) {
                    this.showStepProgressInfo(stepElement);
                } else {
                    this.hideStepProgressInfo(stepElement);
                }
                continue;
            }
            
            // Check if previous step is completed
            const prevStepName = stepOrder[i - 1];
            const prevStepElement = this.steps[prevStepName];
            
            if (prevStepElement && prevStepElement.classList.contains('completed')) {
                // Previous step completed, show current step's progress info
                this.showStepProgressInfo(stepElement);
            } else {
                // Previous step not completed, hide current step's progress info
                this.hideStepProgressInfo(stepElement);
            }
        }
    }

    // Show step progress info area
    showStepProgressInfo(stepElement) {
        const progressInfo = stepElement.querySelector('.step-progress-info');
        if (progressInfo) {
            progressInfo.style.display = 'block';
        }
    }

    // Hide step progress info area
    hideStepProgressInfo(stepElement) {
        const progressInfo = stepElement.querySelector('.step-progress-info');
        if (progressInfo) {
            progressInfo.style.display = 'none';
        }
    }
}

// Initialize flow management component
document.addEventListener('DOMContentLoaded', function() {
    window.flowManager = new FlowManager();
});