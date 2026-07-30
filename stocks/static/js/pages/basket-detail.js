/* ========================================
   BASKET-DETAIL - JavaScript
   Extracted from basket_detail.j2
   ======================================== */


// Get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

function showMessage(message, type) {
    const container = document.getElementById('message-container');
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    container.appendChild(alert);

    setTimeout(() => {
        alert.remove();
    }, 5000);
}

function enableEdit(itemId, field) {
    const row = document.querySelector(`tr[data-item-id="${itemId}"]`);
    const cell = row.querySelector(`.${field}-cell`);

    // Hide display, show edit
    cell.querySelector('.display-mode').style.display = 'none';
    cell.querySelector('.edit-mode').style.display = 'block';

    // Focus the input
    cell.querySelector('.edit-input').focus();
    cell.querySelector('.edit-input').select();
}

function cancelEdit(itemId, field) {
    const row = document.querySelector(`tr[data-item-id="${itemId}"]`);
    const cell = row.querySelector(`.${field}-cell`);

    // Show display, hide edit
    cell.querySelector('.display-mode').style.display = 'block';
    cell.querySelector('.edit-mode').style.display = 'none';
}

function saveEdit(itemId, field) {
    const row = document.querySelector(`tr[data-item-id="${itemId}"]`);
    const cell = row.querySelector(`.${field}-cell`);
    const input = cell.querySelector('.edit-input');
    const newValue = parseFloat(input.value);

    if (isNaN(newValue) || newValue <= 0) {
        showMessage('Please enter a valid positive number', 'error');
        return;
    }

    // Show loading state
    row.classList.add('loading');

    // Prepare form data
    const formData = new FormData();
    formData.append('update_type', field);
    if (field === 'weight') {
        formData.append('weight_percentage', newValue);
    } else {
        formData.append('quantity', newValue);
    }

    // Send AJAX request
    fetch(`/basket-item/${itemId}/edit/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrftoken,
        },
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update all items in the table
                data.items.forEach(itemData => {
                    const itemRow = document.querySelector(`tr[data-item-id="${itemData.id}"]`);
                    if (itemRow) {
                        itemRow.querySelector('.weight-value').textContent = itemData.weight_percentage.toFixed(2);
                        itemRow.querySelector('.quantity-value').textContent = itemData.quantity;
                        itemRow.querySelector('.allocated-amount').textContent = '₹' + itemData.allocated_amount.toFixed(2);
                        itemRow.querySelector('.current-value').textContent = '₹' + itemData.current_value.toFixed(2);

                        const plCell = itemRow.querySelector('.profit-loss');
                        plCell.textContent = '₹' + itemData.profit_loss.toFixed(2);
                        plCell.className = 'profit-loss ' + (itemData.profit_loss >= 0 ? 'positive' : 'negative');
                    }
                });

                // Update investment amount if it changed
                if (data.investment_amount) {
                    const investmentElement = document.querySelector('.stats-grid .stat-card:first-child .stat-value');
                    if (investmentElement) {
                        investmentElement.textContent = '₹' + data.investment_amount.toFixed(2);
                    }
                }

                // Update portfolio stats
                if (data.total_current_value !== undefined) {
                    document.getElementById('total-current-value').textContent = '₹' + data.total_current_value.toFixed(2);

                    const plElement = document.getElementById('total-profit-loss');
                    plElement.textContent = '₹' + data.total_profit_loss.toFixed(2);
                    plElement.className = 'stat-value ' + (data.total_profit_loss >= 0 ? 'positive' : 'negative');

                    const plPercentElement = document.getElementById('profit-loss-percentage');
                    plPercentElement.textContent = data.profit_loss_percentage.toFixed(2) + '%';
                    plPercentElement.className = 'stat-value ' + (data.profit_loss_percentage >= 0 ? 'positive' : 'negative');
                }

                // Hide edit mode for the current item
                cancelEdit(itemId, field);

                // Update message based on edit type
                if (field === 'quantity') {
                    showMessage('Quantity updated! Investment amount and all weights recalculated.', 'success');
                } else {
                    showMessage('Updated successfully! Other stocks rebalanced to maintain 100% total.', 'success');
                }
            } else {
                showMessage(data.error || 'Failed to update', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('An error occurred while updating', 'error');
        })
        .finally(() => {
            row.classList.remove('loading');
        });
}


// Allow Enter key to save, Escape to cancel
document.addEventListener('keydown', function (e) {
    const activeInput = document.activeElement;

    if (activeInput.classList.contains('edit-input')) {
        const cell = activeInput.closest('.editable-cell');
        const row = cell.closest('tr');
        const itemId = row.dataset.itemId;
        const field = cell.classList.contains('weight-cell') ? 'weight' : 'quantity';

        if (e.key === 'Enter') {
            e.preventDefault();
            saveEdit(itemId, field);
        } else if (e.key === 'Escape') {
            e.preventDefault();
            cancelEdit(itemId, field);
        }
    }
});

// Load and render performance comparison chart
// Load and render performance comparison chart
let chartInstance = null;  // Store chart instance for updates
let cachedChartData = null; // Store data to re-render on theme change

function getThemeConfig() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {
        textColor: isDark ? '#cbd5e1' : '#334155', // Slate 300 : Slate 700
        gridColor: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
        titleColor: isDark ? '#f8fafc' : '#0f172a',
        tooltipBg: isDark ? 'rgba(30, 41, 59, 0.95)' : 'rgba(0, 0, 0, 0.8)',
        tooltipBorder: isDark ? 'rgba(255, 255, 255, 0.1)' : 'transparent',
    };
}

function renderChart(data) {
    const ctx = document.getElementById('performanceChart').getContext('2d');
    const theme = getThemeConfig();

    // Destroy existing chart if it exists
    if (chartInstance) {
        chartInstance.destroy();
    }

    // Create gradients for better visual effect
    const gradientBasket = ctx.createLinearGradient(0, 0, 0, 400);
    // Adjust gradient alpha based on theme if needed, but standard usually works
    gradientBasket.addColorStop(0, 'rgba(37, 99, 235, 0.3)'); // Primary blue
    gradientBasket.addColorStop(1, 'rgba(37, 99, 235, 0.01)');

    const gradientNifty = ctx.createLinearGradient(0, 0, 0, 400);
    gradientNifty.addColorStop(0, 'rgba(239, 68, 68, 0.3)'); // Red
    gradientNifty.addColorStop(1, 'rgba(239, 68, 68, 0.01)');

    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: data.datasets.basket.label,
                    data: data.datasets.basket.data,
                    borderColor: '#2563eb', // Primary blue
                    backgroundColor: gradientBasket,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: '#2563eb',
                    pointHoverBorderColor: '#fff',
                    pointHoverBorderWidth: 2
                },
                {
                    label: data.datasets.nifty.label,
                    data: data.datasets.nifty.data,
                    borderColor: '#ef4444', // Red
                    backgroundColor: gradientNifty,
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 6,
                    pointHoverBackgroundColor: '#ef4444',
                    pointHoverBorderColor: '#fff',
                    pointHoverBorderWidth: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    align: 'end',
                    labels: {
                        usePointStyle: true,
                        pointStyle: 'circle',
                        padding: 20,
                        color: theme.textColor,
                        font: {
                            size: 13,
                            family: "'Inter', sans-serif"
                        }
                    }
                },
                tooltip: {
                    enabled: true,
                    mode: 'index',
                    intersect: false,
                    backgroundColor: theme.tooltipBg,
                    titleColor: '#fff',
                    titleFont: {
                        size: 14,
                        weight: 'bold',
                        family: "'Inter', sans-serif"
                    },
                    bodyColor: '#cbd5e1',
                    bodyFont: {
                        size: 13,
                        family: "'Inter', sans-serif"
                    },
                    padding: 12,
                    displayColors: true,
                    borderColor: theme.tooltipBorder,
                    borderWidth: 1,
                    callbacks: {
                        title: function (tooltipItems) {
                            return 'Date: ' + tooltipItems[0].label;
                        },
                        label: function (context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            const value = context.parsed.y;
                            label += '₹' + value.toFixed(2);
                            return label;
                        },
                        footer: function (tooltipItems) {
                            // Show gain/loss from ₹100
                            const basketValue = tooltipItems[0].parsed.y;
                            const niftyValue = tooltipItems[1] ? tooltipItems[1].parsed.y : 100;
                            const basketChange = basketValue - 100;
                            const niftyChange = niftyValue - 100;

                            return [
                                '',
                                tooltipItems[0].dataset.label + ' Return: ' + (basketChange >= 0 ? '+' : '') + basketChange.toFixed(2) + '%',
                                tooltipItems[1] ? (tooltipItems[1].dataset.label + ' Return: ' + (niftyChange >= 0 ? '+' : '') + niftyChange.toFixed(2) + '%') : ''
                            ];
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    grid: {
                        color: theme.gridColor,
                        drawBorder: false
                    },
                    ticks: {
                        callback: function (value) {
                            return '₹' + value.toFixed(0);
                        },
                        font: {
                            size: 11,
                            family: "'Inter', sans-serif"
                        },
                        color: theme.textColor
                    },
                    title: {
                        display: true,
                        text: 'Value of ₹100 Invested',
                        font: {
                            size: 12,
                            weight: '600',
                            family: "'Inter', sans-serif"
                        },
                        color: theme.titleColor
                    }
                },
                x: {
                    grid: {
                        display: false,
                        drawBorder: false
                    },
                    ticks: {
                        maxRotation: 0,
                        autoSkip: true,
                        maxTicksLimit: 6,
                        font: {
                            size: 11,
                            family: "'Inter', sans-serif"
                        },
                        color: theme.textColor
                    },
                    title: {
                        display: false
                    }
                }
            },
            interaction: {
                mode: 'index',
                intersect: false
            },
            hover: {
                mode: 'index',
                intersect: false
            }
        }
    });

    // Update performance summary cards
    if (data.summary) {
        const basketFinal = data.summary.basket_final;
        const niftyFinal = data.summary.nifty_final;
        const basketReturn = data.summary.basket_return_pct;
        const niftyReturn = data.summary.nifty_return_pct;

        document.getElementById('basket-final-value').textContent = '₹' + basketFinal.toFixed(2);
        document.getElementById('nifty-final-value').textContent = '₹' + niftyFinal.toFixed(2);

        document.getElementById('basket-return').textContent = 'Return: ' + (basketReturn >= 0 ? '+' : '') + basketReturn.toFixed(2) + '%';
        document.getElementById('nifty-return').textContent = 'Return: ' + (niftyReturn >= 0 ? '+' : '') + niftyReturn.toFixed(2) + '%';

        // Calculate CAGR dynamically
        if (data.labels && data.labels.length > 0) {
            const startDate = new Date(data.labels[0]);
            const endDate = new Date(data.labels[data.labels.length - 1]);
            const years = (endDate - startDate) / (1000 * 60 * 60 * 24 * 365.25);
            
            if (years >= 0.45) { // Roughly 6m or more
                const bVal = Math.max(0.0001, basketFinal / 100);
                const nVal = Math.max(0.0001, niftyFinal / 100);
                const basketCagr = ((bVal) ** (1 / years) - 1) * 100;
                const niftyCagr = ((nVal) ** (1 / years) - 1) * 100;
                const yearLabel = years >= 0.9 ? years.toFixed(1) + 'y' : '6m';
                
                document.getElementById('basket-return').innerHTML += ` <span style="color:var(--text-secondary); margin-left: 8px; font-size:0.9em; border-left: 1px solid var(--border-color); padding-left: 8px;">CAGR (${yearLabel}): <span class="${basketCagr >= 0 ? 'positive' : 'negative'}">${basketCagr >= 0 ? '+' : ''}${basketCagr.toFixed(2)}%</span></span>`;
                document.getElementById('nifty-return').innerHTML += ` <span style="color:var(--text-secondary); margin-left: 8px; font-size:0.9em; border-left: 1px solid var(--border-color); padding-left: 8px;">CAGR (${yearLabel}): <span class="${niftyCagr >= 0 ? 'positive' : 'negative'}">${niftyCagr >= 0 ? '+' : ''}${niftyCagr.toFixed(2)}%</span></span>`;
            }
        }
    }
}

async function loadPerformanceChart(period = '1m') {
    try {
        // Get basket ID from DOM data attribute
        const basketId = document.querySelector('[data-basket-id]')?.dataset.basketId;
        if (!basketId) {
            console.error('Basket ID not found in DOM');
            document.querySelector('.chart-section').innerHTML = '<p style="text-align: center; color: var(--text-secondary);">Unable to load chart data</p>';
            return;
        }

        const response = await fetch(`/basket/${basketId}/chart-data/?period=${period}`);
        const data = await response.json();

        if (data.success) {
            cachedChartData = data; // Cache data
            renderChart(data); // Render
        } else {
            document.querySelector('.chart-section').innerHTML = '<p style="text-align: center; color: var(--text-secondary);">Unable to load chart data: ' + (data.error || 'Unknown error') + '</p>';
        }
    } catch (error) {
        console.error('Error loading chart:', error);
        document.querySelector('.chart-section').innerHTML = '<p style="text-align: center; color: var(--text-secondary);">Unable to load chart data</p>';
    }
}

// Handle period button clicks
document.querySelectorAll('.period-btn').forEach(button => {
    button.addEventListener('click', function () {
        const period = this.getAttribute('data-period');

        // Update active class
        document.querySelectorAll('.period-btn').forEach(btn => btn.classList.remove('active'));
        this.classList.add('active');

        // Remove manual style manipulation!
        // Styles are handled by CSS class .active

        // Reload chart with new period
        loadPerformanceChart(period);
    });
});


// Load chart when page is ready
document.addEventListener('DOMContentLoaded', () => {
    loadPerformanceChart('1m');  // Default to 1 month

    // Watch for theme changes to re-render chart
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.type === 'attributes' && mutation.attributeName === 'data-theme') {
                if (cachedChartData) {
                    renderChart(cachedChartData);
                }
            }
        });
    });

    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-theme']
    });
});

// Share Basket Functionality
async function shareBasket(basketId) {
    try {
        // Show loading state
        const shareBtn = document.getElementById('share-basket-btn');
        const originalText = shareBtn.innerHTML;
        shareBtn.innerHTML = '⏳ Generating...';
        shareBtn.disabled = true;

        // Call API to create tiny URL
        const response = await fetch(`/basket/${basketId}/share/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': csrftoken,
            }
        });

        const data = await response.json();

        if (data.success) {
            // Show modal with the short URL
            document.getElementById('share-link-input').value = data.short_url;
            document.getElementById('share-modal').classList.add('active');

            // Show stats if available
            if (data.click_count !== undefined) {
                const statsDiv = document.getElementById('share-stats');
                const statsContent = document.getElementById('stats-content');
                statsContent.innerHTML = `This link has been clicked ${data.click_count} time${data.click_count !== 1 ? 's' : ''}`;
                statsDiv.style.display = 'block';
            }
        } else {
            showMessage('Failed to create share link: ' + (data.error || 'Unknown error'), 'error');
        }

        // Reset button
        shareBtn.innerHTML = originalText;
        shareBtn.disabled = false;

    } catch (error) {
        console.error('Error creating share link:', error);
        showMessage('Failed to create share link', 'error');

        // Reset button
        const shareBtn = document.getElementById('share-basket-btn');
        shareBtn.innerHTML = '🔗 Share Basket';
        shareBtn.disabled = false;
    }
}

