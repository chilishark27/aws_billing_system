function getCostClass(cost) {
    if (cost > 5) return 'cost-high';
    if (cost > 1) return 'cost-medium';
    return 'cost-low';
}

function getServiceBadge(service) {
    return `<span class="service-badge service-${service.toLowerCase()}">${service}</span>`;
}

function showLoading(show = true) {
    const loading = document.getElementById('loading');
    const refreshBtn = document.querySelector('.refresh-btn');
    
    if (loading && refreshBtn) {
        if (show) {
            loading.style.display = 'flex';
            refreshBtn.disabled = true;
            refreshBtn.style.opacity = '0.6';
        } else {
            loading.style.display = 'none';
            refreshBtn.disabled = false;
            refreshBtn.style.opacity = '1';
        }
    }
}