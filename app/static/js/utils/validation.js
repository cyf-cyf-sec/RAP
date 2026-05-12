class FormValidator {
    constructor() {
        this.errorHandler = window.errorHandler;
    }

    // Validate GitHub repository URL
    validateRepoUrl(url) {
        if (!url || !url.trim()) {
            return { isValid: false, message: 'Please enter a GitHub repository URL' };
        }

        const trimmedUrl = url.trim();
        
        // GitHub URL regex pattern
        const githubUrlRegex = /^https?:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+(\/)?$/;
        
        if (!githubUrlRegex.test(trimmedUrl)) {
            return { 
                isValid: false, 
                message: 'Please enter a valid GitHub repository URL (format: https://github.com/username/repository)' 
            };
        }

        return { isValid: true };
    }

    validateGitHubToken(token) {
        if (!token || !token.trim()) {
            return { isValid: true };
        }

        const trimmedToken = token.trim();
        
        // GitHub Token basic format validation (starts with ghp_, gho_, ghu_, ghs_, ghr_)
        const tokenRegex = /^(ghp_|gho_|ghu_|ghs_|ghr_)[a-zA-Z0-9_]{36}$/;
        
        if (!tokenRegex.test(trimmedToken)) {
            return { 
                isValid: false, 
                message: 'GitHub Token format is incorrect' 
            };
        }

        return { isValid: true };
    }

    // Validate thread count
    validateThreadCount(count) {
        if (!count || count === '') {
            return { isValid: true }; // Thread count is optional
        }

        const numCount = parseInt(count);
        
        if (isNaN(numCount) || numCount < 1 || numCount > 8) {
            return { 
                isValid: false, 
                message: 'Thread count must be between 1 and 8' 
            };
        }

        return { isValid: true };
    }

    // Validate date range
    validateDateRange(startDate, endDate) {
        if (!startDate && !endDate) {
            return { isValid: true }; // Date range is optional
        }

        if ((startDate && !endDate) || (!startDate && endDate)) {
            return { 
                isValid: false, 
                message: 'Please fill in both start date and end date, or leave both empty' 
            };
        }

        if (startDate && endDate) {
            const start = new Date(startDate);
            const end = new Date(endDate);
            
            if (start > end) {
                return { 
                    isValid: false, 
                    message: 'Start date cannot be later than end date' 
                };
            }

            // Check if dates are in the future
            const today = new Date();
            if (start > today || end > today) {
                return { 
                    isValid: false, 
                    message: 'Date cannot be in the future' 
                };
            }
        }

        return { isValid: true };
    }

    // Validate entire form
    validateForm(formData) {
        const errors = [];

        // Validate repository URL
        const repoUrlValidation = this.validateRepoUrl(formData.repo_url);
        if (!repoUrlValidation.isValid) {
            errors.push({ field: 'repo_url', message: repoUrlValidation.message });
        }

        // Validate GitHub Token
        const tokenValidation = this.validateGitHubToken(formData.github_token);
        if (!tokenValidation.isValid) {
            errors.push({ field: 'github_token', message: tokenValidation.message });
        }

        // Validate thread count
        const threadValidation = this.validateThreadCount(formData.thread_count);
        if (!threadValidation.isValid) {
            errors.push({ field: 'thread_count', message: threadValidation.message });
        }

        // Validate date range
        const dateValidation = this.validateDateRange(formData.start_date, formData.end_date);
        if (!dateValidation.isValid) {
            errors.push({ field: 'start_date', message: dateValidation.message });
            errors.push({ field: 'end_date', message: dateValidation.message });
        }

        return {
            isValid: errors.length === 0,
            errors: errors
        };
    }

    // Real-time validation for single field
    validateField(fieldId, value) {
        switch (fieldId) {
            case 'repo_url':
                return this.validateRepoUrl(value);
            case 'github_token':
                return this.validateGitHubToken(value);
            case 'thread_count':
                return this.validateThreadCount(value);
            default:
                return { isValid: true };
        }
    }

    // Real-time validation and display error
    validateFieldInRealTime(fieldId, value) {
        const validation = this.validateField(fieldId, value);
        
        if (!validation.isValid) {
            this.errorHandler.showFieldError(fieldId, validation.message);
        } else {
            this.errorHandler.hideFieldError(fieldId);
        }
        
        return validation.isValid;
    }
}

// Export singleton instance
window.formValidator = new FormValidator();