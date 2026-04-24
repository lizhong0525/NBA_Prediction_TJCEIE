/**
 * NBA比赛预测系统 - 主JavaScript文件
 * 包含API调用、页面交互、图表渲染等功能
 */

// ==================== 全局配置 ====================
const CONFIG = {
    API_BASE: '/api',
    ANIMATION_DURATION: 500,
    NOTIFICATION_DURATION: 3000
};

// ==================== API服务类 ====================
class NBAService {
    constructor() {
        this.baseURL = CONFIG.API_BASE;
    }

    /**
     * 通用请求方法
     * @param {string} endpoint - API端点
     * @param {Object} options - 请求选项
     * @returns {Promise<Object>} 响应数据
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        try {
            const response = await fetch(url, { ...defaultOptions, ...options });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.message || '请求失败');
            }
            
            return data;
        } catch (error) {
            console.error(`API请求失败 [${endpoint}]:`, error);
            throw error;
        }
    }

    /**
     * 获取首页数据
     */
    async getHomeData() {
        return this.request('/home');
    }

    /**
     * 获取球队列表
     */
    async getTeams() {
        return this.request('/teams');
    }

    /**
     * 获取球队详情
     * @param {string} teamAbbr - 球队缩写
     * @param {string} season - 赛季
     */
    async getTeamDetail(teamAbbr, season = null) {
        const params = season ? `?season=${season}` : '';
        return this.request(`/team/${teamAbbr}${params}`);
    }

