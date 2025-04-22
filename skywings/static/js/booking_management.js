document.addEventListener('DOMContentLoaded', function() {
    // Cancel booking confirmation
    const cancelButtons = document.querySelectorAll('.cancel-booking-btn');
    if (cancelButtons.length) {
        cancelButtons.forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                const bookingRef = this.getAttribute('data-booking-ref');
                const departureDate = this.getAttribute('data-departure');
                
                // Calculate cancellation fee and refund amount
                const totalPrice = parseFloat(this.getAttribute('data-price'));
                const today = new Date();
                const departure = new Date(departureDate);
                const daysUntilDeparture = Math.ceil((departure - today) / (1000 * 60 * 60 * 24));
                
                let refundPercentage, cancellationFee, refundAmount;
                
                if (daysUntilDeparture > 7) {
                    refundPercentage = 90;
                } else if (daysUntilDeparture > 3) {
                    refundPercentage = 70;
                } else if (daysUntilDeparture > 1) {
                    refundPercentage = 50;
                } else {
                    refundPercentage = 0;
                }
                
                cancellationFee = totalPrice * (100 - refundPercentage) / 100;
                refundAmount = totalPrice - cancellationFee;
                
                // Create modal
                const modalHtml = `
                    <div class="modal fade" id="cancelBookingModal" tabindex="-1" aria-labelledby="cancelBookingModalLabel" aria-hidden="true">
                        <div class="modal-dialog">
                            <div class="modal-content">
                                <div class="modal-header bg-danger text-white">
                                    <h5 class="modal-title" id="cancelBookingModalLabel">Cancel Booking</h5>
                                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                                </div>
                                <div class="modal-body">
                                    <p>Are you sure you want to cancel booking <strong>${bookingRef}</strong>?</p>
                                    
                                    <div class="alert alert-info">
                                        <h6 class="alert-heading">Cancellation Details</h6>
                                        <hr>
                                        <p class="mb-0">Days until departure: <strong>${daysUntilDeparture}</strong></p>
                                        <p class="mb-0">Total price: <strong>$${totalPrice.toFixed(2)}</strong></p>
                                        <p class="mb-0">Refund percentage: <strong>${refundPercentage}%</strong></p>
                                        <p class="mb-0">Cancellation fee: <strong>$${cancellationFee.toFixed(2)}</strong></p>
                                        <p class="mb-0">Refund amount: <strong>$${refundAmount.toFixed(2)}</strong></p>
                                    </div>
                                    
                                    <p class="text-danger">This action cannot be undone.</p>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Keep Booking</button>
                                    <form action="/cancel-booking/${bookingRef}" method="POST">
                                        <button type="submit" class="btn btn-danger">Cancel Booking</button>
                                    </form>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                
                // Remove any existing modal
                const existingModal = document.getElementById('cancelBookingModal');
                if (existingModal) {
                    existingModal.remove();
                }
                
                // Add modal to DOM
                document.body.insertAdjacentHTML('beforeend', modalHtml);
                
                // Show modal
                const modal = new bootstrap.Modal(document.getElementById('cancelBookingModal'));
                modal.show();
            });
        });
    }
    
    // Booking filter
    const filterOptions = document.querySelectorAll('.booking-filter');
    if (filterOptions.length) {
        filterOptions.forEach(option => {
            option.addEventListener('click', function() {
                const filter = this.getAttribute('data-filter');
                
                // Update active filter
                document.querySelectorAll('.booking-filter').forEach(opt => {
                    opt.classList.remove('active');
                });
                this.classList.add('active');
                
                // Filter bookings
                document.querySelectorAll('.booking-card').forEach(card => {
                    const status = card.getAttribute('data-status');
                    
                    if (filter === 'all' || status === filter) {
                        card.style.display = 'block';
                    } else {
                        card.style.display = 'none';
                    }
                });
                
                // Update empty state
                updateEmptyState();
                
                // Update filter button text
                const filterBtn = document.getElementById('filter-dropdown-btn');
                if (filterBtn) {
                    filterBtn.textContent = `Filter: ${this.textContent}`;
                }
            });
        });
    }
    
    // Sort bookings
    const sortOptions = document.querySelectorAll('.booking-sort');
    if (sortOptions.length) {
        sortOptions.forEach(option => {
            option.addEventListener('click', function() {
                const sortBy = this.getAttribute('data-sort');
                
                // Update active sort
                document.querySelectorAll('.booking-sort').forEach(opt => {
                    opt.classList.remove('active');
                });
                this.classList.add('active');
                
                // Sort bookings
                const bookingsContainer = document.querySelector('.bookings-container');
                const bookings = Array.from(bookingsContainer.querySelectorAll('.booking-card'));
                
                bookings.sort((a, b) => {
                    if (sortBy === 'date-asc') {
                        const dateA = new Date(a.getAttribute('data-departure'));
                        const dateB = new Date(b.getAttribute('data-departure'));
                        return dateA - dateB;
                    } else if (sortBy === 'date-desc') {
                        const dateA = new Date(a.getAttribute('data-departure'));
                        const dateB = new Date(b.getAttribute('data-departure'));
                        return dateB - dateA;
                    } else if (sortBy === 'booking-date-asc') {
                        const dateA = new Date(a.getAttribute('data-booking-date'));
                        const dateB = new Date(b.getAttribute('data-booking-date'));
                        return dateA - dateB;
                    } else if (sortBy === 'booking-date-desc') {
                        const dateA = new Date(a.getAttribute('data-booking-date'));
                        const dateB = new Date(b.getAttribute('data-booking-date'));
                        return dateB - dateA;
                    } else if (sortBy === 'price-asc') {
                        const priceA = parseFloat(a.getAttribute('data-price'));
                        const priceB = parseFloat(b.getAttribute('data-price'));
                        return priceA - priceB;
                    } else if (sortBy === 'price-desc') {
                        const priceA = parseFloat(a.getAttribute('data-price'));
                        const priceB = parseFloat(b.getAttribute('data-price'));
                        return priceB - priceA;
                    }
                    return 0;
                });
                
                // Re-append sorted bookings
                bookings.forEach(booking => {
                    bookingsContainer.appendChild(booking);
                });
                
                // Update sort button text
                const sortBtn = document.getElementById('sort-dropdown-btn');
                if (sortBtn) {
                    sortBtn.textContent = `Sort: ${this.textContent}`;
                }
            });
        });
    }
    
    // Search bookings
    const searchInput = document.getElementById('booking-search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            
            document.querySelectorAll('.booking-card').forEach(card => {
                const bookingRef = card.getAttribute('data-booking-ref').toLowerCase();
                const flight = card.querySelector('.card-title').textContent.toLowerCase();
                
                if (bookingRef.includes(query) || flight.includes(query)) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
            
            updateEmptyState();
        });
    }
    
    // Booking details expand/collapse
    const detailsToggles = document.querySelectorAll('.booking-details-toggle');
    detailsToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const detailsSection = this.closest('.booking-card').querySelector('.booking-details');
            
            if (detailsSection.style.display === 'block') {
                detailsSection.style.display = 'none';
                this.innerHTML = 'Show Details <i class="fas fa-chevron-down"></i>';
            } else {
                detailsSection.style.display = 'block';
                this.innerHTML = 'Hide Details <i class="fas fa-chevron-up"></i>';
            }
        });
    });
    
    function updateEmptyState() {
        const visibleBookings = document.querySelectorAll('.booking-card[style="display: block;"]').length;
        const emptyState = document.getElementById('bookings-empty-state');
        
        if (emptyState) {
            if (visibleBookings === 0) {
                emptyState.style.display = 'block';
            } else {
                emptyState.style.display = 'none';
            }
        }
    }
    
    // Print boarding pass
    const printBtns = document.querySelectorAll('.print-boarding-pass');
    printBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            
            const bookingRef = this.getAttribute('data-booking-ref');
            const passengerName = this.getAttribute('data-passenger');
            const flight = this.getAttribute('data-flight');
            const date = this.getAttribute('data-date');
            const from = this.getAttribute('data-from');
            const to = this.getAttribute('data-to');
            const seat = this.getAttribute('data-seat');
            const gate = this.getAttribute('data-gate') || 'TBA';
            const boardingTime = this.getAttribute('data-boarding') || 'TBA';
            
            // Create boarding pass HTML
            const boardingPassHtml = `
                <div class="modal fade" id="boardingPassModal" tabindex="-1" aria-hidden="true">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header bg-primary text-white">
                                <h5 class="modal-title">Boarding Pass</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body boarding-pass-container">
                                <div class="boarding-pass">
                                    <div class="boarding-pass-header">
                                        <div class="airline-logo">
                                            <i class="fas fa-plane fa-2x"></i>
                                            <span>SkyWings Airlines</span>
                                        </div>
                                        <div class="boarding-pass-type">BOARDING PASS</div>
                                    </div>
                                    
                                    <div class="boarding-pass-cities">
                                        <div class="city-from">
                                            <div class="city-code">${from}</div>
                                        </div>
                                        <div class="flight-path">
                                            <i class="fas fa-plane"></i>
                                        </div>
                                        <div class="city-to">
                                            <div class="city-code">${to}</div>
                                        </div>
                                    </div>
                                    
                                    <div class="boarding-pass-details">
                                        <div class="detail">
                                            <div class="detail-label">Passenger</div>
                                            <div class="detail-value">${passengerName}</div>
                                        </div>
                                        <div class="detail">
                                            <div class="detail-label">Flight</div>
                                            <div class="detail-value">${flight}</div>
                                        </div>
                                        <div class="detail">
                                            <div class="detail-label">Date</div>
                                            <div class="detail-value">${date}</div>
                                        </div>
                                        <div class="detail">
                                            <div class="detail-label">Seat</div>
                                            <div class="detail-value">${seat}</div>
                                        </div>
                                        <div class="detail">
                                            <div class="detail-label">Gate</div>
                                            <div class="detail-value">${gate}</div>
                                        </div>
                                        <div class="detail">
                                            <div class="detail-label">Boarding</div>
                                            <div class="detail-value">${boardingTime}</div>
                                        </div>
                                    </div>
                                    
                                    <div class="boarding-pass-barcode">
                                        <div class="barcode-display">
                                            <i class="fas fa-barcode fa-3x"></i>
                                        </div>
                                        <div class="booking-reference">${bookingRef}</div>
                                    </div>
                                    
                                    <div class="boarding-pass-notice">
                                        Please be at the gate at least 30 minutes before departure.
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                                <button type="button" class="btn btn-primary" onclick="printBoardingPass()">Print</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            
            // Remove any existing modal
            const existingModal = document.getElementById('boardingPassModal');
            if (existingModal) {
                existingModal.remove();
            }
            
            // Add modal to DOM
            document.body.insertAdjacentHTML('beforeend', boardingPassHtml);
            
            // Print function
            window.printBoardingPass = function() {
                const printContents = document.querySelector('.boarding-pass-container').innerHTML;
                const originalContents = document.body.innerHTML;
                
                document.body.innerHTML = `
                    <style>
                        @media print {
                            body {
                                padding: 0;
                                margin: 0;
                            }
                            .boarding-pass {
                                width: 100%;
                                height: 100%;
                                page-break-after: always;
                            }
                        }
                    </style>
                    <div class="print-container">${printContents}</div>
                `;
                
                window.print();
                document.body.innerHTML = originalContents;
                
                // Re-initialize the modal after restoring content
                const modal = new bootstrap.Modal(document.getElementById('boardingPassModal'));
                modal.show();
            };
            
            // Show modal
            const modal = new bootstrap.Modal(document.getElementById('boardingPassModal'));
            modal.show();
        });
    });
});
