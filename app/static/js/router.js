var AppRouter = {
    init: function () {
        var self = this;

        // Wrap initial page content in a container
        var contentEl = document.getElementById('pageContent');
        if (contentEl) {
            var initialUrl = window.location.pathname;
            var wrapper = document.createElement('div');
            wrapper.className = 'page-container';
            wrapper.setAttribute('data-page', initialUrl);
            while (contentEl.firstChild) {
                wrapper.appendChild(contentEl.firstChild);
            }
            contentEl.appendChild(wrapper);
        }

        document.addEventListener('click', function (e) {
            var link = e.target.closest('[data-route]');
            if (link) {
                e.preventDefault();
                self.navigate(link.getAttribute('href'));
            }
        });

        window.addEventListener('popstate', function (e) {
            if (e.state && e.state.url) {
                self.switchToPage(e.state.url, true);
            }
        });

        this.updateActiveNav(window.location.pathname);
    },

    navigate: function (url) {
        history.pushState({ url: url }, '', url);
        this.switchToPage(url, false);
    },

    switchToPage: function (url, isPopState) {
        var contentEl = document.getElementById('pageContent');
        if (!contentEl) return;

        // Hide all page containers
        var pages = contentEl.querySelectorAll('.page-container');
        pages.forEach(function (p) { p.style.display = 'none'; });

        // Check if target page already exists in DOM
        var targetPage = contentEl.querySelector('.page-container[data-page="' + url + '"]');
        if (targetPage) {
            targetPage.style.display = 'block';
            this.updateActiveNav(url);
            return;
        }

        // Create loading placeholder
        var loadingDiv = document.createElement('div');
        loadingDiv.className = 'page-container';
        loadingDiv.setAttribute('data-page', url);
        loadingDiv.innerHTML = '<div style="text-align:center;padding:40px;color:#999;">Loading...</div>';
        contentEl.appendChild(loadingDiv);

        var self = this;
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (res) {
                if (!res.ok) throw new Error('Page load failed');
                return res.text();
            })
            .then(function (html) {
                var temp = document.createElement('div');
                temp.innerHTML = html;

                var newContent = temp.querySelector('#pageContent');
                var pageHtml = newContent ? newContent.innerHTML : html;

                loadingDiv.innerHTML = pageHtml;
                loadingDiv.style.display = 'block';

                self.updateActiveNav(url);
                self.executePageScripts(loadingDiv);
            })
            .catch(function (err) {
                loadingDiv.innerHTML = '<div style="text-align:center;padding:40px;color:#e74c3c;">Page load failed: ' + err.message + '</div>';
                loadingDiv.style.display = 'block';
            });
    },

    executePageScripts: function (container) {
        var scripts = container.querySelectorAll('script');
        var loadedSrcs = [];
        document.querySelectorAll('script[src]').forEach(function (s) {
            loadedSrcs.push(s.src);
        });

        scripts.forEach(function (oldScript) {
            if (oldScript.src) {
                if (loadedSrcs.indexOf(oldScript.src) !== -1) {
                    return;
                }
                var newScript = document.createElement('script');
                newScript.src = oldScript.src;
                newScript.async = false;
                document.body.appendChild(newScript);
            } else {
                var newScript = document.createElement('script');
                newScript.textContent = '(function(){ ' + oldScript.textContent + ' })();';
                document.body.appendChild(newScript);
            }
        });
    },

    updateActiveNav: function (path) {
        var navLinks = document.querySelectorAll('[data-route]');
        navLinks.forEach(function (link) {
            var href = link.getAttribute('href');
            if (path === href || (href !== '/' && path.startsWith(href))) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }
};

document.addEventListener('DOMContentLoaded', function () {
    AppRouter.init();
});