document.addEventListener('DOMContentLoaded', function() {
    // Airport search autocomplete
    setupAirportAutocomplete('origin');
    setupAirportAutocomplete('destination');
    
    // Validate origin and destination are different
    const searchForm = document.getElementById('flight-search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            const origin = document.getElementById('origin').value;
            const destination = document.getElementById('destination').value;
            
            if (origin === destination) {
                e.preventDefault();
                showError('Origin and destination cannot be the same');
                return false;
            }
            
            // Validate dates
            const departureDate = document.getElementById('departure-date').value;
            const returnDate = document.getElementById('return-date').value;
            const tripType = document.querySelector('input[name="trip-type"]:checked').value;
            
            if (!departureDate) {
                e.preventDefault();
                showError('Please select a departure date');
                return false;
            }
            
            if (tripType === 'round-trip' && !returnDate) {
                e.preventDefault();
                showError('Please select a return date');
                return false;
            }
            
            showLoadingOverlay();
            return true;
        });
    }
    
    // Flight sorting options
    const sortOptions = document.querySelectorAll('.sort-option');
    if (sortOptions.length) {
        sortOptions.forEach(option => {
            option.addEventListener('click', function() {
                const sortBy = this.getAttribute('data-sort');
                const flightType = this.closest('.flight-results').getAttribute('data-flight-type');
                sortFlights(sortBy, flightType);
                
                // Update active sort option
                const sortOptionsInGroup = this.closest('.dropdown-menu').querySelectorAll('.sort-option');
                sortOptionsInGroup.forEach(opt => opt.classList.remove('active'));
                this.classList.add('active');
                
                // Update dropdown button text
                const dropdownButton = this.closest('.dropdown').querySelector('.dropdown-toggle');
                dropdownButton.textContent = 'Sort: ' + this.textContent;
            });
        });
    }
    
    // Price range filter
    const priceSlider = document.getElementById('price-range');
    if (priceSlider) {
        const minPrice = parseInt(priceSlider.getAttribute('data-min'));
        const maxPrice = parseInt(priceSlider.getAttribute('data-max'));
        
        noUiSlider.create(priceSlider, {
            start: [minPrice, maxPrice],
            connect: true,
            step: 10,
            range: {
                'min': minPrice,
                'max': maxPrice
            },
            format: {
                to: function(value) {
                    return Math.round(value);
                },
                from: function(value) {
                    return Math.round(value);
                }
            }
        });
        
        const priceValues = [
            document.getElementById('price-min'),
            document.getElementById('price-max')
        ];
        
        priceSlider.noUiSlider.on('update', function(values, handle) {
            priceValues[handle].innerHTML = '$' + values[handle];
            
            // Filter flights based on price range
            filterFlightsByPrice(values[0], values[1]);
        });
    }
    
    // Time of day filter
    const timeFilters = document.querySelectorAll('.time-filter');
    if (timeFilters.length) {
        timeFilters.forEach(filter => {
            filter.addEventListener('change', function() {
                filterFlightsByTime();
            });
        });
    }
    
    // Flight details expand/collapse
    const flightDetailsBtns = document.querySelectorAll('.flight-details-btn');
    flightDetailsBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const detailsSection = this.closest('.flight-card').querySelector('.flight-details');
            
            if (detailsSection.style.display === 'block') {
                detailsSection.style.display = 'none';
                this.innerHTML = 'Show Details <i class="fas fa-chevron-down"></i>';
            } else {
                detailsSection.style.display = 'block';
                this.innerHTML = 'Hide Details <i class="fas fa-chevron-up"></i>';
            }
        });
    });
});

function setupAirportAutocomplete(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;

    const otherInputId = inputId === 'origin' ? 'destination' : 'origin';
    const otherInput = document.getElementById(otherInputId);

    const $input = $(`#${inputId}`);
    $input.autocomplete({
        source: function(request, response) {
            $.ajax({
                url: "/api/airports",
                data: { query: request.term },
                dataType: "json",
                success: function(data) {
                    response(data);
                },
                error: function() {
                    response([]);
                }
            });
        },
        minLength: 0,  // Allow empty input
        select: function(event, ui) {
            event.preventDefault();
            $(this).val(ui.item.value);
            if (otherInput.value === ui.item.value) {
                otherInput.value = '';
            }
        },
        focus: function(event, ui) {
            event.preventDefault();
            $(this).val(ui.item.value);
        }
    });

    // Trigger autocomplete on focus (click)
    $input.on('focus', function() {
        $(this).autocomplete("search", $(this).val());
    });
}
function showError(message) {
    // Create or update error alert
    let errorAlert = document.getElementById('search-error');
    
    if (!errorAlert) {
        errorAlert = document.createElement('div');
        errorAlert.id = 'search-error';
        errorAlert.classList.add('alert', 'alert-danger', 'mt-3');
        
        const form = document.getElementById('flight-search-form');
        form.insertAdjacentElement('afterend', errorAlert);
    }
    
    errorAlert.textContent = message;
    
    // Scroll to error
    errorAlert.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Dismiss after 5 seconds
    setTimeout(() => {
        if (errorAlert.parentNode) {
            errorAlert.parentNode.removeChild(errorAlert);
        }
    }, 5000);
}

