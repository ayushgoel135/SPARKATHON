document.addEventListener('DOMContentLoaded', function() {
    // Initialize all charts on the page
    initCharts();
    
    // Add event listeners for interactive elements
    setupEventListeners();
});

function initCharts() {
    // Find all chart containers
    const chartContainers = document.querySelectorAll('.chart-container');
    
    chartContainers.forEach(container => {
        const chartId = container.id;
        const chartData = JSON.parse(container.dataset.chart);
        
        if (chartData && chartId) {
            renderChart(chartId, chartData);
        }
    });
}

function renderChart(chartId, chartData) {
    // Use Plotly.js for rendering charts
    Plotly.newPlot(chartId, chartData.data, chartData.layout, {
        responsive: true,
        displayModeBar: false
    });
}

function setupEventListeners() {
    // Refresh button for charts
    document.querySelectorAll('.refresh-chart').forEach(btn => {
        btn.addEventListener('click', function() {
            const chartId = this.dataset.target;
            fetchChartData(chartId);
        });
    });
    
    // Tab switching for dashboard views
    document.querySelectorAll('.nav-tabs .nav-link').forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault();
            const target = this.getAttribute('href');
            document.querySelectorAll('.tab-pane').forEach(pane => {
                pane.classList.remove('active');
            });
            document.querySelector(target).classList.add('active');
        });
    });
}

function fetchChartData(chartId) {
    // AJAX call to fetch updated chart data
    const endpoint = `/api/charts/${chartId}/`;
    
    fetch(endpoint)
        .then(response => response.json())
        .then(data => {
            renderChart(chartId, data);
        })
        .catch(error => {
            console.error('Error fetching chart data:', error);
        });
}

// Utility function for formatting numbers
function formatNumber(value, decimals = 2) {
    return new Intl.NumberFormat('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}