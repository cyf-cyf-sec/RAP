class ErrorHandler {
    constructor() {
        this.errorContainer = document.getElementById('global_error');
    }

    // Show global error message
    showGlobalError(message) {
        if (this.errorContainer) {
            this.errorContainer.textContent = message;
            this.errorContainer.style.display = 'block';
            setTimeout(() => {
                this.hideGlobalError();
            }, 5000);
        }
    }

    // Hide global error message
    hideGlobalError() {
        if (this.errorContainer) {
            this.errorContainer.style.display = 'none';
            this.errorContainer.textContent = '';
        }
    }

    // Show field-level error message
    showFieldError(fieldId, message) {
        const errorElement = document.getElementById(fieldId + '_error');
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
            const inputElement = document.getElementById(fieldId);
            if (inputElement) {
                inputElement.classList.add('error');
            }
        }
    }

    // Hide field-level error message
    hideFieldError(fieldId) {
        const errorElement = document.getElementById(fieldId + '_error');
        if (errorElement) {
            errorElement.style.display = 'none';
            errorElement.textContent = '';
            const inputElement = document.getElementById(fieldId);
            if (inputElement) {
                inputElement.classList.remove('error');
            }
        }
    }

    // Clear all error messages
    clearAllErrors() {
        this.hideGlobalError();
        const errorElements = document.querySelectorAll('.error-message');
        errorElements.forEach(element => {
            element.style.display = 'none';
            element.textContent = '';
        });
        
        const inputElements = document.querySelectorAll('input');
        inputElements.forEach(input => {
            input.classList.remove('error');
        });
    }

    // Handle backend error response
    handleBackendError(errorResponse) {
        if (errorResponse && errorResponse.error) {
            this.showGlobalError(errorResponse.error);
        } else if (errorResponse && errorResponse.message) {
            this.showGlobalError(errorResponse.message);
        } else {
            this.showGlobalError('Server error, please try again later');
        }
    }

    // Handle network error
    handleNetworkError() {
        this.showGlobalError('Network connection error, please check your network');
    }

    // Handle timeout error
    handleTimeoutError() {
        this.showGlobalError('Request timeout, please try again later');
    }
}

// Export singleton instance
window.errorHandler = new ErrorHandler();