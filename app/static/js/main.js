/**
 * Shared frontend utilities for the NBA prediction project.
 */

const CONFIG = {
    API_BASE: '/api',
    NOTIFICATION_DURATION: 3000
};

class NBAService {
    constructor() {
        this.baseURL = CONFIG.API_BASE;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const merged = {
            headers: {
                'Content-Type': 'application/json'
            },
            ...options
        };

        try {
            const response = await fetch(url, merged);
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.message || `Request failed: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error(`API request failed for ${endpoint}:`, error);
            throw error;
        }
    }

    async getHomeData(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/home${query ? `?${query}` : ''}`);
    }

    async getSeasons() {
        return this.request('/seasons');
    }

    async getTeams(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/teams${query ? `?${query}` : ''}`);
    }

    async getTeamDetail(teamAbbr, season = null) {
        const query = new URLSearchParams();
        if (season) {
            query.set('season', season);
        }
        return this.request(`/team/${teamAbbr}${query.toString() ? `?${query}` : ''}`);
    }

    async predictGame(data) {
        return this.request('/predict', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    async getPredictParams() {
        return this.request('/predict/params');
    }

    async getPredictionHistory(limit = 20) {
        return this.request(`/predictions/history?limit=${limit}`);
    }

    async getGames(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/games${query ? `?${query}` : ''}`);
    }

    async getStatsRanking(type = 'win_pct', season = null) {
        const query = new URLSearchParams({ type });
        if (season) {
            query.set('season', season);
        }
        return this.request(`/stats/ranking?${query}`);
    }

    async healthCheck() {
        return this.request('/health');
    }
}

const api = new NBAService();

const Utils = {
    formatDate(date, includeTime = true) {
        if (!date) {
            return '--';
        }

        const parsed = new Date(date);
        if (Number.isNaN(parsed.getTime())) {
            return String(date);
        }

        const options = {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        };

        if (includeTime) {
            options.hour = '2-digit';
            options.minute = '2-digit';
        }

        return parsed.toLocaleString('zh-CN', options);
    },

    formatPercent(value, decimals = 1) {
        const numeric = Number(value || 0);
        return `${(numeric * 100).toFixed(decimals)}%`;
    },

    normalizeConfidence(value) {
        return String(value || 'MEDIUM').toUpperCase();
    },

    getConfidenceMeta(value) {
        const normalized = Utils.normalizeConfidence(value);
        const mapping = {
            HIGH: { label: '高', className: 'badge-success' },
            MEDIUM: { label: '中', className: 'badge-orange' },
            LOW: { label: '低', className: 'badge-nba' }
        };
        return mapping[normalized] || mapping.MEDIUM;
    },

    showNotification(message, type = 'info') {
        const colorMap = {
            success: '#28a745',
            error: '#dc3545',
            warning: '#ffc107',
            info: '#17a2b8'
        };

        const iconMap = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };

        const node = document.createElement('div');
        node.className = 'notification-toast';
        node.innerHTML = `
            <div class="notification-inner">
                <i class="fas fa-${iconMap[type] || iconMap.info}"></i>
                <span>${message}</span>
            </div>
        `;
        node.style.cssText = `
            position: fixed;
            top: 88px;
            right: 20px;
            z-index: 9999;
            min-width: 220px;
            max-width: 360px;
            padding: 14px 18px;
            border-radius: 12px;
            color: #fff;
            background: ${colorMap[type] || colorMap.info};
            box-shadow: 0 10px 30px rgba(0,0,0,0.25);
            transform: translateX(120%);
            transition: transform 0.25s ease;
        `;

        document.body.appendChild(node);
        requestAnimationFrame(() => {
            node.style.transform = 'translateX(0)';
        });

        setTimeout(() => {
            node.style.transform = 'translateX(120%)';
            setTimeout(() => node.remove(), 250);
        }, CONFIG.NOTIFICATION_DURATION);
    },

    showLoading(container, message = '加载中...') {
        if (!container) {
            return;
        }
        container.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner mx-auto mb-3"></div>
                <p class="text-secondary mb-0">${message}</p>
            </div>
        `;
    },

    debounce(fn, wait = 300) {
        let timeoutId;
        return (...args) => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => fn.apply(null, args), wait);
        };
    },

    getUrlParam(name) {
        return new URLSearchParams(window.location.search).get(name);
    }
};

class ChartManager {
    constructor() {
        this.charts = new Map();
    }

    register(id, chart) {
        if (!id || !chart) {
            return chart;
        }

        if (this.charts.has(id)) {
            try {
                this.charts.get(id).dispose();
            } catch (error) {
                console.warn(`Failed to dispose previous chart for ${id}`, error);
            }
        }

        this.charts.set(id, chart);
        return chart;
    }

    get(id) {
        return this.charts.get(id);
    }

    dispose(id) {
        const chart = this.charts.get(id);
        if (chart) {
            chart.dispose();
            this.charts.delete(id);
        }
    }

    resizeAll() {
        this.charts.forEach(chart => {
            try {
                chart.resize();
            } catch (error) {
                console.warn('Failed to resize chart', error);
            }
        });
    }
}

const chartManager = new ChartManager();

class TeamSelector {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = options;
        this.teams = [];
        this.selectedTeam = null;
    }

    async load(params = {}) {
        const response = await api.getTeams(params);
        this.teams = response.data || [];
        return this.teams;
    }

    setValue(team) {
        this.selectedTeam = team || null;
        if (typeof this.options.onSelect === 'function' && team) {
            this.options.onSelect(team);
        }
    }

    getValue() {
        return this.selectedTeam;
    }
}

class PredictionForm {
    constructor(formId) {
        this.form = document.getElementById(formId);
    }
}

window.addEventListener('resize', () => {
    chartManager.resizeAll();
});

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        NBAService,
        ChartManager,
        TeamSelector,
        PredictionForm,
        Utils
    };
}
