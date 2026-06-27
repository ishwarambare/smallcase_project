document.addEventListener('DOMContentLoaded', () => {
    // Text Rotation Animation for Hero Title
    const words = ["Wealth", "Portfolio", "Stocks", "Future"];
    let wordIndex = 0;
    const animatedText = document.getElementById('animated-text');
    if (animatedText) {
        setInterval(() => {
            animatedText.style.opacity = 0;
            setTimeout(() => {
                wordIndex = (wordIndex + 1) % words.length;
                animatedText.textContent = words[wordIndex];
                animatedText.style.opacity = 1;
            }, 500);
        }, 2000);
    }

    const canvas = document.getElementById('landingChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    // Create a beautiful gradient for the chart area
    const gradient = ctx.createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, 'rgba(16, 185, 129, 0.4)'); // Green
    gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

    // Mock data representing a growing portfolio over 6 months
    const data = {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        datasets: [{
            label: 'Portfolio Value',
            data: [10000, 10500, 10200, 11400, 11200, 12500],
            borderColor: '#10b981',
            backgroundColor: gradient,
            borderWidth: 3,
            pointBackgroundColor: '#10b981',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
            fill: true,
            tension: 0 // Zig-zag lines
        }]
    };

    const config = {
        type: 'line',
        data: data,
        options: {
            layout: {
                padding: {
                    bottom: 10,
                    top: 10
                }
            },
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: '#ffffff',
                    bodyColor: '#e2e8f0',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            return '₹' + context.parsed.y.toLocaleString();
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false,
                        drawBorder: false
                    },
                    ticks: {
                        color: 'rgba(148, 163, 184, 0.8)'
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(148, 163, 184, 0.1)',
                        drawBorder: false,
                        borderDash: [5, 5]
                    },
                    ticks: {
                        color: 'rgba(148, 163, 184, 0.8)',
                        callback: function(value) {
                            return '₹' + (value / 1000) + 'k';
                        }
                    }
                }
            },
            interaction: {
                intersect: false,
                mode: 'index',
            },
        }
    };

    new Chart(ctx, config);
});