    /**
     * 预测比赛
     * @param {Object} data - 预测参数
     */
    async predictGame(data) {
        return this.request('/predict', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }

    /**
     * 获取预测参数
     */
    async getPredictParams() {
        return this.request('/predict/params');
    }

    /**
     * 获取预测历史
     * @param {number} limit - 数量限制
     */
    async getPredictionHistory(limit = 20) {
        return this.request(`/predictions/history?limit=${limit}`);
    }

    /**
     * 获取比赛列表
     * @param {Object} params - 查询参数
     */
    async getGames(params = {}) {
        const query = new URLSearchParams(params).toString();
        return this.request(`/games?${query}`);
    }

    /**
     * 获取统计数据排名
     * @param {string} type - 统计类型
     * @param {string} season - 赛季
     */
    async getStatsRanking(type = 'win_pct', season = null) {
        const params = new URLSearchParams({ type });
        if (season) params.append('season', season);
        return this.request(`/stats/ranking?${params}`);
    }

    /**
     * 健康检查
     */
    async healthCheck() {
        return this.request('/health');
    }
}

// 创建全局API服务实例
const api = new NBAService();

// ==================== 工具函数 ====================
const Utils = {
    /**
     * 格式化日期
     * @param {string|Date} date - 日期
     * @param {string} format - 格式
     */
    formatDate(date, format = 'YYYY-MM-DD HH:mm') {
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        
        return format
            .replace('YYYY', year)
            .replace('MM', month)
            .replace('DD', day)
            .replace('HH', hours)
            .replace('mm', minutes);
    },

    /**
     * 格式化百分比
     * @param {number} value - 数值
     * @param {number} decimals - 小数位数
     */
    formatPercent(value, decimals = 1) {
        return (value * 100).toFixed(decimals) + '%';
    },

    /**
     * 显示通知消息
     * @param {string} message - 消息内容
     * @param {string} type - 类型 (success, error, warning, info)
     */
    showNotification(message, type = 'info') {
        const colors = {
            success: '#28a745',
            error: '#dc3545',
            warning: '#ffc107',
            info: '#17a2b8'
        };
        
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = 'notification';
        notification.innerHTML = `
            <div class="notification-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;
        
        // 添加样式
        notification.style.cssText = `
            position: fixed;
            top: 100px;
            right: 20px;
            z-index: 9999;
            background: ${colors[type]};
            color: white;
            padding: 15px 25px;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            animation: slideIn 0.3s ease;
            max-width: 350px;
        `;
        
        document.body.appendChild(notification);
        
        // 自动移除
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(() => notification.remove(), 300);
        }, CONFIG.NOTIFICATION_DURATION);
    },

    /**
     * 显示加载状态
     * @param {HTMLElement} container - 容器元素
     * @param {boolean} show - 是否显示
     */
    showLoading(container, show = true) {
        if (show) {
            container.innerHTML = `
                <div class="loading-spinner">
                    <div class="spinner"></div>
                </div>
            `;
            container.style.display = 'block';
        } else {
            container.innerHTML = '';
        }
    },

    /**
     * 防抖函数
     * @param {Function} func - 函数
     * @param {number} wait - 等待时间
     */
    debounce(func, wait = 300) {
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

    /**
     * 获取URL参数
     * @param {string} name - 参数名
     */
    getUrlParam(name) {
        const params = new URLSearchParams(window.location.search);
        return params.get(name);
    }
};

// ==================== 图表管理类 ====================
class ChartManager {
    constructor() {
        this.charts = new Map();
    }

    /**
     * 创建饼图
     * @param {string} id - 容器ID
     * @param {Object} data - 数据
     * @param {string} title - 标题
     */
    createPieChart(id, data, title = '') {
        const container = document.getElementById(id);
        if (!container) return;

        const chart = echarts.init(container);
        
        const option = {
            title: {
                text: title,
                left: 'center',
                textStyle: {
                    color: '#fff',
                    fontSize: 16
                }
            },
            tooltip: {
                trigger: 'item',
                formatter: '{b}: {c} ({d}%)'
            },
            legend: {
                orient: 'vertical',
                right: 10,
                top: 'center',
                textStyle: {
                    color: '#a0a0a0'
                }
            },
            color: ['#F58426', '#1D428A', '#28a745', '#dc3545'],
            series: [{
                type: 'pie',
                radius: ['40%', '70%'],
                avoidLabelOverlap: false,
                itemStyle: {
                    borderRadius: 10,
                    borderColor: '#0B1026',
                    borderWidth: 2
                },
                label: {
                    show: false,
                    position: 'center'
                },
                emphasis: {
                    label: {
                        show: true,
                        fontSize: 20,
                        fontWeight: 'bold'
                    }
                },
                data: data
            }]
        };

        chart.setOption(option);
        this.charts.set(id, chart);
        return chart;
    }

    /**
     * 创建柱状图
     * @param {string} id - 容器ID
     * @param {Object} data - 数据
     * @param {Object} config - 配置
     */
    createBarChart(id, data, config = {}) {
        const container = document.getElementById(id);
        if (!container) return;

        const chart = echarts.init(container);
        
        const option = {
            title: {
                text: config.title || '',
                left: 'center',
                textStyle: {
                    color: '#fff',
                    fontSize: 16
                }
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'shadow'
                }
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: data.categories,
                axisLabel: {
                    color: '#a0a0a0'
                },
                axisLine: {
                    lineStyle: {
                        color: '#333'
                    }
                }
            },
            yAxis: {
                type: 'value',
                axisLabel: {
                    color: '#a0a0a0'
                },
                splitLine: {
                    lineStyle: {
                        color: 'rgba(255,255,255,0.1)'
                    }
                }
            },
            series: [{
                type: 'bar',
                data: data.values,
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: '#F58426' },
                        { offset: 1, color: '#1D428A' }
                    ]),
                    borderRadius: [5, 5, 0, 0]
                },
                barWidth: '60%'
            }]
        };

        chart.setOption(option);
        this.charts.set(id, chart);
        return chart;
    }

    /**
     * 创建雷达图
     * @param {string} id - 容器ID
     * @param {Object} data - 数据
     * @param {string} title - 标题
     */
    createRadarChart(id, data, title = '') {
        const container = document.getElementById(id);
        if (!container) return;

        const chart = echarts.init(container);
        
        const option = {
            title: {
                text: title,
                left: 'center',
                textStyle: {
                    color: '#fff',
                    fontSize: 16
                }
            },
            tooltip: {
                trigger: 'item'
            },
            legend: {
                bottom: 10,
                textStyle: {
                    color: '#a0a0a0'
                }
            },
            radar: {
                indicator: data.indicators,
                splitArea: {
                    areaStyle: {
                        color: ['rgba(29, 66, 138, 0.1)', 'rgba(29, 66, 138, 0.2)']
                    }
                },
                axisLine: {
                    lineStyle: {
                        color: '#333'
                    }
                },
                splitLine: {
                    lineStyle: {
                        color: 'rgba(255,255,255,0.1)'
                    }
                }
            },
            series: [{
                type: 'radar',
                data: data.teams,
                itemStyle: {
                    borderWidth: 2
                }
            }]
        };

        chart.setOption(option);
        this.charts.set(id, chart);
        return chart;
    }

    /**
     * 创建折线图
     * @param {string} id - 容器ID
     * @param {Object} data - 数据
     * @param {Object} config - 配置
     */
    createLineChart(id, data, config = {}) {
        const container = document.getElementById(id);
        if (!container) return;

        const chart = echarts.init(container);
        
        const option = {
            title: {
                text: config.title || '',
                left: 'center',
                textStyle: {
                    color: '#fff',
                    fontSize: 16
                }
            },
            tooltip: {
                trigger: 'axis'
            },
            legend: {
                data: config.legend || ['数据'],
                bottom: 10,
                textStyle: {
                    color: '#a0a0a0'
                }
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '15%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                boundaryGap: false,
                data: data.categories,
                axisLabel: {
                    color: '#a0a0a0'
                }
            },
            yAxis: {
                type: 'value',
                axisLabel: {
                    color: '#a0a0a0'
                },
                splitLine: {
                    lineStyle: {
                        color: 'rgba(255,255,255,0.1)'
                    }
                }
            },
            series: data.series.map((s, index) => ({
                name: config.legend ? config.legend[index] : '数据',
                type: 'line',
                data: s.data,
                smooth: true,
                lineStyle: {
                    width: 3
                },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: index === 0 ? 'rgba(245, 132, 38, 0.3)' : 'rgba(29, 66, 138, 0.3)' },
                        { offset: 1, color: 'rgba(0, 0, 0, 0)' }
                    ])
                }
            }))
        };

        chart.setOption(option);
        this.charts.set(id, chart);
        return chart;
    }

    /**
     * 窗口调整时重绘图表
     */
    resizeAll() {
        this.charts.forEach(chart => {
            chart.resize();
        });
    }
}

// 创建全局图表管理器
const chartManager = new ChartManager();

// ==================== 球队选择器组件 ====================
class TeamSelector {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            placeholder: '选择球队...',
            onSelect: null,
            ...options
        };
        this.selectedTeam = null;
        this.teams = [];
        this.init();
    }

    async init() {
        try {
            const response = await api.getTeams();
            this.teams = response.data;
            this.render();
        } catch (error) {
            console.error('加载球队列表失败:', error);
        }
    }

    render() {
        if (!this.container) return;

        this.container.innerHTML = `
            <div class="team-selector">
                <div class="team-selector-input" tabindex="0">
                    <span class="team-placeholder">${this.options.placeholder}</span>
                    <i class="fas fa-chevron-down"></i>
                </div>
                <div class="team-selector-dropdown" style="display: none;">
                    <input type="text" class="team-search-input" placeholder="搜索球队...">
                    <div class="team-list"></div>
                </div>
            </div>
        `;

        this.bindEvents();
    }

    bindEvents() {
        const input = this.container.querySelector('.team-selector-input');
        const dropdown = this.container.querySelector('.team-selector-dropdown');
        const searchInput = this.container.querySelector('.team-search-input');
        const teamList = this.container.querySelector('.team-list');

        // 点击展开/收起
        input.addEventListener('click', () => {
            dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
            if (dropdown.style.display === 'block') {
                searchInput.focus();
            }
        });

        // 搜索过滤
        searchInput.addEventListener('input', Utils.debounce((e) => {
            const keyword = e.target.value.toLowerCase();
            const filtered = this.teams.filter(team => 
                team.name.toLowerCase().includes(keyword) ||
                team.city.toLowerCase().includes(keyword) ||
                team.abbr.toLowerCase().includes(keyword)
            );
            this.renderTeamList(teamList, filtered);
        }, 200));

        // 点击外部关闭
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });

        // 初始渲染球队列表
        this.renderTeamList(teamList, this.teams);
    }

    renderTeamList(container, teams) {
        container.innerHTML = teams.map(team => `
            <div class="team-option" data-abbr="${team.abbr}">
                <div class="team-option-logo" style="background: linear-gradient(135deg, #1D428A, #2E5BAA);">
                    ${team.abbr}
                </div>
                <div class="team-option-info">
                    <div class="team-option-name">${team.name}</div>
                    <div class="team-option-city">${team.city}</div>
                </div>
            </div>
        `).join('');

        // 绑定选择事件
        container.querySelectorAll('.team-option').forEach(option => {
            option.addEventListener('click', () => {
                const abbr = option.dataset.abbr;
                this.selectTeam(abbr);
            });
        });
    }

    selectTeam(abbr) {
        const team = this.teams.find(t => t.abbr === abbr);
        if (!team) return;

        this.selectedTeam = team;

        const input = this.container.querySelector('.team-selector-input');
        input.innerHTML = `
            <div class="team-selected">
                <div class="team-option-logo" style="background: linear-gradient(135deg, #1D428A, #2E5BAA); width: 30px; height: 30px; font-size: 0.7rem;">
                    ${team.abbr}
                </div>
                <span>${team.name}</span>
            </div>
            <i class="fas fa-chevron-down"></i>
        `;
        input.classList.add('has-value');

        // 收起下拉
        this.container.querySelector('.team-selector-dropdown').style.display = 'none';

        // 回调
        if (typeof this.options.onSelect === 'function') {
            this.options.onSelect(team);
        }
    }

    getValue() {
        return this.selectedTeam;
    }

    setValue(abbr) {
        this.selectTeam(abbr);
    }
}

// ==================== 预测表单组件 ====================
class PredictionForm {
    constructor(formId) {
        this.form = document.getElementById(formId);
        this.homeSelector = null;
        this.awaySelector = null;
        this.advancedOptions = {};
        this.init();
    }

    init() {
        if (!this.form) return;

        // 初始化球队选择器
        this.homeSelector = new TeamSelector('home-team-selector', {
            placeholder: '选择主队...',
            onSelect: (team) => {
                document.getElementById('home-team').value = team.abbr;
                this.updateTeamPreview('home', team);
            }
        });

        this.awaySelector = new TeamSelector('away-team-selector', {
            placeholder: '选择客队...',
            onSelect: (team) => {
                document.getElementById('away-team').value = team.abbr;
                this.updateTeamPreview('away', team);
            }
        });

        // 绑定事件
        this.bindEvents();
    }

    bindEvents() {
        // 高级选项切换
        const advancedToggle = document.getElementById('advanced-toggle');
        const advancedPanel = document.getElementById('advanced-panel');
        
        if (advancedToggle && advancedPanel) {
            advancedToggle.addEventListener('change', (e) => {
                advancedPanel.style.display = e.target.checked ? 'block' : 'none';
            });
        }

        // 预测按钮
        const predictBtn = document.getElementById('predict-btn');
        if (predictBtn) {
            predictBtn.addEventListener('click', () => this.handlePredict());
        }

        // 重置按钮
        const resetBtn = document.getElementById('reset-btn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.handleReset());
        }
    }

    updateTeamPreview(position, team) {
        const preview = document.getElementById(`${position}-team-preview`);
        if (preview) {
            preview.innerHTML = `
                <div class="team-logo" style="background: linear-gradient(135deg, #1D428A, #2E5BAA);">
                    ${team.abbr}
                </div>
                <div class="team-name">${team.name}</div>
                <div class="team-city">${team.city}</div>
                ${team.win_pct !== undefined ? `<div class="team-record">${team.wins}-${team.losses} (${Utils.formatPercent(team.win_pct)})</div>` : ''}
            `;
        }
    }

    async handlePredict() {
        const homeTeam = document.getElementById('home-team').value;
        const awayTeam = document.getElementById('away-team').value;

        // 验证输入
        if (!homeTeam || !awayTeam) {
            Utils.showNotification('请选择主队和客队', 'warning');
            return;
        }

        if (homeTeam === awayTeam) {
            Utils.showNotification('主队和客队不能相同', 'warning');
            return;
        }

        const btn = document.getElementById('predict-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 预测中...';

        const resultContainer = document.getElementById('prediction-result');
        Utils.showLoading(resultContainer);

        try {
            // 构建请求数据
            const requestData = {
                home_team: homeTeam,
                away_team: awayTeam
            };

            // 检查是否使用高级模式
            const advancedToggle = document.getElementById('advanced-toggle');
            if (advancedToggle && advancedToggle.checked) {
                requestData.mode = 'advanced';
                requestData.home_params = this.collectAdvancedParams('home');
                requestData.away_params = this.collectAdvancedParams('away');
                requestData.weights = this.collectWeights();
            }

            const response = await api.predictGame(requestData);
            this.displayResult(response.data, homeTeam, awayTeam);

        } catch (error) {
            resultContainer.innerHTML = `
                <div class="alert-danger-custom p-4">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    预测失败: ${error.message}
                </div>
            `;
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-basketball"></i> 开始预测';
        }
    }

    collectAdvancedParams(position) {
        return {
            injury_impact: parseFloat(document.getElementById(`${position}-injury`)?.value || 0),
            rest_days: parseInt(document.getElementById(`${position}-rest-days`)?.value || 2),
            back_to_back: document.getElementById(`${position}-back-to-back`)?.checked || false
        };
    }

    collectWeights() {
        return {
            recent_form: parseFloat(document.getElementById('weight-recent')?.value || 0.25),
            home_advantage: parseFloat(document.getElementById('weight-home')?.value || 0.15),
            historical_matchup: parseFloat(document.getElementById('weight-historical')?.value || 0.10),
            efficiency_diff: parseFloat(document.getElementById('weight-efficiency')?.value || 0.40),
            cluster_similarity: parseFloat(document.getElementById('weight-cluster')?.value || 0.10)
        };
    }

    displayResult(result, homeTeam, awayTeam) {
        const container = document.getElementById('prediction-result');
        const homeWinProb = result.home_win_probability || result.home_win_prob || 0.5;
        const awayWinProb = result.away_win_probability || result.away_win_prob || 0.5;
        const winner = result.predicted_winner;
        const winnerCn = result.predicted_winner_cn || (winner === homeTeam ? '主队' : '客队');

        container.innerHTML = `
            <div class="prediction-result fade-in">
                <div class="prediction-winner">
                    <i class="fas fa-trophy"></i>
                    预测胜方: ${result.home_team_cn || homeTeam}
                </div>
                
                <div class="prediction-probability mt-4">
                    <div class="probability-item">
                        <div class="probability-value text-nba-blue">${Utils.formatPercent(homeWinProb)}</div>
                        <div class="probability-label">${result.home_team_cn || homeTeam}</div>
                        <div class="probability-bar">
                            <div class="probability-fill" style="width: ${homeWinProb * 100}%; background: linear-gradient(90deg, #1D428A, #2E5BAA);"></div>
                        </div>
                    </div>
                    <div class="probability-item">
                        <div class="probability-value text-nba-orange">${Utils.formatPercent(awayWinProb)}</div>
                        <div class="probability-label">${result.away_team_cn || awayTeam}</div>
                        <div class="probability-bar">
                            <div class="probability-fill" style="width: ${awayWinProb * 100}%; background: linear-gradient(90deg, #F58426, #FF9F5A);"></div>
                        </div>
                    </div>
                </div>

                <div class="confidence-badge mt-4">
                    <span class="badge ${result.confidence_level === 'high' ? 'badge-success' : result.confidence_level === 'medium' ? 'badge-orange' : 'badge-nba'}">
                        置信度: ${result.confidence_level === 'high' ? '高' : result.confidence_level === 'medium' ? '中' : '低'}
                    </span>
                </div>

                ${result.key_factors && result.key_factors.length ? `
                    <div class="key-factors mt-4">
                        <h5 class="mb-3"><i class="fas fa-chart-line me-2"></i>关键因素</h5>
                        <ul class="factor-list">
                            ${result.key_factors.map(factor => `
                                <li class="factor-item">
                                    <span class="factor-name">${factor.name}</span>
                                    <span class="factor-impact ${factor.impact > 0 ? 'positive' : 'negative'}">
                                        ${factor.impact > 0 ? '+' : ''}${(factor.impact * 100).toFixed(1)}%
                                    </span>
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                ` : ''}

                ${result.adjustments_applied ? `
                    <div class="adjustments mt-4">
                        <h5 class="mb-3"><i class="fas fa-sliders-h me-2"></i>参数调整</h5>
                        <div class="row g-2">
                            ${Object.entries(result.adjustments_applied).map(([key, value]) => `
                                <div class="col-md-6">
                                    <div class="adjustment-item p-2 rounded" style="background: rgba(255,255,255,0.05);">
                                        <small class="text-secondary">${key}</small>
                                        <div class="text-nba-orange">${typeof value === 'number' ? (value * 100).toFixed(1) + '%' : value}</div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    handleReset() {
        this.form.reset();
        document.getElementById('home-team-preview').innerHTML = `
            <div class="team-logo mx-auto" style="background: rgba(255,255,255,0.1);">
                <i class="fas fa-question"></i>
            </div>
            <div class="team-name text-secondary">待选择</div>
        `;
        document.getElementById('away-team-preview').innerHTML = `
            <div class="team-logo mx-auto" style="background: rgba(255,255,255,0.1);">
                <i class="fas fa-question"></i>
            </div>
            <div class="team-name text-secondary">待选择</div>
        `;
        document.getElementById('prediction-result').innerHTML = '';
    }
}

// ==================== 页面初始化 ====================
document.addEventListener('DOMContentLoaded', () => {
    // 响应式图表调整
    window.addEventListener('resize', () => {
        chartManager.resizeAll();
    });

    // 添加通知动画样式
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        .notification-content {
            display: flex;
            align-items: center;
            gap: 10px;
        }
    `;
    document.head.appendChild(style);

    // 球队选择器样式
    const selectorStyle = document.createElement('style');
    selectorStyle.textContent = `
        .team-selector {
            position: relative;
            width: 100%;
        }
        .team-selector-input {
            background: rgba(255,255,255,0.05);
            border: 2px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 15px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s;
        }
        .team-selector-input:hover,
        .team-selector-input:focus {
            border-color: #F58426;
            outline: none;
        }
        .team-selector-input.has-value {
            border-color: #1D428A;
        }
        .team-placeholder {
            color: #a0a0a0;
        }
        .team-selected {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .team-selector-dropdown {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: #0B1026;
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            margin-top: 8px;
            z-index: 100;
            max-height: 350px;
            overflow: hidden;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        }
        .team-search-input {
            width: 100%;
            padding: 12px 15px;
            background: rgba(255,255,255,0.05);
            border: none;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            color: #fff;
            font-size: 14px;
        }
        .team-search-input::placeholder {
            color: #a0a0a0;
        }
        .team-list {
            max-height: 280px;
            overflow-y: auto;
        }
        .team-option {
            display: flex;
            align-items: center;
            padding: 12px 15px;
            cursor: pointer;
            transition: background 0.2s;
        }
        .team-option:hover {
            background: rgba(245,132,38,0.1);
        }
        .team-option-logo {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-weight: 700;
            font-size: 0.8rem;
            margin-right: 12px;
            flex-shrink: 0;
        }
        .team-option-info {
            flex: 1;
        }
        .team-option-name {
            font-weight: 500;
            color: #fff;
        }
        .team-option-city {
            font-size: 0.85rem;
            color: #a0a0a0;
        }
        .team-preview-card {
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            padding: 30px;
            text-align: center;
        }
    `;
    document.head.appendChild(selectorStyle);
});

// ==================== 导出模块 ====================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { NBAService, ChartManager, TeamSelector, PredictionForm, Utils };
}