function closeShareModal() {
    document.getElementById('share-modal').classList.remove('active');
    // Reset copy button
    const copyBtn = document.getElementById('copy-btn-text');
    copyBtn.textContent = 'Copy';
    copyBtn.parentElement.classList.remove('copied');
}

async function copyShareLink() {
    const linkInput = document.getElementById('share-link-input');
    const copyBtnText = document.getElementById('copy-btn-text');
    const copyBtn = copyBtnText.parentElement;

    try {
        await navigator.clipboard.writeText(linkInput.value);
        copyBtnText.textContent = 'Copied!';
        copyBtn.classList.add('copied');

        // Reset after 2 seconds
        setTimeout(() => {
            copyBtnText.textContent = 'Copy';
            copyBtn.classList.remove('copied');
        }, 2000);

        showMessage('Link copied to clipboard!', 'success');
    } catch (error) {
        // Fallback for older browsers
        linkInput.select();
        document.execCommand('copy');
        copyBtnText.textContent = 'Copied!';
        copyBtn.classList.add('copied');

        setTimeout(() => {
            copyBtnText.textContent = 'Copy';
            copyBtn.classList.remove('copied');
        }, 2000);

        showMessage('Link copied to clipboard!', 'success');
    }
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('share-modal');
    if (e.target === modal) {
        closeShareModal();
    }
});
