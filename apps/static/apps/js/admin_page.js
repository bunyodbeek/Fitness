const monthlyData = window.dashboardData.monthly;
const revenueData = window.dashboardData.revenue;
const weeklyActivity = window.dashboardData.weekly;
const {premium, free, inactive} = window.dashboardData.counts;

Chart.defaults.color = 'rgba(255, 255, 255, 0.7)';
Chart.defaults.borderColor = 'rgba(212, 175, 55, 0.2)';

new Chart(document.getElementById('userGrowthChart'), {
    type: 'line',
    data: {
        labels: monthlyData.map(d => d.month),
        datasets: [
            {
                label: 'Jami Userlar',
                data: monthlyData.map(d => d.total_users),
                borderColor: '#d4af37',
                backgroundColor: 'rgba(212, 175, 55, 0.1)',
                tension: 0.4,
                fill: true
            },
            {
                label: 'Premium Userlar',
                data: monthlyData.map(d => d.premium_users),
                borderColor: '#f4e5a1',
                backgroundColor: 'rgba(244, 229, 161, 0.1)',
                tension: 0.4,
                fill: true
            }
        ]
    }
});

new Chart(document.getElementById('revenueChart'), {
    type: 'bar',
    data: {
        labels: revenueData.map(d => d.month),
        datasets: [{
            label: "Daromad (so'm)",
            data: revenueData.map(d => d.revenue),
            backgroundColor: function (context) {
                const ctx = context.chart.ctx;
                const gradient = ctx.createLinearGradient(0, 0, 0, 300);
                gradient.addColorStop(0, 'rgba(212, 175, 55, 0.8)');
                gradient.addColorStop(1, 'rgba(212, 175, 55, 0.2)');
                return gradient;
            },
            borderWidth: 2,
            borderRadius: 8
        }]
    }
});

// User Distribution Chart
new Chart(document.getElementById('userDistributionChart'), {
    type: 'doughnut',
    data: {
        labels: ['Premium Userlar', 'Free Userlar', 'Inactive Userlar'],
        datasets: [{
            data: [premium, free, inactive],
            backgroundColor: [
                'rgba(212, 175, 55, 0.8)',
                'rgba(244, 229, 161, 0.5)',
                'rgba(255, 255, 255, 0.1)'
            ]
        }]
    }
});

new Chart(document.getElementById('dailyActivityChart'), {
    type: 'line',
    data: {
        labels: weeklyActivity.map(d => d.day),
        datasets: [{
            label: 'Faol Userlar',
            data: weeklyActivity.map(d => d.active_users),
            borderColor: '#d4af37',
            backgroundColor: 'rgba(212, 175, 55, 0.2)',
            tension: 0.4,
            fill: true
        }]
    }
});

// Auto-refresh every 5 minutes
setInterval(() => location.reload(), 300000);
