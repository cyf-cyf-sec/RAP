class FormComponent {
    constructor() {
        this.form = document.getElementById('crawlForm');
        this.submitBtn = document.getElementById('submit_btn');
        this.loadingContainer = document.getElementById('loading_container');
        
        this.errorHandler = window.errorHandler;
        this.formValidator = window.formValidator;
        this.apiClient = window.apiClient;
        this.flowManager = window.flowManager;
        
        this.init();
    }

    init() {
        if (this.form) {
            this.form.addEventListener('submit', this.handleSubmit.bind(this));
            
            this.setupRealTimeValidation();
            this.setupFlatpickr();
            
            document.addEventListener('prCrawlCompleted', this.handlePRCrawlCompleted.bind(this));
            document.addEventListener('prFilterCompleted', this.handlePRFilterCompleted.bind(this));
            document.addEventListener('prDetailsCompleted', this.handlePRDetailsCompleted.bind(this));
            document.addEventListener('filesCrawlCompleted', this.handleFilesCrawlCompleted.bind(this));
            document.addEventListener('functionExtractCompleted', this.handleFunctionExtractCompleted.bind(this));
            document.addEventListener('codeGenCompleted', this.handleCodeGenCompleted.bind(this));
            
            this.setupCodegenToggle();
        }
    }
    
    setupFlatpickr() {
        const dateInputs = this.form.querySelectorAll('[data-flatpickr]');
        if (typeof flatpickr === 'undefined') {
            console.warn('[WARN] flatpickr not loaded, using native text inputs');
            return;
        }
        dateInputs.forEach(input => {
            try {
                flatpickr(input, {
                    dateFormat: 'Y-m-d',
                    allowInput: true
                });
            } catch (e) {
                console.warn('[WARN] flatpickr init failed for', input.id, e);
            }
        });
    }
    
    setupCodegenToggle() {
        const radioYes = this.form.querySelector('input[name="enable_codegen"][value="yes"]');
        const radioNo = this.form.querySelector('input[name="enable_codegen"][value="no"]');
        const codegenOptions = document.getElementById('codegen_options');
        
        if (radioYes && radioNo && codegenOptions) {
            radioYes.addEventListener('change', () => {
                codegenOptions.style.display = 'block';
            });
            radioNo.addEventListener('change', () => {
                codegenOptions.style.display = 'none';
            });
        }
    }

    // Set up real-time validation
    setupRealTimeValidation() {
        const inputs = this.form.querySelectorAll('input');
        
        inputs.forEach(input => {
            input.addEventListener('blur', (e) => {
                if (this.formValidator) {
                    this.formValidator.validateFieldInRealTime(e.target.id, e.target.value);
                }
            });
            
            input.addEventListener('input', (e) => {
                if (this.errorHandler) {
                    this.errorHandler.hideFieldError(e.target.id);
                }
            });
        });
    }

    // Handle form submission
    async handleSubmit(e) {
        e.preventDefault();
        
        // Clear all errors
        if (this.errorHandler) {
            this.errorHandler.clearAllErrors();
        }
        
        // Get form data
        const formData = this.getFormData();
        
        // Frontend validation
        const validation = this.formValidator ? this.formValidator.validateForm(formData) : { isValid: true };
        
        if (!validation.isValid) {
            if (this.errorHandler) {
                validation.errors.forEach(error => {
                    this.errorHandler.showFieldError(error.field, error.message);
                });
            }
            return;
        }
        
        // Show loading state
        this.showLoading();
        
        try {
            // If token exists, test repository connection first (internal process, not shown to user)
            if (formData.github_token && formData.github_token.trim()) {
                // Silently validate repository connection
                const validationResponse = await this.apiClient.validateRepository(
                    formData.repo_url, 
                    formData.github_token
                );
                
                if (!validationResponse.valid) {
                    this.errorHandler.showGlobalError(`Repository connection failed: ${validationResponse.error}`);
                    this.hideLoading();
                    return;
                }
            }
            
            // Submit form data to backend for PR list crawling (step 1)
            const response = await this.apiClient.startPRListCrawling(formData);
            
            // Backend returns status: 'started' indicating task has started
            if (response.status === 'started') {
                this.disableForm();
                this.currentTaskId = response.task_id;

                // Show flow display area
                if (this.flowManager) {
                    this.flowManager.show();
                    this.flowManager.reset();
                    
                    // Start first step (PR list crawl)
                    this.flowManager.startStep('pr_crawler');
                    
                    // Start progress polling
                    this.startProgressPolling(response.task_id);
                }
            } else {
                this.errorHandler.handleBackendError(response);
            }
        } catch (error) {
            console.error('Form submission error:', error);
            
            if (error.name === 'NetworkError') {
                this.errorHandler.handleNetworkError();
            } else if (error.name === 'TimeoutError') {
                this.errorHandler.handleTimeoutError();
            } else {
                this.errorHandler.handleBackendError(error);
            }
        } finally {
            this.hideLoading();
        }
    }
    
    // Start step 4: Code file crawling
    async startCodeFilesCrawlingStep(detailsOutputPath) {
        
        try {
            this.showLoading('Crawling code files...');
            
            const formData = this.getFormData();

            const response = await this.apiClient.startCodeFilesCrawling(
                detailsOutputPath,
                formData.github_token
            );
            
            // Backend returns status: 'started' indicating task has started
            if (response.status === 'started') {
                
                // Update flowManager, mark step 3 completed, start step 4
                if (this.flowManager) {
                    console.log('Updating flowManager: completeStep(commit_crawler), startStep(file_crawler)');
                    this.flowManager.completeStep('commit_crawler');
                    this.flowManager.startStep('file_crawler');
                }
                
                this.startProgressPolling(response.task_id);
            } else {
                this.errorHandler.handleBackendError(response);
            }
        } catch (error) {
            
            if (error.name === 'NetworkError') {
                this.errorHandler.handleNetworkError();
            } else if (error.name === 'TimeoutError') {
                this.errorHandler.handleTimeoutError();
            } else {
                this.errorHandler.handleBackendError(error);
            }
        } finally {
            this.hideLoading();
        }
    }

    // Get form data
    getFormData() {
        const formData = new FormData(this.form);
        
        const startEl = document.getElementById('start_date');
        const endEl = document.getElementById('end_date');
        
        const data = {
            repo_url: formData.get('repo_url') || '',
            github_token: formData.get('github_token') || '',
            start_date: (startEl && startEl.value) || '',
            end_date: (endEl && endEl.value) || '',
            thread_count: formData.get('thread_count') || ''
        };
        return data;
    }
    
    // Start step 2: PR classification (filter)
    async startPRClassificationStep(prFilePath) {
        try {
            this.showLoading('Running PR filter...');
            
            const formData = this.getFormData();
            
            // Call backend classification API
            const response = await this.apiClient.startPRClassification(
                prFilePath,
                formData.start_date,
                formData.end_date
            );
            
            // Backend returns status: 'started' indicating task has started
            if (response.status === 'started') {

                // Update flowManager, mark step 1 completed, start step 2
                if (this.flowManager) {
                    this.flowManager.completeStep('pr_crawler');
                    this.flowManager.startStep('pr_filter');
                }
                
                // Start progress polling
                this.startProgressPolling(response.task_id);
            } else {
                this.errorHandler.handleBackendError(response);
            }
        } catch (error) {

            if (error.name === 'NetworkError') {
                this.errorHandler.handleNetworkError();
            } else if (error.name === 'TimeoutError') {
                this.errorHandler.handleTimeoutError();
            } else {
                this.errorHandler.handleBackendError(error);
            }
        } finally {
            this.hideLoading();
        }
    }
    
    // Handle PR crawl completion event
    handlePRCrawlCompleted(event) {
        const prData = event.detail;
        
        if (prData && prData.prFilePath) {
            // Auto start step 2
            this.startPRClassificationStep(prData.prFilePath);
        }
    }
    
    // Handle PR filter completion event (step 2 completed)
    handlePRFilterCompleted(event) {
        const filterData = event.detail;
        
        if (filterData && filterData.outputFile) {
            // Auto start step 3
            this.startPRDetailsCrawlingStep(filterData.outputFile);
        }
    }
    
    // Handle PR details crawl completion event (step 3 completed)
    handlePRDetailsCompleted(event) {
        const detailsData = event.detail;
        
        if (detailsData && detailsData.outputFile) {
            // Auto start step 4
            this.startCodeFilesCrawlingStep(detailsData.outputFile);
        } else {
            console.error('Step 4 start failed: missing outputFile');
            console.log('detailsData:', detailsData);
        }
    }
    
    // Handle step 4 completion event
    handleFilesCrawlCompleted(event) {
        const filesData = event.detail;
        
        if (filesData && filesData.outputFile) {
            // Auto start step 5
            this.startFunctionExtractionStep(filesData.outputFile);
        }
    }
    
    // Handle step 5 completion event
    handleFunctionExtractCompleted(event) {
        const functionData = event.detail;
        
        if (functionData && functionData.outputFile) {
            const enableCodegen = this.isCodegenEnabled();
            
            if (enableCodegen) {
                this.startCodeGenerationStep(functionData.outputFile, functionData.totalFunctions);
            } else {
                this.startDeduplicationStep(functionData.outputFile, functionData.totalFunctions);
            }
        }
    }
    
    isCodegenEnabled() {
        const radioYes = this.form.querySelector('input[name="enable_codegen"][value="yes"]');
        return radioYes && radioYes.checked;
    }
    
    getCodegenConfig() {
        const provider = document.getElementById('codegen_provider').value || 'deepseek';
        const apiKey = document.getElementById('codegen_api_key').value || '';
        return { provider, apiKey };
    }
    
    async startCodeGenerationStep(functionOutputPath, totalFunctions) {
        try {
            this.showLoading('Generating AI code...');
            
            const config = this.getCodegenConfig();
            const functionFilePath = functionOutputPath + '/function.jsonl';
            
            const response = await this.apiClient.startCodeGeneration(
                functionFilePath,
                config.provider,
                '',
                config.apiKey,
                ''
            );
            
            if (response.status === 'started') {
                console.log('Code generation task started:', response.task_id);
                
                if (this.flowManager) {
                    this.flowManager.completeStep('function_extractor');
                    const codegenStep = document.getElementById('step_code_generation');
                    if (codegenStep) codegenStep.style.display = 'flex';
                    this.flowManager.startStep('code_generation');
                }
                
                this.startCodegenCompletionCheck(response.task_id, functionOutputPath, totalFunctions);
            } else {
                this.errorHandler.handleBackendError(response);
            }
        } catch (error) {
            console.error('Code generation error:', error);
            if (error.name === 'NetworkError') {
                this.errorHandler.handleNetworkError();
            } else if (error.name === 'TimeoutError') {
                this.errorHandler.handleTimeoutError();
            } else {
                this.errorHandler.handleBackendError(error);
            }
        } finally {
            this.hideLoading();
        }
    }
    
    async startCodegenCompletionCheck(taskId, functionOutputPath, totalFunctions) {
        console.log('=== Starting code generation completion check ===');
        
        const checkCompletion = async () => {
            try {
                const progress = await this.apiClient.getTaskProgress(taskId);
                
                if (progress.status === 'completed') {
                    console.log('Code generation completed:', progress);
                    
                    if (this.flowManager && progress.tasks && progress.tasks.code_generation) {
                        this.flowManager.updateCodeGenerationProgress(progress.tasks.code_generation);
                    }
                    
                    if (this.flowManager) {
                        this.flowManager.completeStep('code_generation');
                    }
                    
                    const event = new CustomEvent('codeGenCompleted', {
                        detail: {
                            outputFile: functionOutputPath,
                            totalFunctions: totalFunctions
                        }
                    });
                    document.dispatchEvent(event);
                    
                    return;
                } else if (progress.status === 'failed') {
                    console.error('Code generation failed:', progress.error);
                    if (this.flowManager) {
                        this.flowManager.failStep('code_generation', progress.error || 'Generation failed');
                    }
                    this.enableForm();
                    return;
                }
                
                if (this.flowManager && progress.tasks && progress.tasks.code_generation) {
                    this.flowManager.updateCodeGenerationProgress(progress.tasks.code_generation);
                }
                
                setTimeout(checkCompletion, 2000);
            } catch (error) {
                console.error('Code gen check error:', error);
                setTimeout(checkCompletion, 2000);
            }
        };
        
        checkCompletion();
    }
    
    handleCodeGenCompleted(event) {
        const data = event.detail;
        
        if (data && data.outputFile) {
            this.startDeduplicationStep(data.outputFile, data.totalFunctions);
        }
    }

    // Start step 3: PR details crawl
    async startPRDetailsCrawlingStep(prFilePath) {
        try {
            this.showLoading('Crawling PR details...');
            
            const formData = this.getFormData();
            
            const response = await this.apiClient.startPRDetailsCrawling(
                prFilePath,
                formData.github_token,
                parseInt(formData.thread_count) || 4
            );
            
            if (response.status === 'started') {
                
                // Update flowManager, mark step 2 completed, start step 3
                if (this.flowManager) {
                    this.flowManager.completeStep('pr_filter');
                    this.flowManager.startStep('commit_crawler');
                }
                
                // Start progress polling
                this.startProgressPolling(response.task_id);
            } else {
                this.errorHandler.handleBackendError(response);
            }
        } catch (error) {
            if (error.name === 'NetworkError') {
                this.errorHandler.handleNetworkError();
            } else if (error.name === 'TimeoutError') {
                this.errorHandler.handleTimeoutError();
            } else {
                this.errorHandler.handleBackendError(error);
            }
        } finally {
            this.hideLoading();
        }
    }
    
    // Start step 5: Function extraction
    async startFunctionExtractionStep(codeFilesPath) {
        try {
            this.showLoading('Extracting functions...');
            
            const formData = this.getFormData();
            
            // Get step 3 output path (PR details path)
            const prDetailsPath = this.flowManager ? this.flowManager.detailsOutputFile : '';

            const response = await this.apiClient.startFunctionExtraction(
                prDetailsPath,
                codeFilesPath,
                formData.github_token
            );

            if (response.status === 'started') {
                console.log('Function extraction task started:', response.task_id);
                
                // Update flowManager, mark step 4 completed, start step 5
                if (this.flowManager) {
                    this.flowManager.completeStep('file_crawler');
                    this.flowManager.startStep('function_extractor');
                }

                this.startProgressPolling(response.task_id);
            } else {
                this.errorHandler.handleBackendError(response);
            }
        } catch (error) {
            
            if (error.name === 'NetworkError') {
                this.errorHandler.handleNetworkError();
            } else if (error.name === 'TimeoutError') {
                this.errorHandler.handleTimeoutError();
            } else {
                this.errorHandler.handleBackendError(error);
            }
        } finally {
            this.hideLoading();
        }
    }
    
    // Start step 6: Code deduplication
    async startDeduplicationStep(functionOutputPath, totalFunctions) {
        try {
            this.showLoading('Running code deduplication...');

            const response = await this.apiClient.startCodeDeduplication(
                functionOutputPath,
                totalFunctions
            );

            if (response.status === 'started') {
                console.log('Code deduplication task started:', response.task_id);

                if (this.flowManager) {
                    this.flowManager.completeStep('function_extractor');
                    this.flowManager.startStep('deduplication');
                }

                this.startDeduplicationCompletionCheck(response.task_id);
            } else {
                this.errorHandler.handleBackendError(response);
            }
        } catch (error) {
            
            if (error.name === 'NetworkError') {
                this.errorHandler.handleNetworkError();
            } else if (error.name === 'TimeoutError') {
                this.errorHandler.handleTimeoutError();
            } else {
                this.errorHandler.handleBackendError(error);
            }
        } finally {
            this.hideLoading();
        }
    }

    // Show loading state
    showLoading() {
        if (this.submitBtn) {
            this.submitBtn.disabled = true;
            this.submitBtn.textContent = 'Processing...';
        }
        
        if (this.loadingContainer) {
            this.loadingContainer.style.display = 'block';
        }
    }

    // Hide loading state
    hideLoading() {
        if (this.submitBtn) {
            this.submitBtn.disabled = false;
            this.submitBtn.textContent = 'Start Analysis';
        }
        
        if (this.loadingContainer) {
            this.loadingContainer.style.display = 'none';
        }
    }

    // Show success message
    showSuccessMessage(message) {
        const errorContainer = document.getElementById('global_error');
        if (errorContainer) {
            errorContainer.textContent = message;
            errorContainer.style.display = 'block';
            errorContainer.className = 'global-error-message success';
            setTimeout(() => {
                errorContainer.style.display = 'none';
            }, 5000);
        }
    }

    // Start progress polling
    startProgressPolling(taskId) {
        
        // Poll every 3 seconds
        const pollingInterval = setInterval(async () => {
            try {
                const progressData = await this.apiClient.getTaskProgress(taskId);
                
                if (this.flowManager) {
                    this.flowManager.handleProgressUpdate(progressData);
                }
                
                // If task completed or failed, stop polling
                if (progressData.status === 'completed' || progressData.status === 'failed') {
                    clearInterval(pollingInterval);
                    
                    if (progressData.status === 'completed') {
                        if (progressData.current_task === 'pr_filter' || progressData.current_task === 'pr_classification') {
                            this.showSuccessMessage('Analysis task completed!');
                        }
                    } else {
                        this.errorHandler.showGlobalError(`Analysis task failed: ${progressData.error}`);
                        this.enableForm();
                    }
                }
            } catch (error) {
                console.error('Failed to get progress:', error);
            }
        }, 3000); // Poll every 3 seconds
        
        this.currentPollingInterval = pollingInterval;
    }
    
    // Step 6: Check deduplication task completion (no progress polling)
    async startDeduplicationCompletionCheck(taskId) {
        console.log('=== Starting deduplication completion check ===');
        console.log('taskId:', taskId);
        
        const checkCompletion = async () => {
            try {
                const progress = await this.apiClient.getTaskProgress(taskId);
                
                if (progress.status === 'completed') {
                    console.log('Deduplication task completed:', progress);

                    if (this.flowManager && progress.tasks && progress.tasks.deduplication) {
                        this.flowManager.updateDeduplicationProgress(progress.tasks.deduplication);
                    }

                    if (this.flowManager) {
                        this.flowManager.completeStep('deduplication');
                    }
                    
                    this.enableForm();
                    
                    return;
                } else if (progress.status === 'failed') {
                    console.error('Deduplication task failed:', progress.error);
                    this.enableForm();
                    return;
                }
                
                setTimeout(checkCompletion, 2000);
            } catch (error) {
                setTimeout(checkCompletion, 2000);
            }
        };

        checkCompletion();
    }

    disableForm() {
        const inputs = this.form.querySelectorAll('input');
        inputs.forEach(input => input.disabled = true);
        const flatpickrInputs = this.form.querySelectorAll('[data-flatpickr]');
        flatpickrInputs.forEach(input => {
            if (input._flatpickr) input._flatpickr.set('clickOpens', false);
        });
        if (this.submitBtn) this.submitBtn.disabled = true;
    }

    enableForm() {
        const inputs = this.form.querySelectorAll('input');
        inputs.forEach(input => input.disabled = false);
        const flatpickrInputs = this.form.querySelectorAll('[data-flatpickr]');
        flatpickrInputs.forEach(input => {
            if (input._flatpickr) input._flatpickr.set('clickOpens', true);
        });
        if (this.submitBtn) this.submitBtn.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    window.formComponent = new FormComponent();
});

document.addEventListener('pageLoaded', function() {
    if (window.formComponent) {
        window.formComponent = new FormComponent();
    }
});