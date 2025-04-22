document.addEventListener('DOMContentLoaded', function() {
    const seatContainer = document.querySelector('.seat-map-container');
    if (!seatContainer) return;
    
    const flightId = seatContainer.getAttribute('data-flight-id');
    const maxPassengers = parseInt(seatContainer.getAttribute('data-max-passengers'));
    let selectedSeats = [];
    
    // Define continueBtn early to avoid TDZ error
    const continueBtn = document.getElementById('continue-btn');
    
    // Load existing selections from session if any
    const preSelectedSeats = seatContainer.getAttribute('data-selected-seats');
    if (preSelectedSeats) {
        selectedSeats = preSelectedSeats.split(',').map(id => id.trim());
        updateSelectedSeats();
    }
    
    // Handle seat selection
    const seats = document.querySelectorAll('.seat');
    seats.forEach(seat => {
        seat.addEventListener('click', function() {
            const seatId = this.getAttribute('data-seat-id');
            
            // Check if seat is already booked
            if (this.classList.contains('booked')) {
                showToast('This seat is already booked', 'danger');
                return;
            }
            
            // Toggle selection
            if (this.classList.contains('selected')) {
                // Deselect seat
                this.classList.remove('selected');
                selectedSeats = selectedSeats.filter(id => id !== seatId);
            } else {
                // Check if max selection reached
                if (selectedSeats.length >= maxPassengers) {
                    showToast(`You can only select up to ${maxPassengers} seats`, 'warning');
                    return;
                }
                
                // Select seat
                this.classList.add('selected');
                selectedSeats.push(seatId);
            }
            
            updateSelectedSeats();
        });
    });
    
    // Continue button event listener
    if (continueBtn) {
        continueBtn.addEventListener('click', function() {
            if (selectedSeats.length === 0) {
                showToast('Please select at least one seat', 'warning');
                return;
            }
            
            if (selectedSeats.length < maxPassengers) {
                if (!confirm(`You've only selected ${selectedSeats.length} of ${maxPassengers} seats. Do you want to continue?`)) {
                    return;
                }
            }
            
            // Store selected seats
            saveSelectedSeats(flightId);
        });
    }
    
    // Seat class selector
    const seatClassSelect = document.getElementById('seat-class');
    if (seatClassSelect) {
        seatClassSelect.addEventListener('change', function() {
            const seatClass = this.value;
            
            // Show seats for selected class only
            document.querySelectorAll('.seat-class-section').forEach(section => {
                if (section.getAttribute('data-class') === seatClass) {
                    section.style.display = 'block';
                } else {
                    section.style.display = 'none';
                }
            });
            
            // Clear selected seats when changing class
            selectedSeats = [];
            document.querySelectorAll('.seat.selected').forEach(seat => {
                seat.classList.remove('selected');
            });
            updateSelectedSeats();
        });
    }
    
    // Initialize tooltips for seats
    const seatTooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    seatTooltips.forEach(tooltip => {
        new bootstrap.Tooltip(tooltip);
    });
    
    // Seat info toggle
    const infoToggle = document.getElementById('seat-info-toggle');
    if (infoToggle) {
        infoToggle.addEventListener('click', function() {
            const seatInfo = document.getElementById('seat-info');
            if (seatInfo.style.display === 'none') {
                seatInfo.style.display = 'block';
                this.innerHTML = 'Hide Seat Information <i class="fas fa-chevron-up"></i>';
            } else {
                seatInfo.style.display = 'none';
                this.innerHTML = 'Show Seat Information <i class="fas fa-chevron-down"></i>';
            }
        });
    }
    
    // Update seat selection summary
    function updateSelectedSeats() {
        const selectedList = document.getElementById('selected-seats');
        const priceElement = document.getElementById('selected-price');
        const totalElement = document.getElementById('total-price');
        const seatPriceElement = document.getElementById('seat-price');
        
        if (!selectedList || !priceElement || !totalElement) return;
        
        // Clear the list
        selectedList.innerHTML = '';
        
        if (selectedSeats.length === 0) {
            selectedList.innerHTML = '<li class="list-group-item">No seats selected</li>';
            priceElement.textContent = '$0.00';
            totalElement.textContent = '$0.00';
            
            if (continueBtn) {
                continueBtn.disabled = true;
            }
            return;
        }
        
        // Update continue button state
        if (continueBtn) {
            continueBtn.disabled = false;
        }
        
        // Add each selected seat to the list
        let totalPrice = 0;
        const seatPrice = parseFloat(seatPriceElement.getAttribute('data-price'));
        
        selectedSeats.forEach(seatId => {
            const seat = document.querySelector(`.seat[data-seat-id="${seatId}"]`);
            const seatNumber = seat.getAttribute('data-seat-number');
            
            const listItem = document.createElement('li');
            listItem.className = 'list-group-item d-flex justify-content-between align-items-center';
            listItem.innerHTML = `
                <span>Seat ${seatNumber}</span>
                <span class="badge bg-primary rounded-pill">$${seatPrice.toFixed(2)}</span>
            `;
            selectedList.appendChild(listItem);
            
            totalPrice += seatPrice;
        });
        
        // Update total price
        priceElement.textContent = `$${totalPrice.toFixed(2)}`;
        totalElement.textContent = `$${totalPrice.toFixed(2)}`;
    }
    
    // Save selected seats via AJAX
    function saveSelectedSeats(flightId) {
        // Show loading overlay
        showLoadingOverlay();
        
        fetch(`/store-selected-seats/${flightId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                selected_seats: selectedSeats
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Get URL for next step from the continue button
                const nextUrl = continueBtn.getAttribute('data-next-url');
                window.location.href = nextUrl;
            } else {
                showToast('Failed to save seat selection', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('An error occurred. Please try again.', 'danger');
        });
    }
    
    // Helper to show toast notifications
    function showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) return;
        
        const toast = document.createElement('div');
        toast.className = `toast bg-${type} text-white`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="toast-header bg-${type} text-white">
                <i class="fas fa-info-circle me-2"></i>
                <strong class="me-auto">Notification</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        `;
        
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast, {
            autohide: true,
            delay: 3000
        });
        bsToast.show();
        
        // Remove toast from DOM after it's hidden
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    }
    
    // Seat map legend toggle (with fix from earlier)
    const legendToggle = document.getElementById('legend-toggle');
    if (legendToggle) {
        legendToggle.addEventListener('click', function() {
            const legend = document.getElementById('seat-legend');
            if (legend.style.display === 'none' || legend.style.display === '') {
                legend.style.display = 'flex';
                this.innerHTML = 'Hide Legend <i class="fas fa-chevron-up"></i>';
            } else {
                legend.style.display = 'none';
                this.innerHTML = 'Show Legend <i class="fas fa-chevron-down"></i>';
            }
        });
    }
});

// Placeholder for showLoadingOverlay (assuming it’s defined elsewhere or needs implementation)
function showLoadingOverlay() {
    // If not defined elsewhere, add basic implementation:
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.innerHTML = '<div class="spinner-border text-primary" role="status"></div><div class="loading-text">Processing...</div>';
    document.body.appendChild(overlay);
    setTimeout(() => overlay.remove(), 2000); // Remove after 2s (adjust as needed)
}