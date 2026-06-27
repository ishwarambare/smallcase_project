/* ========================================
   BASKET-CREATE - JavaScript
   Extracted from basket_create.j2
   ======================================== */

// Global function to remove stock from portfolio selection
window.removeStock = function(checkboxId) {
    const checkbox = document.getElementById(checkboxId);
    if (checkbox) {
        checkbox.checked = false;
        updateCount();
    }
};

function updateCount() {
    console.log('Updating count and portfolio display');
    const checkedCheckboxes = document.querySelectorAll('input[name="stocks"]:checked');
    const checkedCount = checkedCheckboxes.length;
    
    // Update badge counts
    document.getElementById('count').textContent = checkedCount;
    const selectedBadge = document.getElementById('selectedBadge');
    if (selectedBadge) {
        selectedBadge.textContent = checkedCount;
    }
    const summaryCount = document.getElementById('summaryCount');
    if (summaryCount) {
        summaryCount.textContent = checkedCount;
    }

    // Visual feedback for minimum requirement (min 2 stocks)
    const countDisplay = document.getElementById('selectedCount');
    if (checkedCount < 2) {
        countDisplay.style.background = '#ef4444'; // Red for error
    } else {
        countDisplay.style.background = 'var(--primary-color)';
    }

    // Get investment amount
    const investmentAmountInput = document.getElementById('investment_amount');
    const investmentAmount = parseFloat(investmentAmountInput.value) || 0;

    // Update investment amount in summary
    const summaryInvestment = document.getElementById('summaryInvestment');
    if (summaryInvestment) {
        summaryInvestment.textContent = '₹' + investmentAmount.toLocaleString('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    // Calculate weight & allocation
    const weightPerStock = checkedCount > 0 ? (100 / checkedCount) : 0;
    const amountPerStock = checkedCount > 0 ? (investmentAmount / checkedCount) : 0;

    const summaryWeight = document.getElementById('summaryWeight');
    if (summaryWeight) {
        summaryWeight.textContent = checkedCount > 0 ? weightPerStock.toFixed(1) + '%' : '0%';
    }

    const summaryAllocPerStock = document.getElementById('summaryAllocPerStock');
    if (summaryAllocPerStock) {
        summaryAllocPerStock.textContent = '₹' + amountPerStock.toLocaleString('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    // Update Selected Stocks List
    const selectedStocksList = document.getElementById('selectedStocksList');
    if (!selectedStocksList) return;

    if (checkedCount === 0) {
        selectedStocksList.innerHTML = `
            <div class="empty-selected-state">
                <div class="empty-icon">📈</div>
                <p>No stocks selected yet</p>
                <span>Select stocks from the list to build your portfolio.</span>
            </div>
        `;
    } else {
        let cardsHTML = '';
        checkedCheckboxes.forEach(checkbox => {
            const wrapper = checkbox.closest('.stock-checkbox');
            if (wrapper) {
                const symbol = wrapper.getAttribute('data-symbol');
                const name = wrapper.getAttribute('data-name');
                const priceVal = parseFloat(wrapper.getAttribute('data-price')) || 0;
                const checkboxId = checkbox.id;

                const formattedPrice = priceVal > 0 
                    ? '₹' + priceVal.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                    : 'Price N/A';

                const formattedAllocAmount = investmentAmount > 0 
                    ? '₹' + amountPerStock.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                    : '₹0.00';

                cardsHTML += `
                    <div class="selected-stock-card" data-checkbox-id="${checkboxId}">
                        <div class="selected-stock-info">
                            <div class="selected-stock-symbol">${symbol}</div>
                            <div class="selected-stock-name" title="${name}">${name}</div>
                        </div>
                        <div class="selected-stock-financials">
                            <div class="selected-stock-price">${formattedPrice}</div>
                            <div class="selected-stock-alloc">
                                <span class="selected-stock-weight">${weightPerStock.toFixed(1)}%</span>
                                <span class="selected-stock-amount">${formattedAllocAmount}</span>
                            </div>
                        </div>
                        <button type="button" class="remove-stock-btn" onclick="removeStock('${checkboxId}')" title="Remove stock">×</button>
                    </div>
                `;
            }
        });
        selectedStocksList.innerHTML = cardsHTML;
    }
    updateAdvisor();
}

let activeRedFlagsList = [];
let activeAvoidStocks = [];
let advisorFetchTimeout = null;

function updateAdvisor() {
    const checkedCheckboxes = document.querySelectorAll('input[name="stocks"]:checked');
    const checkedCount = checkedCheckboxes.length;
    const advisorCard = document.getElementById('basketAdvisorCard');
    const healthScoreEl = document.getElementById('advisorHealthScore');
    const warningsListEl = document.getElementById('advisorWarningsList');

    if (!advisorCard) return;

    if (checkedCount === 0) {
        advisorCard.style.display = 'none';
        activeRedFlagsList = [];
        activeAvoidStocks = [];
        return;
    }

    advisorCard.style.display = 'block';
    healthScoreEl.innerHTML = `
        <div class="advisor-loading">
            <span class="advisor-spinner"></span>
            <span>Running fundamental health checks...</span>
        </div>
    `;
    warningsListEl.innerHTML = '';

    if (advisorFetchTimeout) clearTimeout(advisorFetchTimeout);

    advisorFetchTimeout = setTimeout(async () => {
        const symbols = [];
        checkedCheckboxes.forEach(cb => {
            const wrapper = cb.closest('.stock-checkbox');
            if (wrapper) {
                symbols.push(wrapper.getAttribute('data-symbol'));
            }
        });

        if (symbols.length === 0) return;

        try {
            const langPrefix = window.location.pathname.startsWith('/en/') ? '/en' : (window.location.pathname.startsWith('/hi/') ? '/hi' : '');
            const resp = await fetch(`${langPrefix}/api/stock/analysis-summary/?symbols=${symbols.join(',')}`);
            const data = await resp.json();

            if (!data.success) {
                healthScoreEl.innerHTML = `<span class="advisor-error">⚠️ Failed to load fundamental analysis data.</span>`;
                return;
            }

            activeRedFlagsList = [];
            activeAvoidStocks = [];
            let htmlScore = '';
            let htmlWarnings = '';

            let totalScore = 0;
            let count = 0;
            const stockSummaries = [];

            for (const sym of symbols) {
                const stockData = data.results[sym];
                if (!stockData || stockData.error) continue;

                count++;
                totalScore += stockData.score;
                
                if (stockData.red_flags && stockData.red_flags.length) {
                    stockData.red_flags.forEach(flag => {
                        activeRedFlagsList.push({ symbol: sym, flag: flag });
                    });
                }

                if (stockData.verdict === 'AVOID' || stockData.verdict === 'STRONG AVOID') {
                    activeAvoidStocks.push({ symbol: sym, verdict: stockData.verdict });
                }

                stockSummaries.push({
                    symbol: sym,
                    verdict: stockData.verdict,
                    verdictColor: stockData.verdict_color,
                    verdictEmoji: stockData.verdict_emoji,
                    score: stockData.score,
                    maxScore: stockData.max_score
                });
            }

            if (count > 0) {
                const avgScore = totalScore / count;
                let ratingClass = 'hold';
                let ratingText = 'MODERATE';
                if (avgScore >= 10) {
                    ratingClass = 'strong-buy';
                    ratingText = 'EXCELLENT';
                } else if (avgScore >= 4) {
                    ratingClass = 'buy';
                    ratingText = 'GOOD';
                } else if (avgScore >= -2) {
                    ratingClass = 'hold';
                    ratingText = 'MODERATE';
                } else {
                    ratingClass = 'avoid';
                    ratingText = 'AVOID/RISKY';
                }

                htmlScore = `
                    <div class="advisor-overall-rating ${ratingClass}">
                        <div class="rating-label">Basket Health Rating</div>
                        <div class="rating-value">${ratingText}</div>
                        <div class="rating-detail">Avg. Score: ${avgScore.toFixed(1)} / 25</div>
                    </div>
                    <div class="advisor-stocks-breakdown">
                        ${stockSummaries.map(s => `
                            <div class="advisor-stock-item">
                                <span class="stock-sym">${s.symbol}</span>
                                <span class="stock-verdict ${s.verdictColor}">${s.verdictEmoji} ${s.verdict} (${s.score}/${s.maxScore})</span>
                            </div>
                        `).join('')}
                    </div>
                `;
            } else {
                htmlScore = `<div style="font-size:0.85rem;color:var(--text-secondary);">No fundamental analysis available for these symbols.</div>`;
            }

            if (activeRedFlagsList.length || activeAvoidStocks.length) {
                htmlWarnings = `
                    <div class="advisor-warnings-box">
                        <div class="warnings-title">🚨 Alerts &amp; Red Flags (${activeRedFlagsList.length + activeAvoidStocks.length})</div>
                        <ul class="warnings-list">
                            ${activeAvoidStocks.map(s => `
                                <li class="warning-avoid"><strong>${s.symbol}</strong> is flagged as <strong>${s.verdict}</strong>!</li>
                            `).join('')}
                            ${activeRedFlagsList.map(item => `
                                <li><strong>${item.symbol}</strong>: ${item.flag}</li>
                            `).join('')}
                        </ul>
                    </div>
                `;
            } else if (count > 0) {
                htmlWarnings = `
                    <div class="advisor-success-box">
                        🟢 All clear! No critical red flags detected in selected stocks.
                    </div>
                `;
            }

            healthScoreEl.innerHTML = htmlScore;
            warningsListEl.innerHTML = htmlWarnings;

        } catch (err) {
            console.error('Advisor fetch error:', err);
            healthScoreEl.innerHTML = `<span class="advisor-error">⚠️ Error performing fundamental checks.</span>`;
        }
    }, 400);
}

// Form validation before submit
const form = document.querySelector('form');
if (form) {
    form.addEventListener('submit', function (e) {
        const checked = document.querySelectorAll('input[name="stocks"]:checked').length;
        if (checked < 2) {
            e.preventDefault();
            alert('Please select at least 2 stocks for your basket.');
            return false;
        }

        if (activeAvoidStocks.length > 0 || activeRedFlagsList.length > 0) {
            let warnMsg = '⚠️ WARNING: Your selected basket contains investment concerns:\n\n';
            if (activeAvoidStocks.length > 0) {
                warnMsg += `- AVOID / STRONG AVOID recommendations: ${activeAvoidStocks.map(s => s.symbol).join(', ')}\n`;
            }
            if (activeRedFlagsList.length > 0) {
                warnMsg += `- Critical Red Flags detected:\n  ${activeRedFlagsList.slice(0, 3).map(item => `${item.symbol}: ${item.flag}`).join('\n  ')}`;
                if (activeRedFlagsList.length > 3) {
                    warnMsg += `\n  ... and ${activeRedFlagsList.length - 3} more flags.`;
                }
            }
            warnMsg += '\n\nAre you sure you want to proceed with purchasing/creating this basket?';
            
            if (!confirm(warnMsg)) {
                e.preventDefault();
                return false;
            }
        }
    });
}

// Listen to investment amount input to update allocations dynamically
const investmentAmountInput = document.getElementById('investment_amount');
if (investmentAmountInput) {
    investmentAmountInput.addEventListener('input', updateCount);
}

function filterStocks() {
    const searchTerm = document.getElementById('searchStock').value.toLowerCase();
    const stockItems = document.querySelectorAll('.stock-checkbox');

    stockItems.forEach(item => {
        const name = item.getAttribute('data-name').toLowerCase();
        const symbol = item.getAttribute('data-symbol').toLowerCase();

        if (name.includes(searchTerm) || symbol.includes(searchTerm)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

// Initialize count on page load
updateCount();