function sortFlights(sortBy, flightType) {
    const flightsContainer = document.querySelector(`.flight-results[data-flight-type="${flightType}"] .flights-container`);
    const flights = Array.from(flightsContainer.querySelectorAll('.flight-card'));
    
    flights.sort((a, b) => {
        if (sortBy === 'price-asc') {
            const priceA = parseFloat(a.getAttribute('data-price'));
            const priceB = parseFloat(b.getAttribute('data-price'));
            return priceA - priceB;
        } else if (sortBy === 'price-desc') {
            const priceA = parseFloat(a.getAttribute('data-price'));
            const priceB = parseFloat(b.getAttribute('data-price'));
            return priceB - priceA;
        } else if (sortBy === 'duration-asc') {
            const durationA = parseInt(a.getAttribute('data-duration'));
            const durationB = parseInt(b.getAttribute('data-duration'));
            return durationA - durationB;
        } else if (sortBy === 'departure-asc') {
            const departureA = new Date(a.getAttribute('data-departure'));
            const departureB = new Date(b.getAttribute('data-departure'));
            return departureA - departureB;
        } else if (sortBy === 'departure-desc') {
            const departureA = new Date(a.getAttribute('data-departure'));
            const departureB = new Date(b.getAttribute('data-departure'));
            return departureB - departureA;
        } else if (sortBy === 'arrival-asc') {
            const arrivalA = new Date(a.getAttribute('data-arrival'));
            const arrivalB = new Date(b.getAttribute('data-arrival'));
            return arrivalA - arrivalB;
        } else if (sortBy === 'arrival-desc') {
            const arrivalA = new Date(a.getAttribute('data-arrival'));
            const arrivalB = new Date(b.getAttribute('data-arrival'));
            return arrivalB - arrivalA;
        }
        return 0;
    });
    
    // Clear container and re-append sorted flights
    flightsContainer.innerHTML = '';
    flights.forEach(flight => flightsContainer.appendChild(flight));
}

function filterFlightsByPrice(minPrice, maxPrice) {
    const flights = document.querySelectorAll('.flight-card');
    
    flights.forEach(flight => {
        const price = parseFloat(flight.getAttribute('data-price'));
        
        if (price >= minPrice && price <= maxPrice) {
            flight.style.display = 'block';
        } else {
            flight.style.display = 'none';
        }
    });
    
    updateFilterSummary();
}

function filterFlightsByTime() {
    const timeFilters = document.querySelectorAll('.time-filter:checked');
    const selectedTimes = Array.from(timeFilters).map(filter => filter.value);
    
    // If no time filters selected, show all flights
    if (selectedTimes.length === 0) {
        document.querySelectorAll('.flight-card').forEach(flight => {
            flight.style.display = 'block';
        });
        return;
    }
    
    const flights = document.querySelectorAll('.flight-card');
    
    flights.forEach(flight => {
        const departureTime = new Date(flight.getAttribute('data-departure'));
        const hours = departureTime.getHours();
        
        let showFlight = false;
        
        if (selectedTimes.includes('morning') && hours >= 5 && hours < 12) {
            showFlight = true;
        } else if (selectedTimes.includes('afternoon') && hours >= 12 && hours < 18) {
            showFlight = true;
        } else if (selectedTimes.includes('evening') && hours >= 18 && hours < 22) {
            showFlight = true;
        } else if (selectedTimes.includes('night') && (hours >= 22 || hours < 5)) {
            showFlight = true;
        }
        
        flight.style.display = showFlight ? 'block' : 'none';
    });
    
    updateFilterSummary();
}

function updateFilterSummary() {
    // Count visible flights
    const visibleFlights = document.querySelectorAll('.flight-card[style="display: block;"]').length;
    const totalFlights = document.querySelectorAll('.flight-card').length;
    
    // Update summary text
    const summary = document.getElementById('filter-summary');
    if (summary) {
        summary.textContent = `Showing ${visibleFlights} of ${totalFlights} flights`;
    }
    
    // Show/hide no results message
    const noResults = document.getElementById('no-results');
    if (noResults) {
        if (visibleFlights === 0) {
            noResults.style.display = 'block';
        } else {
            noResults.style.display = 'none';
        }
    }
}

function showLoadingOverlay() {
    // Placeholder for loading overlay (if needed)
    console.log("Loading...");
}