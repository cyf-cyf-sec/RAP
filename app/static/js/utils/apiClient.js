class ApiClient {
    constructor() {
        this.baseUrl = ''; // Use relative paths
        this.timeout = 30000; // 30 second timeout
    }

    // General request method
    async request(endpoint, options = {}) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        try {
            const response = await fetch(endpoint, {
                ...options,
                signal: controller.signal,
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                
                // Handle backend unified error format
                const errorMessage = errorData.error || errorData.message || `HTTP error: ${response.status}`;
                const apiError = new Error(errorMessage);
                apiError.response = errorData;
                apiError.status = response.status;
                throw apiError;
            }

            // Return different formats based on response type
            if (options.responseType === 'blob') {
                return await response.blob();
            }
            
            return await response.json();
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                const timeoutError = new Error('Request timeout');
                timeoutError.name = 'TimeoutError';
                throw timeoutError;
            }
            
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                const networkError = new Error('Network connection error');
                networkError.name = 'NetworkError';
                throw networkError;
            }
            
            throw error;
        }
    }

    // Start PR list crawling (step 1)
    async startPRListCrawling(formData) {
        return await this.request('/analysisPR/crawlPRList', {
            method: 'POST',
            body: JSON.stringify(formData)
        });
    }

    // Start PR analysis (full analysis flow)
    async submitAnalysis(formData) {
        return await this.request('/analysisPR/analyzePR', {
            method: 'POST',
            body: JSON.stringify(formData)
        });
    }

    // Start PR classification (step 2)
    async startPRClassification(prFilePath, startDate = '', endDate = '') {
        return await this.request('/analysisPR/classifyPRs', {
            method: 'POST',
            body: JSON.stringify({
                pr_file_path: prFilePath,
                start_date: startDate,
                end_date: endDate
            })
        });
    }

    // Start step 3: PR details crawling
    async startPRDetailsCrawling(prFilePath, githubToken = '', threadCount = 4) {
        return await this.request('/analysisPR/crawlPRDetails', {
            method: 'POST',
            body: JSON.stringify({
                pr_file_path: prFilePath,
                github_token: githubToken,
                thread_count: threadCount
            })
        });
    }
    
    // Start step 4: Code file crawling
    async startCodeFilesCrawling(detailsOutputPath, githubToken = '') {
        return await this.request('/analysisFile/downloadFiles', {
            method: 'POST',
            body: JSON.stringify({
                pr_details_path: detailsOutputPath,
                github_token: githubToken
            })
        });
    }
    
    // Start step 5: Function extraction
    async startFunctionExtraction(prDetailsPath, codeFilesPath, githubToken = '') {
        return await this.request('/analysisCode/extractFunctions', {
            method: 'POST',
            body: JSON.stringify({
                pr_details_path: prDetailsPath,
                code_files_path: codeFilesPath,
                github_token: githubToken
            })
        });
    }
    
    // Start step 6: Code deduplication
    async startCodeDeduplication(inputPath, totalFunctions) {
        return await this.request('/analysisCode/deduplicateCode', {
            method: 'POST',
            body: JSON.stringify({
                input_path: inputPath,
                total_functions: totalFunctions
            })
        });
    }
    
    async startCodeGeneration(functionFilePath, provider, model, apiKey, endpoint) {
        return await this.request('/analysisCode/generateAgentCode', {
            method: 'POST',
            body: JSON.stringify({
                function_file_path: functionFilePath,
                provider: provider,
                model: model,
                api_key: apiKey,
                endpoint: endpoint
            })
        });
    }
    
    // Download dataset ZIP file
    async downloadDataset(outputPath) {
        return await this.request('/analysisCode/downloadDataset', {
            method: 'POST',
            body: JSON.stringify({
                input_path: outputPath
            }),
            responseType: 'blob'
        });
    }

    // Validate repository connectivity
    async validateRepository(repoUrl, token) {
        return await this.request('/api/validate-repository', {
            method: 'POST',
            body: JSON.stringify({
                repo_url: repoUrl,
                github_token: token
            })
        });
    }

    // Get task progress
    async getTaskProgress(taskId) {
        return await this.request(`/analysisPR/task-progress/${taskId}`);
    }

    // Get analysis results
    async getAnalysisResults(taskId) {
        return await this.request(`/api/results/${taskId}`);
    }

    // Cancel task
    async cancelTask(taskId) {
        return await this.request(`/api/cancel-task/${taskId}`, {
            method: 'POST'
        });
    }
}

// Export singleton instance
window.apiClient = new ApiClient();