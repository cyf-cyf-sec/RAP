class App {
    constructor() {
        this.modules = [];
        this.init();
    }

    init() {
        this.waitForDependencies().then(() => {
            this.initializeModules();
            this.setupGlobalErrorHandling();
        }).catch(error => {
            console.error('Application initialization failed:', error);
        });
    }

    // Wait for dependency modules to load
    waitForDependencies() {
        return new Promise((resolve) => {
            const checkDependencies = () => {
                if (window.errorHandler && window.formValidator && window.apiClient) {
                    resolve();
                } else {
                    setTimeout(checkDependencies, 100);
                }
            };
            checkDependencies();
        });
    }

    initializeModules() {
        this.setupGlobalEventListeners();
    }

    // Set up global error handling
    setupGlobalErrorHandling() {
        window.addEventListener('error', (event) => {
            if (!window.location.hostname.includes('localhost')) {
                this.reportError(event.error);
            }
        });

        window.addEventListener('unhandledrejection', (event) => {
            console.error('Unhandled Promise rejection:', event.reason);
            event.preventDefault();
        });
    }

    setupGlobalEventListeners() {
        // Page visibility change event
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                console.log('Page hidden');
            } else {
                console.log('Page visible');
            }
        });

        window.addEventListener('online', () => {
            console.log('Network connection restored');
            window.errorHandler.showGlobalError('Network connection restored', 'success');
        });

        window.addEventListener('offline', () => {
            console.log('Network connection lost');
            window.errorHandler.showGlobalError('Network connection lost');
        });
    }

    reportError(error) {
        const errorInfo = {
            message: error.message,
            stack: error.stack,
            url: window.location.href,
            userAgent: navigator.userAgent,
            timestamp: new Date().toISOString()
        };
        
    }

    // Utility: show success message
    showSuccess(message) {
        console.log('Success:', message);
    }

    // Utility: show warning message
    showWarning(message) {
        console.warn('Warning:', message);
    }
}

// Application startup
document.addEventListener('DOMContentLoaded', function() {
    window.app = new App();
});

// Export utility functions for other modules
window.AppUtils = {
    // Format date
    formatDate(date) {
        return new Date(date).toLocaleDateString('en-US');
    },

    // Format file size
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    // Debounce function
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Throttle function
    throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
};